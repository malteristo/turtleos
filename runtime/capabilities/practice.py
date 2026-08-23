from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


ArtifactKind = Literal["note", "session", "proposal"]


@dataclass(frozen=True)
class CapabilityResult:
    capability_id: str
    status: str
    artifact_path: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "capability_id": self.capability_id,
            "status": self.status,
            "artifact_path": self.artifact_path,
            "message": self.message,
        }


class PracticeCapabilities:
    def __init__(self, practice_dir: Path):
        self.practice_dir = practice_dir

    def write_artifact(self, kind: ArtifactKind, title: str, body: str, task_id: str) -> CapabilityResult:
        if kind == "note":
            return self.append_note(body)
        if kind == "session":
            return self.write_session(title, body)
        if kind == "proposal":
            return self.write_proposal(title, body, task_id)
        raise ValueError(f"Unsupported practice artifact kind: {kind}")

    def append_note(self, body: str) -> CapabilityResult:
        notes_dir = self.practice_dir / "state" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = self._next_dated_path(notes_dir, suffix="md", prefix="handoff")
        entry = body.strip()
        if not entry.startswith("-"):
            entry = f"- {entry}"
        path.write_text(f"# Handoff note\n\n{entry}\n", encoding="utf-8")
        return CapabilityResult("practice.append_note", "ok", str(path), "note appended")

    def write_session(self, title: str, body: str) -> CapabilityResult:
        path = self._next_dated_path(self.practice_dir / "sessions", suffix="md")
        content = f"# {title.strip() or 'Session'}\n\n{body.strip()}\n"
        path.write_text(content, encoding="utf-8")
        return CapabilityResult("practice.write_session", "ok", str(path), "session artifact written")

    def write_proposal(self, title: str, body: str, task_id: str) -> CapabilityResult:
        slug = _slug(title) or task_id
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        directory = self.practice_dir / "proposals"
        directory.mkdir(parents=True, exist_ok=True)
        path = _unique_path(directory / f"{date}-{slug}.md")
        content = f"# Proposal - {title.strip() or task_id}\n\n{body.strip()}\n"
        path.write_text(content, encoding="utf-8")
        return CapabilityResult("practice.write_proposal", "ok", str(path), "proposal artifact written")

    def _next_dated_path(self, directory: Path, suffix: str, prefix: str | None = None) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stem = f"{date}-{prefix}" if prefix else date
        return _unique_path(directory / f"{stem}.{suffix}")


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _slug(value: str) -> str:
    chars = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60]
