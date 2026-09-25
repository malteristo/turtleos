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

    def test_group_preserves_order_and_drops_empty(self) -> None:
        grouped = fs.group_lines_by_five_state(
            [("live", "a"), ("resting", "b"), ("live", "c"), ("gone", "d")]
        )
        self.assertEqual(list(grouped), list(fs.FIVE_STATES))
        self.assertEqual(grouped["live"], ["a", "c"])
        self.assertEqual(grouped["resting"], ["b"])
        self.assertEqual(grouped["gone"], ["d"])
        self.assertEqual(grouped["sealed"], [])

    def test_unknown_name_lands_in_live(self) -> None:
        grouped = fs.group_lines_by_five_state([("stale", "x")])
        self.assertEqual(grouped["live"], ["x"])

    def test_title_and_sections_name_the_states(self) -> None:
        grouped = fs.group_lines_by_five_state(
            [("live", "one"), ("resting", "two")]
        )
        title = fs.five_state_title(grouped)
        self.assertTrue(title.startswith("Eddies — "))
        self.assertIn("1 live", title)
        self.assertIn("1 resting", title)
        self.assertLess(title.index("live"), title.index("resting"))
        self.assertNotIn("dormant", title)
        body = fs.render_five_state_sections(grouped)
        self.assertIn("**live · 1**", body)
        self.assertIn("**resting · 1**", body)
        self.assertNotIn("cooled", body)
        self.assertNotIn("──", body)

    def test_fit_stays_under_discord_limit(self) -> None:
        rows = [f"{i:03d} " + ("x" * 80) for i in range(200)]
        grouped = fs.group_lines_by_five_state([("resting", r) for r in rows])
        raw = fs.render_five_state_sections(grouped)
        self.assertGreater(len(raw), fs.EMBED_DESCRIPTION_LIMIT)
        fitted = fs.fit_embed_description(grouped, expand=True, cap=200)
        self.assertLessEqual(len(fitted), fs.EMBED_DESCRIPTION_LIMIT)
        self.assertIn("**resting · 200**", fitted)
        self.assertIn("more", fitted)
        self.assertIn("200 resting", fs.five_state_title(grouped))

    def test_glance_collapses_resting_and_caps_live(self) -> None:
        live = [f"talk-{i}" for i in range(20)]
        resting = [f"park-{i}" for i in range(24)]
        grouped = fs.group_lines_by_five_state(
            [("live", name) for name in live] + [("resting", name) for name in resting]
        )
        glance = fs.fit_embed_description(grouped, expand=False)
        self.assertIn("**live · 20**", glance)
        self.assertIn("talk-0", glance)
        self.assertIn("… and 8 more", glance)
        self.assertIn("**resting · 24**", glance)
        self.assertIn("parked", glance)
        self.assertNotIn("park-0", glance)
        inventory = fs.fit_embed_description(grouped, expand=True)
        self.assertIn("park-0", inventory)

    def test_fields_are_glanceable(self) -> None:
        grouped = fs.group_lines_by_five_state(
            [("live", "**talk** · 1d"), ("resting", "**asleep** · 12d")]
        )
        fields = dict(fs.five_state_fields(grouped, expand=False))
        self.assertEqual(set(fields), {"live · 1", "resting · 1"})
        self.assertIn("**talk**", fields["live · 1"])
        self.assertEqual(fields["resting · 1"], "parked")
        self.assertNotIn("id:", fields["live · 1"])


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
