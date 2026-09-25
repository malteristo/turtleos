"""Member lanes are readable by the team but advanced only by their owner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import thread_registry
from channel_primitives import resolve_primitive
from team_lanes import (
    bind_current_eddy,
    gate_lane_turn,
    get_current_eddy_id,
    lane_context,
    register_lane,
)


def primitive():
    return resolve_primitive(
        {
            "spaces": {
                "quest": {
                    "members": ["member-a", "member-b"],
                    "coordinator": "member-a",
                    "memory": "own_root",
                }
            },
            "channels": {"7": {"primitive": "team", "mage": "quest"}},
        },
        7,
    )


class TeamLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def tearDown(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def test_only_owner_advances_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            register_lane(
                11,
                activity_id="galactic-adventure",
                owner="member-a",
                character="Gargibald",
            )
            self.assertTrue(
                gate_lane_turn(11, actor="member-a", primitive=primitive()).allowed
            )
            refused = gate_lane_turn(11, actor="member-b", primitive=primitive())
            self.assertFalse(refused.allowed)
            self.assertEqual(refused.owner, "member-a")

    def test_context_names_siblings_without_copying_their_transcripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            thread_registry.register_thread(22, "Ossimandus")
            register_lane(11, activity_id="galactic-adventure", owner="member-a")
            register_lane(22, activity_id="galactic-adventure", owner="member-b")
            rendered = lane_context(11)
            self.assertIn("member-b", rendered.lower())
            self.assertIn("eddy 22", rendered)
            self.assertNotIn("transcript", rendered.lower())

    def test_current_eddy_carries_tool_provenance(self) -> None:
        bind_current_eddy(44)
        self.assertEqual(get_current_eddy_id(), 44)


if __name__ == "__main__":
    unittest.main()
