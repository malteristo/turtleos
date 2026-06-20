"""Magic-attuned legacy: Turtle prose → River act button extraction.

Not used on native eddies (TURTLE_SPEC §5.8 harness split). Retained for canary smoke,
unit tests, and optional `attunement: magic` strangle — not invoked from ``handle_dialogue``.
"""

from __future__ import annotations

import re

from cmd_dispatch import CONTEXTUAL_ACTION_COMMANDS, SENESCHAL_ACTION_COMMANDS

# Full legacy allowlist (includes lifecycle trio — native seneschal excludes those).
LEGACY_CONTEXTUAL_ACTION_COMMANDS = CONTEXTUAL_ACTION_COMMANDS

_CONTEXTUAL_COMMAND_RE = re.compile(r"`(![A-Za-z][\w-]*(?:\s+[^`]+)?)`")
_RECOMMENDATION_CUE_RE = re.compile(
    r"\b(?:want me to|should i|would you like (?:me to )?|i(?:'d| would) recommend(?: running)?|try(?: running)?|you could run)\b",
    re.IGNORECASE,
)
_PLAIN_COMMAND_RE = re.compile(
    r"!(?:eddy-check|readiness|diagnose|threads|checkpoint|release|dissolve|absorb|absorbed|forget|status|fetch|thread|flows|new)"
    r"(?:\s+[^.\n`»]+)?",
    re.IGNORECASE,
)


def contextual_action_label(command: str) -> str:
    body = command.strip().lstrip("!")
    cmd = body.split(None, 1)[0].lower() if body else ""
    rest = body.split(None, 1)[1] if " " in body else ""

    if cmd == "thread":
        match = re.search(r'"([^"]+)"', rest)
        topic = match.group(1) if match else rest.split("--", 1)[0].strip()
        return f"Create thread: {topic[:42]}" if topic else "Create thread"
    if cmd == "new":
        return "Open eddy"
    labels = {
        "status": "Show status",
        "diagnose": "Run diagnose",
        "checkpoint": "Checkpoint",
        "release": "Release session",
        "dissolve": "Dissolve eddy",
        "threads": "Show threads",
        "eddy-check": "Check eddies",
        "fetch": "Fetch link",
        "absorb": "Absorb thread",
        "absorbed": "Show absorbed",
        "forget": "Forget context",
        "readiness": "Assess readiness",
        "flows": "Flow menu",
    }
    return labels.get(cmd, f"Run !{cmd}")


def _recommendation_tail(reply: str) -> str:
    paragraphs = []
    for block in reply.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("-#"):
            continue
        paragraphs.append(block)
    if paragraphs:
        return paragraphs[-1]
    lines = [ln for ln in reply.splitlines() if ln.strip() and not ln.strip().startswith("-#")]
    return "\n".join(lines[-6:])


def trim_contextual_command(command: str) -> str:
    text = command.strip().rstrip("?.!,;:")
    text = text.lstrip("!")
    if not text:
        return "!"
    parts = text.split()
    cmd = parts[0].lower()
    if cmd == "thread":
        return "!" + " ".join(parts)
    if cmd in ("absorb", "fetch", "forget", "new") and len(parts) > 1:
        return "!" + " ".join(parts)
    return "!" + parts[0].lower()


def _append_contextual_action(
    actions: list,
    seen: set,
    command: str,
    *,
    allowed_commands: set[str] | frozenset[str] | None = None,
) -> None:
    command = trim_contextual_command(command)
    cmd = command.lstrip("!").split(None, 1)[0].lower()
    allow = allowed_commands if allowed_commands is not None else LEGACY_CONTEXTUAL_ACTION_COMMANDS
    if cmd not in allow:
        return
    key = command.lower()
    if key in seen:
        return
    seen.add(key)
    actions.append((contextual_action_label(command), command))


def extract_contextual_actions(
    reply: str,
    *,
    allowed_commands: set[str] | frozenset[str] | None = None,
) -> list[tuple[str, str]]:
    """Parse Turtle prose for backtick / recommendation ``!`` commands (legacy only)."""
    actions = []
    seen: set[str] = set()
    for match in _CONTEXTUAL_COMMAND_RE.finditer(reply):
        _append_contextual_action(
            actions, seen, match.group(1).strip(), allowed_commands=allowed_commands
        )

    tail = _recommendation_tail(reply)
    if _RECOMMENDATION_CUE_RE.search(tail):
        for match in _PLAIN_COMMAND_RE.finditer(tail):
            _append_contextual_action(
                actions, seen, match.group(0).strip(), allowed_commands=allowed_commands
            )

    if len(actions) > 3:
        return []
    return actions


def filter_seneschal_actions(
    actions: list[tuple[str, str]],
    history: list[dict],
) -> list[tuple[str, str]]:
    """Drop act buttons for commands River already ran recently in this eddy."""
    if not actions or not history:
        return actions
    recent = "\n".join(m.get("content", "") for m in history[-12:])
    completed: set[str] = set()
    for line in recent.splitlines():
        if line.startswith("[Act: !"):
            cmd = line.split("]", 1)[0].replace("[Act: !", "").strip().lower()
            if cmd:
                completed.add(cmd.split()[0])
    if not completed:
        return actions
    filtered = []
    for label, command in actions:
        cmd = command.lstrip("!").split(None, 1)[0].lower()
        if cmd in completed:
            continue
        filtered.append((label, command))
    return filtered


# Canary / test aliases matching former discord_bot private names
_extract_contextual_actions = extract_contextual_actions
_filter_seneschal_actions = filter_seneschal_actions
_contextual_action_label = contextual_action_label

__all__ = [
    "SENESCHAL_ACTION_COMMANDS",
    "LEGACY_CONTEXTUAL_ACTION_COMMANDS",
    "extract_contextual_actions",
    "filter_seneschal_actions",
    "_extract_contextual_actions",
    "_filter_seneschal_actions",
]
