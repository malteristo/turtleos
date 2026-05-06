from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - deployed turtleOS has PyYAML
    yaml = None


@dataclass(frozen=True)
class RuntimePaths:
    principal: str
    practice_dir: Path
    runtime_dir: Path
    workshop_root: Path | None
    native_runtime_dir: Path
    tasks_dir: Path
    audit_dir: Path

    @classmethod
    def for_principal(cls, principal: str = "kermit", registry_path: Path | None = None) -> "RuntimePaths":
        registry = _load_registry(registry_path or Path("mage_registry.yaml"))
        mages = registry.get("mages", {})
        if principal not in mages:
            raise KeyError(f"Unknown principal {principal!r}; known: {', '.join(sorted(mages))}")
        entry = mages[principal]
        practice_dir = _expand(entry["practice_dir"])
        runtime_dir = _expand(entry.get("runtime_dir", entry["practice_dir"]))
        workshop_root_value = entry.get("workshop_root")
        workshop_root = _expand(workshop_root_value) if workshop_root_value else None
        native_runtime_dir = runtime_dir / "native-runtime"
        return cls(
            principal=principal,
            practice_dir=practice_dir,
            runtime_dir=runtime_dir,
            workshop_root=workshop_root,
            native_runtime_dir=native_runtime_dir,
            tasks_dir=native_runtime_dir / "tasks",
            audit_dir=native_runtime_dir / "audit",
        )

    def ensure(self) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)


def _expand(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to read mage_registry.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Registry must be a mapping: {path}")
    return data
