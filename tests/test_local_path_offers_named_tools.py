"""The catalog is not the path.

`tools_for_channel` is what a room *may* see. `dialogue_turn.local_turn_tools`
is what a room on the local model *does* see. From 2026-09-17 to 2026-09-21
the health rules text said "call `recap_health_visit` so it sticks", the
catalog offered it, and the local path offered nothing — so a spoken
appointment recap on `#my-health` never wrote a line, and every test was
green because every test asked the catalog.

This file asks the path. For each attunement whose rules text names a tool,
the tool must be offered where that room's turns actually run — and the
check must be able to fail (positive control below).
"""
from __future__ import annotations

import re
import sys
import unittest
from unittest.mock import patch

import dialogue_turn
import tos_tools
from channel_primitives import resolve_primitive
from primitive_runtime import runtime_for
from state import THREAD_CONTEXTS


def _registry() -> dict:
    return {
        "mages": {
            "operator": {"practice_dir": "/tmp/operator"},
            "patient": {"practice_dir": "/tmp/patient"},
        },
        "spaces": {
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
            "3": {"primitive": "craft", "mage": "operator"},
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


def _names(tools) -> set[str]:
    return {
        (t.get("function") or {}).get("name") or t.get("name") or "" for t in tools
    }


ALL_TOOL_NAMES = _names(tos_tools.TOS_TOOLS)


def _tools_named_in(rules: str) -> set[str]:
    return {
        name
        for name in ALL_TOOL_NAMES
        if name and re.search(rf"\b{re.escape(name)}\b", rules)
    }


def _local_path(channel_id) -> tuple[set[str], int]:
    # No built memory: the memory pair is a consequence of `memory/topics.yaml`,
    # not of this test. The governed set must not depend on it.
    with patch.object(dialogue_turn, "local_memory_tools", return_value=[]):
        tools, rounds = dialogue_turn.local_turn_tools(channel_id)
    return _names(tools), rounds


class RulesTextNamesOnlyToolsThePathOffers(unittest.TestCase):
    """Class-level guard: a prompt may not promise a tool the loop hides."""

    def test_every_tool_a_rules_text_names_reaches_the_local_path(self) -> None:
        registry = _registry()
        checked = 0
        with patch("mage._MAGE_REGISTRY", registry):
            for channel_id in registry["channels"]:
                primitive = resolve_primitive(registry, channel_id)
                profile = runtime_for(primitive).prompt_profile
                rules = (THREAD_CONTEXTS.get(profile) or {}).get("rules") or ""
                named = _tools_named_in(rules)
                if not named:
                    continue
                catalog = _names(tos_tools.tools_for_channel(int(channel_id)))
                path, _ = _local_path(int(channel_id))
                for name in sorted(named):
                    with self.subTest(channel=channel_id, profile=profile, tool=name):
                        checked += 1
                        self.assertIn(name, catalog, "rules name a tool the catalog lacks")
                        self.assertIn(
                            name,
                            path,
                            f"{profile!r} rules promise {name}; the local path never offers it",
                        )
        self.assertGreater(checked, 0, "no rules text names any tool — the guard checked nothing")

    def test_the_guard_can_fail(self) -> None:
        """Positive control: hide the governed set and the health promise breaks."""
        registry = _registry()
        with patch("mage._MAGE_REGISTRY", registry), patch.object(
            tos_tools, "LOCAL_GOVERNED_CAPABILITIES", frozenset()
        ):
            path, _ = _local_path(6)
        self.assertNotIn("recap_health_visit", path)
        self.assertIn("recap_health_visit", _tools_named_in(THREAD_CONTEXTS["health"]["rules"]))


class HealthRoomOnTheLocalModel(unittest.TestCase):
    def test_health_local_path_offers_the_governed_record_tools(self) -> None:
        with patch("mage._MAGE_REGISTRY", _registry()):
            names, rounds = _local_path(6)
        for name in (
            "recap_health_visit",
            "save_health_observation",
            "keep_health_question",
            "prepare_health_appointment",
            "search_record_evidence",
        ):
            self.assertIn(name, names)
        self.assertEqual(rounds, dialogue_turn.LOCAL_TEAM_TOOL_ROUNDS)

    def test_health_local_path_keeps_the_sensitive_boundary(self) -> None:
        with patch("mage._MAGE_REGISTRY", _registry()):
            names, _ = _local_path(6)
        for name in ("search_practice_files", "read_practice_file", "run_turtleos_shell", "exa_search"):
            self.assertNotIn(name, names)

    def test_solo_health_matches_shared_health(self) -> None:
        with patch("mage._MAGE_REGISTRY", _registry()):
            solo, _ = _local_path(5)
            shared, _ = _local_path(6)
        self.assertEqual(solo, shared)

    def test_a_private_river_without_memory_stays_plain(self) -> None:
        """Negative control: the governed set is a room property, not a new default."""
        with patch("mage._MAGE_REGISTRY", _registry()):
            names, rounds = _local_path(1)
        self.assertEqual(names, set())
        self.assertEqual(rounds, dialogue_turn.LOCAL_MEMORY_TOOL_ROUNDS)

    def test_team_room_still_gets_its_team_tools(self) -> None:
        with patch("mage._MAGE_REGISTRY", _registry()):
            names, _ = _local_path(7)
        self.assertIn("read_team_state", names)
        self.assertNotIn("recap_health_visit", names)


if __name__ == "__main__":
    unittest.main()
