#!/usr/bin/env python3
"""Content fetching and processing for turtleOS Discord bot.

Handles URL extraction, platform-specific fetching (Twitter/X, YouTube, Reddit),
generic web scraping via trafilatura, LITL safety checks, and
Discord attachment preprocessing via Gemini.

CLI tool integration (2026-04-06): Delegates to community-maintained CLI tools
(twitter-cli, rdt-cli, yt-dlp) when available, falling back to existing methods.
Inspired by Agent Reach pattern: use the best tool for each platform.

Extracted from discord_bot.py 2026-03-24 for structural health.
"""

import asyncio
import json
import os
import re
import shutil

import httpx

from url_validate import assert_fetch_url_allowed, ssrf_httpx_request_hook


_VENV_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin")


def _cli_path(name):
    """Get the path to a CLI tool, preferring the local venv."""
    venv_path = os.path.join(_VENV_BIN, name)
    if os.path.exists(venv_path):
        return venv_path
    return shutil.which(name)


async def _run_cli(args, timeout=30):
    """Run a CLI command asynchronously, return (stdout, returncode)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode(errors="replace"), proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return "", -1
    except Exception:
        return "", -1


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


def _fetch_http_client(**kwargs) -> httpx.AsyncClient:
    """httpx client with SSRF validation on every request (incl. redirects)."""
    hooks = kwargs.pop("event_hooks", None) or {}
    request_hooks = list(hooks.get("request") or [])
    request_hooks.insert(0, ssrf_httpx_request_hook)
    hooks["request"] = request_hooks
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)


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
        async with _fetch_http_client(
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

    _GARBAGE_SIGNALS = ["javascript is disabled", "enable javascript",
                        "this page doesn't exist", "try searching for something else",
                        "you've been blocked", "log in to your", "use your developer token",
                        "file a ticket", "blocked by network security"]
    lower = extracted.lower()
    if any(g in lower for g in _GARBAGE_SIGNALS) and len(extracted) < 500:
        return None, "blocked or JS-gated page (no useful content)"

    return extracted, "article"


async def _wayback_fetch(url, timeout=15):
    """Layer 4: Try Wayback Machine for archived version."""
    wayback_api = f"https://archive.org/wayback/available?url={url}"
    try:
        async with _fetch_http_client(timeout=httpx.Timeout(timeout), follow_redirects=True) as http:
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
        async with _fetch_http_client(
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
            _BLOCKED = ["you've been blocked", "blocked by network security",
                        "log in to your", "use your developer token"]
            lower = text.lower()
            if any(b in lower for b in _BLOCKED) and len(text) < 500:
                return None, "jina: target blocked access"
            return text, "jina"
    except Exception as e:
        return None, f"jina error: {type(e).__name__}"



async def fetch_url_content(url, timeout=15):
    """Fetch readable text from a URL using graceful degradation.
    Tries: direct fetch → wayback archive. Returns (content, source_type) or (None, attempts_report)."""
    from url_validate import validate_fetch_url

    blocked = validate_fetch_url(url)
    if blocked:
        return None, f"SSRF blocked: {blocked}"

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


async def _fetch_full_tweet(tweet_id):
    """Fetch full tweet text via Twitter API v2 (handles truncation from oembed)."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from twitter_ops import get_client
        client = get_client()
        response = client.get_tweet(
            tweet_id,
            tweet_fields=["text", "author_id", "note_tweet"],
        )
        if response.data:
            return response.data.text
    except Exception as e:
        print(f"Full tweet fetch failed: {type(e).__name__}: {e}")
    return None


async def _twitter_cli_fetch(url):
    """Fetch tweet via twitter-cli (cookie-based auth, full text, no truncation).
    Requires TWITTER_AUTH_TOKEN + TWITTER_CT0 in environment."""
    cli = _cli_path("twitter")
    if not cli:
        return None, "twitter-cli not installed"

    stdout, rc = await _run_cli([cli, "tweet", url], timeout=15)
    if rc != 0 or "not_authenticated" in stdout or "ok: false" in stdout:
        reason = "auth failed" if "not_authenticated" in stdout else f"rc={rc}"
        return None, f"twitter-cli: {reason}"

    if "ok: true" not in stdout:
        return None, "twitter-cli: unexpected output"

    try:
        import yaml
        data = yaml.safe_load(stdout)
        tweets = data.get("data", [])
        if not tweets:
            return None, "twitter-cli: no tweet data"
        tweet = tweets[0] if isinstance(tweets, list) else tweets
        text = tweet.get("text", "")
        author_data = tweet.get("author", {})
        author = author_data.get("screenName") or author_data.get("name", "unknown")
        metrics = tweet.get("metrics", {})

        result = f"Tweet by @{author}:\n{text}"
        if metrics:
            result += f"\n[{metrics.get('likes', 0)} likes, {metrics.get('retweets', 0)} RTs, {metrics.get('views', 0)} views]"

        urls_in_tweet = re.findall(r"https?://t\.co/\S+", text)
        if urls_in_tweet:
            linked_content = []
            async with _fetch_http_client(timeout=httpx.Timeout(10), follow_redirects=True) as http:
                for tco in urls_in_tweet[:3]:
                    try:
                        link_resp = await http.get(tco, follow_redirects=True)
                        final_url = str(link_resp.url)
                        if "x.com" in final_url or "twitter.com" in final_url:
                            continue
                        if link_resp.status_code == 200 and "text/html" in link_resp.headers.get("content-type", ""):
                            import trafilatura
                            extracted = trafilatura.extract(link_resp.text, include_links=False, favor_recall=True)
                            if extracted and len(extracted.strip()) > 50:
                                linked_content.append(f"[Linked article from {final_url}]:\n{extracted[:6000]}")
                            else:
                                linked_content.append(f"[Linked: {final_url} — content not extractable]")
                        else:
                            linked_content.append(f"[Linked: {final_url}]")
                    except Exception:
                        linked_content.append(f"[Linked: {tco} (could not follow)]")
            if linked_content:
                result += "\n\n" + "\n".join(linked_content)

        return result, "twitter-cli"
    except ImportError:
        return None, "twitter-cli: pyyaml not installed for parsing"
    except Exception as e:
        return None, f"twitter-cli parse error: {type(e).__name__}"


