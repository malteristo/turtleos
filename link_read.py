"""Eddy link reading — structured fetch, file spill, Discord status embeds."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
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
# Re-exported from the runtime, which owns the rule. Two literals meant two
# numbers to change and one of them would be missed.
from runtime.link_offers import COMMENTARY_MAX as AUTO_URL_COMMENTARY_MAX
from runtime.link_offers import MEDIA_COMMENTARY_MAX as AUTO_URL_MEDIA_COMMENTARY_MAX
MAX_URLS_PER_MESSAGE = 3
SPILL_THRESHOLD = PROMPT_INLINE_MAX

# The engagement-cue pattern moved to `runtime.link_offers.READ_CUE_RE` — it is a
# judgement about the message, not about Discord, and it needed watch/listen cues
# a reading-only list could not carry. Do not re-add a local copy.

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
    """Delegates to `runtime.link_offers` — one list of self-hosts, not two."""
    from runtime.link_offers import external_urls as _external_urls

    return _external_urls(urls)


def should_auto_fetch_urls(text: str, urls: list[str]) -> bool:
    """URL-primary messages auto-read; long incidental text gets an offer instead.

    Delegates to `runtime.link_offers.should_auto_fetch`. The rule — commentary
    length as a proxy for "the link is incidental", with a wider ceiling for media
    because sharing a video *with* a remark is the ordinary way to share a video —
    is a judgement about the message, not about Discord. The operator's 08-12
    report was exactly this: every bare YouTube link shape fetched its transcript,
    and the moment he wrote a sentence around one it stopped.

    Kept as a name here because callers and shake scripts use it; kept as a
    *delegation* because a second copy of a rule revised twice in one week is a
    second copy that will not be revised the third time.
    """
    from runtime.link_offers import should_auto_fetch

    return should_auto_fetch(text, urls)


def plan_dialogue_urls(
    visible_content: str,
    external: list[str],
    *,
    native_eddy: bool = False,
) -> tuple[bool, list[str], list[str]]:
    """Return (auto_fetch, urls_for_context, pending_incidental_urls).

    Native and legacy eddies share heuristics: silent link-read when URL-primary,
    short commentary, or read cue; otherwise a read offer for long incidental text.
    ``native_eddy`` is reserved for future divergence; behavior is unified (harness
    split: Turtle read for conversation; River ``!fetch`` = library save only).
    """
    del native_eddy  # unified policy — see docs/chapters/2026-06-20-harness-split-read-vs-cache.md
    if not external:
        return False, [], []
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
    from core.url_validate import validate_fetch_url

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
    source_message: Any,
    urls: list[str],
    bot_client: discord.Client,
) -> None:
    """Offer to fetch when a link is incidental to a long message.

    **The first production path through the transport seam** (2026-08-14). The
    shape, end to end:

        discord.Message → IncomingMessage → runtime decides → OutgoingMessage
                        → discord_render posts it

    `runtime.link_offers.link_offer_for` chooses whether to offer at all, what the
    offer says, and what the button is called — none of which is a Discord
    question. `discord_render.send_outgoing` decides that an offer looks like an
    embed with a persistent button. Before this, both halves were this function.

    Until now `runtime/messages.py` had zero production importers: a tested,
    documented seam that nothing crossed. The design chapter claimed it was
    shipped, and `tests/test_runtime_adoption.py` was written to keep that claim
    honest by counting the modules production could not reach.

    There is no Skip. Ignoring an offer is a decline, and a button that converts
    silence into a required act manufactures the event the ledger exists to infer.

    `source_message` is the message object now, not its id — the adapter needs the
    author and the channel to resolve identity, and passing the id meant the caller
    took the message apart before the seam could.
    """
    from runtime.adapters.discord import incoming_from_discord
    from runtime.link_offers import link_offer_for

    external = external_urls(urls)
    if not external:
        return

    incoming = incoming_from_discord(source_message, urls=tuple(external))
    outgoing = link_offer_for(incoming)
    if outgoing is None:
        return

    action = outgoing.actions[0]
    # Was `channel.id if isinstance(channel, discord.Thread) else getattr(channel, "id", 0)`
    # — both branches returned the same value, and the isinstance check made the
    # function untestable without a real Discord type for no behavioural gain.
    thread_id = getattr(channel, "id", 0)
    source_message_id = getattr(source_message, "id", 0)

    async def _on_read(interaction: discord.Interaction, chosen) -> None:
        await interaction.response.defer()
        from offer_ledger import record_for_channel

        record_for_channel(thread_id, kind="link_read", event="accepted")
        try:
            from discord_bot import run_link_read_followup

            await run_link_read_followup(
                interaction,
                source_message_id,
                list(chosen.payload.get("urls", ()))[:MAX_URLS_PER_MESSAGE],
            )
        except Exception as exc:
            print(f"Link read followup failed: {type(exc).__name__}: {exc}")
            await interaction.followup.send("Could not read the link.", ephemeral=True)
            return
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass

    from discord_render import send_outgoing

    sent = await send_outgoing(
        channel,
        outgoing,
        incoming,
        prefix=f"turtle:link:read:{thread_id}:{source_message_id}",
        # The legacy `custom_id` exactly, with no action key appended. Discord
        # matches persistent views by `custom_id`, so a new format would leave
        # every already-posted offer with a button that does nothing — a
        # regression the practitioner would meet before anyone else.
        custom_id_for=lambda prefix, _action: prefix,
        handlers={action.key: _on_read},
        bot_client=bot_client,
        title="🔗 Link detected",
        color=_COLOR_READING,
        footer=f"`!fetch {external[0][:80]}` · hide Discord preview: <url>",
    )
    if sent is None:
        # A post that failed is not an offer, so it is not recorded as one. This is
        # the affordance whose label and auto-fetch rules were revised twice in one
        # week with no take rate to judge either revision by.
        return

    from offer_ledger import record_for_channel

    record_for_channel(thread_id, kind="link_read", event="offered", detail=action.key)
    from bar_anchor import ensure_channel_bars

    await ensure_channel_bars(channel)

