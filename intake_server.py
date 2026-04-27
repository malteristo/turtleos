"""turtleOS intake server — embedded web interface for long-form content.

Runs an aiohttp web server inside the bot process, sharing the event loop.
Serves a mobile-friendly intake form that bypasses Discord's character limit.

Flow:
  1. Mage opens /intake on their phone (via Tailscale)
  2. Pastes long content, optionally picks a thread
  3. On submit: full text saves to box/intake/, summary posted to vortex
  4. Turtle can reference the full file when needed
  5. Files metabolize after resonance is extracted
"""

import asyncio
import os
import re
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from aiohttp import web

from mage import get_pd
from llm import chat_ollama
from shell_harness import run_shell_command
from state import OLLAMA_URL

INTAKE_PORT = int(os.environ.get("INTAKE_PORT", "8742"))
INTAKE_BOX_DIR = "box/intake"
SUMMARY_MODEL = "qwen3.5:9b"
SUMMARY_CTX = 4096
SUMMARY_TIMEOUT = 30
METABOLISM_DAYS = 7

SUMMARY_PROMPT = (
    "Summarize the following text in 3-5 concise bullet points. "
    "Capture the core ideas, key arguments, and any actionable insights. "
    "Be specific, not generic. No preamble."
)


def _ensure_intake_dir() -> Path:
    """Ensure box/intake/ exists in the practice directory."""
    pd = get_pd()
    intake_dir = Path(pd) / INTAKE_BOX_DIR
    intake_dir.mkdir(parents=True, exist_ok=True)
    return intake_dir


def _slugify(text: str, max_len: int = 40) -> str:
    """Create a filesystem-safe slug from text."""
    slug = re.sub(r'[^\w\s-]', '', text.lower().strip())
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug[:max_len].rstrip('-') or "intake"


async def _summarize(content: str) -> str:
    """Generate a brief summary using a small local model."""
    snippet = content[:8000]
    try:
        result = await asyncio.wait_for(
            chat_ollama(
                SUMMARY_PROMPT,
                [{"role": "user", "content": snippet}],
                model=SUMMARY_MODEL,
                num_ctx=SUMMARY_CTX,
                think=False,
            ),
            timeout=SUMMARY_TIMEOUT,
        )
        if result:
            return result.strip()
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Intake summary failed: {type(e).__name__}: {e}")
    return content[:500] + "\n…"


