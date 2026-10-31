"""Five-state mapper — each name, and the priority that makes two facts one name."""

from __future__ import annotations

import unittest
from pathlib import Path

import eddy_five_state as fs


class EddyFiveStateTests(unittest.TestCase):
    def test_names_are_exactly_the_five(self) -> None:
        self.assertEqual(
            fs.FIVE_STATES, ("gone", "sealed", "kept", "resting", "live")
        )

    def test_empty_row_is_live(self) -> None:
        self.assertEqual(fs.eddy_five_state({}), "live")
        self.assertEqual(fs.eddy_five_state(None), "live")

    def test_dissolved_is_gone(self) -> None:
        self.assertEqual(
            fs.eddy_five_state({"harvest_status": "dissolved"}), "gone"
        )

    def test_locked_is_sealed(self) -> None:
        self.assertEqual(fs.eddy_five_state({"locked": True}), "sealed")
        self.assertEqual(fs.eddy_five_state({}, discord_locked=True), "sealed")

    def test_keep_or_home_is_kept(self) -> None:
        self.assertEqual(fs.eddy_five_state({"continuity": "keep"}), "kept")
        self.assertEqual(fs.eddy_five_state({}, is_home=True), "kept")

    def test_cooled_or_archived_is_resting(self) -> None:
        self.assertEqual(
            fs.eddy_five_state({"harvest_status": "cooled"}), "resting"
        )
        self.assertEqual(fs.eddy_five_state({}, discord_archived=True), "resting")

    def test_gone_beats_sealed_kept_and_resting(self) -> None:
        self.assertEqual(
            fs.eddy_five_state(
                {
                    "harvest_status": "dissolved",
                    "locked": True,
                    "continuity": "keep",
                },
                discord_archived=True,
                is_home=True,
            ),
            "gone",
        )

    def test_sealed_beats_kept_and_resting(self) -> None:
        self.assertEqual(
            fs.eddy_five_state(
                {"harvest_status": "cooled", "continuity": "keep", "locked": True},
                is_home=True,
            ),
            "sealed",
        )

    def test_kept_beats_resting(self) -> None:
        self.assertEqual(
            fs.eddy_five_state(
                {"harvest_status": "cooled", "continuity": "keep"}
            ),
            "kept",
        )


class DestRegisterTests(unittest.TestCase):
    def test_lifecycle_bar_register_names_the_mapping(self) -> None:
        text = Path("docs/ux/eddy-lifecycle-bar.md").read_text(encoding="utf-8")
        self.assertIn("## Five-state register", text)
        for name in fs.FIVE_STATES:
            self.assertIn(f"| **{name}**", text)
        self.assertIn("eddy_five_state", text)
        # Positive control: a dest that only lists the names is not a mapping.
        self.assertIn("harvest_status == dissolved", text)

    def test_system_state_dest_names_the_glance_rules(self) -> None:
        text = Path("docs/ux/system-state.md").read_text(encoding="utf-8")
        for phrase in (
            "One question per view",
            "Attention order",
            "One modifier that changes the next act",
            "Counts are complete; lists may collapse",
            "One order",
        ):
            self.assertIn(phrase, text)
        self.assertIn("!threads", text)

    def test_awareness_line_uses_five_state_not_activity(self) -> None:
        from thread_registry import format_thread_awareness_line

        line = format_thread_awareness_line(
            "1",
            {
                "name": "probe",
                "harvest_status": "cooled",
                "created": "2026-09-01T00:00:00+00:00",
                "last_activity": "2026-09-01T00:00:00+00:00",
            },
        )
        self.assertIn("resting", line)
        self.assertNotIn("status:cooled", line)
        self.assertNotIn("status:active", line)


if __name__ == "__main__":
    unittest.main()
