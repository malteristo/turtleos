"""Nightly error triage: new kinds of error, judged, reported only when they need someone.

Detection already existed: the 04:15 ops run (``core/log_watch``) marks error
classes absent from the previous night, and writes them into a report file. On
2026-09-27 it marked ``wrong_client:constructed`` new and nobody read it. This
adds what was missing — judgment and delivery — plus a pass over error lines
``log_watch`` has no class for (folded into signatures: timestamps, ids, names
and message text removed; only signatures never seen before count).

The model part is judgment a script cannot make: which open issue a new kind
belongs to, and whether a person is needed. The measure it serves is
time-to-detection (``docs/quality-measures.md``).
State and the running inbox live in ``house/`` (``error_triage.json``,
``error_triage.md``). A night with nothing new posts nothing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from cloud_fallback import house_dir

LOG_NAMES = ("discord.log", "river.log", "mcp.log")
MAX_READ_BYTES = 8 * 1024 * 1024
MAX_JUDGED = 10
RUN_HOURS = range(5, 8)  # after the 04:15 ops run has written its report

_ERROR = re.compile(
    r"(Traceback|Error\b|Exception\b|\bfailed\b|WRONG-CLIENT|rate limited|\bWARNING\b)", re.I
)
_STAMP = re.compile(r"^\[[^\]]*\]\s*")
_QUOTED = re.compile(r"(\"[^\"]*\"|'[^']*'|`[^`]*`|«[^»]*»)")
_NUMBER = re.compile(r"\d+")
_AFTER_COLON_TEXT = re.compile(r"(thread|channel|member|for|in)\s*:?\s+#?\S+", re.I)


def signature(line: str) -> str:
    """The shape of an error line — same bug, same signature, whatever the ids or names."""
    text = _STAMP.sub("", line.strip())
    text = _QUOTED.sub("Q", text)
    text = _AFTER_COLON_TEXT.sub(lambda m: m.group(1) + " X", text)
    text = _NUMBER.sub("N", text)
    head, sep, tail = text.partition(": ")
    if sep:
        # After the colon is the exception's message: its type word is the shape,
        # the rest is content (and sometimes a member's words).
        text = f"{head}: {(tail.split() or [''])[0]}"
    return re.sub(r"\s+", " ", text)[:140]


def _state_path() -> Path:
    return house_dir() / "error_triage.json"


def read_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(state: dict) -> None:
    house_dir(create=True)
    _state_path().write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")


def collect(log_dir: Path, state: dict) -> dict[str, dict]:
    """New error signatures since the last run: ``{sig: {"count", "log"}}``. Advances offsets."""
    offsets = state.setdefault("offsets", {})
    seen = state.setdefault("seen", {})
    found: dict[str, dict] = {}
    for name in LOG_NAMES:
        path = log_dir / name
        try:
            size = path.stat().st_size
        except OSError:
            continue
        start = int(offsets.get(name, 0))
        if size < start:
            start = 0
        start = max(start, size - MAX_READ_BYTES)
        with open(path, "rb") as fh:
            fh.seek(start)
            chunk = fh.read().decode("utf-8", errors="replace")
        offsets[name] = size
        for line in chunk.splitlines():
            if not _ERROR.search(line) or line.lstrip().startswith(("File ", "Traceback")):
                continue
            sig = signature(line)
            if sig in seen:
                seen[sig]["count"] = seen[sig].get("count", 0) + 1
                continue
            row = found.setdefault(sig, {"count": 0, "log": name})
            row["count"] += 1
    return found


_PROMPT = """You triage error signatures from a small self-hosted chat system's logs.
Each signature is a log line with ids, names and quoted text removed.
Open issues (filename — title):
{issues}

New signatures (id · count · log · signature):
{sigs}