def _metabolize_old_files(intake_dir: Path):
    """Remove intake files older than METABOLISM_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=METABOLISM_DAYS)
    removed = 0
    for f in intake_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                removed += 1
    if removed:
        print(f"Intake metabolism: removed {removed} old files")


INTAKE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>🌀 vortex</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --accent: #7c3aed;
    --accent-hover: #6d28d9;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --border: #334155;
    --success: #10b981;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px;
  }
  .container {
    width: 100%;
    max-width: 600px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  header {
    text-align: center;
    padding: 24px 0 8px;
  }
  header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  header .subtitle {
    color: var(--text-dim);
    font-size: 0.85rem;
    margin-top: 4px;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  label {
    font-size: 0.8rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
  }
  textarea {
    width: 100%;
    min-height: 45dvh;
    padding: 14px;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 15px;
    line-height: 1.5;
    resize: vertical;
    font-family: inherit;
    transition: border-color 0.2s;
  }
  textarea:focus {
    outline: none;
    border-color: var(--accent);
  }
  textarea::placeholder {
    color: var(--text-dim);
    opacity: 0.6;
  }
  input[type="text"] {
    width: 100%;
    padding: 12px 14px;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 15px;
    font-family: inherit;
  }
  input[type="text"]:focus {
    outline: none;
    border-color: var(--accent);
  }
  input[type="text"]::placeholder {
    color: var(--text-dim);
    opacity: 0.6;
  }
  .meta-row {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .char-count {
    font-size: 0.8rem;
    color: var(--text-dim);
    margin-left: auto;
    font-variant-numeric: tabular-nums;
  }
  button[type="submit"] {
    width: 100%;
    padding: 14px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    -webkit-tap-highlight-color: transparent;
  }
  button[type="submit"]:hover {
    background: var(--accent-hover);
  }
  button[type="submit"]:active {
    transform: scale(0.98);
  }
  button[type="submit"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .result {
    padding: 16px;
    border-radius: var(--radius);
    text-align: center;
    display: none;
  }
  .result.success {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: var(--success);
    display: block;
  }
  .result.error {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #ef4444;
    display: block;
  }
  .spinner {
    display: none;
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    margin: 0 auto;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .footer {
    text-align: center;
    color: var(--text-dim);
    font-size: 0.75rem;
    padding: 12px 0;
    opacity: 0.5;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🌀 vortex</h1>
    <div class="subtitle">drop content into the river</div>
  </header>

  <form id="intake-form" method="POST" action="/intake">
    <div class="form-group" style="margin-bottom:12px">
      <label for="title">Title (optional)</label>
      <input type="text" id="title" name="title" placeholder="auto-generated if empty">
    </div>

    <div class="form-group" style="margin-bottom:12px">
      <label for="source_url">Source URL (optional)</label>
      <input type="text" id="source_url" name="source_url" placeholder="original URL for pasted unfetchable content">
    </div>

    <div class="form-group" style="margin-bottom:12px">
      <label for="content">Content</label>
      <textarea id="content" name="content" placeholder="Paste text, notes, conversations, anything..." required></textarea>
      <div class="meta-row">
        <span class="char-count" id="char-count">0 chars</span>
      </div>
    </div>

    <button type="submit" id="submit-btn">
      <span id="btn-text">Drop into vortex</span>
      <div class="spinner" id="spinner"></div>
    </button>
  </form>

  <div class="result" id="result"></div>
  <div class="footer">turtleOS intake · content saves to box/, metabolizes in 7 days</div>
</div>

<script>
const textarea = document.getElementById('content');
const charCount = document.getElementById('char-count');
const form = document.getElementById('intake-form');
const submitBtn = document.getElementById('submit-btn');
const btnText = document.getElementById('btn-text');
const spinner = document.getElementById('spinner');
const result = document.getElementById('result');
const params = new URLSearchParams(window.location.search);

const sourceUrl = params.get('url') || '';
const suggestedTitle = params.get('title') || '';
if (sourceUrl) document.getElementById('source_url').value = sourceUrl;
if (suggestedTitle) document.getElementById('title').value = suggestedTitle;

textarea.addEventListener('input', () => {
  const len = textarea.value.length;
  charCount.textContent = len.toLocaleString() + ' chars';
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!textarea.value.trim()) return;

  submitBtn.disabled = true;
  btnText.style.display = 'none';
  spinner.style.display = 'block';
  result.className = 'result';
  result.style.display = 'none';

  try {
    const resp = await fetch('/intake', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: textarea.value,
        title: document.getElementById('title').value || '',
        source_url: document.getElementById('source_url').value || ''
      })
    });
    const data = await resp.json();
    if (data.ok) {
      result.className = 'result success';
      result.innerHTML = '🌀 ' + data.message;
      textarea.value = '';
      charCount.textContent = '0 chars';
    } else {
      result.className = 'result error';
      result.textContent = data.error || 'Something went wrong';
    }
  } catch (err) {
    result.className = 'result error';
    result.textContent = 'Connection failed: ' + err.message;
  } finally {
    submitBtn.disabled = false;
    btnText.style.display = 'inline';
    spinner.style.display = 'none';
  }
});
</script>
</body>
</html>"""


async def handle_intake_page(request):
    """Serve the intake form."""
    return web.Response(text=INTAKE_HTML, content_type="text/html")


