"""turtleOS boom thread — standing intake thread for universal capture.

Everything posted to the boom thread auto-captures to boom.md.
URLs are fetched (platform-aware: Twitter, YouTube, articles) and distilled.
Attachments are extracted. Plain text goes direct.
After capture, Turtle scans for follow-up opportunities and offers actions.
From phone: Share -> Discord -> boom thread. Done.
"""

import os
import re
from datetime import datetime, timezone

import discord

from mage import get_pd
from practice_io import read_safe, count_items
from content_fetch import (
    extract_urls, detect_platform,
    extract_attachments, fetch_twitter,
)
import asyncio

from llm import chat_ollama
from state import REFLECTION_MODEL  # unused but kept for potential future fallback

# Boom distillation: use 9b with thinking disabled for speed (~2s vs ~30s)
BOOM_DISTILL_MODEL = "qwen3.5:9b"
BOOM_DISTILL_TIMEOUT = 30  # seconds — generous, should be ~2-5s with think=False
BOOM_DISTILL_CTX = 4096
BOOM_DISTILL_THINK = False  # qwen3.5 thinks by default, costs 10-30x in latency


DISTILL_SYSTEM = (
    "You distill shared content into concise boom entries for a thinking "
    "partner's capture buffer. Be specific and preserve the original voice."
)

DISTILL_PROMPT = (
    "Distill this into 1-3 boom entries (each starting with '- '). "
    "Capture the key insight, argument, or point. Be specific, not generic. "
    "If it's a tweet, preserve the author's voice and the core point. "
    "If it's a thread (author + replies), capture the full argument arc. "
    "If it's an article, capture the argument. "
    "If it's a tool or repo, capture what it does and why it matters.\n\n"
    "Source: {source}\n\nCONTENT:\n{content}"
)


# ─── Follow-up action detection ─────────────────────────────────

# Patterns that suggest follow-up actions
YOUTUBE_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)'
)
GITHUB_PATTERN = re.compile(
    r'https?://github\.com/([\w.-]+/[\w.-]+)'
)
PAPER_PATTERNS = [
    re.compile(r'https?://arxiv\.org/(?:abs|pdf)/([\d.]+)'),
    re.compile(r'https?://(?:papers\.ssrn|doi\.org|scholar\.google)'),
]
PERSON_HINT_PATTERNS = [
    re.compile(r'@(\w{2,15})'),  # Twitter handles in content
]


def detect_follow_ups(content, original_url=""):
    """Scan fetched content for actionable follow-up opportunities.

    Returns list of dicts: [{type, url, label, action_description}]
    """
    actions = []

    # YouTube videos in content
    for match in YOUTUBE_PATTERN.finditer(content):
        yt_url = match.group(0)
        if yt_url != original_url:  # Don't suggest the URL they already shared
            actions.append({
                "type": "youtube",
                "url": yt_url,
                "label": f"YouTube video found",
                "action": f"Fetch transcript of {yt_url}",
                "emoji": "\U0001f3ac",
            })

    # GitHub repos in content
    for match in GITHUB_PATTERN.finditer(content):
        gh_url = match.group(0)
        repo = match.group(1)
        if gh_url != original_url:
            actions.append({
                "type": "github",
                "url": gh_url,
                "label": f"GitHub: {repo}",
                "action": f"Fetch README of {repo}",
                "emoji": "\U0001f4e6",
            })

    # Arxiv papers
    for pattern in PAPER_PATTERNS:
        for match in pattern.finditer(content):
            paper_url = match.group(0)
            if paper_url != original_url:
                actions.append({
                    "type": "paper",
                    "url": paper_url,
                    "label": "Research paper",
                    "action": f"Fetch and distill {paper_url}",
                    "emoji": "\U0001f4c4",
                })

    # Also detect YouTube if the original shared URL was a tweet containing a YT link
    for match in YOUTUBE_PATTERN.finditer(original_url):
        actions.append({
            "type": "youtube",
            "url": original_url,
            "label": "YouTube video",
            "action": "Fetch transcript",
            "emoji": "\U0001f3ac",
        })

    # Content-based signals: detect references to findable sources
    # When someone quotes a known creator + topic, the source is likely findable
    content_lower = content.lower()

    # Video/podcast/talk references in text
    video_hints = re.findall(
        r'(?:(?:video|podcast|talk|interview|episode|clip|says in (?:a|his|her|the))'
        r'[^.]{0,60}?(?:by|with|from|featuring)\s+([A-Z][a-z]+ [A-Z][a-z]+))|'
        r'((?:[A-Z][a-z]+ )+[A-Z][a-z]+)\s+(?:says|said|argues|explains|discusses|mentions|talks about)',
        content,
    )
    for match in video_hints:
        person = match[0] or match[1]
        if person and len(person) > 3:
            # Check if there's a video/media indicator
            if any(hint in content_lower for hint in ['video', 'podcast', 'talk', 'interview',
                                                        'clip', 'episode', 'says', 'pic.twitter']):
                search_query = f"{person} {content_lower.split(person.lower())[0][-30:].strip()}"
                actions.append({
                    "type": "search",
                    "url": "",
                    "query": person,
                    "label": f"Source: {person}",
                    "action": f"Search for {person} source",
                    "emoji": "\U0001f50d",
                })
                break  # Only one search suggestion

    return actions[:3]  # Max 3 follow-up suggestions


