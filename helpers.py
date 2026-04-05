"""turtleOS shared helpers — utilities used across multiple modules."""

import discord
from datetime import datetime, timezone

from state import (
    client, OPS_EMBED_COLOR,
    dialogue_histories, MAX_DIALOGUE_HISTORY,
    get_channel, HAS_GEMINI, GOOGLE_API_KEY,
)


# ─── Message Splitting ──────────────────────────────────────────

def split_message(text, limit=1900):
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ─── Activity Logging ───────────────────────────────────────────

async def log_activity(text: str, emoji: str = "\u2699\ufe0f", channel=None):
    target = channel or get_channel("dialogue")
    if not target:
        return
    ts_str = datetime.now(timezone.utc).strftime("%H:%M")
    embed = discord.Embed(
        description=f"{emoji} {ts_str} {text}",
        color=OPS_EMBED_COLOR,
    )
    try:
        await target.send(embed=embed, silent=True)
    except Exception:
        pass


# ─── History Management ─────────────────────────────────────────

def get_history(channel_id: int) -> list[dict]:
    if channel_id not in dialogue_histories:
        dialogue_histories[channel_id] = []
    return dialogue_histories[channel_id]


async def load_thread_history(thread: discord.Thread, max_messages: int = 50) -> list[dict]:
    """Load a thread's Discord message history into the in-memory format."""
    history = []
    try:
        async for msg in thread.history(limit=max_messages, oldest_first=True):
            if msg.author.bot and msg.author == client.user:
                content = msg.content
                if content and not content.startswith("🧵"):
                    history.append({"role": "assistant", "content": content})
            elif not msg.author.bot:
                history.append({"role": "user", "content": f"[{msg.author.display_name}]: {msg.content}"})
    except Exception as e:
        print(f"Failed to load thread history for {thread.name}: {e}")
    if history and len(history) > MAX_DIALOGUE_HISTORY:
        history = history[-MAX_DIALOGUE_HISTORY:]
    return history


def summarize_thread_context(history: list[dict], thread_name: str) -> str:
    """Build a brief summary of what was loaded from thread history."""
    user_msgs = [m for m in history if m["role"] == "user"]
    assistant_msgs = [m for m in history if m["role"] == "assistant"]
    first_user = user_msgs[0]["content"][:120] if user_msgs else ""
    last_user = user_msgs[-1]["content"][:120] if len(user_msgs) > 1 else ""
    parts = [f"*{len(user_msgs)} mage / {len(assistant_msgs)} spirit messages*"]
    if first_user:
        parts.append(f"Started with: {first_user}…" if len(first_user) >= 118 else f"Started with: {first_user}")
    if last_user and last_user != first_user:
        parts.append(f"Last: {last_user}…" if len(last_user) >= 118 else f"Last: {last_user}")
    return "\n".join(parts)


# ─── Attachment Processing ──────────────────────────────────────

async def preprocess_attachments(attachments):
    """Wrapper that passes Gemini config to content_fetch."""
    from content_fetch import preprocess_attachments as _preprocess_attachments_raw
    try:
        from google import genai as _genai
        genai_mod = _genai if HAS_GEMINI else None
    except ImportError:
        genai_mod = None
    return await _preprocess_attachments_raw(attachments, genai_module=genai_mod, api_key=GOOGLE_API_KEY)
