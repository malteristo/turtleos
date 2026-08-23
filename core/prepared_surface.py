"""Render a practice artifact for reading *in* Discord, on a phone.

An `.md` attachment is the right way to hand someone a file to keep. It is the
wrong way to give them something to read. Measured on the two prepared eddies:
desktop Discord opens a formatted, syntax-coloured modal, while mobile offers no
preview at all — it downloads the file and hands it to a system viewer that
renders raw markdown as unwrapped monospace at roughly half the size of Discord's
own body text, and decodes it as Latin-1, so every em dash arrives as ``â€"``.
The artifact that was supposed to travel is the one surface that does not.

Discord's own renderer is the fix, and it is already on every device: headers,
bold, lists, quotes and subtext all render natively at readable size. So the
artifact goes out **as messages**, and the file rides along for keeping.

The two carriers serve different readers, which is why both stay:

- **Messages** are for the practitioner — rendered, legible, no download.
- **The file** is for Turtle, which reads it with practice-file tools, and for
  the desktop-and-archive case where a real file is what you want.

Splitting rules exist because the naive version is worse than the file. Chunks
break at section headings, never mid-sentence, and never mid-paragraph; a
sequence footer makes a delivered document distinguishable from someone talking
at length. Horizontal rules are dropped because Discord does not render ``---``
and it arrives as literal dashes.
"""

from __future__ import annotations

import re

# Discord's hard cap is 2000; leave room for the sequence footer.
DISCORD_LIMIT = 2000
BODY_LIMIT = 1900

_RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_HEADING = re.compile(r"^#{1,6} ")


def strip_horizontal_rules(text: str) -> str:
    """Drop separator lines — Discord renders ``---`` as literal dashes."""
    kept = [line for line in text.splitlines() if not _RULE.match(line)]
    return "\n".join(kept)


def split_into_blocks(text: str) -> list[str]:
    """Split at headings, keeping each heading attached to the body beneath it."""
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) and current:
            blocks.append("\n".join(current).strip("\n"))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip("\n"))
    return [b for b in blocks if b.strip()]


def _split_oversize(block: str, limit: int) -> list[str]:
    """A section too long for one message — break on paragraphs, then lines."""
    out: list[str] = []
    buf = ""
    units = block.split("\n\n")
    for unit in units:
        candidate = f"{buf}\n\n{unit}" if buf else unit
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            out.append(buf)
            buf = ""
        if len(unit) <= limit:
            buf = unit
            continue
        # A single paragraph over the limit: break on line ends, and only if
        # there are none, on whitespace. Never mid-word.
        remaining = unit
        while len(remaining) > limit:
            cut = remaining.rfind("\n", 0, limit)
            if cut <= 0:
                cut = remaining.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            out.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        buf = remaining
    if buf:
        out.append(buf)
    return out


def render_for_discord(text: str, *, limit: int = BODY_LIMIT) -> list[str]:
    """Artifact text → ordered message bodies, each safely under the cap."""
    blocks = split_into_blocks(strip_horizontal_rules(text).strip())
    chunks: list[str] = []
    buf = ""
    for block in blocks:
        if len(block) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_oversize(block, limit))
            continue
        candidate = f"{buf}\n\n{block}" if buf else block
        if len(candidate) <= limit:
            buf = candidate
        else:
            chunks.append(buf)
            buf = block
    if buf:
        chunks.append(buf)
    return chunks


def with_footers(chunks: list[str], rel_path: str) -> list[str]:
    """Mark the sequence so a delivered document is not mistaken for chatter."""
    name = rel_path.replace("\\", "/").rstrip("/").split("/")[-1]
    total = len(chunks)
    out = []
    for i, chunk in enumerate(chunks, start=1):
        footer = f"\n-# 📄 {name} · {i}/{total}"
        if i == total:
            footer += f" · file attached · workshop path `{rel_path}`"
        out.append(chunk.rstrip() + footer)
    return out


def render_surface_messages(text: str, rel_path: str) -> list[str]:
    """Full pipeline: artifact text → messages ready to send, in order."""
    messages = with_footers(render_for_discord(text), rel_path)
    over = [(i, len(m)) for i, m in enumerate(messages, start=1) if len(m) > DISCORD_LIMIT]
    if over:
        raise ValueError(f"Rendered chunks exceed Discord's limit: {over}")
    return messages