# ─── Follow-up action buttons ───────────────────────────────────

class FollowUpView(discord.ui.View):
    """Discord buttons for follow-up actions on captured content."""

    def __init__(self, actions, boom_path, timestamp):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.boom_path = boom_path
        self.timestamp = timestamp

        for i, action in enumerate(actions[:3]):
            button = FollowUpButton(
                action=action,
                boom_path=boom_path,
                timestamp=timestamp,
                row=0,
            )
            self.add_item(button)


class FollowUpButton(discord.ui.Button):
    """A single follow-up action button."""

    def __init__(self, action, boom_path, timestamp, **kwargs):
        self.action_data = action
        self.boom_path = boom_path
        self.timestamp = timestamp
        label = f"{action['emoji']} {action['action']}"
        if len(label) > 80:
            label = label[:77] + "..."
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            **kwargs,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        action = self.action_data
        result_text = ""

        try:
            if action["type"] == "youtube":
                from content_fetch import fetch_youtube_transcript
                content, source = await fetch_youtube_transcript(action["url"])
                if content:
                    # Distill the transcript
                    prompt = DISTILL_PROMPT.format(source=action["url"], content=content[:6000])
                    distilled = await chat_ollama(
                        DISTILL_SYSTEM,
                        [{"role": "user", "content": prompt}],
                        model=BOOM_DISTILL_MODEL, num_ctx=BOOM_DISTILL_CTX,
                        think=BOOM_DISTILL_THINK,
                    )
                    if distilled:
                        with open(self.boom_path, "a") as f:
                            f.write(f"\n### Follow-up: {action['url']} ({self.timestamp})\n")
                            f.write(distilled.strip() + "\n")
                        result_text = f"Transcript fetched and distilled to boom.\n> {distilled.strip()[:300]}"
                    else:
                        result_text = "Got the transcript but distillation failed."
                else:
                    result_text = f"Couldn't fetch transcript: {source}"

            elif action["type"] == "github":
                from content_fetch import fetch_url_content
                readme_url = action["url"].rstrip("/") + "/blob/main/README.md"
                content, source = await fetch_url_content(action["url"])
                if content:
                    prompt = DISTILL_PROMPT.format(source=action["url"], content=content[:4000])
                    distilled = await chat_ollama(
                        DISTILL_SYSTEM,
                        [{"role": "user", "content": prompt}],
                        model=BOOM_DISTILL_MODEL, num_ctx=BOOM_DISTILL_CTX,
                        think=BOOM_DISTILL_THINK,
                    )
                    if distilled:
                        with open(self.boom_path, "a") as f:
                            f.write(f"\n### Follow-up: {action['url']} ({self.timestamp})\n")
                            f.write(distilled.strip() + "\n")
                        result_text = f"Repo README distilled to boom.\n> {distilled.strip()[:300]}"
                    else:
                        result_text = "Fetched but distillation failed."
                else:
                    result_text = f"Couldn't fetch: {source}"

            elif action["type"] == "paper":
                from content_fetch import fetch_url_content
                content, source = await fetch_url_content(action["url"])
                if content:
                    prompt = DISTILL_PROMPT.format(source=action["url"], content=content[:4000])
                    distilled = await chat_ollama(
                        DISTILL_SYSTEM,
                        [{"role": "user", "content": prompt}],
                        model=BOOM_DISTILL_MODEL, num_ctx=BOOM_DISTILL_CTX,
                        think=BOOM_DISTILL_THINK,
                    )
                    if distilled:
                        with open(self.boom_path, "a") as f:
                            f.write(f"\n### Follow-up: {action['url']} ({self.timestamp})\n")
                            f.write(distilled.strip() + "\n")
                        result_text = f"Paper distilled to boom.\n> {distilled.strip()[:300]}"
                    else:
                        result_text = "Fetched but distillation failed."
                else:
                    result_text = f"Couldn't fetch: {source}"

            elif action["type"] == "search":
                # Content-based search — try to find the source via YouTube search
                query = action.get("query", "")
                result_text = (
                    f"Search suggested for: **{query}**\n"
                    "This is a content hint — Turtle detected a reference to a findable source. "
                    "Search manually or paste the URL here and I'll fetch it."
                )

        except Exception as e:
            result_text = f"Follow-up failed: {type(e).__name__}: {e}"

        # Disable the button after use
        self.disabled = True
        self.style = discord.ButtonStyle.success
        await interaction.message.edit(view=self.view)

        if len(result_text) > 1900:
            result_text = result_text[:1900] + "..."
        await interaction.followup.send(result_text)


