"""Resolved channel contracts select runtime behavior without domain branches."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from channel_primitives import resolve_primitive
from primitive_runtime import (
    dispatch_parent_message,
    runtime_for,
    startup_hooks_for_registry,
)


def _registry(name: str, *, base: str | None = None) -> dict:
    entry = {"primitive": name, "mage": "room"}
    if base:
        entry["base"] = base
    registry = {
        "mages": {"room": {"practice_dir": "/tmp/room"}},
        "spaces": {
            "room": {
                "practice_dir": "/tmp/room",
                "members": ["one", "two"],
                "subject": "two",
                "steward": "one",
                "coordinator": "one",
                "memory": "isolated" if name == "health" else "own_root",
            }
        },
        "channels": {"42": entry},
    }
    if base == "solo":
        registry["channels"]["42"]["mage"] = "one"
        registry["mages"]["one"] = {"practice_dir": "/tmp/one"}
        registry["channels"]["42"]["subject"] = "one"
    return registry


class PrimitiveRuntimePolicyTests(unittest.TestCase):
    def test_policy_is_compiled_from_contract_fields(self) -> None:
        craft = resolve_primitive(_registry("craft"), 42)
        runtime = runtime_for(craft)
        self.assertEqual(runtime.parent_handler, "craft_intake")
        self.assertEqual(runtime.prompt_profile, "craft")
        self.assertFalse(runtime.include_shared_memory)
        self.assertFalse(runtime.lifecycle_bar)

        team = resolve_primitive(_registry("team"), 42)
        runtime = runtime_for(team)
        self.assertEqual(runtime.parent_handler, "river")
        self.assertEqual(runtime.readiness_profile, "team")
        self.assertTrue(runtime.lifecycle_bar)

    def test_startup_hooks_follow_capabilities(self) -> None:
        registry = _registry("health")
        self.assertEqual(
            startup_hooks_for_registry(registry),
            frozenset({"governed_record_views"}),
        )
        self.assertEqual(
            startup_hooks_for_registry(_registry("team")),
            frozenset({"team_state_views"}),
        )


class ParentDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_deterministic_intake_goes_to_river(self) -> None:
        primitive = resolve_primitive(_registry("craft"), 42)
        message = MagicMock()
        message.channel.id = 42
        lock = AsyncMock()
        lock.__aenter__.return_value = None
        lock.__aexit__.return_value = None
        intake = AsyncMock()
        river = AsyncMock()
        handled = await dispatch_parent_message(
            message,
            MagicMock(),
            primitive,
            lock=lock,
            craft_handler=intake,
            river_handler=river,
            reconcile_bar=MagicMock(),
        )
        self.assertTrue(handled)
        river.assert_awaited_once_with(message)
        intake.assert_not_awaited()

    async def test_operational_team_parent_uses_river(self) -> None:
        primitive = resolve_primitive(_registry("team"), 42)
        message = MagicMock()
        message.channel.id = 42
        lock = AsyncMock()
        lock.__aenter__.return_value = None
        lock.__aexit__.return_value = None
        river = AsyncMock()
        handled = await dispatch_parent_message(
            message,
            MagicMock(),
            primitive,
            lock=lock,
            craft_handler=AsyncMock(),
            river_handler=river,
            reconcile_bar=MagicMock(),
        )
        self.assertTrue(handled)
        river.assert_awaited_once_with(message)


if __name__ == "__main__":
    unittest.main()
