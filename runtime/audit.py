from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import utc_now


@dataclass
class AuditRecord:
    action: str
    status: str
    task_id: str | None = None
    event_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    record_id: str = field(default_factory=lambda: f"aud_{uuid4().hex[:12]}")
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "event_id": self.event_id,
            "action": self.action,
            "status": self.status,
            "details": self.details,
        }


class AuditLog:
    def __init__(self, audit_dir: Path):
        self.audit_dir = audit_dir
        self.path = audit_dir / "audit.jsonl"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def append(self, record: AuditRecord) -> AuditRecord:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")
        return record

    def records_for_task(self, task_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("task_id") == task_id:
                records.append(data)
        return records