async def fetch_twitter(url):
    """Fetch tweet content. Tries twitter-cli first (full text), falls back to oembed.
    Follows links found in tweet text and extracts their content too."""
    # Layer 1: twitter-cli (cookie-based, full text, metrics)
    content, reason = await _twitter_cli_fetch(url)
    if content:
        return content, "twitter-cli"
    print(f"twitter-cli fallback: {reason}")

    # Layer 2: oembed (no auth needed, but truncates long tweets)
    import html as _html

    oembed_url = f"https://publish.twitter.com/oembed?url={url}&omit_script=true"
    try:
        async with _fetch_http_client(timeout=httpx.Timeout(10), follow_redirects=True) as http:
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

            # If oembed truncated, try Twitter API then Jina Reader for full text
            if "\u2026" in text or text.rstrip().endswith("..."):
                if tweet_id:
                    full_text = await _fetch_full_tweet(tweet_id)
                    if full_text and len(full_text) > len(text):
                        result = f"Tweet by {author}:\n{full_text}"
                        if linked_content:
                            result += "\n\n" + "\n".join(linked_content)
                        if replies:
                            result += f"\n\n[Author thread ({len(replies)} replies):]"
                            for i, reply_text in enumerate(replies, 1):
                                result += f"\n{i}. {reply_text}"
                    else:
                        jina_content, jina_reason = await _jina_fetch(url, timeout=20)
                        if jina_content and len(jina_content) > len(text):
                            result = f"Tweet by {author} (via Jina Reader):\n{jina_content[:6000]}"
                        else:
                            result += "\n\n[Note: Tweet may be truncated. Full text may contain more context.]"

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


async def fetch_reddit(url):
    """Fetch Reddit post content via rdt-cli (no auth needed for public posts)."""
    cli = _cli_path("rdt")
    if not cli:
        return None, "rdt-cli not installed"

    match = re.search(r"/comments/([a-z0-9]+)", url)
    if not match:
        return None, "could not extract Reddit post ID from URL"
    post_id = match.group(1)

    stdout, rc = await _run_cli([cli, "read", post_id], timeout=20)
    if rc != 0 or "ok: false" in stdout:
        return None, f"rdt-cli failed (rc={rc})"

    if "ok: true" not in stdout:
        return None, "rdt-cli: unexpected output format"

    try:
        import yaml
        data = yaml.safe_load(stdout)
        listings = data.get("data", [])
        if isinstance(listings, list) and listings:
            first_listing = listings[0]
            children = first_listing.get("data", {}).get("children", [])
            if children and isinstance(children[0], dict):
                post = children[0].get("data", {})
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                author = post.get("author", "unknown")
                subreddit = post.get("subreddit_name_prefixed", "")
                score = post.get("score", 0)
                num_comments = post.get("num_comments", 0)
                post_url = post.get("url", "")

                result = f"Reddit: {title}\n"
                result += f"by u/{author} in {subreddit} | {score} points, {num_comments} comments\n"
                if selftext:
                    result += f"\n{selftext[:6000]}"
                elif post_url:
                    result += f"\n[Link post: {post_url}]"

                # Include top comments from second listing
                if len(listings) > 1:
                    comment_children = listings[1].get("data", {}).get("children", [])
                    top_comments = []
                    for c in comment_children[:5]:
                        if c.get("kind") == "t1":
                            cd = c.get("data", {})
                            c_author = cd.get("author", "?")
                            c_body = cd.get("body", "")
                            c_score = cd.get("score", 0)
                            if c_body:
                                top_comments.append(f"u/{c_author} ({c_score} pts): {c_body[:500]}")
                    if top_comments:
                        result += f"\n\n[Top {len(top_comments)} comments:]\n"
                        result += "\n---\n".join(top_comments)

                return result, "reddit"
    except ImportError:
        pass
    except Exception:
        pass

    if len(stdout) > 100:
        return f"Reddit post (raw YAML):\n{stdout[:6000]}", "reddit"
    return None, "rdt-cli: could not parse output"


