#!/usr/bin/env python3
"""Content fetching and processing for turtleOS Discord bot.

Handles URL extraction, platform-specific fetching (Twitter/X, YouTube),
generic web scraping via trafilatura, LITL safety checks, and
Discord attachment preprocessing via Gemini.

Extracted from discord_bot.py 2026-03-24 for structural health.
"""

import re

import httpx


_URL_PATTERN = re.compile(r"https?://[^\s<>\"\')\]]+")
_LITL_PATTERNS = re.compile(
    r"(?i)(ignore.*(?:previous|above|system)|you are now|new instructions|"
    r"disregard.*prompt|system prompt|<\/?(system|instruction)>)",
)

SUPPORTED_ATTACHMENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
}
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20MB


async def extract_urls(text):
    """Extract URLs from message text. Returns list of URL strings."""
    return _URL_PATTERN.findall(text)


async def _direct_fetch(url, timeout=15):
    """Layer 1: Direct HTTP GET + trafilatura extraction."""
    try:
        import trafilatura
    except ImportError:
        return None, "trafilatura not installed"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        ) as http:
            resp = await http.get(url)
            if resp.status_code != 200:
                return None, f"HTTP {resp.status_code}"
            ct = resp.headers.get("content-type", "")
            if "text/html" not in ct and "text/plain" not in ct:
                return None, f"unsupported content-type: {ct}"
            html = resp.text
    except Exception as e:
        return None, f"fetch error: {type(e).__name__}"

    extracted = trafilatura.extract(
        html,
        include_links=False,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not extracted or len(extracted.strip()) < 50:
        return None, "no readable content extracted"

    return extracted, "article"


async def _wayback_fetch(url, timeout=15):
    """Layer 4: Try Wayback Machine for archived version."""
    wayback_api = f"https://archive.org/wayback/available?url={url}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True) as http:
            api_resp = await http.get(wayback_api)
            if api_resp.status_code != 200:
                return None, "wayback API unavailable"
            data = api_resp.json()
            snapshot = data.get("archived_snapshots", {}).get("closest", {})
            if not snapshot or not snapshot.get("available"):
                return None, "no wayback snapshot"
            archive_url = snapshot["url"]
            resp = await http.get(archive_url)
            if resp.status_code != 200:
                return None, f"wayback HTTP {resp.status_code}"
    except Exception as e:
        return None, f"wayback error: {type(e).__name__}"

    try:
        import trafilatura
        extracted = trafilatura.extract(resp.text, include_links=False, favor_recall=True)
        if extracted and len(extracted.strip()) > 50:
            timestamp = snapshot.get("timestamp", "unknown")
            return f"[Archived version from {timestamp[:8]}]\n{extracted}", "wayback"
    except Exception:
        pass
    return None, "wayback: no readable content"


async def _jina_fetch(url, timeout=20):
    """Layer 2: Jina Reader — renders JavaScript, returns clean markdown."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={
                "Accept": "text/plain",
                "X-No-Cache": "true",
            },
        ) as http:
            resp = await http.get(jina_url)
            if resp.status_code != 200:
                return None, f"jina HTTP {resp.status_code}"
            text = resp.text.strip()
            if len(text) < 50:
                return None, "jina: no readable content"
            return text, "jina"
    except Exception as e:
        return None, f"jina error: {type(e).__name__}"



async def fetch_url_content(url, timeout=15):
    """Fetch readable text from a URL using graceful degradation.
    Tries: direct fetch → wayback archive. Returns (content, source_type) or (None, attempts_report)."""
    attempts = []

    # Layer 1: Direct fetch
    content, reason = await _direct_fetch(url, timeout)
    if content:
        return content, "article"
    attempts.append(f"direct: {reason}")

    # Layer 2: Jina Reader (renders JS, handles modern sites)
    content, reason = await _jina_fetch(url, timeout=20)
    if content:
        return content, "jina"
    attempts.append(f"jina: {reason}")

    # Layer 3: Wayback Machine
    content, reason = await _wayback_fetch(url, timeout)
    if content:
        return content, "wayback"
    attempts.append(f"wayback: {reason}")

    return None, " → ".join(attempts)


def litl_check(text):
    """Check for potential prompt injection patterns in fetched content.
    Returns list of matched patterns, empty if clean."""
    return _LITL_PATTERNS.findall(text)




async def _fetch_tweet_reply_chain(tweet_id, author_username, max_replies=5):
    """Fetch the author's own replies to a tweet (self-thread pattern).

    Uses Twitter API v2 via tweepy. Returns list of reply texts or empty list.
    Common pattern: author posts main tweet, then adds context in replies.
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from twitter_ops import get_client
        client = get_client()

        # Search for replies from the same author to this tweet
        query = f"conversation_id:{tweet_id} from:{author_username} to:{author_username}"
        response = client.search_recent_tweets(
            query=query,
            max_results=min(max_replies, 10),
            tweet_fields=["created_at", "text", "in_reply_to_user_id"],
        )

        if not response.data:
            return []

        # Sort by creation time and return texts
        replies = sorted(response.data, key=lambda t: t.created_at or "")
        return [t.text for t in replies]
    except Exception as e:
        print(f"Reply chain fetch failed: {type(e).__name__}: {e}")
        return []


def _extract_tweet_id_and_username(url):
    """Extract tweet ID and username from X/Twitter URL.

    Handles:
    - https://x.com/username/status/123456
    - https://x.com/i/status/123456  (shared via mobile, no username)
    - https://twitter.com/username/status/123456
    """
    import re as _re
    # Pattern with username
    match = _re.search(r'(?:twitter\.com|x\.com)/(\w+)/status/(\d+)', url)
    if match:
        username = match.group(1)
        tweet_id = match.group(2)
        if username == 'i':
            username = None  # mobile share URL, no username
        return tweet_id, username
    return None, None

async def fetch_twitter(url):
    """Extract tweet content via Twitter's oembed API (no auth needed).
    Follows links found in tweet text and extracts their content too.
    For X articles that can't be scraped, provides actionable guidance."""
    import html as _html

    oembed_url = f"https://publish.twitter.com/oembed?url={url}&omit_script=true"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10), follow_redirects=True) as http:
            resp = await http.get(oembed_url)
            if resp.status_code != 200:
                return None, f"oembed HTTP {resp.status_code}"
            data = resp.json()
            raw_html = data.get("html", "")
            text = re.sub(r"<[^>]+>", " ", raw_html)
            text = _html.unescape(text).strip()
            text = re.sub(r"\s+", " ", text)
            author = data.get("author_name", "unknown")

            tweet_urls = [u for u in re.findall(r"https?://t\.co/\S+", text)]
            linked_content = []
            for tco in tweet_urls[:2]:
                try:
                    link_resp = await http.get(tco, follow_redirects=True, timeout=httpx.Timeout(10))
                    final_url = str(link_resp.url)
                    if "x.com" in final_url or "twitter.com" in final_url:
                        linked_content.append(
                            f"[Linked: {final_url} — This is an X/Twitter page that requires "
                            f"a browser to read. To get this content: screenshot it or copy-paste "
                            f"the text directly.]"
                        )
                    elif link_resp.status_code == 200 and "text/html" in link_resp.headers.get("content-type", ""):
                        import trafilatura
                        extracted = trafilatura.extract(link_resp.text, include_links=False, favor_recall=True)
                        if extracted and len(extracted.strip()) > 50:
                            linked_content.append(f"[Linked article from {final_url}]:\n{extracted[:6000]}")
                        else:
                            linked_content.append(
                                f"[Linked: {final_url} — Page requires JavaScript or content "
                                f"couldn't be extracted. Screenshot or paste the text.]"
                            )
                    else:
                        linked_content.append(f"[Linked: {final_url}]")
                except Exception:
                    linked_content.append(f"[Linked: {tco} (could not follow)]")

            result = f"Tweet by {author}:\n{text}"
            if linked_content:
                result += "\n\n" + "\n".join(linked_content)

            # Fetch author's reply chain (self-thread pattern)
            tweet_id, username = _extract_tweet_id_and_username(url)
            if not username:
                # Extract username from oembed author_url
                author_url = data.get("author_url", "")
                if author_url:
                    username = author_url.rstrip("/").split("/")[-1]
            if tweet_id and username:
                replies = await _fetch_tweet_reply_chain(tweet_id, username)
                if replies:
                    result += f"\n\n[Author thread ({len(replies)} replies):]"
                    for i, reply_text in enumerate(replies, 1):
                        result += f"\n{i}. {reply_text}"

            # Detect truncation (oembed cuts off long tweets with …)
            if "\u2026" in text or text.rstrip().endswith("..."):
                result += "\n\n[Note: Tweet appears truncated. Full text may contain more context. Author may have reply-thread with additional points.]"

            return result, "twitter"
    except Exception as e:
        return None, f"oembed error: {type(e).__name__}"


