"""A drop in the parent channel opens one eddy.

Boom: the eddy is the boom event. Boom Turtle answers in it. The channel
does not post a registration, and nothing is appended to the backlog.

Magic: the same drop opens a session. Spirit checks the message, and carries
it out when it is ready. Summon still opens a session with nothing in hand.

This module stays a leaf. Opening the eddy lives in the room that already
talks to Discord, so this file does not import it back.
"""

from __future__ import annotations


def boom_channel_retired(name: str | None) -> bool:
    """The thinking room has moved home. Another craft room keeps its intake."""
    return (name or "").strip().lower() in {"boom", "craft-turtle"}


MOVED_HOME = "A thought opens at home."


def drop_kind(primitive_name: str | None, *, display: bool) -> str | None:
    """'boom', 'session', or None when the parent should keep its other acts.

    A display (threads, waiting, a menu) wins. Gestures never reach here.
    """
    if display or not primitive_name:
        return None
    if primitive_name == "craft":
        return "boom"
    if primitive_name == "magic":
        return "session"
    return None


def eddy_title(text: str) -> str:
    """The sidebar name: his first line, or 'boom' when the drop has none.

    The same trimming as an eddy rename. It is written out here so this
    file does not import the module that opens eddies.
    """
    line = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line:
            break
    if len(line) >= 2 and line[0] == line[-1] and line[0] in "\"'":
        line = line[1:-1].strip()
    line = " ".join(line.split())[:100]
    return line or "boom"


def preface_for(anchor_text: str, forward: str) -> str:
    """Forwarded words that are not already the message the eddy hangs on.

    Empty when the drop is only a forward, or only a comment. The turn
    reads the message itself. This is the other half, posted into the eddy
    so Boom Turtle has it.
    """
    forward = (forward or "").strip()
    comment = (anchor_text or "").strip()
    if not forward or not comment or forward in comment:
        return ""
    return forward[:1800]


SESSION_OPENED = (
    "This session opened on his message in the channel. "
    "Check it against the workshop, then carry it out if it is ready."
)