async def _yt_dlp_fetch(url, timeout=30):
    """Fetch YouTube metadata + subtitles via yt-dlp (supports 1800+ sites)."""
    cli = _cli_path("yt-dlp")
    if not cli:
        return None, "yt-dlp not installed"

    stdout, rc = await _run_cli(
        [cli, "--dump-json", "--no-download", url],
        timeout=timeout,
    )
    if rc != 0 or not stdout.strip():
        return None, f"yt-dlp failed (rc={rc})"

    try:
        data = json.loads(stdout)
        title = data.get("title", "Unknown")
        uploader = data.get("uploader", "unknown")
        duration = data.get("duration", 0)
        description = data.get("description", "")

        subs = data.get("subtitles", {})
        auto_subs = data.get("automatic_captions", {})

        transcript_text = None
        for lang in ["en", "de", "de-DE"]:
            sub_list = subs.get(lang) or auto_subs.get(lang)
            if sub_list:
                for fmt in sub_list:
                    if fmt.get("ext") == "json3" and fmt.get("url"):
                        try:
                            async with _fetch_http_client(timeout=httpx.Timeout(15)) as http:
                                resp = await http.get(fmt["url"])
                                if resp.status_code == 200:
                                    sub_data = resp.json()
                                    segments = []
                                    for ev in sub_data.get("events", []):
                                        for s in ev.get("segs", []):
                                            t = s.get("utf8", "").strip()
                                            if t and t != "\n":
                                                segments.append(t)
                                    if segments:
                                        transcript_text = " ".join(segments)
                        except Exception:
                            pass
                    if transcript_text:
                        break
                if transcript_text:
                    break

        mins, secs = divmod(int(duration), 60)
        result = f"YouTube: {title}\nBy: {uploader} | Duration: {mins}m{secs}s\n"
        if transcript_text:
            result += f"\nTranscript:\n{transcript_text[:8000]}"
        elif description:
            result += f"\nDescription:\n{description[:4000]}"
        else:
            result += "\n[No transcript or description available.]"
        return result, "yt-dlp"
    except Exception as e:
        return None, f"yt-dlp parse error: {type(e).__name__}"


def detect_platform(url):
    """Detect known platforms that need special handling."""
    if "twitter.com/" in url or "x.com/" in url:
        return "twitter"
    if "youtube.com/" in url or "youtu.be/" in url:
        return "youtube"
    if "reddit.com/" in url or "redd.it/" in url:
        return "reddit"
    return None


async def process_urls(urls, max_urls=3):
    """Fetch and process URLs using graceful degradation.
    Includes LITL safety check and link depth transparency reporting."""
    from link_read import fetch_urls_for_dialogue, format_fetch_results_for_dialogue

    results = await fetch_urls_for_dialogue(urls, max_urls=max_urls)
    for result in results:
        if result.ok and result.litl_hits:
            print(f"LITL detected in {result.url}: {result.litl_hits[:3]}")
    return format_fetch_results_for_dialogue(results)


async def extract_attachments(message):
    """Download supported attachments from a Discord message.
    Returns list of (mime_type, bytes, filename) tuples."""
    results = []
    for att in message.attachments:
        ct = att.content_type or ""
        mime = ct.split(";")[0].strip().lower()
        if not mime or mime == "application/octet-stream":
            mime = _guess_attachment_mime(att.filename)
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


def _guess_attachment_mime(filename: str) -> str:
    """Infer MIME from extension when Discord omits content_type."""
    lower = (filename or "").lower()
    if lower.endswith((".jpg", ".jpeg", ".mp.jpg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".pdf"):
        return "application/pdf"
    return ""


_ATTACHMENT_PREPROCESS_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")


def _is_transient_gemini_error(exc: Exception) -> bool:
    name = type(exc).__name__
    if name in ("ServerError", "ServiceUnavailable", "ResourceExhausted", "TooManyRequests"):
        return True
    msg = str(exc).lower()
    return any(token in msg for token in ("503", "429", "unavailable", "high demand", "resource exhausted"))


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

    last_error = None
    for model in _ATTACHMENT_PREPROCESS_MODELS:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=parts,
                )
                return response.text or "[Could not extract content from attachment]"
            except Exception as e:
                last_error = e
                if _is_transient_gemini_error(e) and attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                print(f"Gemini preprocessing failed ({model}): {e}")
                break
    err_name = type(last_error).__name__ if last_error else "UnknownError"
    names = ", ".join(filename for _, _, filename in attachments)
    return (
        f"[Attachment processing failed ({err_name}) for: {names}. "
        "The image was received but vision extraction is temporarily unavailable — "
        "ask the practitioner to retry, paste a description, or re-send the image.]"
    )
