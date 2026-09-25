"""Cross-preset channel contract conformance matrix."""

from __future__ import annotations

import unittest

from channel_primitives import resolve_primitive
from primitive_runtime import runtime_for
from tos_tools import tools_for_channel


def _registry() -> dict:
    return {
        "mages": {
            "operator": {"practice_dir": "/tmp/operator"},
            "patient": {"practice_dir": "/tmp/patient"},
        },
        "spaces": {
            "shared": {"members": ["operator", "member"], "memory": "own_root"},
            "partners": {"members": ["operator", "member"], "memory": "own_root"},
            "health": {
                "members": ["operator", "patient"],
                "subject": "patient",
                "steward": "operator",
                "memory": "isolated",
            },
            "team": {
                "members": ["operator", "member"],
                "coordinator": "operator",
                "memory": "own_root",
            },
        },
        "channels": {
            "1": {"primitive": "private", "mage": "operator"},
            "2": {"primitive": "shared", "mage": "shared"},
            "3": {"primitive": "craft", "mage": "operator"},
            "4": {"primitive": "partnership", "mage": "partners"},
            "5": {
                "primitive": "health",
                "base": "solo",
                "mage": "patient",
                "subject": "patient",
            },
            "6": {"primitive": "health", "mage": "health"},
            "7": {"primitive": "team", "mage": "team"},
        },
    }


EXPECTED = {
    "private": ("solo", "river", "native", "personal_plus_shared", True, "standard_local"),
    "shared": ("shared", "river", "native", "own_root", True, "shared_local"),
    "craft": ("solo", "craft_intake", "craft", "personal_without_shared", False, "operator_local"),
    "partnership": ("shared", "river", "native", "own_root", True, "shared_local"),
    "health-solo": ("solo", "river", "health", "isolated", False, "sensitive_local"),
    "health-shared": ("shared", "river", "health", "isolated", False, "sensitive_local"),
    "team": ("shared", "river", "native", "own_root", True, "shared_local"),
}


class ChannelConformanceMatrixTests(unittest.TestCase):
    def test_all_presets_resolve_one_complete_runtime(self) -> None:
        registry = _registry()
        labels = {
            "1": "private",
            "2": "shared",
            "3": "craft",
            "4": "partnership",
            "5": "health-solo",
            "6": "health-shared",
            "7": "team",
        }
        for channel_id, label in labels.items():
            with self.subTest(preset=label):
                primitive = resolve_primitive(registry, channel_id)
                self.assertIsNotNone(primitive)
                runtime = runtime_for(primitive)
                self.assertIsNotNone(runtime)
                expected = EXPECTED[label]
                self.assertEqual(
                    (
                        primitive.base,
                        runtime.parent_handler,
                        runtime.prompt_profile,
                        primitive.memory_boundary,
                        runtime.lifecycle_bar,
                        primitive.data_policy,
                    ),
                    expected,
                )
                self.assertTrue(primitive.has("dialogue"))
                self.assertTrue(primitive.has("story"))
                self.assertTrue(primitive.eddy_parent)

    def test_authority_and_write_surfaces_are_preset_specific(self) -> None:
        registry = _registry()
        solo_health = resolve_primitive(registry, 5)
        shared_health = resolve_primitive(registry, 6)
        team = resolve_primitive(registry, 7)
        partnership = resolve_primitive(registry, 4)

        self.assertTrue(solo_health.has_role("patient", "subject"))
        self.assertFalse(solo_health.has_role("patient", "steward"))
        self.assertTrue(shared_health.has_role("patient", "subject"))
        self.assertTrue(shared_health.has_role("operator", "steward"))
        self.assertTrue(shared_health.has("governed_record"))
        self.assertTrue(team.has("shared_work"))
        self.assertTrue(team.has("goal_state"))
        self.assertTrue(team.has("member_lanes"))
        self.assertTrue(team.has_role("operator", "coordinator"))
        self.assertTrue(team.has("task_state"))
        self.assertTrue(team.has("decision_state"))
        self.assertTrue(team.has("artifact_state"))
        self.assertTrue(team.has("intersection_state"))
        self.assertFalse(partnership.has("shared_work"))

    def test_tool_surfaces_do_not_leak_between_presets(self) -> None:
        registry = _registry()
        from unittest.mock import patch

        with patch("mage._MAGE_REGISTRY", registry):
            health_names = {
                item["function"]["name"] for item in tools_for_channel(6)
            }
            craft_names = {
                item["function"]["name"] for item in tools_for_channel(3)
            }
            team_names = {
                item["function"]["name"] for item in tools_for_channel(7)
            }
        self.assertIn("search_record_evidence", health_names)
        self.assertNotIn("exa_search", health_names)
        self.assertIn("exa_search", craft_names)
        self.assertNotIn("search_record_evidence", team_names)
        self.assertNotIn("exa_search", team_names)
        self.assertIn("read_team_state", team_names)
        self.assertIn("set_my_team_front", team_names)
        self.assertIn("propose_team_decision", team_names)
        self.assertNotIn("read_team_state", health_names)
        self.assertNotIn("read_team_state", craft_names)


if __name__ == "__main__":
    unittest.main()
