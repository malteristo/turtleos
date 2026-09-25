"""Audit lines land in the source's own root. The host keeps counts only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.atomic_io import file_lock

AUDIT_REL = Path("state") / "mcp_audit.jsonl"


def append(root: Path, *, grant: str, principal: str, operation: str, decision: str) -> None:
    if not root.is_dir():
        return
    path = root / AUDIT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "grant": grant,
            "principal": principal,
            "operation": operation,
            "decision": decision,
        },
        ensure_ascii=False,
    )
    with file_lock(path):
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
