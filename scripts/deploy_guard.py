#!/usr/bin/env python3
"""Is anyone mid-conversation right now? Exit 0 if quiet, 1 if not.

A restart is not a pause. The bot identifies fresh, Discord does not replay what a
bot missed while it was down, and nothing here backfills practitioner messages on
startup — the only history reads at boot are for control panels and the thread
registry. So a message sent during the ten-to-twenty seconds a restart takes is not
delayed. **It is never seen and never answered**, and the person who sent it gets
silence with no explanation.

That is the whole cost of a deploy, and it is invisible to whoever deploys. This
script makes it visible, and `restart.sh` refuses on it.

The operator's rule, chosen 2026-08-15: *never interrupt a live conversation.* Deploys
wait for quiet. He is not asked for approval per restart — the point of the rule is
that the check replaces the question, because an approval that has to be requested
gets skipped under momentum, and four both-bot restarts on one "deploy now" is how
this rule came to be written.

WHAT COUNTS AS ACTIVITY, AND WHY THIS SIGNAL

`<practice-root>/dialogue/<channel_id>.json` is the conversation history, rewritten
whenever a turn is appended (`helpers.sync_history`). Its mtime is exactly "when this
conversation last moved." Background work — bar refreshes, pre-warms, the nightly
report — does not touch it.

`<practice-root>/dialogue/<channel_id>.lock` is a turn that is running. It holds
the process id. A living process is busy no matter how old the history file is.
A dead process is a turn that crashed, and it does not hold the restart.

`<practice-root>/story/eddies/*.lock` is a write in flight, which is the worst
possible moment to restart.

Deliberately **not** the logs. Most lines there carry no timestamp, and the ones that
do come from discord.py's own logger rather than from practitioner turns — a detector
built on them would fire on gateway chatter and miss real conversation, which is the
worst of both directions.

FAIL CLOSED

If no signal files can be found at all, this refuses rather than reporting quiet. A
detector that cannot see must not read as "all clear" — that is the shape that let a
pre-push gate allow every push while printing a reassuring line. Refusing costs one
flag; a dropped message cannot be recovered at all.

    python3 scripts/deploy_guard.py                 # default: 1 minute after the last turn
    python3 scripts/deploy_guard.py --quiet-minutes 20
    python3 scripts/deploy_guard.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# One minute. A restart takes about fifteen seconds, and a message sent in that
# gap is never seen. The minute is the gap after a turn ends: long enough to
# send the next line, and the window in which a restart is safe. A turn that is
# running is not this gap. It is a lock in dialogue/ whose process is alive, so
# the reply is not cut off because the previous turn is old.
#
# Half an hour was the earlier hold. Ten minutes cleared into a craft pitch on
# 2026-10-10, and thirty was chosen so a pause for thought would not look
# finished. On 2026-10-16 that hold was the thing in the way: the next idea
# waited out the deploy. The turn itself is the signal now. Thirty remains the
# ceiling past which the guard gets forced every time, which is not having one.
DEFAULT_QUIET_MINUTES = 1.0

WORKSHOPS = Path.home() / "workshops"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _in_flight(workshops: Path) -> tuple[str, str] | None:
    """A dialogue lock whose process is alive. A dead process is a crashed turn."""
    if not workshops.is_dir():
        return None
    for root in sorted(p for p in workshops.iterdir() if p.is_dir()):
        for path in sorted(root.glob("dialogue/*.lock")):
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                return root.name, f"turn in flight ({path.stem})"
            if _pid_alive(pid):
                return root.name, f"turn in flight ({path.stem})"
    return None


def _signals(workshops: Path) -> list[tuple[float, str, str]]:
    """(mtime, practice root, what it was) for everything that marks a live turn."""
    found: list[tuple[float, str, str]] = []
    if not workshops.is_dir():
        return found
    for root in sorted(p for p in workshops.iterdir() if p.is_dir()):
        for path in root.glob("dialogue/*.json"):
            found.append((path.stat().st_mtime, root.name, f"turn in {path.stem}"))
        # A lock means a write is happening as you read this.
        for path in root.glob("story/eddies/*.lock"):
            found.append((path.stat().st_mtime, root.name, f"write in flight ({path.stem})"))
    return found


def _describe(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s ago"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min ago"
    return f"{seconds / 3600:.1f} h ago"


def assess(quiet_minutes: float = DEFAULT_QUIET_MINUTES, workshops: Path = WORKSHOPS) -> dict:
    signals = _signals(workshops)
    now = time.time()
    flight = _in_flight(workshops)
    if flight is not None:
        root, what = flight
        return {
            "verdict": "busy",
            "quiet": False,
            "in_flight": True,
            "idle_seconds": 0,
            "threshold_seconds": quiet_minutes * 60,
            "last_activity": "now",
            "where": root,
            "what": what,
            "conversations_seen": len(signals),
        }

    if not signals:
        return {
            "verdict": "unknown",
            "quiet": False,
            "reason": (
                f"no conversation signal found under {workshops}. This check cannot "
                "see, which is not the same as nothing happening — refusing."
            ),
        }

    mtime, root, what = max(signals, key=lambda s: s[0])
    idle = now - mtime
    quiet = idle >= quiet_minutes * 60
    return {
        "verdict": "quiet" if quiet else "busy",
        "quiet": quiet,
        "idle_seconds": round(idle, 1),
        "threshold_seconds": quiet_minutes * 60,
        "last_activity": _describe(idle),
        "where": root,
        "what": what,
        "conversations_seen": len(signals),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet-minutes", type=float, default=DEFAULT_QUIET_MINUTES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = assess(args.quiet_minutes)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["quiet"] else 1

    if result["verdict"] == "unknown":
        print(f"CANNOT TELL — {result['reason']}")
        return 1

    gap = f"{args.quiet_minutes:.0f} min" if args.quiet_minutes >= 1 else f"{args.quiet_minutes * 60:.0f}s"
    if result["quiet"]:
        print(
            f"QUIET — last turn {result['last_activity']} "
            f"({result['where']}). {gap.capitalize()} has passed and no turn is running. Safe to restart."
        )
        return 0

    if result.get("in_flight"):
        print(
            f"BUSY — {result['what']} in {result['where']}.\n"
            f"The turn finishes, then {gap} is the safe gap.\n"
            f"A restart drops anything sent in the next ~15s, and it is never redelivered.\n"
            f"Wait for that, or restart anyway with:\n"
            f"    ./restart.sh --force"
        )
        return 1

    print(
        f"BUSY — last turn {result['last_activity']} in {result['where']} "
        f"({result['what']}).\n"
        f"The safe gap is {gap} after a turn. Talking holds the restart until that turn finishes.\n"
        f"A restart drops anything sent in the next ~15s, and it is never redelivered.\n"
        f"Wait for that gap, or restart anyway with:\n"
        f"    ./restart.sh --force"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
