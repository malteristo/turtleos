"""Turtle flow bootstrap — conversational opening when a flow loads in-eddy."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flow_runner import (
    FlowSpec,
    ensure_campaign_bootstrap,
    load_flow_spec,
    read_flow_intake_values,
    strip_model_operational_lines,
    apply_flow_reply_guard,
    _checkpoint_line,
    _flow_summary_line,
)
from helpers import split_message
from llm import chat_ollama
from mage import get_mage_name, get_pd, set_practice_context_for_channel
from prompts import get_native_eddy_prompt
from state import TURTLE_MODEL, active_sessions, dialogue_histories, get_channel_lock


def _bootstrap_dir(runtime_dir: str | None = None) -> Path:
    from mage import get_runtime_dir

    root = Path(runtime_dir or get_runtime_dir())
    path = root / "thread-state" / "flow-bootstrap"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _all_bootstrap_dirs() -> list[Path]:
    from mage import list_registered_runtime_dirs

    dirs: list[Path] = []
    seen: set[str] = set()
    for runtime_dir in list_registered_runtime_dirs():
        if runtime_dir in seen:
            continue
        seen.add(runtime_dir)
        bootstrap = Path(runtime_dir) / "thread-state" / "flow-bootstrap"
        bootstrap.mkdir(parents=True, exist_ok=True)
        dirs.append(bootstrap)
    if not dirs:
        dirs.append(_bootstrap_dir())
    return dirs


def write_flow_bootstrap_request(
    thread_id: int,
    parent_id: int,
    flow_id: str,
    *,
    lens: bool = False,
) -> None:
    path = _bootstrap_dir() / f"{thread_id}.json"
    payload = {
        "thread_id": thread_id,
        "parent_id": parent_id,
        "flow_id": flow_id,
        "lens": lens,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def pop_flow_bootstrap_request(
    thread_id: int,
    *,
    runtime_dir: str | None = None,
) -> dict | None:
    path = _bootstrap_dir(runtime_dir) / f"{thread_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    path.unlink(missing_ok=True)
    return data if isinstance(data, dict) else None


def list_flow_bootstrap_requests() -> list[dict]:
    out: list[dict] = []
    for bootstrap_dir in _all_bootstrap_dirs():
        runtime_dir = str(bootstrap_dir.parent.parent)
        for path in sorted(bootstrap_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("thread_id"):
                payload = dict(data)
                payload["_runtime_dir"] = runtime_dir
                out.append(payload)
    return out


def _intake_fields_complete(spec: FlowSpec, values: dict[str, str]) -> bool:
    if not spec.intake or not spec.intake.fields:
        return True
    for field in spec.intake.fields:
        if field.required and not (values.get(field.id) or "").strip():
            return False
    return True


def _next_intake_field(spec: FlowSpec, values: dict[str, str]):
    if not spec.intake:
        return None
    for field in spec.intake.fields:
        if not (values.get(field.id) or "").strip():
            return field
    return None


def format_history_excerpt(history: list[dict], max_chars: int = 4000) -> str:
    """Compact transcript for lens-load bootstrap."""
    lines: list[str] = []
    for msg in history[-24:]:
        role = msg.get("role") or "user"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = "Practitioner" if role == "user" else "Turtle"
        lines.append(f"{label}: {content[:900]}")
    text = "\n".join(lines)
    return text[:max_chars]


def build_bootstrap_user_seed(
    spec: FlowSpec,
    practice_dir: str | None = None,
    *,
    lens: bool = False,
    history_excerpt: str = "",
) -> str:
    """Instructions injected as the practitioner's implicit 'load flow' act."""
    pd = practice_dir or get_pd()
    lines = [
        "[Flow bootstrap — the practitioner loaded this guided flow in the eddy.]",
        f"Flow: {spec.title}",
    ]
    if lens:
        lines.extend([
            "[Lens load — apply this flow to the conversation already underway. "
            "Do NOT treat this as a fresh eddy.]",
            "Summarize what the thread already holds (briefly), then explain how "
            f"{spec.title} will work on *this* material.",
        ])
        if history_excerpt.strip():
            lines.extend([
                "",
                "Thread context so far:",
                history_excerpt.strip(),
            ])
    summary = _flow_summary_line(spec)
    if summary:
        lines.append(f"What this is for: {summary}")
    if spec.entry_contract:
        lines.append(f"Outcome shape: {spec.entry_contract}")

    lines.append(_checkpoint_line(spec, pd))

    intake_vals = read_flow_intake_values(spec, pd) if spec.intake else {}
    if spec.intake and spec.intake.fields:
        if _intake_fields_complete(spec, intake_vals):
            lines.extend([
                "Intake is already captured in Flow Intake below — do NOT re-ask those fields.",
                "Open briefly: acknowledge checkpoint if present, then continue from Territory / "
                "Next right thing per the flow body — not Phase 1 from scratch.",
            ])
        else:
            field = _next_intake_field(spec, intake_vals)
            if field:
                lines.extend([
                    "Conversational intake — max 2 sentences orienting, then exactly ONE question:",
                    f"Ask: {field.label}",
                ])
                if field.placeholder:
                    lines.append(f"Tone hint: {field.placeholder}")
                lines.append(
                    "Do NOT explain the flow as a program. Do NOT stack questions or numbered menus."
                )
    else:
        lines.append(
            "Orient in 2–3 short sentences. Invite them to bring what they have. Stay in flow voice."
        )

    lines.append("Keep the opening compact — they should talk more than you.")
    return "\n".join(lines)


