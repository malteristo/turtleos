"""Policy-neutral primitives for governed, append-only practice state.

Domain adapters decide who may confirm and how an applied proposal changes
state.  This module owns the invariants shared by health records and team work:
immutable proposal identity, one transaction lock, idempotent terminal
decisions, and atomic event append.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable

from core.atomic_io import atomic_write_json, atomic_write_text, file_lock


def create_proposal(
    practice_dir: str | Path,
    namespace: str,
    payload: dict,
) -> dict:
    """Persist one content-addressed proposal without overwriting it."""
    root = Path(practice_dir)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    proposal = dict(payload)
    proposal["proposal_id"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:16]
    path = proposal_path(root, namespace, proposal["proposal_id"])
    if not path.exists():
        atomic_write_json(path, proposal, indent=2)
    return proposal


def transact_proposal(
    practice_dir: str | Path,
    namespace: str,
    proposal_id: str,
    *,
    mutate: Callable[[dict], dict],
    status_key: str,
    terminal_statuses: Iterable[str],
    log_relative: str | Path,
    log_event: Callable[[dict], dict] | None = None,
) -> dict:
    """Mutate a non-terminal proposal exactly once under a namespace lock."""
    root = Path(practice_dir)
    path = proposal_path(root, namespace, proposal_id)
    lock = root / namespace / "transaction"
    terminal = frozenset(terminal_statuses)
    with file_lock(lock):
        proposal = json.loads(path.read_text(encoding="utf-8"))
        if proposal.get(status_key) in terminal:
            return proposal
        before = proposal.get(status_key)
        proposal = mutate(dict(proposal))
        atomic_write_json(path, proposal, indent=2)
        if proposal.get(status_key) in terminal and proposal.get(status_key) != before:
            append_jsonl(
                root,
                log_relative,
                log_event(proposal) if log_event is not None else proposal,
            )
        return proposal


def pending_proposals(
    practice_dir: str | Path,
    namespace: str,
    *,
    status_key: str,
    pending_status: str = "pending",
) -> list[dict]:
    """Read valid pending proposals from one governed namespace."""
    rows = []
    directory = Path(practice_dir) / namespace / "proposals"
    for path in sorted(directory.glob("*.json")):
        try:
            proposal = json.loads(path.read_text(encoding="utf-8"))
            if proposal.get(status_key) == pending_status:
                rows.append(proposal)
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def append_jsonl(
    root: str | Path,
    relative: str | Path,
    event: dict,
) -> dict:
    """Append one JSON event atomically across River and Turtle processes."""
    base = Path(root)
    path = base / relative
    with file_lock(path):
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        payload = json.dumps(event, sort_keys=True, ensure_ascii=False)
        atomic_write_text(path, existing + payload + "\n")
    return {"path": str(relative), "event_id": event.get("event_id")}


def proposal_path(root: Path, namespace: str, proposal_id: str) -> Path:
    if not proposal_id or any(
        char not in "0123456789abcdef" for char in proposal_id
    ):
        raise ValueError("invalid proposal id")
    if not namespace or "/" in namespace or ".." in namespace:
        raise ValueError("invalid governed namespace")
    return root / namespace / "proposals" / f"{proposal_id}.json"
