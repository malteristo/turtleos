"""Eddy link reading — structured fetch, file spill, Discord status embeds."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlencode

import discord

from content_fetch import (
    _URL_PATTERN,
    detect_platform,
    fetch_reddit,
    fetch_twitter,
    fetch_url_content,
    fetch_youtube_transcript,
    litl_check,
    _yt_dlp_fetch,
)

PROMPT_INLINE_MAX = 8000
DIALOGUE_INJECT_MAX = PROMPT_INLINE_MAX
HISTORY_INLINE_MAX = 6000
AUTO_URL_COMMENTARY_MAX = 120
MAX_URLS_PER_MESSAGE = 3
SPILL_THRESHOLD = PROMPT_INLINE_MAX

_AUTO_READ_CUE_RE = re.compile(
    r"\b("
    r"read|summarize|summary|what do you think|what's the argument|"
    r"whats the argument|check this|check out|look at this|thoughts on"
    r")\b",
    re.IGNORECASE,
)

_COLOR_READING = 0x5865F2
_COLOR_OK = 0x57F287
_COLOR_FAIL = 0xFEE75C

_BLANK_EDDY_NAMES = frozenset({"new eddy", "blank eddy", "thread"})


def should_rename_thread_from_fetch(
    current_name: str,
    url: str,
    *,
    river_enabled: bool,
) -> bool:
    """True only when link-read may retitle — never when River owns naming."""
    if river_enabled:
        return False
    current = (current_name or "").strip().lower()
    if current in _BLANK_EDDY_NAMES:
        return True
    return current == url_display_host(url)


@dataclass
class FetchResult:
    url: str
    ok: bool
    content: str | None = None
    source: str | None = None
    attempts: list[str] = field(default_factory=list)
    char_count: int = 0
    litl_hits: list[str] = field(default_factory=list)
    title: str | None = None
    artifact_path: str | None = None
    prompt_excerpt_chars: int = 0


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-") or "link-read"


def url_display_host(url: str) -> str:
    try:
        host = urlparse(url).netloc or url
    except Exception:
        host = url
    return host.removeprefix("www.")


def external_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    for url in urls:
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            host = ""
        if "discord" in host:
            continue
        out.append(url)
    return out


def should_auto_fetch_urls(text: str, urls: list[str]) -> bool:
    """URL-primary messages auto-read; long incidental text gets Read/Skip offer."""
    if not urls:
        return False
    commentary = text or ""
    for url in urls:
        commentary = commentary.replace(url, " ")
    commentary = re.sub(r"\s+", " ", commentary).strip()
    if not commentary:
        return True
    if len(commentary) <= AUTO_URL_COMMENTARY_MAX:
        return True
    if _AUTO_READ_CUE_RE.search(commentary):
        return True
    return False


def plan_dialogue_urls(
    visible_content: str,
    external: list[str],
    *,
    native_eddy: bool,
) -> tuple[bool, list[str], list[str]]:
    """Return (auto_fetch, urls_for_context, pending_incidental_urls).

    Native eddies: never auto-fetch — Turtle discusses the link; seneschal may offer `!fetch`.
    Legacy: auto-fetch when URL-primary; otherwise Read/Skip offer via pending_incidental.
    """
    if not external:
        return False, [], []
    if native_eddy:
        return False, external, []
    if should_auto_fetch_urls(visible_content, external):
        return True, external, []
    return False, external, external


def _guess_title(content: str, url: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("http"):
            return stripped[:120]
    return url_display_host(url)


def spill_fetch_artifact(result: FetchResult) -> FetchResult:
    """Write full extract to box/intake/ when above spill threshold."""
    if not result.ok or not result.content:
        return result

    result.prompt_excerpt_chars = min(len(result.content), PROMPT_INLINE_MAX)
    if result.char_count <= SPILL_THRESHOLD:
        return result

    try:
        from mage import get_pd

        intake_dir = Path(get_pd()) / "box" / "intake"
        intake_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = _slugify(result.title or url_display_host(result.url))
        filename = f"{ts}-{slug}.md"
        rel = f"box/intake/{filename}"
        header_title = result.title or "Web extract"
        file_content = (
            f"# {header_title}\n\n"
            f"*Link read {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC*\n\n"
            f"**Source:** {result.url}\n\n"
            f"---\n\n{result.content}\n"
        )
        (intake_dir / filename).write_text(file_content, encoding="utf-8")
        result.artifact_path = rel
        print(f"Link read spill: {rel} ({result.char_count:,} chars)")
    except Exception as exc:
        print(f"Link read spill failed: {type(exc).__name__}: {exc}")
    return result


async def _fetch_one_url(url: str) -> FetchResult:
    from url_validate import validate_fetch_url

    blocked = validate_fetch_url(url)
    if blocked:
        return FetchResult(url=url, ok=False, attempts=[f"SSRF blocked: {blocked}"])

    platform = detect_platform(url)
    content: str | None = None
    source_type: str | None = None
    attempts: list[str] = []

    if platform == "twitter":
        content, source_type = await fetch_twitter(url)
        if not content:
            attempts.append(f"twitter oembed: {source_type}")
    elif platform == "youtube":
        content, source_type = await fetch_youtube_transcript(url)
        if not content:
            attempts.append(f"youtube transcript: {source_type}")
            content, source_type = await _yt_dlp_fetch(url)
            if not content:
                attempts.append(f"yt-dlp: {source_type}")
    elif platform == "reddit":
        content, source_type = await fetch_reddit(url)
        if not content:
            attempts.append(f"reddit rdt-cli: {source_type}")

    if not content:
        content, source_type = await fetch_url_content(url)
        if not content and source_type:
            attempts.append(source_type)

    if not content:
        return FetchResult(url=url, ok=False, attempts=attempts)

    litl_hits = litl_check(content)
    result = FetchResult(
        url=url,
        ok=True,
        content=content,
        source=source_type,
        char_count=len(content),
        litl_hits=litl_hits,
        title=_guess_title(content, url),
    )
    return spill_fetch_artifact(result)


async def fetch_urls_for_dialogue(urls: list[str], max_urls: int = MAX_URLS_PER_MESSAGE) -> list[FetchResult]:
    results: list[FetchResult] = []
    for url in urls[:max_urls]:
        results.append(await _fetch_one_url(url))
    return results


async def fetch_urls_with_status(
    channel: discord.abc.Messageable,
    urls: list[str],
) -> tuple[list[FetchResult], str]:
    """Fetch with Reading→Read status embed. Returns (results, dialogue_block)."""
    if not urls:
        return [], ""
    status_msg = await post_fetch_status(channel, urls[0])
    async with channel.typing():
        results = await fetch_urls_for_dialogue(urls)
        await edit_fetch_status(status_msg, results)
    return results, format_fetch_results_for_dialogue(results)


def format_result_for_dialogue(result: FetchResult) -> str:
    """Block injected into Turtle context for this turn."""
    if result.ok and result.content:
        nested = _URL_PATTERN.findall(result.content)
        nested = [
            u
            for u in nested
            if u != result.url
            and not u.startswith("https://t.co/")
            and "twitter.com" not in u
            and "x.com" not in u
        ]
        header = f"[URL: {result.url} (via {result.source})]"
        excerpt = result.content[:PROMPT_INLINE_MAX]
        if result.artifact_path:
            body = (
                f"[Full text: `{result.artifact_path}` — {result.char_count:,} chars]\n\n"
                f"{excerpt}\n\n"
                f"[Turtle read the first {len(excerpt):,} characters for this turn; "
                f"full extract is in the file above. Ask to search or focus on a section if needed.]"
            )
        elif len(result.content) > PROMPT_INLINE_MAX:
            body = (
                f"{excerpt}\n\n"
                f"[Note: extract truncated to {PROMPT_INLINE_MAX:,} chars for this turn; "
                f"full extract was {result.char_count:,} chars.]"
            )
        else:
            body = excerpt

        if result.litl_hits:
            body = (
                f"[LITL WARNING: Content contains instruction-like patterns: "
                f"{result.litl_hits[:3]}. Presenting raw content with caution.]\n"
                f"{body}"
            )

        entry = f"{header}\n{body}"
        if nested[:3]:
            entry += "\n\n[Link depth report: Found nested URLs in this content:"
            for nu in nested[:3]:
                np = detect_platform(nu)
                entry += f"\n  - {nu} ({np or 'web'} — not yet explored)"
            entry += "\n  Tell me if you want me to explore any of these.]"
        return entry

    attempts_str = " → ".join(result.attempts) if result.attempts else "unknown"
    return (
        f"[URL: {result.url}]\n"
        f"[Tried: {attempts_str}]\n"
        f"[Could not extract content. Options: share a screenshot, "
        f"paste the text directly, or try `!fetch {result.url} --fresh`.]"
    )


def format_fetch_results_for_dialogue(results: list[FetchResult]) -> str:
    if not results:
        return ""
    return "\n\n---\n\n".join(format_result_for_dialogue(r) for r in results)


def paste_endpoint_for(url: str) -> str:
    base = os.environ.get("INTAKE_PUBLIC_URL", "http://localhost:8742/paste")
    return f"{base}?{urlencode({'url': url})}"


async def post_fetch_status(channel: discord.abc.Messageable, url: str) -> discord.Message | None:
    host = url_display_host(url)
    embed = discord.Embed(
        title="🔗 Reading…",
        description=host,
        color=_COLOR_READING,
    )
    try:
        return await channel.send(embed=embed, silent=True)
    except discord.HTTPException as exc:
        print(f"Link read status post failed: {exc}")
        return None


async def edit_fetch_status(status_msg: discord.Message | None, results: list[FetchResult]) -> None:
    if not status_msg or not results:
        return
    embed = _status_embed_single(results[0]) if len(results) == 1 else _status_embed_multi(results)
    try:
        await status_msg.edit(embed=embed)
    except discord.HTTPException as exc:
        print(f"Link read status edit failed: {exc}")


def _partial_read_status_lines(result: FetchResult) -> list[str]:
    """Embed lines: extract size vs what Turtle actually sees this turn."""
    injected = result.prompt_excerpt_chars or min(result.char_count, PROMPT_INLINE_MAX)
    lines = [
        f"**{result.char_count:,} chars** extracted · `{result.source or 'direct'}`",
    ]
    if result.char_count > injected:
        lines.append(f"**{injected:,} / {result.char_count:,}** in context for this turn.")
        if result.artifact_path:
            lines.append(f"Full text: `{result.artifact_path}`")
        else:
            lines.append(
                f"_{result.char_count - injected:,} chars not in context — paste or ask for a section._"
            )
    else:
        lines.append(f"**{result.char_count:,}** in context for this turn.")
    return lines


def _status_embed_single(result: FetchResult) -> discord.Embed:
    host = url_display_host(result.url)
    if result.ok:
        parts = _partial_read_status_lines(result)
        if result.litl_hits:
            parts.append(f"⚠️ Instruction-like patterns flagged ({len(result.litl_hits)}).")
        parts.append("_Discord's link preview above is cosmetic — this is what Turtle read._")
        embed = discord.Embed(
            title=f"🔗 Read {host}",
            description="\n".join(parts),
            color=_COLOR_OK,
        )
        footer_bits = []
        if result.title and result.title != host:
            footer_bits.append(result.title[:80])
        footer_bits.append(f"!fetch for distill/cache · hide preview: <url>")
        embed.set_footer(text=" · ".join(footer_bits)[:200])
        return embed

    attempts = " → ".join(result.attempts) if result.attempts else "unknown"
    paste = paste_endpoint_for(result.url)
    return discord.Embed(
        title=f"🔗 Couldn't read {host}",
        description=(
            f"**Tried:** {attempts[:900]}\n\n"
            f"Paste full text: {paste}\n"
            f"Or: `!fetch {result.url}`"
        ),
        color=_COLOR_FAIL,
    )


def _status_embed_multi(results: list[FetchResult]) -> discord.Embed:
    ok = sum(1 for r in results if r.ok)
    lines = []
    for result in results:
        host = url_display_host(result.url)
        if result.ok:
            flag = " ⚠️" if result.litl_hits else ""
            spill = f" → `{result.artifact_path}`" if result.artifact_path else ""
            lines.append(
                f"✓ **{host}** · {result.char_count:,} chars · `{result.source}`{spill}{flag}"
            )
        else:
            lines.append(f"✗ **{host}** · fetch failed")
    color = _COLOR_OK if ok == len(results) else (_COLOR_FAIL if ok == 0 else _COLOR_READING)
    return discord.Embed(
        title=f"🔗 Read {ok}/{len(results)} links",
        description="\n".join(lines),
        color=color,
    )


async def maybe_refine_thread_name_from_fetch(
    thread: discord.Thread,
    results: list[FetchResult],
) -> None:
    """Retitle blank eddies from article title — River owns naming when split-bot."""
    if not results or not results[0].ok or not results[0].title:
        return
    title = results[0].title.strip()[:100]
    if not title:
        return
    try:
        from mage import river_bot_enabled

        river_on = river_bot_enabled()
    except Exception:
        river_on = False
    if not should_rename_thread_from_fetch(
        thread.name or "", results[0].url, river_enabled=river_on
    ):
        return
    try:
        from thread_registry import update_thread_name

        await thread.edit(name=title)
        update_thread_name(thread.id, title)
        print(f"Link read thread rename: {thread.id} -> {title}")
    except discord.HTTPException as exc:
        print(f"Link read thread rename failed: {exc}")


async def post_link_offer(
    channel: discord.abc.Messageable,
    source_message_id: int,
    urls: list[str],
    bot_client: discord.Client,
) -> None:
    """Offer Read/Skip when a link is incidental to a long message."""
    external = external_urls(urls)
    if not external:
        return
    host = url_display_host(external[0])
    extra = f" (+{len(external) - 1} more)" if len(external) > 1 else ""
    embed = discord.Embed(
        title="🔗 Link detected",
        description=(
            f"**{host}**{extra}\n\n"
            "This message is long — the link wasn't auto-read.\n"
            "Use **Read article** to fetch it, or **Skip** to ignore."
        ),
        color=_COLOR_READING,
    )
    embed.set_footer(text=f"`!fetch {external[0][:80]}` · hide Discord preview: <url>")
    thread_id = channel.id if isinstance(channel, discord.Thread) else getattr(channel, "id", 0)
    view = LinkOfferView(thread_id, source_message_id, external)
    bot_client.add_view(view)
    try:
        await channel.send(embed=embed, view=view, silent=True)
        from bar_anchor import ensure_channel_bars

        await ensure_channel_bars(channel)
    except discord.HTTPException as exc:
        print(f"Link offer post failed: {exc}")


class LinkOfferView(discord.ui.View):
    """Read article / Skip for incidental links."""

    def __init__(self, thread_id: int, source_message_id: int, urls: list[str]):
        super().__init__(timeout=None)
        self._thread_id = thread_id
        self._source_message_id = source_message_id
        self._urls = urls[:MAX_URLS_PER_MESSAGE]
        read_btn = discord.ui.Button(
            label="Read article",
            style=discord.ButtonStyle.primary,
            custom_id=f"turtle:link:read:{thread_id}:{source_message_id}",
        )
        read_btn.callback = self._on_read
        self.add_item(read_btn)
        skip_btn = discord.ui.Button(
            label="Skip",
            style=discord.ButtonStyle.secondary,
            custom_id=f"turtle:link:skip:{thread_id}:{source_message_id}",
        )
        skip_btn.callback = self._on_skip
        self.add_item(skip_btn)

    async def _on_read(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            from discord_bot import run_link_read_followup

            await run_link_read_followup(interaction, self._source_message_id, self._urls)
        except Exception as exc:
            print(f"Link read followup failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send("Could not read the link.", ephemeral=True)
            return
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass

    async def _on_skip(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description="Link skipped — Turtle won't fetch unless you ask again.",
            color=0x5865F2,
        )
        await interaction.response.edit_message(embed=embed, view=None)
