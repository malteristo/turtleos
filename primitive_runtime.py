"""One runtime binding for every resolved channel contract.

The primitive catalogue declares policy. This module turns that policy into
runtime choices so callers do not grow domain-name conditionals.
"""

from __future__ import annotations

from dataclasses import dataclass

from channel_primitives import ChannelPrimitive


@dataclass(frozen=True)
class PrimitiveRuntime:
    prompt_profile: str
    parent_handler: str
    readiness_profile: str
    startup_hooks: tuple[str, ...]
    include_shared_memory: bool
    lifecycle_bar: bool


_PARENT_HANDLERS = {
    "ambient": "river",
    "governed_intake": "river",
    "operational": "river",
    "deterministic_intake": "craft_intake",
}


def runtime_for(primitive: ChannelPrimitive | None) -> PrimitiveRuntime | None:
    """Compile a validated primitive into its executable runtime policy."""
    if primitive is None:
        return None
    parent_handler = _PARENT_HANDLERS.get(primitive.parent_posture)
    if parent_handler is None:
        return None
    if primitive.has("shared_work"):
        readiness_profile = "team"
    elif primitive.data_policy == "sensitive_local":
        readiness_profile = "health"
    elif primitive.base == "shared":
        readiness_profile = "space"
    else:
        readiness_profile = "operator"
    startup_hooks = tuple(
        hook
        for capability, hook in (
            ("craft_readiness", "craft_readiness_views"),
            ("governed_record", "governed_record_views"),
            ("shared_work", "team_state_views"),
        )
        if primitive.has(capability)
    )
    return PrimitiveRuntime(
        prompt_profile=primitive.attunement,
        parent_handler=parent_handler,
        readiness_profile=readiness_profile,
        startup_hooks=startup_hooks,
        include_shared_memory=primitive.memory_boundary == "personal_plus_shared",
        lifecycle_bar=primitive.lifecycle_bar,
    )


def startup_hooks_for_registry(registry: dict) -> frozenset[str]:
    """Return the hooks required by all valid active channel contracts."""
    from channel_primitives import resolve_primitive

    hooks: set[str] = set()
    for channel_id in (registry.get("channels") or {}):
        runtime = runtime_for(resolve_primitive(registry, channel_id))
        if runtime is not None:
            hooks.update(runtime.startup_hooks)
    return frozenset(hooks)


def rehydrate_runtime_views(
    client, registry: dict, *, default_runtime_dir: str
) -> dict[str, int]:
    """Restore persistent UI selected by primitive capabilities."""
    restored: dict[str, int] = {}
    hooks = startup_hooks_for_registry(registry)
    if "craft_readiness_views" in hooks:
        from craft_ready_ui import rehydrate_ready_views

        restored["craft_readiness"] = rehydrate_ready_views(
            client, default_runtime_dir
        )
    if "governed_record_views" in hooks:
        from health_record_ui import register_pending_health_views

        restored["governed_record"] = register_pending_health_views(
            client, registry
        )
    if "team_state_views" in hooks:
        from team_state import rehydrate_registry_views

        restored["team_state"] = rehydrate_registry_views(registry)
    return restored


async def dispatch_parent_message(
    message,
    client,
    primitive: ChannelPrimitive | None,
    *,
    lock,
    craft_handler,
    river_handler,
    reconcile_bar,
) -> bool:
    """Run one parent-channel behavior from the resolved contract."""
    runtime = runtime_for(primitive)
    if primitive is None or runtime is None or primitive.parent_owner != "river":
        return False

    async with lock:
        if runtime.parent_handler == "craft_intake":
            # River sees the drop and chooses. Intake is an act, not the only mouth.
            await river_handler(message)
            reconcile_bar(message.channel, client)
        elif runtime.parent_handler == "river":
            await river_handler(message)
        else:  # pragma: no cover - runtime_for rejects unknown handlers
            return False
    return True
