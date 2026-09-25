"""Galactic Adventure advances per member without losing shared state."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import thread_registry
from campaign_state import (
    extract_scene_boundary,
    rebuild_views,
    record_turn,
    render_context,
    seed_from_prologue,
)
from channel_primitives import resolve_primitive
from team_federation import unseen_sibling_events
from team_lanes import register_lane


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


class CampaignStateTests(unittest.TestCase):
    def setUp(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def tearDown(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def test_prologue_is_immutable_source_and_views_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seeded = seed_from_prologue(
                tmp,
                primitive=primitive(),
                activity_id="galactic-adventure",
                source_thread_id=99,
                checkpoint_text="# Original table\n\nOssimandus ran.",
                world="Lower Procrastination faces demolition.",
                current_scene="Purple static surrounds the village.",
                member_states={
                    "member-a": "Gargibald holds the Guide.",
                    "member-b": "Ossimandus is running with two books.",
                },
            )
            repeated = seed_from_prologue(
                tmp,
                primitive=primitive(),
                activity_id="galactic-adventure",
                source_thread_id=99,
                checkpoint_text="# Original table\n\nOssimandus ran.",
                world="Lower Procrastination faces demolition.",
                current_scene="Purple static surrounds the village.",
                member_states={
                    "member-a": "Gargibald holds the Guide.",
                    "member-b": "Ossimandus is running with two books.",
                },
            )
            self.assertEqual(
                repeated["event"]["event_id"], seeded["event"]["event_id"]
            )
            self.assertTrue(Path(seeded["source"]).is_file())
            (Path(tmp) / "campaign" / "state.json").unlink()
            (Path(tmp) / "campaign" / "world.md").unlink()
            rebuilt = rebuild_views(tmp)
            self.assertIn("demolition", rebuilt["world"])
            self.assertIn(
                "two books", rebuilt["members"]["member-b"]["state"]
            )
            self.assertIn(
                "Original table", Path(seeded["source"]).read_text(encoding="utf-8")
            )

    def test_two_lanes_advance_independently_and_cross_later(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            thread_registry.register_thread(22, "Ossimandus")
            register_lane(
                11,
                activity_id="galactic-adventure",
                owner="member-a",
                character="Gargibald",
            )
            register_lane(
                22,
                activity_id="galactic-adventure",
                owner="member-b",
                character="Ossimandus",
            )
            seed_from_prologue(
                tmp,
                primitive=primitive(),
                activity_id="galactic-adventure",
                source_thread_id=99,
                checkpoint_text="prologue",
                world="Lower Procrastination",
                current_scene="Five minutes remain",
                member_states={"member-a": "ready", "member-b": "ready"},
            )
            record_turn(
                tmp,
                primitive=primitive(),
                actor="member-a",
                thread_id=11,
                player_text="I inspect the Guide.",
                turtle_text="The Guide flashes an escape route.",
            )
            record_turn(
                tmp,
                primitive=primitive(),
                actor="member-b",
                thread_id=22,
                player_text="I sprint toward the gate.",
                turtle_text="The purple gate begins to open.",
            )
            events = [
                json.loads(line)
                for line in (Path(tmp) / "campaign" / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(
                [row["actor"] for row in events if row["kind"] == "campaign_turn"],
                ["member-a", "member-b"],
            )
            unseen = unseen_sibling_events(
                tmp,
                activity_id="galactic-adventure",
                lane_owner="member-a",
            )
            self.assertEqual(len(unseen), 1)
            self.assertEqual(unseen[0]["actor"], "member-b")
            member_context = render_context(
                tmp, thread_id=11, actor="member-a"
            )
            self.assertNotIn("two books", member_context)
            self.assertIn("ready", member_context)

    def test_reducer_failure_keeps_raw_event_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            register_lane(11, activity_id="galactic-adventure", owner="member-a")

            def broken(_state, _event):
                raise RuntimeError("bad reduction")

            result = record_turn(
                tmp,
                primitive=primitive(),
                actor="member-a",
                thread_id=11,
                player_text="I move.",
                turtle_text="The world answers.",
                semantic_reducer=broken,
            )
            self.assertEqual(result["reducer_status"], "pending")
            self.assertTrue((Path(tmp) / "campaign" / "events.jsonl").is_file())
            self.assertTrue(
                (Path(tmp) / "campaign" / "reducer-failures.jsonl").is_file()
            )

    def test_scene_boundary_marker_is_hidden_and_reconciles_shared_scene(self) -> None:
        clean, scene = extract_scene_boundary(
            "The gate closes behind you.\n\n"
            "[[campaign-scene: Both paths now meet beyond the purple gate.]]"
        )
        self.assertEqual(clean, "The gate closes behind you.")
        self.assertEqual(scene, "Both paths now meet beyond the purple gate.")

        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            register_lane(11, activity_id="galactic-adventure", owner="member-a")
            result = record_turn(
                tmp,
                primitive=primitive(),
                actor="member-a",
                thread_id=11,
                player_text="I cross.",
                turtle_text=clean,
                scene_boundary=scene,
            )
            self.assertEqual(result["state"]["current_scene"], scene)


if __name__ == "__main__":
    unittest.main()