# ─── Main handler ────────────────────────────────────────────────

async def handle_boom_thread_message(message):
    """Auto-capture everything in the boom thread to boom.md.

    Text -> direct capture. URLs -> platform-aware fetch + distill.
    Attachments -> extract + capture. Scans for follow-up actions.
    Always gives feedback. Returns True when handled.
    """
    pd = get_pd()
    boom_path = os.path.join(pd, "boom.md")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    text = message.content.strip()
    entries = []
    feedback_parts = []
    url_strings = []
    all_fetched_content = []  # For follow-up scanning
    all_follow_ups = []

    # 1. Handle URLs — platform-aware fetch and distill
    urls = await extract_urls(text)
    if urls:
        for url_info in urls:
            url = url_info if isinstance(url_info, str) else url_info.get("url", str(url_info))
            url_strings.append(url)
            platform = detect_platform(url)
            content = None
            source_label = url

            # Platform-specific fetching
            if platform == "twitter":
                content, source_type = await fetch_twitter(url)
                if content:
                    source_label = "tweet"
            elif platform == "youtube":
                # YouTube shared directly — capture and offer transcript
                from content_fetch import fetch_youtube_transcript
                content, source_type = await fetch_youtube_transcript(url)
                if content:
                    source_label = "youtube transcript"

            # Fallback to generic fetch if platform-specific failed
            if not content:
                from content_fetch import fetch_url_content
                content, source_type = await fetch_url_content(url)

            if content and len(content) > 50:
                all_fetched_content.append((url, content))

                # Distill the content (with timeout — interactive context)
                prompt = DISTILL_PROMPT.format(source=url, content=content[:4000])
                try:
                    distill_result = await asyncio.wait_for(
                        chat_ollama(
                            DISTILL_SYSTEM,
                            [{"role": "user", "content": prompt}],
                            model=BOOM_DISTILL_MODEL, num_ctx=BOOM_DISTILL_CTX,
                        think=BOOM_DISTILL_THINK,
                        ),
                        timeout=BOOM_DISTILL_TIMEOUT,
                    )
                    if distill_result:
                        entries.append(f"### Shared: {url} ({timestamp})")
                        entries.append(distill_result.strip())
                        # Build feedback from the distilled content
                        first_entry = distill_result.strip().split("\n")[0]
                        if first_entry.startswith("- "):
                            first_entry = first_entry[2:]
                        feedback_parts.append(f"> {first_entry[:200]}")
                        # Detect truncation
                        if "\u2026" in content or "truncated" in content.lower() or "reply-thread" in content.lower():
                            feedback_parts.append(
                                "*Tweet may be truncated or have reply-thread context. "
                                "Paste the full text here if you want the complete picture.*"
                            )
                    else:
                        entries.append(f"- [{url}] (shared {timestamp})")
                        feedback_parts.append("Captured link, but distillation returned empty.")
                except asyncio.TimeoutError:
                    entries.append(f"- [{url}] ({source_label}, shared {timestamp})")
                    # Still capture raw content snippet
                    snippet = content[:200].replace("\n", " ")
                    entries.append(f"  > {snippet}")
                    feedback_parts.append(f"> {snippet[:150]}\n*Distillation timed out — raw content captured.*")
                except Exception as e:
                    entries.append(f"- [{url}] ({source_label}, shared {timestamp})")
                    feedback_parts.append(f"Captured link, distill failed: {type(e).__name__}")

                # Scan fetched content for follow-up opportunities
                follow_ups = detect_follow_ups(content, original_url=url)
                all_follow_ups.extend(follow_ups)
            else:
                entries.append(f"- [{url}] (shared {timestamp}, could not fetch content)")
                feedback_parts.append("Captured the link but couldn't fetch content. Paste the text here if you want it processed.")

    # 2. Handle attachments
    if message.attachments:
        extracted = await extract_attachments(message)
        for content_text, mime, fname in extracted:
            if content_text:
                entries.append(f"### Shared: {fname} ({timestamp})")
                entries.append(f"- {content_text[:500]}")
                feedback_parts.append(f"Attachment `{fname}` captured.")
            else:
                entries.append(f"- [attachment: {fname}] (shared {timestamp})")
                feedback_parts.append(f"Attachment `{fname}` saved (couldn't extract text).")

    # 3. Plain text (strip URLs to see if there's additional context)
    clean_text = text
    for url in url_strings:
        clean_text = clean_text.replace(url, "").strip()

    if clean_text and not clean_text.startswith("!"):
        entries.append(f"- {clean_text} ({timestamp})")
        if not urls and not message.attachments:
            feedback_parts.append("Noted.")

    # 4. Write to boom
    if entries:
        with open(boom_path, "a") as f:
            f.write("\n" + "\n".join(entries) + "\n")

        count = count_items(read_safe(boom_path))
        await message.add_reaction("\U0001f4a5")  # boom emoji

        # Build the reply
        detail = "\n".join(feedback_parts) if feedback_parts else ""
        reply_text = f"Captured to boom ({count} items). {detail}".strip()
        if len(reply_text) > 1900:
            reply_text = reply_text[:1900] + "..."

        # If there are follow-up actions, attach buttons
        if all_follow_ups:
            # Deduplicate by URL
            seen = set()
            unique_follow_ups = []
            for fu in all_follow_ups:
                if fu["url"] not in seen:
                    seen.add(fu["url"])
                    unique_follow_ups.append(fu)

            view = FollowUpView(unique_follow_ups, boom_path, timestamp)
            await message.reply(reply_text, view=view, mention_author=False)
        else:
            await message.reply(reply_text, mention_author=False)

    # Return full fetched content for dialogue to reference
    if all_fetched_content:
        parts = []
        for url, raw in all_fetched_content:
            parts.append(f"[Content from {url}]:\n{raw[:8000]}")
        return "\n\n---\n\n".join(parts)
    return None