async def fetch_youtube_transcript(url):
    """Extract YouTube transcript if available."""
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    if not match:
        return None, "no video ID found"
    video_id = match.group(1)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id)
        text = " ".join(s.text for s in transcript.snippets)
        return f"YouTube transcript ({video_id}):\n{text[:8000]}", "youtube"
    except ImportError:
        return None, "youtube_transcript_api not installed"
    except Exception as e:
        return None, f"transcript error: {type(e).__name__}"


def detect_platform(url):
    """Detect known platforms that need special handling."""
    if "twitter.com/" in url or "x.com/" in url:
        return "twitter"
    if "youtube.com/" in url or "youtu.be/" in url:
        return "youtube"
    return None


async def process_urls(urls, max_urls=3):
    """Fetch and process URLs using graceful degradation.
    Includes LITL safety check on fetched content."""
    results = []
    for url in urls[:max_urls]:
        platform = detect_platform(url)
        content, source_type = None, None
        attempts = []

        if platform == "twitter":
            content, source_type = await fetch_twitter(url)
            if not content:
                attempts.append(f"twitter oembed: {source_type}")
        elif platform == "youtube":
            content, source_type = await fetch_youtube_transcript(url)
            if not content:
                attempts.append(f"youtube transcript: {source_type}")

        if not content:
            content, source_type = await fetch_url_content(url)
            if not content:
                attempts.append(source_type)

        if content:
            litl_hits = litl_check(content)
            if litl_hits:
                results.append(
                    f"[URL: {url} (via {source_type})]\n"
                    f"[LITL WARNING: Content contains instruction-like patterns: "
                    f"{litl_hits[:3]}. Presenting raw content with caution.]\n"
                    f"{content[:6000]}"
                )
                print(f"LITL detected in {url}: {litl_hits[:3]}")
            else:
                results.append(f"[URL: {url} (via {source_type})]\n{content[:8000]}")
        else:
            attempts_str = " → ".join(attempts) if attempts else "unknown"
            results.append(
                f"[URL: {url}]\n"
                f"[Tried: {attempts_str}]\n"
                f"[Could not extract content. Options: share a screenshot, "
                f"paste the text directly, or try `!fetch {url} --fresh`.]"
            )
    return "\n\n---\n\n".join(results) if results else ""


