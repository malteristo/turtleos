"""Proposal → confirmation → atomic mutation → append-only change record."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from governed_state import (
    append_jsonl,
    create_proposal,
    pending_proposals as _pending_proposals,
    transact_proposal,
)
from provenance_guard import validate_event


TERMINAL_DECISIONS = frozenset({"applied", "rejected"})


def propose(
    practice_dir: str | Path,
    *,
    primitive,
    actor: str,
    operations: list[dict],
    reason: str,
    explicit: bool = False,
) -> dict:
    """Create an immutable proposal. Explicit self-testimony may auto-apply."""
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema": 1,
        "primitive": primitive.name,
        "subject": primitive.subject,
        "actor": actor,
        "actor_role": primitive.role_for(actor),
        "reason": reason,
        "explicit": bool(explicit),
        "created_at": created_at,
        "operations": operations,
        "decision": "pending",
    }
    return create_proposal(practice_dir, "record", payload)


def decide(
    practice_dir: str | Path,
    proposal_id: str,
    *,
    actor: str,
    decision: str,
    handlers: dict[str, Callable[[Path, dict], dict | None]],
) -> dict:
    """Apply or reject exactly once under a practice-wide transaction lock."""
    if decision not in {"confirm", "reject"}:
        raise ValueError("decision must be confirm or reject")
    root = Path(practice_dir)

    def mutate(proposal: dict) -> dict:
        role = _role_for_decision(proposal, actor)
        if role is None:
            raise PermissionError("actor has no mutation authority")
        if decision == "confirm" and actor != proposal.get("subject"):
            raise PermissionError("only the record owner can confirm practice meaning")
        if decision == "reject":
            proposal["decision"] = "rejected"
            proposal["decided_by"] = actor
            proposal["decided_at"] = datetime.now(timezone.utc).isoformat()
            return proposal

        _validate_operations(root, proposal, actor)
        effects = []
        for operation in proposal.get("operations") or []:
            handler = handlers.get(str(operation.get("op") or ""))
            if handler is None:
                raise ValueError(f"unsupported operation: {operation.get('op')}")
            effects.append(handler(root, operation))
        proposal["decision"] = "applied"
        proposal["decided_by"] = actor
        proposal["decided_at"] = datetime.now(timezone.utc).isoformat()
        proposal["effects"] = effects
        return proposal

    return transact_proposal(
        root,
        "record",
        proposal_id,
        mutate=mutate,
        status_key="decision",
        terminal_statuses=TERMINAL_DECISIONS,
        log_relative=Path("record") / "changes.jsonl",
        log_event=_change_event,
    )


def pending_proposals(practice_dir: str | Path) -> list[dict]:
    return _pending_proposals(
        practice_dir,
        "record",
        status_key="decision",
    )


def _validate_operations(root: Path, proposal: dict, deciding_actor: str) -> None:
    subject = str(proposal.get("subject") or "")
    for operation in proposal.get("operations") or []:
        provenance = operation.get("provenance")
        if provenance:
            result = validate_event(
                provenance,
                subject=subject,
                source_exists=lambda source_id: (
                    root / "documents" / "manifests" / f"{source_id}.json"
                ).is_file(),
            )
            if not result.ok:
                details = "; ".join(item.detail for item in result.findings)
                raise ValueError(f"provenance rejected: {details}")
        if operation.get("op") == "append_observation":
            speaker = str((provenance or {}).get("actor") or proposal.get("actor") or "")
            kind = str((provenance or {}).get("kind") or "")
            if speaker != subject and kind != "member_report":
                raise PermissionError(
                    "a member cannot author the subject's observation; record it as member_report"
                )
        if proposal.get("actor_role") == "steward" and operation.get("op") in {
            "replace_claim",
            "append_observation",
        } and deciding_actor != subject:
            raise PermissionError("the steward cannot confirm subject-owned health meaning")


def _role_for_decision(proposal: dict, actor: str) -> str | None:
    if actor == proposal.get("subject"):
        return "subject"
    if actor == proposal.get("actor") and proposal.get("actor_role") == "member":
        # Members may withdraw their own pending proposal, but not confirm it.
        return "member"
    if actor == proposal.get("actor") and proposal.get("actor_role") == "steward":
        return "steward"
    return None


def _change_event(proposal: dict) -> dict:
    return {
        "proposal_id": proposal["proposal_id"],
        "decision": proposal["decision"],
        "actor": proposal.get("decided_by"),
        "at": proposal.get("decided_at"),
        "reason": proposal.get("reason"),
        "effects": proposal.get("effects") or [],
    }
