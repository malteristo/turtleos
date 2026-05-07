#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from typing import Any

import yaml

from runtime.audit import AuditLog
from runtime.handoff import submit_practice_handoff
from runtime.model_probe import submit_model_probe
from runtime.paths import RuntimePaths
from runtime.policy import CapabilityRegistry, PolicyDenied
from runtime.readiness import RuntimeReadiness
from runtime.tasks import TaskStore


REQUIRED_SUCCESS_ACTIONS = [
    "event.received",
    "task.created",
    "task.running",
    "policy.checked",
    "capability.called",
    "artifact.validated",
    "task.completed",
]


class OfflineReadiness(RuntimeReadiness):
    def _services(self) -> dict[str, Any]:
        return {"status": "ready", "missing_required": [], "labels": {"offline-smoke": {"status": "stubbed"}}}

    def _models(self) -> dict[str, Any]:
        return {"status": "ready", "ollama": "stubbed", "count": 1, "models": ["offline-smoke"]}


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="turtle-native-smoke-"))
    try:
        registry = make_registry(root)
        paths = RuntimePaths.for_principal("smoke", registry_path=registry)
        success_task = assert_success_handoff(paths, registry)
        failed_task = assert_failed_handoff(paths, registry)
        probe_task = assert_model_probe(paths, registry)
        assert_policy_root(paths)
        readiness = OfflineReadiness(paths).assess(limit=10)
        assert readiness["overall"] == "degraded", readiness
        assert readiness["tasks"]["total"] == 3, readiness
        assert len(readiness["tasks"]["recent_failures"]) == 1, readiness
        assert readiness["artifacts"]["status"] == "ready", readiness
        print(json.dumps({
            "status": "passed",
            "root": str(root),
            "success_task": success_task.task_id,
            "failed_task": failed_task.task_id,
            "probe_task": probe_task.task_id,
            "readiness": readiness["overall"],
        }, indent=2, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def make_registry(root: Path) -> Path:
    practice_dir = root / "practice"
    runtime_dir = root / "runtime"
    practice_dir.mkdir(parents=True)
    (practice_dir / "sessions").mkdir()
    (practice_dir / "proposals").mkdir()
    (practice_dir / "boom.md").write_text("# Boom\n", encoding="utf-8")
    registry = root / "mage_registry.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "mages": {
                    "smoke": {
                        "practice_dir": str(practice_dir),
                        "runtime_dir": str(runtime_dir),
                        "workshop_root": str(root),
                    }
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry


def assert_success_handoff(paths: RuntimePaths, registry: Path):
    task = submit_practice_handoff(
        principal="smoke",
        artifact="proposal",
        title="Smoke Success",
        body="The isolated native runtime smoke suite wrote this proposal.",
        source="smoke-suite",
        interface="script",
        registry_path=registry,
    )
    assert task.state == "completed", task.to_dict()
    assert task.artifact_refs, task.to_dict()
    artifact_path = Path(task.artifact_refs[0]["artifact_path"])
    assert artifact_path.exists(), artifact_path
    assert artifact_path.read_text(encoding="utf-8").startswith("# Proposal - Smoke Success")
    actions = [record["action"] for record in AuditLog(paths.audit_dir).records_for_task(task.task_id)]
    missing = [action for action in REQUIRED_SUCCESS_ACTIONS if action not in actions]
    assert not missing, {"missing": missing, "actions": actions}
    return task


def assert_failed_handoff(paths: RuntimePaths, registry: Path):
    try:
        submit_practice_handoff(
            principal="smoke",
            artifact="escape",
            title="Smoke Failure",
            body="This should fail before capability execution.",
            source="smoke-suite",
            interface="script",
            registry_path=registry,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid artifact unexpectedly succeeded")

    tasks = TaskStore(paths.tasks_dir).list()
    failed = next(task for task in tasks if task.title == "Smoke Failure")
    assert failed.state == "failed", failed.to_dict()
    actions = [record["action"] for record in AuditLog(paths.audit_dir).records_for_task(failed.task_id)]
    assert "task.failed" in actions, actions
    return failed


def assert_model_probe(paths: RuntimePaths, registry: Path):
    task = submit_model_probe(
        principal="smoke",
        title="Smoke Model Probe",
        prompt="What is one invariant a persistent practice partner should preserve?",
        context="Offline smoke context.",
        providers=["stub:alpha", "stub:beta"],
        source="smoke-suite",
        interface="script",
        registry_path=registry,
    )
    assert task.state == "completed", task.to_dict()
    assert task.artifact_refs, task.to_dict()
    artifact_path = Path(task.artifact_refs[0]["artifact_path"])
    assert artifact_path.exists(), artifact_path
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["comparison"]["successful_count"] == 2, artifact
    actions = [record["action"] for record in AuditLog(paths.audit_dir).records_for_task(task.task_id)]
    assert actions.count("model.provider.completed") == 2, actions
    assert "artifact.validated" in actions, actions
    return task


def assert_policy_root(paths: RuntimePaths) -> None:
    registry = CapabilityRegistry.default(paths)
    ok = registry.validate_artifact_path(
        capability_id="practice.write_proposal",
        artifact_path=str(paths.practice_dir / "proposals" / "ok.md"),
    )
    assert ok["status"] == "ok", ok
    try:
        registry.validate_artifact_path(capability_id="practice.write_proposal", artifact_path="/tmp/escaped.md")
    except PolicyDenied:
        return
    raise AssertionError("escaped artifact path unexpectedly accepted")


if __name__ == "__main__":
    raise SystemExit(main())
