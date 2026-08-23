"""What a shared link is, and what the offer about it should be called.

A runtime decision that has been living inside a Discord UI module. The label
on a link button depends on what the link *is* — a video's content is its
transcript, an article's is its text — and nothing platform-specific is
involved in working that out. `link_read.py` hardcoded "Read article" for every
URL, so a YouTube link shared with a sentence around it offered to read an
article that does not exist.

Reported by the operator on 2026-08-12 and confirmed across three sittings:
bare links of every shape (watch, youtu.be, mobile URLs with parameters)
auto-fetch their transcript correctly; a link with other text in the same
message gets neither the fetch nor the right button.

Two decisions live here and both were previously platform-coupled:

* **What is this link** — `classify_url`. `content_fetch.detect_platform`
  delegates here so there is one list rather than two that drift.
* **What may the offer be called** — `action_for_urls`. The runtime chooses the
  label; a transport renders it, or folds it into prose when it has no buttons.

No transport import, by design — see ``tests/test_transport_boundary.py``.
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from runtime.messages import Action, IncomingMessage, OutgoingMessage

ContentKind = Literal["youtube", "twitter", "reddit", "article"]

# Host fragments, matched against the netloc only. Substring-matching the whole
# URL (as `detect_platform` did) means a link *about* YouTube on some other site
# classifies as a video.
_KIND_HOSTS: tuple[tuple[ContentKind, tuple[str, ...]], ...] = (
    ("youtube", ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")),
    ("twitter", ("twitter.com", "x.com", "mobile.twitter.com")),
    ("reddit", ("reddit.com", "redd.it", "old.reddit.com")),
)

# The label is what the practitioner reads before deciding, so it has to name
# what will actually arrive. "Read article" on a video is a coin flip he should
# not have to make.
_KIND_LABELS: dict[str, str] = {
    "youtube": "Fetch transcript",
    "twitter": "Read thread",
    "reddit": "Read discussion",
    "article": "Read article",
}

_KIND_NOUNS: dict[str, str] = {
    "youtube": "YouTube video",
    "twitter": "X/Twitter thread",
    "reddit": "Reddit discussion",
    "article": "Article",
}

# Kinds whose content is spoken or posted rather than written as a page. For
# these, commentary length is a bad proxy for "the link is incidental": sharing
# a video *with* a remark about it is the normal way to share a video.
MEDIA_KINDS: frozenset[str] = frozenset({"youtube"})

# Cues that mean "engage with this link". The original set covered reading only,
# which is why "watch this" on a video read as incidental commentary.
READ_CUE_RE = re.compile(
    r"\b("
    r"read|summarize|summary|what do you think|what's the argument|"
    r"whats the argument|check this|check out|look at this|thoughts on|"
    r"watch|watch this|listen|this video|this talk|explains|"
    r"schau|hör (?:dir )?(?:das|die)|lies"
    r")\b",
    re.IGNORECASE,
)


def _netloc(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host.removeprefix("www.")


def classify_url(url: str) -> ContentKind:
    host = _netloc(url)
    if not host:
        return "article"
    for kind, hosts in _KIND_HOSTS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return kind
    return "article"


def classify_urls(urls: list[str] | tuple[str, ...]) -> ContentKind | None:
    """The kind the whole set shares, or None when it is mixed."""
    kinds = {classify_url(u) for u in urls if u}
    if len(kinds) == 1:
        return kinds.pop()
    return None


def has_media(urls: list[str] | tuple[str, ...]) -> bool:
    return any(classify_url(u) in MEDIA_KINDS for u in urls if u)


def describe_url(url: str) -> str:
    """Enough to judge the link without fetching it.

    The embed used to show a bare host and a count — `aihero.dev (+22 more)` —
    from which the operator could not tell what the link was about, which made
    the button a guess. A title needs a fetch; the kind and the path do not, and
    together they are most of the judgement.
    """
    host = _netloc(url) or url
    noun = _KIND_NOUNS[classify_url(url)]
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        if parsed.query and classify_url(url) in MEDIA_KINDS:
            path = f"{path}?{parsed.query}"
    except Exception:
        path = ""
    if path:
        if len(path) > 60:
            path = path[:57] + "…"
        return f"{noun} · {host}/{path}"
    return f"{noun} · {host}"


def describe_urls(urls: list[str] | tuple[str, ...], *, limit: int = 3) -> str:
    shown = [u for u in urls if u][:limit]
    if not shown:
        return ""
    lines = [f"• {describe_url(u)}" for u in shown]
    remaining = len([u for u in urls if u]) - len(shown)
    if remaining > 0:
        lines.append(f"• …and {remaining} more")
    return "\n".join(lines)


def action_for_urls(urls: list[str] | tuple[str, ...]) -> Action | None:
    """The offer's key and label, chosen from what the links are."""
    present = [u for u in urls if u]
    if not present:
        return None
    kind = classify_urls(present)
    if kind is None:
        return Action(key="read_links", label="Read links", payload={"kind": "mixed"})
    return Action(key=f"read_{kind}", label=_KIND_LABELS[kind], payload={"kind": kind})