async def handle_intake_submit(request):
    """Handle intake form submission."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    content = data.get("content", "").strip()
    if not content:
        return web.json_response({"ok": False, "error": "No content"}, status=400)

    title = data.get("title", "").strip()
    source_url = data.get("source_url", "").strip()
    intake_dir = _ensure_intake_dir()

    # Metabolize old files while we're here
    _metabolize_old_files(intake_dir)

    # Generate title if not provided
    if not title:
        first_line = content.split("\n")[0][:80].strip()
        title = first_line if first_line else "intake"

    # Save full content to file
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(title)
    filename = f"{ts}-{slug}.md"
    filepath = intake_dir / filename

    source_line = f"**Source URL:** {source_url}\n" if source_url else ""
    file_content = (
        f"# {title}\n\n"
        f"*Received {datetime.now().strftime('%Y-%m-%d %H:%M')} via vortex intake*\n\n"
        f"{source_line}"
        f"---\n\n{content}\n"
    )
    filepath.write_text(file_content, encoding="utf-8")
    print(f"Intake saved: {filepath} ({len(content)} chars)")

    # Generate summary
    summary = await _summarize(content)

    # Post to vortex via Discord
    bot_app = request.app
    discord_client = bot_app.get("discord_client")
    vortex_thread_id = bot_app.get("vortex_thread_id")

    posted_to = None
    if discord_client and vortex_thread_id:
        try:
            import discord
            thread = discord_client.get_channel(vortex_thread_id)
            if thread:
                embed = discord.Embed(
                    title=f"📄 {title}",
                    description=summary[:4000],
                    color=0x7c3aed,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.set_footer(text=f"intake · {len(content):,} chars · {filename}")
                embed.add_field(
                    name="Full content",
                    value=f"`box/intake/{filename}`",
                    inline=False,
                )
                if source_url:
                    embed.add_field(
                        name="Source URL",
                        value=source_url[:1024],
                        inline=False,
                    )
                await thread.send(embed=embed)
                posted_to = thread.name

                # Now let the prism decide: route or spawn?
                # We simulate a vortex message by injecting into handle flow
                from eddy_spawn import (
                    get_routable_eddies, detect_resonance,
                    URL_PATTERN
                )

                guild_id = str(thread.guild.id) if thread.guild else None
                if guild_id:
                    try:
                        routable = await get_routable_eddies(guild_id)
                        match = await detect_resonance(content[:3000], routable)
                        if match and "thread" in match:
                            target = match["thread"]
                            route_embed = discord.Embed(
                                description=summary[:4000],
                                color=0x9B59B6,
                                timestamp=datetime.now(timezone.utc),
                            )
                            route_embed.set_author(name="vortex intake")
                            route_embed.set_footer(
                                text=f"🌀 routed · full text: box/intake/{filename}"
                            )
                            await target.send(embed=route_embed)
                            posted_to = f"{thread.name} → {target.name}"
                    except Exception as e:
                        print(f"Intake prism routing failed: {e}")
        except Exception as e:
            print(f"Intake Discord post failed: {e}")

    return web.json_response({
        "ok": True,
        "message": f"<strong>{title}</strong> received ({len(content):,} chars)"
                   + (f"<br><small>posted to {posted_to}</small>" if posted_to else ""),
        "file": filename,
    })


async def handle_health(request):
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "turtleos-intake"})


def _shell_endpoint_authorized(request) -> bool:
    """Allow local requests, or token-authenticated remote requests."""
    token = os.environ.get("TURTLE_SHELL_TOKEN", "").strip()
    if token:
        auth = request.headers.get("Authorization", "")
        header_token = request.headers.get("X-Turtle-Shell-Token", "")
        return auth == f"Bearer {token}" or header_token == token
    return request.remote in {"127.0.0.1", "::1", "localhost"}


async def handle_shell_submit(request):
    """Run a constrained turtleOS shell command.

    This endpoint is intentionally not a general terminal. Without
    TURTLE_SHELL_TOKEN it only accepts localhost callers; remote callers must
    present the token. The harness itself still enforces command allowlists.
    """
    if not _shell_endpoint_authorized(request):
        return web.json_response({"ok": False, "error": "shell endpoint not authorized"}, status=403)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    command = data.get("command", "").strip()
    if not command:
        return web.json_response({"ok": False, "error": "No command"}, status=400)

    result = run_shell_command(
        command,
        cwd=data.get("cwd") or None,
        reason=data.get("reason", "shell endpoint"),
        requester=data.get("requester", "shell-endpoint"),
    )
    status = 200 if result.get("ok") else (400 if result.get("allowed") else 403)
    return web.json_response(result, status=status)


def create_intake_app(discord_client=None, vortex_thread_id=None) -> web.Application:
    """Create the aiohttp web application."""
    app = web.Application()
    app["discord_client"] = discord_client
    app["vortex_thread_id"] = vortex_thread_id

    app.router.add_get("/", handle_intake_page)
    app.router.add_get("/intake", handle_intake_page)
    app.router.add_post("/intake", handle_intake_submit)
    app.router.add_get("/paste", handle_intake_page)
    app.router.add_post("/paste", handle_intake_submit)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/shell", handle_shell_submit)

    return app


async def start_intake_server(discord_client=None, vortex_thread_id=None):
    """Start the intake web server in the background."""
    app = create_intake_app(discord_client, vortex_thread_id)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", INTAKE_PORT)
    await site.start()
    print(f"Intake server running on http://0.0.0.0:{INTAKE_PORT}")
    return runner
