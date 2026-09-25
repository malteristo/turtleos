"""What a turn did to attune, said in one line — and when it did it.

A local turn on a 31B model can run three minutes. For all of that time
Discord shows a typing dot and nothing else, and on 2026-09-03 the operator,
who had just deployed the memory agent, read the dot as "Turtle got stuck".
It had not; it was reading an 8k-char transcript, carrying five topics of
room memory, and composing. None of that was visible, and none of it was
timed — the runtime's own log had no timestamps, so the duration had to be
read off Discord.

Two things live here, both pure so ``dialogue_turn`` stays thin:

* the **attunement trace** — the steps a turn took (links read, topics
  remembered, notes carried, tools used) rendered as a progress line while the
  turn runs long and as a closing line when it lands;
* a **timestamping stream** for the bots' stdout, so every log line carries
  the moment it was written. The turn duration is on the reply-sent line;
  the timestamp is on everything.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime

# After this many seconds of a running turn, the practitioner is told what the
# turn is doing. Below it a turn is simply a reply; a trace on every fast turn
# would be recital. Env-overridable so a slower or faster host can move it.
PROGRESS_AFTER_SECONDS = float(os.environ.get("TURN_PROGRESS_AFTER_SECONDS", "45"))

LOG_STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def fmt_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.0f} s" if seconds >= 10 else f"{seconds:.1f} s"
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes} m {rest:02d} s"


@dataclass
class AttunementSteps:
    """What went into the prompt before the model was asked anything."""

    links: int = 0
    link_chars: int = 0
    attachments: list[str] = field(default_factory=list)
    forwarded: bool = False
    dereferenced: int = 0
    topics: list[str] = field(default_factory=list)
    room_notes: int = 0
    home_plan: bool = False
    absorbed_threads: int = 0
    prompt_chars: int = 0

    def lines(self) -> list[str]:
        out: list[str] = []
        if self.links:
            noun = "link" if self.links == 1 else "links"
            chars = f" ({self.link_chars:,} chars)" if self.link_chars else ""
            out.append(f"read {self.links} {noun}{chars}")
        if self.attachments:
            out.append("read " + ", ".join(self.attachments[:3]))
        if self.forwarded:
            out.append("read the forwarded message")
        if self.dereferenced:
            out.append(f"read {self.dereferenced} linked Discord message(s)")
        if self.topics:
            shown = ", ".join(self.topics[:4])
            more = f" +{len(self.topics) - 4}" if len(self.topics) > 4 else ""
            out.append(f"remembering: {shown}{more}")
        if self.room_notes:
            out.append(f"{self.room_notes} recent note(s) of this room")
        if self.home_plan:
            out.append("the home plan")
        if self.absorbed_threads:
            out.append(f"{self.absorbed_threads} absorbed thread(s)")
        return out


# ─── The step card ───────────────────────────────────────────────────
#
# One message, edited as the turn works: what was read, what is remembered,
# each lookup as it happens, the model's own sentence before a lookup, and
# how long it has been composing. Discord has no token stream; it has edits,
# and a bot may edit its own message every second or two without being
# throttled. That is the whole modality — the card is the Cursor-style tool
# feed rendered with the primitive Discord actually offers (2026-09-03).

CARD_EDIT_INTERVAL_SECONDS = float(os.environ.get("TURN_CARD_EDIT_INTERVAL_SECONDS", "1.5"))
CARD_TICK_SECONDS = float(os.environ.get("TURN_CARD_TICK_SECONDS", "30"))
CARD_MAX_LINES = 14
CARD_PROSE_CHARS = 160
CARD_ASK_CHARS = 72
_MAX_RESULT_PREVIEW = 60


@dataclass
class Step:
    icon: str
    text: str


def attunement_step_list(steps: AttunementSteps) -> list[Step]:
    """The card the practitioner sees. Topics stay off it — Memory's mouth is the glance."""
    out: list[Step] = []
    for line in steps.lines():
        if line.startswith("remembering"):
            continue
        out.append(Step("✅", line))
    return out


def _clip_ask(text: str, limit: int = CARD_ASK_CHARS) -> str:
    line = " ".join((text or "").split())
    if len(line) <= limit:
        return line
    return line[: limit - 1].rstrip() + "…"


def _blocked_reason(result: str) -> str | None:
    """Human reason if the tool was refused by policy, else None.

    The model sees ``ToolResult[blocked] tool: <summary>``. The card must
    never show that wrapper — it is what made "blocked" unreadable on the
    first live watch (2026-09-04).
    """
    first = (result or "").strip().splitlines()[0] if result else ""
    if not first:
        return None
    rest = first
    if first.lower().startswith("toolresult[blocked]"):
        rest = first.split(":", 1)[-1].strip() if ":" in first else ""
    lower = rest.lower()
    if lower.startswith("shell command blocked:"):
        rest = rest.split(":", 1)[-1].strip()
    if first.lower().startswith("toolresult[blocked]") or lower.startswith("shell command blocked"):
        return _clip_ask(rest or "policy refused", limit=80)
    return None