# ─── The whole offer decision, in runtime terms ───────────────────
#
# Below this line the module stops answering "what is this link" and starts
# answering "should we offer, and what does the offer say" — which is the decision
# `link_read.post_link_offer` used to make while also building a Discord embed.
# Separating them is what makes the offer testable without a Discord object and
# renderable on a surface that has no buttons.

# Hosts whose links are the transport talking about itself. A Discord CDN link or
# a message permalink is not an article someone shared.
_SELF_HOSTS: tuple[str, ...] = ("discord",)

# A link with a paragraph of commentary is probably incidental — except for media,
# where sharing a video *with* a remark is the ordinary way to share a video. The
# operator's 2026-08-12 report was exactly this: every bare YouTube link fetched
# its transcript, and the moment he wrote a sentence around one it stopped.
COMMENTARY_MAX = 120
MEDIA_COMMENTARY_MAX = 400


def external_urls(urls: list[str] | tuple[str, ...]) -> list[str]:
    """Drop links that point back at the transport itself."""
    out: list[str] = []
    for url in urls:
        host = _netloc(url)
        if any(fragment in host for fragment in _SELF_HOSTS):
            continue
        out.append(url)
    return out


def commentary_around(text: str, urls: list[str] | tuple[str, ...]) -> str:
    """What the practitioner wrote *besides* the links."""
    remainder = text or ""
    for url in urls:
        remainder = remainder.replace(url, " ")
    return re.sub(r"\s+", " ", remainder).strip()


def should_auto_fetch(text: str, urls: list[str] | tuple[str, ...]) -> bool:
    """True when the links are the point of the message, so reading needs no offer."""
    present = [u for u in urls if u]
    if not present:
        return False
    commentary = commentary_around(text, present)
    if not commentary:
        return True
    ceiling = MEDIA_COMMENTARY_MAX if has_media(present) else COMMENTARY_MAX
    if len(commentary) <= ceiling:
        return True
    return bool(READ_CUE_RE.search(commentary))


def link_offer_for(incoming: IncomingMessage) -> OutgoingMessage | None:
    """The offer to make about the links in this turn, or None to stay quiet.

    Returns a reply object, not an embed: the words are the runtime's, the chrome
    is the transport's. A surface with no buttons renders the same offer as prose
    (`OutgoingMessage.renderable_actions` returns nothing there) rather than
    posting a control it cannot draw — which is the act-offer defect that had six
    offers queued and none ever shown.
    """
    external = external_urls(incoming.urls)
    if not external:
        return None
    action = action_for_urls(external)
    if action is None:
        return None

    action = Action(
        key=action.key,
        label=action.label,
        payload={**action.payload, "urls": tuple(external)},
    )
    text = (
        f"{describe_urls(external)}\n\n"
        "This message is long — the link wasn't auto-read.\n"
        f"Use **{action.label}** if you want it. Ignoring this is fine."
    )
    return OutgoingMessage.answering(incoming, text, actions=(action,))
