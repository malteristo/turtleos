#!/usr/bin/env python3
"""Every craft eddy, its temperature, and — on request — what it actually says.

Two jobs, both platform-side because both need things only the platform has: the
thread registry, the readiness sidecar, and the bot token.

**`--json`** emits one row per craft eddy: name, last activity, readiness state,
target condition, temperature. This is the glance the design chapter asked for
(Q3), in the form Spirit can read from the workshop; the Discord render is a
separate slice.

**`--read THREAD_ID`** returns the thread's messages as text. This is the half
that was missing from the arrival's readiness evaluation and it is the point of
the whole command: until now Spirit judged an eddy from its *summary* — an eddy
note, a prepared surface, a handoff packet — never from the conversation. The
Mage's own test is whether the outcome is evident *from the content of the
conversation*, and that test was unrunnable from the workshop.

It reads over the **REST API, not the gateway**. A second `discord.Client` would
open a second gateway session for the same bot, which is a presence change and a
resource the running bot owns; `GET /channels/{id}/messages` is a read that costs
the live bot nothing. Read-only by construction — there is no write path in this
file, and that is deliberate for something an agent will run often.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CRAFT_PARENT_NAME = "craft-turtle"
DISCORD_API = "https://discord.com/api/v10"
READ_LIMIT_DEFAULT = 200


def _has_eddy_note(thread_id) -> bool:
    """Whether a written synthesis exists for this eddy.

    Deliberately a filesystem check and not a message-count threshold: the
    floor has moved before, and what a reader actually cares about is whether
    there is a note to read.
    """
    from mage import get_pd

    try:
        notes = Path(get_pd()) / "story" / "eddies"
        return any(notes.glob(f"{thread_id}-*.md"))
    except Exception:
        return True  # unknown is not the same as absent; don't cry wolf


def _rows() -> list[dict]:
    from core.craft_readiness import is_stale_ready, target_survived, temperature
    from core.prepared_eddies import load_sidecar
    from mage import get_runtime_dir
    from thread_registry import load_registry

    runtime = get_runtime_dir()
    readiness = (load_sidecar(runtime).get("readiness") or {})
    threads = load_registry().get("threads") or {}

    out: list[dict] = []
    for tid, entry in threads.items():
        if str(entry.get("parent_channel")) != CRAFT_PARENT_NAME:
            continue
        row = readiness.get(str(tid)) if isinstance(readiness.get(str(tid)), dict) else {}
        last = entry.get("last_activity")
        out.append(
            {
                "thread_id": str(tid),
                "name": entry.get("name") or "",
                "last_activity": last,
                "message_count": entry.get("message_count") or 0,
                "harvest_status": entry.get("harvest_status") or "",
                "state": row.get("state"),
                "target_condition": row.get("target_condition") or "",
                "gap": row.get("gap") or "",
                "spark": row.get("spark") or "",
                "suggested_spark": row.get("suggested_spark") or "",
                "spark_count": int(row.get("spark_count") or 0),
                "temperature": temperature(state=row.get("state"), last_practitioner_message_at=last),
                # Under the refine model a confirmed target is a waypoint, so a
                # ready eddy that kept talking is ordinary — and the recorded
                # sentence may be behind the conversation. The first one went
                # stale in seven minutes.
                "stale": is_stale_ready(row, last),
                "revisions": len(row.get("target_history") or []),
                "survived": target_survived(row) if row.get("target_history") else None,
                # An eddy under the reflection floor never gets a written note,
                # so a reader looking for one finds nothing and calls the eddy
                # empty. Two were sitting at `cold` on 2026-08-17 for exactly
                # this reason and both produced a usable target the moment
                # `--read` was pointed at them. The board should say which of
                # the two silences it is looking at.
                "no_note": not _has_eddy_note(tid),
            }
        )
    # Ready first, then by recency. A cooled eddy sorts last regardless: it has
    # already been answered, and the board is for deciding what is next.
    order = {"ready": 0, "hot": 1, "warm": 2, "cooling": 3, "cold": 4}
    out.sort(
        key=lambda r: (
            1 if r["harvest_status"] == "cooled" else 0,
            order.get(r["temperature"], 9),
            r["last_activity"] or "",
        )
    )
    return out


def _token() -> str:
    """Bot token from the environment the bot itself uses."""
    for key in ("DISCORD_BOT_TOKEN", "DISCORD_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value
    env = REPO / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() in ("DISCORD_BOT_TOKEN", "DISCORD_TOKEN") and value.strip():
                return value.strip().strip('"').strip("'")
    raise SystemExit("no bot token in environment or .env")


def read_thread(thread_id: str, limit: int = READ_LIMIT_DEFAULT) -> str:
    """The conversation, oldest first. Paginates because eddies run long."""
    import httpx

    headers = {"Authorization": f"Bot {_token()}"}
    collected: list[dict] = []
    before: str | None = None
    with httpx.Client(timeout=30.0, headers=headers) as http:
        meta = http.get(f"{DISCORD_API}/channels/{thread_id}")
        meta.raise_for_status()
        name = meta.json().get("name") or thread_id

        while len(collected) < limit:
            params = {"limit": min(100, limit - len(collected))}
            if before:
                params["before"] = before
            resp = http.get(f"{DISCORD_API}/channels/{thread_id}/messages", params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            collected.extend(batch)
            before = batch[-1]["id"]

    lines = [f"# {name}  ({len(collected)} messages)", ""]
    for msg in reversed(collected):
        author = (msg.get("author") or {}).get("global_name") or (msg.get("author") or {}).get(
            "username", "?"
        )
        stamp = (msg.get("timestamp") or "")[:16].replace("T", " ")
        content = (msg.get("content") or "").strip()
        for embed in msg.get("embeds") or []:
            title = embed.get("title") or ""
            desc = embed.get("description") or ""
            if title or desc:
                content = f"{content}\n[embed] {title}\n{desc}".strip()
        if not content:
            continue
        lines.append(f"**{author}** · {stamp}\n{content}\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="rows as JSON")
    parser.add_argument("--read", metavar="THREAD_ID", help="the conversation itself")
    parser.add_argument("--limit", type=int, default=READ_LIMIT_DEFAULT)
    args = parser.parse_args()

    if args.read:
        print(read_thread(args.read, args.limit))
        return 0

    rows = _rows()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    print(f"craft board · {len(rows)} eddies · {now}")
    for row in rows:
        flag = "COOLED " if row["harvest_status"] == "cooled" else ""
        print(f"  {row['temperature']:<8} {flag}{row['name'][:58]:<58} {row['thread_id']}")
        if row["target_condition"]:
            print(f"           → {row['target_condition']}")
        if row.get("no_note"):
            print("           ○ no note — quiet is not empty; read it directly (--read)")
        if row.get("stale"):
            print("           ⟳ the eddy moved after this was agreed — target may be behind")
        if row.get("revisions"):
            kept = "held its direction" if row.get("survived") else "changed direction"
            print(f"           ({row['revisions']} revision(s), {kept})")
        if row["gap"]:
            print(f"           ✗ {row['gap']}")
        if row.get("spark"):
            print(f"           ✦ sparked ×{row['spark_count']}: {row['spark'][:80]}")
        elif row.get("suggested_spark"):
            print(f"           · delta noted (not posted): {row['suggested_spark'][:76]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
