"""Spirit's tool for the coding-delegate key.

Offered in the owner's magic room, the same door as the workshop tools. It
says whether the key is set and asks the turn to post the modal button. It
never reads the key.
"""

from __future__ import annotations

from delegate_key import key_is_set, mark_offer, status

TOOL = "delegate_setup"
NOT_SET = (
    "The coding-delegate key is not set. A button will be posted: he pastes a "
    "spend-capped Anthropic key in a modal. Spirit will not see it. Not the house's key. "
    "Pi is not on the house yet, so no session can start."
)
ALREADY = (
    "The coding-delegate key is already set. A button will be posted if he wants to replace it. "
    "Spirit does not see the key. The driver is not in yet, so no session can start."
)


def _spec() -> dict:
    return {
        "type": "function",
        "function": {
            "name": TOOL,
            "description": (
                "Offer the coding-delegate key modal, or say that the key is already set. "
                "Spirit never sees the key. Call this when he asks to set up Pi, or before "
                "briefing a coding session."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }


def handles(name: str) -> bool:
    return name == TOOL


def channel_line(name: str) -> str | None:
    return "offered the coding-delegate key" if name == TOOL else None


def offered() -> bool:
    from workshop_tools import offered as workshop_offered

    return workshop_offered()


def tools_offered() -> list[dict]:
    return [_spec()] if offered() else []


def call(name: str, arguments: dict | None = None) -> str:
    if name != TOOL:
        return "That tool is not available."
    if not offered():
        return "Not in this room."
    mark_offer()
    # status() is read so a missing status file still reports "set" when the key file is there.
    _ = status()
    return ALREADY if key_is_set() else NOT_SET
