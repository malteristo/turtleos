"""Link resonance cache and ``!fetch`` command (TURTLE_SPEC §9.5 distill-for-library)."""

from __future__ import annotations

import hashlib
import os
from urllib.parse import urlencode, urlparse

import discord

from content_fetch import (
    detect_platform as _detect_platform,
    fetch_twitter as _fetch_twitter,
    fetch_url_content as _fetch_url_content,
    fetch_youtube_transcript as _fetch_youtube_transcript,
    litl_check as _litl_check,
)
from helpers import local_now
from llm import chat_ollama
from mage import get_runtime_dir
from practice_io import truncate
from state import REFLECTION_MODEL

INTAKE_PUBLIC_URL = os.environ.get("INTAKE_PUBLIC_URL", "http://localhost:8742/paste")
FETCH_ACT_EXCERPT_MAX = 2000


def resonance_cache_dir() -> str:
    return os.path.join(get_runtime_dir(), "link-resonance")


def get_cached_resonance(url: str) -> str | None:
    cache_dir = resonance_cache_dir()
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, f"{url_hash}.md")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            pass
    return None


def cache_resonance(url: str, resonance: str, title: str = "") -> None:
    cache_dir = resonance_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, f"{url_hash}.md")
    now = local_now().strftime("%Y-%m-%d %H:%M")
    content = f"# {title or url}\n\n**URL:** {url}\n**Cached:** {now}\n\n---\n\n{resonance}\n"
    try:
        with open(path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"Resonance cache write failed for {url}: {e}")


async def distill_resonance(raw_content: str, url: str) -> str:
    prompt = (
        "Distill this web content into its essential resonance. "
        "Extract the key insights, claims, or ideas worth remembering. "
        "Write concisely — bullet points or short paragraphs. "
        "If it's a tweet, preserve the voice. If it's an article, capture the argument. "
        "If it's a page with little content, say so. "
        "Output ONLY the distilled resonance, nothing else."
    )
    try:
        result = await chat_ollama(
            prompt,
            [{"role": "user", "content": f"URL: {url}\n\nContent:\n{raw_content[:6000]}"}],
            model=REFLECTION_MODEL,
            num_ctx=8192,
        )
        return result.strip() if result else raw_content[:2000]
    except Exception:
        return raw_content[:2000]


def paste_endpoint_for(url: str) -> str:
    """Build a prefilled paste endpoint link for unfetchable content."""
    return f"{INTAKE_PUBLIC_URL}?{urlencode({'url': url})}"


def fetch_act_digest(url: str, resonance: str) -> str:
    """Rich act digest so Turtle can discuss fetched content on the next turn."""
    lines = [ln for ln in (resonance or "").splitlines() if ln.strip()]
    title = lines[0].lstrip("# ").strip() if lines else url
    body = resonance.strip()
    if len(lines) > 5:
        body = "\n".join(lines[5:]).strip() or body
    excerpt = truncate(body, FETCH_ACT_EXCERPT_MAX)
    return (
        f'Fetched and cached "{title}" ({url}). '
        f"The article is available in this eddy for discussion.\n\n"
        f"[Content excerpt]\n{excerpt}"
    )


async def cmd_fetch(message, args):
    if not args:
        await message.reply(
            "Usage: `!fetch <url>` — distill and cache resonance in `link-resonance/`\n"
            "For dialogue read, drop the URL in chat (auto-read) or use **Read article** on incidental links.\n"
            "Copy-paste friendly: `!fetch https://example.com/article`",
            mention_author=False,
        )
        return

    url = args[0].strip("<>")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        await message.reply(f"Not a valid URL: `{url}`", mention_author=False)
        return

    from url_validate import validate_fetch_url

    blocked = validate_fetch_url(url)
    if blocked:
        await message.reply(
            f"Cannot fetch `{url}` — {blocked}",
            mention_author=False,
        )
        return

    cached = get_cached_resonance(url)
    if cached:
        lines = cached.split("\n")
        title = lines[0].lstrip("# ").strip() if lines else url
        embed = discord.Embed(
            title=f"\U0001f517 {title}",
            description=truncate("\n".join(lines[5:]), 2000),
            color=0x3498DB,
        )
        embed.set_footer(text="Cached resonance • add --fresh to refetch • drop URL in chat for dialogue read")
        await message.reply(embed=embed, mention_author=False)
        if "--fresh" not in " ".join(args):
            return fetch_act_digest(url, cached)

    async with message.channel.typing():
        raw_content, source_type = None, None
        platform = _detect_platform(url)
        if platform == "twitter":
            raw_content, source_type = await _fetch_twitter(url)
        elif platform == "youtube":
            raw_content, source_type = await _fetch_youtube_transcript(url)
        if not raw_content:
            raw_content, source_type = await _fetch_url_content(url)

        if not raw_content:
            paste_url = paste_endpoint_for(url)
            await message.reply(
                f"\U0001f517 Could not fetch `{url}` ({source_type}).\n"
                f"Paste the text here so Turtle can process it with source context: {paste_url}",
                mention_author=False,
            )
            return None

        litl_hits = _litl_check(raw_content)
        if litl_hits:
            await message.reply(
                f"⚠️ Content from `{url}` contains instruction-like patterns ({len(litl_hits)} hits). "
                "Presenting with caution.",
                mention_author=False,
            )

        resonance = await distill_resonance(raw_content, url)
        cache_resonance(url, resonance, title=url)

    embed = discord.Embed(
        title=f"\U0001f517 {url}",
        description=truncate(resonance, 2000),
        color=0x3498DB,
    )
    embed.set_footer(
        text=f"Distilled via {source_type or 'direct'} • cached in link-resonance/ • drop URL in chat for dialogue read"
    )
    await message.reply(embed=embed, mention_author=False)
    return fetch_act_digest(url, resonance)


# Back-compat aliases for in-repo callers migrating off commands.py
_get_cached_resonance = get_cached_resonance
_cache_resonance = cache_resonance
