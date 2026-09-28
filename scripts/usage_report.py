#!/usr/bin/env python3
"""What the cloud cost, per month and room, from the house usage ledger.

    python3 scripts/usage_report.py            # every month on record
    python3 scripts/usage_report.py 2026-10    # one month

Reads ``house/usage.jsonl`` (or ``$TURTLEOS_HOUSE_DIR``). Turns on a model with
no price on record are counted and shown as unpriced, not as zero.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud_fallback import house_dir  # noqa: E402


def summarise(rows: list[dict], month: str | None = None) -> list[str]:
    buckets: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"turns": 0, "usd": 0.0, "unpriced": 0, "in": 0, "cached": 0, "out": 0}
    )
    for row in rows:
        m = str(row.get("ts", ""))[:7]
        if month and m != month:
            continue
        b = buckets[(m, row.get("room", "?"), row.get("model", "?"))]
        b["turns"] += 1
        b["in"] += row.get("input_tokens", 0) + row.get("cache_creation_input_tokens", 0)
        b["cached"] += row.get("cache_read_input_tokens", 0)
        b["out"] += row.get("output_tokens", 0)
        if row.get("usd") is None:
            b["unpriced"] += 1
        else:
            b["usd"] += row["usd"]
    if not buckets:
        return ["No cloud usage on record" + (f" for {month}." if month else ".")]
    lines = []
    for m in sorted({k[0] for k in buckets}):
        total = sum(v["usd"] for k, v in buckets.items() if k[0] == m)
        lines.append(f"{m}: ${total:.2f}")
        for (bm, room, model), v in sorted(buckets.items()):
            if bm != m:
                continue
            extra = f" · {v['unpriced']} unpriced" if v["unpriced"] else ""
            lines.append(
                f"  #{room} · {model} · {v['turns']} turns · ${v['usd']:.2f}"
                f" · tokens in {v['in']:,} cached {v['cached']:,} out {v['out']:,}{extra}"
            )
    return lines


def main(argv: list[str]) -> int:
    path = house_dir() / "usage.jsonl"
    rows = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print("\n".join(summarise(rows, argv[0] if argv else None)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
