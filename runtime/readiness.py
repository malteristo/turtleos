from __future__ import annotations

import json
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .events import utc_now
from .paths import RuntimePaths
from .tasks import Task, TaskStore


SERVICE_LABELS = [
    "com.turtle.discord",
    "com.turtle.canary",
    "com.turtle.caddy",
]


@dataclass(frozen=True)
class RuntimeReadiness:
    paths: RuntimePaths

    def assess(self, *, limit: int = 10) -> dict[str, Any]:
        tasks = TaskStore(self.paths.tasks_dir).list()
        recent = tasks[:limit]
        recent_failures = [task for task in tasks if task.state == "failed"][:limit]
        services = self._services()
        models = self._models()
        artifacts = self._artifacts(recent)
        status = self._overall_status(services=services, models=models, artifacts=artifacts, recent_failures=recent_failures)
        return {
            "generated_at": utc_now(),
            "principal": self.paths.principal,
            "overall": status,
            "paths": {
                "practice_dir": str(self.paths.practice_dir),
                "runtime_dir": str(self.paths.runtime_dir),
                "native_runtime_dir": str(self.paths.native_runtime_dir),
            },
            "services": services,
            "models": models,
            "tasks": {
                "total": len(tasks),
                "recent_limit": limit,
                "recent": [summarize_task(task) for task in recent],
                "recent_failures": [summarize_task(task) for task in recent_failures],
            },
            "artifacts": artifacts,
        }

    def _services(self) -> dict[str, Any]:
        try:
            result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5, check=False)
        except Exception as exc:
            return {"status": "impaired", "error": str(exc), "labels": {}}

        labels: dict[str, dict[str, Any]] = {}
        for label in SERVICE_LABELS:
            labels[label] = {"status": "missing", "pid": None, "last_exit_code": None}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            label = parts[-1]
            if label not in labels:
                continue
            pid_raw, exit_raw = parts[0], parts[1]
            labels[label] = {
                "status": "running" if pid_raw != "-" else "loaded",
                "pid": _int_or_none(pid_raw),
                "last_exit_code": _int_or_none(exit_raw),
            }

        required = ["com.turtle.discord"]
        missing_required = [label for label in required if labels[label]["status"] == "missing"]
        return {
            "status": "impaired" if missing_required else "ready",
            "missing_required": missing_required,
            "labels": labels,
        }

    def _models(self) -> dict[str, Any]:
        url = "http://localhost:11434/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"status": "impaired", "ollama": "unreachable", "error": str(exc), "models": []}

        models = sorted(model.get("name", "") for model in payload.get("models", []) if model.get("name"))
        return {
            "status": "ready" if models else "degraded",
            "ollama": "reachable",
            "count": len(models),
            "models": models[:20],
        }

    def _artifacts(self, recent_tasks: list[Task]) -> dict[str, Any]:
        practice_dir = self.paths.practice_dir
        surfaces = {
            "practice_dir": summarize_path(practice_dir),
            "boom": summarize_path(practice_dir / "boom.md"),
            "sessions": summarize_directory(practice_dir / "sessions", "*.md"),
            "proposals": summarize_directory(practice_dir / "proposals", "*.md"),
        }
        visible_refs = []
        missing_refs = []
        for task in recent_tasks:
            for ref in task.artifact_refs:
                artifact_path = ref.get("artifact_path")
                if not artifact_path:
                    continue
                path = Path(artifact_path)
                entry = {"task_id": task.task_id, "artifact_path": str(path), "exists": path.exists()}
                if path.exists():
                    visible_refs.append(entry)
                else:
                    missing_refs.append(entry)
        status = "impaired" if not practice_dir.exists() or missing_refs else "ready"
        return {"status": status, "surfaces": surfaces, "visible_refs": visible_refs, "missing_refs": missing_refs}

    def _overall_status(
        self,
        *,
        services: dict[str, Any],
        models: dict[str, Any],
        artifacts: dict[str, Any],
        recent_failures: list[Task],
    ) -> str:
        if services.get("status") == "impaired" or artifacts.get("status") == "impaired":
            return "impaired"
        if models.get("status") == "impaired":
            return "impaired"
        if recent_failures:
            return "degraded"
        if models.get("status") == "degraded":
            return "degraded"
        return "ready"


def summarize_task(task: Task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "state": task.state,
        "kind": task.kind,
        "title": task.title,
        "updated_at": task.updated_at,
        "failure": task.failure,
        "artifact_refs": task.artifact_refs,
    }


def summarize_path(path: Path) -> dict[str, Any]:
    exists = path.exists()
    data: dict[str, Any] = {"path": str(path), "exists": exists}
    if exists:
        stat = path.stat()
        data.update({"size": stat.st_size, "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
    return data


def summarize_directory(path: Path, pattern: str) -> dict[str, Any]:
    data = summarize_path(path)
    if not path.is_dir():
        data.update({"count": 0, "latest": None})
        return data
    files = sorted(path.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    data.update({"count": len(files), "latest": str(files[0]) if files else None})
    return data


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