def describe_tool(name: str, args: dict | None, result: str | None) -> Step:
    """A lookup as a person would say it, with what it found."""
    args = args or {}
    result = result or ""
    blocked = _blocked_reason(result)
    if name == "search_practice_files":
        q = _clip_ask(str(args.get("query") or "").strip())
        if blocked:
            return Step("🔎", f'searched notes for "{q}" — blocked: {blocked}')
        m = re.search(r"\*\*(\d+) snippet", result)
        found = f" → {m.group(1)} match(es)" if m else (" → nothing" if result.startswith("No matches") else "")
        return Step("🔎", f'searched notes for "{q}"{found}')
    if name == "read_practice_file":
        path = args.get("filename") or args.get("path") or "?"
        if blocked:
            return Step("📖", f"read `{path}` — blocked: {blocked}")
        return Step("📖", f"read `{path}`")
    if name == "list_practice_files":
        return Step("📂", f"listed `{args.get('directory') or '/'}`")
    if name == "offer_river_act":
        return Step("🪶", f"offered: {args.get('action') or 'an act'}")
    if name == "run_turtleos_shell":
        cmd = _clip_ask(str(args.get("command") or "").strip())
        shown = f"`{cmd}`" if cmd else "shell"
        if blocked:
            return Step("🔧", f"{shown} — blocked: {blocked}")
        return Step("🔧", shown)
    if name == "exa_search":
        q = _clip_ask(str(args.get("query") or "").strip())
        if blocked:
            return Step("🔎", f'searched web for "{q}" — blocked: {blocked}')
        m = re.search(r"Found (\d+) result", result)
        found = f" → {m.group(1)} result(s)" if m else (" → nothing" if "no result" in result.lower() else "")
        return Step("🔎", f'searched web for "{q}"{found}')
    if blocked:
        ask = _clip_ask(str(args.get("command") or args.get("query") or args.get("filename") or "").strip())
        suffix = f" `{ask}`" if ask else ""
        return Step("🔧", f"{name}{suffix} — blocked: {blocked}")
    preview = ""
    if result:
        first = result.strip().splitlines()[0]
        if not first.lower().startswith("toolresult["):
            preview = f" → {first[:_MAX_RESULT_PREVIEW]}"
    return Step("🔧", f"{name}{preview}")


def prose_step(text: str) -> Step | None:
    """The model's own sentence before a lookup — its stated intent for the step."""
    line = " ".join(text.split())
    if not line:
        return None
    if len(line) > CARD_PROSE_CHARS:
        line = line[: CARD_PROSE_CHARS - 1].rstrip() + "…"
    return Step("💭", f"*{line}*")


def render_card(
    steps: list[Step], elapsed: float, model: str, *, done: bool = False, composing: bool = True
) -> str:
    header = f"-# 🐢 {'attuned in' if done else 'working ·'} {fmt_duration(elapsed)}"
    body = list(steps)
    if len(body) > CARD_MAX_LINES:
        hidden = len(body) - CARD_MAX_LINES
        body = body[: CARD_MAX_LINES - 1] + [Step("…", f"{hidden} more step(s)")]
    lines = [header] + [f"-# {s.icon} {s.text}" for s in body]
    if not done and composing:
        lines.append(f"-# ✍️ {model} is composing…")
    elif done:
        lines.append(f"-# {model}")
    return "\n".join(lines)


def render_trace(steps: AttunementSteps, elapsed: float, model: str, tools: list[str] | None = None) -> str:
    """The line the progress notice becomes once the reply has landed."""
    parts = [f"attuned in {fmt_duration(elapsed)}", *steps.lines()]
    if tools:
        parts.append("looked up: " + ", ".join(_count_names(tools)))
    else:
        parts.append("no lookups")
    parts.append(model)
    return "-# 🐢 " + " · ".join(parts)


def render_log(label: str, steps: AttunementSteps, elapsed: float, model: str,
               reply_chars: int, tools: list[str] | None = None) -> str:
    """The reply-sent log line: duration first, then what the turn carried."""
    parts = [f"{reply_chars} chars in {fmt_duration(elapsed)}", f"prompt={steps.prompt_chars}", model]
    parts.extend(steps.lines())
    if tools:
        parts.append("looked up: " + ", ".join(_count_names(tools)))
    return f"Turtle reply sent [{label}]: " + " · ".join(parts)


def _count_names(tools: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for name in tools:
        counts[name] = counts.get(name, 0) + 1
    return [f"{n} ×{c}" if c > 1 else n for n, c in counts.items()]


def tool_names(tools_executed) -> list[str]:
    """Names out of whatever shape the tool loop returned (dicts, objects, strings)."""
    names: list[str] = []
    for t in tools_executed or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict):
            names.append(str(t.get("name") or t.get("tool") or "tool"))
        else:
            names.append(str(getattr(t, "name", None) or getattr(t, "tool", None) or "tool"))
    return names


class TimestampedStream:
    """Prefix every line written to a text stream with the local time.

    Installed over stdout in the bots' ``main()``. Partial writes (no trailing
    newline) are stamped once, at the start of the line; the next write on the
    same line is not stamped again.
    """

    def __init__(self, stream, fmt: str = LOG_STAMP_FORMAT, clock=None):
        self._stream = stream
        self._fmt = fmt
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._at_line_start = True

    def write(self, text: str) -> int:
        if not text:
            return 0
        stamp = f"[{self._clock().strftime(self._fmt)}] "
        out: list[str] = []
        for i, piece in enumerate(text.split("\n")):
            if i:
                out.append("\n")
                self._at_line_start = True
            if piece:
                if self._at_line_start:
                    out.append(stamp)
                    self._at_line_start = False
                out.append(piece)
        return self._stream.write("".join(out))

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install_timestamps() -> None:
    """Stamp the running process's stdout. Idempotent.

    stdout only: discord.py's own logging handler already stamps what it
    writes to stderr, and a second stamp on those lines would be noise.
    """
    if not isinstance(sys.stdout, TimestampedStream):
        sys.stdout = TimestampedStream(sys.stdout)
