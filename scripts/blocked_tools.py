#!/usr/bin/env python3
"""Group policy-blocked tool calls by tool and reason.

``tool-actions.jsonl`` already records ``kind=blocked`` (see ``tool_result.py``).
This is the named query the 2026-09-04 craft watch asked for: how often a
lookup is refused, by which tool, for which reason — so a correct allowlist
refusal is distinguishable from a tool that cannot do the job.

Does not write. The ledger is the write path.

Usage:
    python3 scripts/blocked_tools.py                  # every runtime jsonl under ~/workshops
    python3 scripts/blocked_tools.py --path FILE
    python3 scripts/blocked_tools.py --json
    python3 scripts/blocked_tools.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

WORKSHOPS = Path.home() / "workshops"


def normalize_reason(summary: str) -> str:
    """Strip the wrappers the model sees; keep the policy sentence."""
    text = " ".join((summary or "").split())
    lower = text.lower()
    if lower.startswith("toolresult[blocked]"):
        text = text.split(":", 1)[-1].strip() if ":" in text else text
        lower = text.lower()
    if lower.startswith("shell command blocked:"):
        text = text.split(":", 1)[-1].strip()
    return text or "(no reason)"


def load_blocked(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") != "blocked":
                continue
            rows.append(rec)
    return rows


def group(rows: list[dict]) -> list[tuple[str, str, int]]:
    counts: Counter[tuple[str, str]] = Counter()
    for rec in rows:
        if rec.get("kind") != "blocked":
            continue
        tool = str(rec.get("tool") or "unknown")
        reason = normalize_reason(str(rec.get("summary") or ""))
        counts[(tool, reason)] += 1
    return sorted(
        ((tool, reason, n) for (tool, reason), n in counts.items()),
        key=lambda t: (-t[2], t[0], t[1]),
    )


def find_ledgers(workshops: Path) -> list[Path]:
    if not workshops.is_dir():
        return []
    return sorted(workshops.glob("*/tool-actions.jsonl"))


def render(groups: list[tuple[str, str, int]], *, sources: int, rows: int) -> str:
    if not groups:
        return f"blocked tools · 0 events · {sources} ledger(s)\n  (none)"
    lines = [f"blocked tools · {rows} events · {len(groups)} reason(s) · {sources} ledger(s)"]
    for tool, reason, n in groups:
        lines.append(f"  {n:>4}  {tool}  {reason}")
    return "\n".join(lines)


def self_test() -> None:
    """Positive control: a planted block is counted; a success is not."""
    payload = "\n".join(
        [
            json.dumps({"tool": "run_turtleos_shell", "kind": "blocked",
                        "summary": "Shell command blocked: command not allowed: sed"}),
            json.dumps({"tool": "run_turtleos_shell", "kind": "blocked",
                        "summary": "Shell command blocked: command not allowed: sed"}),
            json.dumps({"tool": "run_turtleos_shell", "kind": "blocked",
                        "summary": "Shell command blocked: command not allowed: rm"}),
            json.dumps({"tool": "exa_search", "kind": "success",
                        "summary": "Found 5 result(s)"}),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tool-actions.jsonl"
        path.write_text(payload + "\n", encoding="utf-8")
        rows = load_blocked([path])
        groups = group(rows)
        by_reason = {(t, r): n for t, r, n in groups}
        assert len(rows) == 3, rows
        assert by_reason[("run_turtleos_shell", "command not allowed: sed")] == 2
        assert by_reason[("run_turtleos_shell", "command not allowed: rm")] == 1
        assert all(t != "exa_search" for t, _, _ in groups)
        empty = group(load_blocked([Path(tmp) / "missing.jsonl"]))
        assert empty == []
        # The check can fail: a file of successes must not report a block.
        path.write_text(json.dumps({"tool": "x", "kind": "success", "summary": "ok"}) + "\n")
        assert group(load_blocked([path])) == []
    print("blocked_tools self-test: ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="one jsonl ledger")
    parser.add_argument("--workshops", type=Path, default=WORKSHOPS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    paths = [args.path] if args.path else find_ledgers(args.workshops)
    rows = load_blocked(paths)
    groups = group(rows)
    if args.json:
        print(json.dumps(
            [{"tool": t, "reason": r, "count": n} for t, r, n in groups],
            indent=2,
        ))
        return 0
    print(render(groups, sources=len(paths), rows=len(rows)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"blocked_tools self-test FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
