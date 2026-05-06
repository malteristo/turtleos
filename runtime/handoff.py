from __future__ import annotations

from pathlib import Path
from typing import Literal

from .audit import AuditLog, AuditRecord
from .capabilities.practice import PracticeCapabilities
from .events import Event
from .paths import RuntimePaths
from .policy import CapabilityRegistry
from .tasks import Task, TaskStore


ArtifactKind = Literal["boom", "session", "proposal"]


def submit_practice_handoff(
    *,
    principal: str,
    artifact: ArtifactKind,
    title: str,
    body: str,
    source: str,
    interface: str,
    registry_path: Path | str = Path("mage_registry.yaml"),
    scope: str = "practice",
    trust_level: str = "operator",
    approved: bool = False,
) -> Task:
    """Create a durable task and execute one governed practice artifact capability."""
    paths = RuntimePaths.for_principal(principal, registry_path=Path(registry_path))
    paths.ensure()
    audit = AuditLog(paths.audit_dir)
    store = TaskStore(paths.tasks_dir)

    event = Event(
        source=source,
        interface=interface,
        principal=principal,
        scope=scope,
        trust_level=trust_level,
        payload={"artifact": artifact, "title": title, "body": body},
    )
    task = Task.from_event(event, kind="practice.handoff", title=title)
    task.checkpoint["event"] = event.to_dict()

    event_record = audit.append(
        AuditRecord("event.received", "ok", task_id=task.task_id, event_id=event.event_id, details=event.to_dict())
    )
    task.audit_refs.append(event_record.record_id)
    created_record = audit.append(AuditRecord("task.created", "ok", task_id=task.task_id, event_id=event.event_id))
    task.audit_refs.append(created_record.record_id)
    store.save(task)

    try:
        task.mark_running()
        running_record = audit.append(AuditRecord("task.running", "ok", task_id=task.task_id, event_id=event.event_id))
        task.audit_refs.append(running_record.record_id)
        store.save(task)

        capability_id = _capability_id_for_artifact(artifact)
        policy = CapabilityRegistry.default(paths)
        decision = policy.authorize(capability_id=capability_id, principal=principal, approved=approved)
        policy_record = audit.append(
            AuditRecord(
                "policy.checked",
                "ok",
                task_id=task.task_id,
                event_id=event.event_id,
                details=decision.to_dict(),
            )
        )
        task.audit_refs.append(policy_record.record_id)

        capability = PracticeCapabilities(paths.practice_dir)
        result = capability.write_artifact(artifact, title, body, task.task_id)
        validation = policy.validate_artifact_path(
            capability_id=result.capability_id,
            artifact_path=result.artifact_path,
        )
        task.artifact_refs.append(result.to_dict())
        capability_record = audit.append(
            AuditRecord(
                "capability.called",
                result.status,
                task_id=task.task_id,
                event_id=event.event_id,
                details=result.to_dict(),
            )
        )
        task.audit_refs.append(capability_record.record_id)
        artifact_record = audit.append(
            AuditRecord(
                "artifact.validated",
                validation["status"],
                task_id=task.task_id,
                event_id=event.event_id,
                details=validation,
            )
        )
        task.audit_refs.append(artifact_record.record_id)
        task.mark_completed(next_action="Inspect with `./turtle task show <task_id>` and `./turtle audit <task_id>`.")
        complete_record = audit.append(AuditRecord("task.completed", "ok", task_id=task.task_id, event_id=event.event_id))
        task.audit_refs.append(complete_record.record_id)
    except Exception as exc:
        task.mark_failed(str(exc), next_action="Inspect audit and repair the failing capability or policy.")
        failed_record = audit.append(
            AuditRecord("task.failed", "error", task_id=task.task_id, event_id=event.event_id, details={"error": str(exc)})
        )
        task.audit_refs.append(failed_record.record_id)
        store.save(task)
        raise

    store.save(task)
    return task


def _capability_id_for_artifact(artifact: str) -> str:
    if artifact == "boom":
        return "practice.append_boom"
    if artifact == "session":
        return "practice.write_session"
    if artifact == "proposal":
        return "practice.write_proposal"
    raise ValueError(f"Unsupported practice artifact kind: {artifact}")
