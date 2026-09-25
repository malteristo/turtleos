"""Shared-work state preserves consent while keeping progress legible."""

from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from channel_primitives import resolve_primitive
from team_state import (
    decide_change,
    propose_change,
    read_state,
    rebuild_views,
    record_event,
)
from readiness import assess_team_primitive


def team_primitive():
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


class TeamGovernanceTests(unittest.TestCase):
    def test_team_readiness_measures_rebuildable_state_and_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = assess_team_primitive(tmp, team_primitive())
            self.assertIsNone(result["highest_leverage"])
            self.assertTrue((Path(tmp) / "team" / "current.md").is_file())
            self.assertIn("Team authority", result["summary"])

    def test_horizon_requires_every_member(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = team_primitive()
            proposal = propose_change(
                tmp,
                primitive=primitive,
                actor="member-a",
                kind="horizon",
                payload={"text": "Make an asynchronous adventure together"},
            )
            first = decide_change(
                tmp,
                proposal["proposal_id"],
                primitive=primitive,
                actor="member-a",
                decision="confirm",
            )
            self.assertEqual(first["status"], "pending")
            self.assertIsNone(read_state(tmp)["horizon"])

            second = decide_change(
                tmp,
                proposal["proposal_id"],
                primitive=primitive,
                actor="member-b",
                decision="confirm",
            )
            self.assertEqual(second["status"], "applied")
            self.assertEqual(
                read_state(tmp)["horizon"]["text"],
                "Make an asynchronous adventure together",
            )

    def test_member_owns_their_front_even_when_coordinator_proposes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = team_primitive()
            proposal = propose_change(
                tmp,
                primitive=primitive,
                actor="member-a",
                kind="member_front",
                payload={
                    "member": "member-b",
                    "relation": "explore",
                    "text": "Find Ossimandus's route out",
                },
                explicit=True,
            )
            self.assertEqual(proposal["status"], "pending")
            with self.assertRaises(PermissionError):
                decide_change(
                    tmp,
                    proposal["proposal_id"],
                    primitive=primitive,
                    actor="member-a",
                    decision="confirm",
                )

            applied = decide_change(
                tmp,
                proposal["proposal_id"],
                primitive=primitive,
                actor="member-b",
                decision="confirm",
            )
            self.assertEqual(applied["status"], "applied")
            self.assertEqual(
                read_state(tmp)["fronts"]["member-b"]["relation"], "explore"
            )

    def test_explicit_own_front_applies_without_assigning_a_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = team_primitive()
            result = propose_change(
                tmp,
                primitive=primitive,
                actor="member-a",
                kind="member_front",
                payload={
                    "member": "member-a",
                    "relation": "challenge",
                    "text": "Test whether the obvious route is real",
                },
                explicit=True,
            )
            self.assertEqual(result["status"], "applied")
            self.assertEqual(
                read_state(tmp)["fronts"]["member-a"]["relation"], "challenge"
            )

    def test_views_rebuild_deterministically_from_attributed_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = team_primitive()
            record_event(
                tmp,
                primitive=primitive,
                actor="member-b",
                kind="contribution",
                payload={"text": "Ossimandus ran for the gate"},
                source_eddy="22",
            )
            first = rebuild_views(tmp)
            first.pop("rebuilt_at")
            (Path(tmp) / "team" / "current.json").unlink()
            second = rebuild_views(tmp)
            second.pop("rebuilt_at")
            self.assertEqual(first, second)
            event = json.loads(
                (Path(tmp) / "team" / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(event["actor"], "member-b")
            self.assertEqual(event["source_eddy"], "22")

    def test_concurrent_events_serialize_without_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = team_primitive()

            def write(index: int) -> None:
                record_event(
                    tmp,
                    primitive=primitive,
                    actor="member-a" if index % 2 == 0 else "member-b",
                    kind="contribution",
                    payload={"text": f"contribution {index}"},
                    source_eddy=str(index),
                )

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(write, range(24)))
            lines = (
                Path(tmp) / "team" / "events.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 24)
            self.assertEqual(rebuild_views(tmp)["event_count"], 24)


if __name__ == "__main__":
    unittest.main()
