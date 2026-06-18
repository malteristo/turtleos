"""Turtle-side opening after River flow intake handoff (split-bot safe)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flow_runner import strip_model_operational_lines
from helpers import split_message
from llm import chat_ollama
from mage import get_mage_name, get_pd, set_practice_context_for_channel
from prompts import get_native_eddy_prompt
from state import TURTLE_MODEL, active_sessions, dialogue_histories, get_channel_lock


_OPENING_SEED = (
    "[River intake complete. Intention and territory are in Flow Intake below — "
    "do not re-ask them or explain what Navigator is. Open with one grounded move: "
    "briefly reflect what you heard, then at most one question toward the next right thing.]"
)


def _handoff_dir() -> Path:
    from mage import get_runtime_dir

    path = Path(get_runtime_dir()) / "thread-state" / "intake-handoff"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_intake_handoff_request(thread_id: int, parent_id: int, flow_id: str) -> None:
    path = _handoff_dir() / f"{thread_id}.json"
    payload = {
        "thread_id": thread_id,
        "parent_id": parent_id,
        "flow_id": flow_id,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def pop_intake_handoff_request(thread_id: int) -> dict | None:
    path = _handoff_dir() / f"{thread_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    path.unlink(missing_ok=True)
    return data if isinstance(data, dict) else None


def list_intake_handoff_requests() -> list[dict]:
    out: list[dict] = []
    for path in sorted(_handoff_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("thread_id"):
            out.append(data)
    return out


async def deliver_flow_intake_opening(client, thread_id: int, parent_id: int, flow_id: str) -> bool:
    """Generate and post Turtle's opening after explicit Begin (Turtle process only)."""
    from commands import thread_configs
    from thread_registry import update_thread_activity

    set_practice_context_for_channel(parent_id)

    try:
        channel = client.get_channel(thread_id) or await client.fetch_channel(thread_id)
    except Exception as exc:
        print(f"Intake opening: could not fetch thread {thread_id}: {exc}")
        return False

    if not hasattr(channel, "send"):
        print(f"Intake opening: channel {thread_id} is not messageable")
        return False

    cfg = dict(thread_configs.get(thread_id) or {})
    cfg.update(
        {
            "context_type": flow_id,
            "intake_complete": True,
            "intake_skipped": False,
            "native_vanilla": True,
            "blank_eddy": False,
            "awaiting_title": False,
            "model": cfg.get("model") or TURTLE_MODEL,
            "use_api": False,
        }
    )
    thread_configs[thread_id] = cfg

    fake_message = SimpleNamespace(channel=channel)
    from discord_bot import _build_native_runtime_env

    system_prompt = _build_native_runtime_env(fake_message, cfg) + get_native_eddy_prompt(flow_id)
    messages = [{"role": "user", "content": _OPENING_SEED}]

    lock = get_channel_lock(thread_id)
    async with lock:
        async with channel.typing():
            try:
                reply = await chat_ollama(
                    system_prompt,
                    messages,
                    model=cfg["model"],
                    num_ctx=32768,
                    think=False,
                )
            except Exception as exc:
                print(f"Intake opening LLM failed: {type(exc).__name__}: {exc}")
                return False

        if not reply:
            reply = "I'm here — intake landed. What's the one thing that feels most stuck right now?"

        reply, stripped_ops = strip_model_operational_lines(reply)
        if stripped_ops:
            print(f"Intake opening stripped ops: {stripped_ops}")

        from flow_runner import apply_flow_reply_guard

        reply, guard_notes = apply_flow_reply_guard(reply, flow_id, [])
        if guard_notes:
            print(f"Intake opening flow guard: {guard_notes}")

        from eddy_spawn import post_flow_presence_if_needed

        await post_flow_presence_if_needed(channel, cfg)

        for chunk in split_message(reply):
            await channel.send(chunk)

        history = dialogue_histories.setdefault(thread_id, [])
        history.append({"role": "assistant", "content": reply})
        now = datetime.now(timezone.utc)
        active_sessions[thread_id] = {"started": now, "last_message": now, "closed": False}

        try:
            update_thread_activity(thread_id)
        except Exception:
            pass

    print(
        f"Intake opening delivered: {flow_id} thread={thread_id} "
        f"practitioner={get_mage_name()} pd={get_pd()}"
    )
    return True


async def process_intake_handoff(client, payload: dict) -> None:
    thread_id = int(payload["thread_id"])
    parent_id = int(payload["parent_id"])
    flow_id = str(payload["flow_id"])
    if pop_intake_handoff_request(thread_id) is None:
        return
    await asyncio.sleep(0.35)
    await deliver_flow_intake_opening(client, thread_id, parent_id, flow_id)


async def intake_handoff_watcher(client) -> None:
    """Poll for River-written handoff files (split-bot; River cannot call handle_dialogue)."""
    while True:
        try:
            for payload in list_intake_handoff_requests():
                await process_intake_handoff(client, payload)
        except Exception as exc:
            print(f"Intake handoff watcher error: {type(exc).__name__}: {exc}")
        await asyncio.sleep(0.5)


def start_intake_handoff_watcher(client) -> asyncio.Task:
    return asyncio.create_task(intake_handoff_watcher(client))
