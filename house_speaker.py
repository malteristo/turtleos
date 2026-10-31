"""What the house speaker is allowed to say.

A spoken sentence is a turn in the home channel. The reply may have a longer
writing and a talk. The speaker says the talk. The writing above it stays
written.

Until a reply carries a talk, the reply itself is what would have been read,
so that is what may be spoken. A talk that is present and empty is not filled
in from the page. The speaker then says that the reply is written in the home
channel.

The door that would hand the sentence to the home channel is not started here.
`spoken` is the rule. `chat_response` is the body a local voice pipeline reads
back. Neither one posts anywhere.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

TALK_MARK = re.compile(r"(?m)^(?:\*\*)?The talk(?:\*\*)?[ \t]*$")

# The speaker only reads a talk the reply actually carries. The close asks
# for one. Until the house has that close, the page is what gets spoken.
TALK_CLOSE = """## The talk

End every reply with a blank line, then a line that is exactly `The talk`, then the part that will be read aloud. The writing above is the page. A numbered list on the page is for working on several things at once. The talk carries the relevant context of that page, so a person who only hears it can oversee the work. It adds nothing the page did not already say. If there is nothing to say aloud, `The talk` is the last line and nothing follows it. When the talk is waiting for an answer, its last sentence ends with a question mark. A finished answer does not."""

WRITTEN_IN_HOME = "The reply is in the home channel."
DID_NOT_ANSWER = "The home channel did not answer."
DID_NOT_HEAR = "I didn't hear a sentence."


def _without_asides(text: str) -> str:
    """Drop the small lines a reader can skip and a speaker must not say."""
    kept = [line for line in text.splitlines() if not line.strip().startswith("-#")]
    return "\n".join(kept).strip()


def spoken(reply: str | None) -> str | None:
    """The words the speaker may say.

    No talk mark: the reply itself, when it has words.
    A talk mark: only the words after the last mark. Empty means nothing,
    not the page above the mark.
    """
    text = (reply or "").strip()
    if not text:
        return None
    marks = list(TALK_MARK.finditer(text))
    if not marks:
        heard = _without_asides(text)
        return heard or None
    tip = _without_asides(text[marks[-1].end():])
    return tip or None


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts).strip()
    return ""


def sentence_of(body: dict) -> str:
    """The newest sentence in a chat body. Earlier turns are not re-sent."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        text = _text_of(message.get("content"))
        if text:
            return text
    return ""


def chat_response(sentence: str, reply: str | None, *, failed: bool = False) -> dict:
    """The body the voice pipeline reads. The page is not in it."""
    if failed:
        content = DID_NOT_ANSWER
    elif not sentence.strip():
        content = DID_NOT_HEAR
    else:
        content = spoken(reply) or WRITTEN_IN_HOME
    return {
        "model": "home",
        "message": {"role": "assistant", "content": content},
        "done": True,
    }


def answer_body(body: dict, turn: Callable[[str], str | None]) -> dict:
    """Run one sentence through `turn` and return what the speaker may say.

    `turn` receives the sentence and returns the full reply, page included.
    A failure becomes one spoken line and does not include the exception.
    """
    sentence = sentence_of(body)
    if not sentence:
        return chat_response(sentence, None)
    try:
        reply = turn(sentence)
    except Exception:
        return chat_response(sentence, None, failed=True)
    return chat_response(sentence, reply)


def loads_body(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