Answer with JSON only: {{"items": [one object per id]}}, each object
{{"id": <id>, "class": "<3-6 words naming the kind of failure>", "issue": "<filename from the list or null>", "needs_person": <true|false>, "why": "<one short sentence>"}}
needs_person is true only when something is broken for a user or will get worse without a change; noise, expected retries and one-off network blips are false."""


def open_issues(issues_dir: Path) -> list[tuple[str, str]]:
    out = []
    for path in sorted(issues_dir.glob("[0-9]*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "## Done" in text:
            continue
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("#")), path.stem)
        out.append((path.name, title[:100]))
    return out


async def judge(new: dict[str, dict], issues: list[tuple[str, str]], ask: Callable[[str], Awaitable[str]]) -> list[dict]:
    """The model's reading of each new signature, validated. A bad answer is recorded as unjudged."""
    rows = sorted(new.items(), key=lambda kv: -kv[1]["count"])[:MAX_JUDGED]
    prompt = _PROMPT.format(
        issues="\n".join(f"- {n} — {t}" for n, t in issues) or "- (none)",
        sigs="\n".join(f"{i} · {r['count']} · {r['log']} · {s}" for i, (s, r) in enumerate(rows)),
    )
    names = {n for n, _ in issues}
    try:
        parsed = json.loads(await ask(prompt))
        if isinstance(parsed, dict):
            parsed = parsed.get("items") or parsed.get("results") or [parsed]
    except Exception:
        parsed = []
    by_id = {a.get("id"): a for a in parsed if isinstance(a, dict)}
    out = []
    for i, (sig, row) in enumerate(rows):
        a = by_id.get(i) or {}
        issue = a.get("issue") if a.get("issue") in names else None
        out.append({
            "signature": sig, "count": row["count"], "log": row["log"],
            "class": str(a.get("class") or "unjudged")[:60],
            "issue": issue,
            "needs_person": bool(a.get("needs_person")) if a else True,
            "why": str(a.get("why") or "the model gave no reading")[:160],
        })
    return out


def report_lines(judged: list[dict]) -> list[str]:
    lines = []
    for j in judged:
        if not j["needs_person"]:
            continue
        where = f"issue {j['issue']}" if j["issue"] else "no issue yet"
        lines.append(f"- **{j['class']}** ({j['count']}× in {j['log']}; {where}) — {j['why']}\n  `{j['signature']}`")
    return lines


def log_watch_new(report_json: Path, today: str) -> dict[str, dict]:
    """New, non-weather classes from tonight's ops report — the named kinds ``log_watch`` knows."""
    try:
        data = json.loads(report_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    classes = (data.get("log_watch") or {}).get("classes") or []
    return {
        f"log_watch {c['class_id']}": {"count": int(c.get("count") or 0), "log": "ops report"}
        for c in classes
        if c.get("new") and not c.get("weather") and str(c.get("last", "")) >= _day_before(today)
    }


def _day_before(today: str) -> str:
    from datetime import timedelta

    return (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


async def run_nightly(
    log_dir: Path,
    issues_dir: Path,
    ask: Callable[[str], Awaitable[str]],
    *,
    report_json: Path | None = None,
    now: datetime | None = None,
) -> str | None:
    """Once a night in ``RUN_HOURS``. Returns the report, or None when nothing needs a person."""
    now = now or datetime.now()
    state = read_state()
    today = now.strftime("%Y-%m-%d")
    if now.hour not in RUN_HOURS or state.get("last_night") == today:
        return None
    first_run = "offsets" not in state
    new = collect(log_dir, state)
    if report_json is not None and not first_run:
        new.update({k: v for k, v in log_watch_new(report_json, today).items() if k not in state["seen"]})
    judged = [] if first_run or not new else await judge(new, open_issues(issues_dir), ask)
    for sig, row in new.items():
        state["seen"][sig] = {"first": today, "count": row["count"]}
    for j in judged:
        state["seen"][j["signature"]].update(cls=j["class"], issue=j["issue"], needs_person=j["needs_person"])
    state["last_night"] = today
    _write_state(state)
    lines = report_lines(judged)
    if judged:
        inbox = house_dir(create=True) / "error_triage.md"
        with open(inbox, "a", encoding="utf-8") as fh:
            fh.write(f"\n## {today}\n\n" + "\n".join(
                f"- [{'person' if j['needs_person'] else 'noise'}] {j['class']} ({j['count']}×, {j['log']}; "
                f"{j['issue'] or 'no issue'}) — {j['why']}\n  `{j['signature']}`" for j in judged
            ) + "\n")
    if first_run:
        return f"Error triage started: {len(new)} kinds of error already in the logs recorded as known; from tonight only new ones are judged."
    if not lines:
        return None
    return "Error triage — new since last night, needs a look:\n" + "\n".join(lines)