async def start_flow_bootstrap(
    thread,
    flow_id: str,
    parent_id: int,
    bot_client,
    *,
    lens: bool = False,
) -> None:
    """River-side: add Turtle if needed and queue bootstrap delivery."""
    from commands import thread_configs
    from eddy_spawn import pop_awaiting_title, river_add_turtle_to_eddy

    set_practice_context_for_channel(parent_id)
    if not lens:
        pop_awaiting_title(thread.id, parent_id)

    cfg = thread_configs.get(thread.id) or {}
    if not cfg.get("presence_posted"):
        await river_add_turtle_to_eddy(thread)

    write_flow_bootstrap_request(thread.id, parent_id, flow_id, lens=lens)


async def deliver_flow_bootstrap(
    client,
    thread_id: int,
    parent_id: int,
    flow_id: str,
    *,
    lens: bool = False,
) -> bool:
    """Turtle speaks first after flow load — self-feed from checkpoint / intake state."""
    from commands import thread_configs
    from eddy_flow_library import post_flow_rename_offer, suggest_rename_title
    from eddy_spawn import post_flow_presence_if_needed
    from helpers import get_history
    from thread_registry import update_thread_activity

    set_practice_context_for_channel(parent_id)
    spec = load_flow_spec(flow_id)
    if not spec:
        return False

    ensure_campaign_bootstrap(spec, get_pd())
    try:
        from flow_runner import prepare_flow_reads

        prepare_flow_reads(spec, get_pd())
    except Exception as exc:
        print(f"Flow read prepare failed ({flow_id}): {type(exc).__name__}: {exc}")

    try:
        channel = client.get_channel(thread_id) or await client.fetch_channel(thread_id)
    except Exception as exc:
        print(f"Flow bootstrap: could not fetch thread {thread_id}: {exc}")
        return False

    if not hasattr(channel, "send"):
        return False

    cfg = dict(thread_configs.get(thread_id) or {})
    cfg.update(
        {
            "context_type": flow_id,
            "native_vanilla": True,
            "blank_eddy": False,
            "bootstrap_complete": True,
            "awaiting_title": False,
            "model": cfg.get("model") or TURTLE_MODEL,
            "use_api": False,
        }
    )
    thread_configs[thread_id] = cfg

    fake_message = SimpleNamespace(channel=channel)
    from discord_bot import _build_native_runtime_env

    system_prompt = _build_native_runtime_env(fake_message, cfg) + get_native_eddy_prompt(flow_id)
    history_excerpt = format_history_excerpt(get_history(thread_id)) if lens else ""
    seed = build_bootstrap_user_seed(
        spec,
        get_pd(),
        lens=lens,
        history_excerpt=history_excerpt,
    )
    messages = [{"role": "user", "content": seed}]

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
                print(f"Flow bootstrap LLM failed: {type(exc).__name__}: {exc}")
                return False

        if not reply:
            reply = (
                "Navigator is here to find one concrete next step — not a plan. "
                "What are you working toward right now?"
            )

        reply, stripped_ops = strip_model_operational_lines(reply)
        if stripped_ops:
            print(f"Flow bootstrap stripped ops: {stripped_ops}")

        reply, guard_notes = apply_flow_reply_guard(reply, flow_id, [])
        if guard_notes:
            print(f"Flow bootstrap flow guard: {guard_notes}")

        await post_flow_presence_if_needed(channel, cfg)
        cfg["presence_posted"] = True

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

        if lens:
            suggested = await suggest_rename_title(thread_id, history_excerpt)
            await post_flow_rename_offer(channel, thread_id, parent_id, suggested, client)

    print(
        f"Flow bootstrap delivered: {flow_id} thread={thread_id} "
        f"practitioner={get_mage_name()} pd={get_pd()}"
    )
    return True


async def process_flow_bootstrap(client, payload: dict) -> None:
    thread_id = int(payload["thread_id"])
    parent_id = int(payload["parent_id"])
    flow_id = str(payload["flow_id"])
    lens = bool(payload.get("lens"))
    runtime_dir = payload.get("_runtime_dir")
    if pop_flow_bootstrap_request(thread_id, runtime_dir=runtime_dir) is None:
        return
    set_practice_context_for_channel(parent_id)
    await asyncio.sleep(0.35)
    await deliver_flow_bootstrap(client, thread_id, parent_id, flow_id, lens=lens)


async def flow_bootstrap_watcher(client) -> None:
    """Poll for River-written bootstrap requests (split-bot)."""
    while True:
        try:
            for payload in list_flow_bootstrap_requests():
                await process_flow_bootstrap(client, payload)
        except Exception as exc:
            print(f"Flow bootstrap watcher error: {type(exc).__name__}: {exc}")
        await asyncio.sleep(0.5)


def start_flow_bootstrap_watcher(client) -> asyncio.Task:
    return asyncio.create_task(flow_bootstrap_watcher(client))