async def extract_attachments(message):
    """Download supported attachments from a Discord message.
    Returns list of (mime_type, bytes, filename) tuples."""
    results = []
    for att in message.attachments:
        ct = att.content_type or ""
        mime = ct.split(";")[0].strip().lower()
        if mime not in SUPPORTED_ATTACHMENT_TYPES:
            continue
        if att.size > MAX_ATTACHMENT_SIZE:
            continue
        try:
            data = await att.read()
            results.append((mime, data, att.filename))
        except Exception as e:
            print(f"Attachment download failed ({att.filename}): {e}")
    return results


async def preprocess_attachments(attachments, genai_module=None, api_key=None):
    """Use Gemini Flash to describe/extract content from attachments.
    Returns a text summary to prepend to the user message."""
    if not genai_module or not api_key:
        return "[Attachments received but no Gemini API key configured for processing.]"

    client = genai_module.Client(api_key=api_key)
    parts = []
    for mime, data, filename in attachments:
        if mime == "application/pdf":
            parts.append(f"The user attached a PDF file: {filename}. Extract all text content, describe any images, charts or tables.")
        else:
            parts.append(f"The user attached an image: {filename}. Describe what you see in detail. If there is text, read all of it.")
        parts.append(genai_module.types.Part.from_bytes(data=data, mime_type=mime))

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts,
        )
        return response.text or "[Could not extract content from attachment]"
    except Exception as e:
        print(f"Gemini preprocessing failed: {e}")
        return f"[Attachment processing error: {type(e).__name__}]"
