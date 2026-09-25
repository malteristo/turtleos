"""Sibling activity reaches member lanes as bounded attributed candidates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import thread_registry
from channel_primitives import resolve_primitive
from team_federation import (
    mark_offered_delivered,
    record_activity_event,
    render_intersections,
    unseen_sibling_events,
)
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


class FederationTests(unittest.TestCase):
    def setUp(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def tearDown(self) -> None:
        thread_registry.clear_registry_cache_for_tests()

    def test_sibling_summary_is_delivered_once_without_transcript_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "thread_registry._registry_path",
            return_value=Path(tmp) / "registry.yaml",
        ):
            thread_registry.register_thread(11, "Gargibald")
            thread_registry.register_thread(22, "Ossimandus")
            register_lane(11, activity_id="galactic", owner="member-a")
            register_lane(22, activity_id="galactic", owner="member-b")
            event = record_activity_event(
                tmp,
                primitive=primitive(),
                actor="member-b",
                activity_id="galactic",
                lane_id=22,
                summary="Ossimandus reached the purple gate",
                payload={"private_transcript": "must not render"},
            )

            rendered = render_intersections(
                tmp, thread_id=11, actor="member-a"
            )
            self.assertIn("Ossimandus reached the purple gate", rendered)
            self.assertNotIn("private_transcript", rendered)
            self.assertEqual(mark_offered_delivered(), 1)
            self.assertEqual(
                unseen_sibling_events(
                    tmp, activity_id="galactic", lane_owner="member-a"
                ),
                [],
            )
            self.assertEqual(event["actor"], "member-b")

    def test_member_does_not_receive_their_own_event_as_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record_activity_event(
                tmp,
                primitive=primitive(),
                actor="member-a",
                activity_id="galactic",
                lane_id=11,
                summary="Gargibald examined the notice",
            )
            self.assertEqual(
                unseen_sibling_events(
                    tmp, activity_id="galactic", lane_owner="member-a"
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
