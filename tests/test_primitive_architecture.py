"""A new practice preset must not reopen domain-conditional dispatch."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_CONSUMERS = (
    "dialogue_turn.py",
    "practice_dispatch.py",
    "readiness.py",
    "discord_bot.py",
    "tos_tools.py",
    "eddy_lifecycle_bar.py",
    "team_state.py",
    "team_lanes.py",
    "team_federation.py",
    "campaign_state.py",
)
FORBIDDEN_HELPERS = (
    "uses_team_surface",
    "uses_partnership_surface",
    "uses_health_surface",
    "uses_craft_surface",
)


def conditional_offenders(text_by_path: dict[str, str]) -> list[str]:
    return [
        f"{path}: {helper}"
        for path, text in text_by_path.items()
        for helper in FORBIDDEN_HELPERS
        if helper in text
    ]


class PrimitiveArchitectureTests(unittest.TestCase):
    def test_hot_consumers_use_the_contract_not_domain_helpers(self) -> None:
        texts = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in CONTRACT_CONSUMERS
        }
        self.assertEqual(conditional_offenders(texts), [])

    def test_parent_posture_has_an_executable_consumer(self) -> None:
        runtime = (ROOT / "primitive_runtime.py").read_text(encoding="utf-8")
        self.assertIn("primitive.parent_posture", runtime)
        self.assertIn("primitive.has(capability)", runtime)

    def test_shared_prompt_runtime_cannot_read_compass(self) -> None:
        runtime = (ROOT / "dialogue_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn('"compass.md"', runtime)
        self.assertNotIn("personal compass", runtime.lower())

    def test_team_capabilities_have_runtime_consumers(self) -> None:
        catalogue = (ROOT / "channel_primitives.py").read_text(encoding="utf-8")
        consumers = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "team_state.py",
                "team_lanes.py",
                "team_federation.py",
                "tos_tools.py",
            )
        )
        for capability in (
            "goal_state",
            "member_lanes",
            "task_state",
            "decision_state",
            "artifact_state",
            "intersection_state",
        ):
            self.assertIn(f'"{capability}"', catalogue)
            self.assertIn(f'"{capability}"', consumers)

    def test_campaign_flow_uses_automatic_event_state(self) -> None:
        flow = (ROOT / "template" / "flows" / "dnd_dm.md").read_text(
            encoding="utf-8"
        )
        turn = (ROOT / "dialogue_turn.py").read_text(encoding="utf-8")
        self.assertIn("events.jsonl", flow)
        self.assertNotIn("write_practice_file", flow)
        self.assertIn("from campaign_state import extract_scene_boundary, record_turn", turn)
        self.assertIn("record_turn(", turn)

    def test_guard_detects_the_old_extension_shape(self) -> None:
        planted = {"dialogue_turn.py": "if uses_team_surface(parent_id): pass"}
        self.assertEqual(
            conditional_offenders(planted),
            ["dialogue_turn.py: uses_team_surface"],
        )


if __name__ == "__main__":
    unittest.main()
