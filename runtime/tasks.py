from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import Event, utc_now


@dataclass
class Task:
    kind: str
    title: str
    principal: str
    scope: str
    source_event_id: str
    correlation_id: str
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    state: str = "created"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    audit_refs: list[str] = field(default_factory=list)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None
    next_action: str | None = None

    @classmethod
    def from_event(cls, event: Event, kind: str, title: str) -> "Task":
        return cls(
            kind=kind,
            title=title,
            principal=event.principal,
            scope=event.scope,
            source_event_id=event.event_id,
            correlation_id=event.correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "title": self.title,
            "principal": self.principal,
            "scope": self.scope,
            "source_event_id": self.source_event_id,
            "correlation_id": self.correlation_id,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "artifact_refs": self.artifact_refs,
            "audit_refs": self.audit_refs,
            "checkpoint": self.checkpoint,
            "failure": self.failure,
            "next_action": self.next_action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            kind=data["kind"],
            title=data["title"],
            principal=data["principal"],
            scope=data["scope"],
            source_event_id=data["source_event_id"],
            correlation_id=data["correlation_id"],
            task_id=data["task_id"],
            state=data.get("state", "created"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            artifact_refs=data.get("artifact_refs", []),
            audit_refs=data.get("audit_refs", []),
            checkpoint=data.get("checkpoint", {}),
            failure=data.get("failure"),
            next_action=data.get("next_action"),
        )

    def mark_running(self) -> None:
        self.state = "running"
        self.updated_at = utc_now()

    def mark_completed(self, next_action: str | None = None) -> None:
        self.state = "completed"
        self.next_action = next_action
        self.updated_at = utc_now()

    def mark_failed(self, failure: str, next_action: str | None = None) -> None:
        self.state = "failed"
        self.failure = failure
        self.next_action = next_action
        self.updated_at = utc_now()

    def mark_cleared(self, reason: str) -> None:
        self.state = "cleared"
        self.next_action = None
        self.checkpoint["cleared"] = {"reason": reason, "cleared_at": utc_now()}
        self.updated_at = utc_now()


class TaskStore:
    def __init__(self, tasks_dir: Path):
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def save(self, task: Task) -> Task:
        self.path_for(task.task_id).write_text(
            json.dumps(task.to_dict(), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return task

    def load(self, task_id: str) -> Task:
        path = self.path_for(task_id)
        if not path.exists():
            raise FileNotFoundError(f"Task not found: {task_id}")
        return Task.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[Task]:
        tasks = []
        for path in sorted(self.tasks_dir.glob("task_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            tasks.append(Task.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return tasks
