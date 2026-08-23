"""Legacy shim — River modal intake replaced by flow_bootstrap (Slice 2).

Stale Begin buttons and old handoff files still route through bootstrap delivery.
"""

from __future__ import annotations

from flow_bootstrap import (
    deliver_flow_bootstrap,
    list_flow_bootstrap_requests,
    pop_flow_bootstrap_request,
    process_flow_bootstrap,
    start_flow_bootstrap_watcher,
    write_flow_bootstrap_request,
)


def _legacy_handoff_dir():
    from mage import get_runtime_dir
    from pathlib import Path

    path = Path(get_runtime_dir()) / "thread-state" / "intake-handoff"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_intake_handoff_request(thread_id: int, parent_id: int, flow_id: str) -> None:
    write_flow_bootstrap_request(thread_id, parent_id, flow_id)


def pop_intake_handoff_request(thread_id: int) -> dict | None:
    legacy = _legacy_handoff_dir() / f"{thread_id}.json"
    if legacy.exists():
        import json

        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        legacy.unlink(missing_ok=True)
        if isinstance(data, dict):
            return data
    return pop_flow_bootstrap_request(thread_id)


def list_intake_handoff_requests() -> list[dict]:
    import json

    out = list_flow_bootstrap_requests()
    seen = {int(p["thread_id"]) for p in out if p.get("thread_id")}
    for path in sorted(_legacy_handoff_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("thread_id"):
            tid = int(data["thread_id"])
            if tid not in seen:
                out.append(data)
    return out


async def deliver_flow_intake_opening(client, thread_id: int, parent_id: int, flow_id: str) -> bool:
    return await deliver_flow_bootstrap(client, thread_id, parent_id, flow_id)


async def process_intake_handoff(client, payload: dict) -> None:
    await process_flow_bootstrap(client, payload)


async def intake_handoff_watcher(client) -> None:
    from flow_bootstrap import flow_bootstrap_watcher

    await flow_bootstrap_watcher(client)


def start_intake_handoff_watcher(client):
    return start_flow_bootstrap_watcher(client)
