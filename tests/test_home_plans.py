"""Unit tests for pinned home eddies registry (slices 0–1, 4, 6)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import home_plans as hp


class TestHomePlansRegistry(unittest.TestCase):
    def test_bind_1to1_and_sticky(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = hp.bind_home(
                tmp,
                title="Workout plan",
                home_eddy_id=111,
                river_channel_id=222,
                body="## Day 1\n- Squats\n",
            )
            self.assertEqual(plan["title"], "Workout plan")
            self.assertTrue(plan["sticky"])
            self.assertTrue(str(plan["artifact_path"]).startswith("state/notes/"))
            self.assertTrue(hp.is_sticky_eddy(tmp, 111))
            self.assertFalse(hp.is_sticky_eddy(tmp, 999))

            art = Path(tmp) / plan["artifact_path"]
            self.assertTrue(art.is_file())
            self.assertIn("Squats", art.read_text(encoding="utf-8"))

            again = hp.get_by_eddy(tmp, 111)
            self.assertIsNotNone(again)
            self.assertEqual(again["id"], plan["id"])

    def test_refuse_duplicate_eddy_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = hp.bind_home(
                tmp,
                title="Plan A",
                home_eddy_id=1,
                river_channel_id=9,
            )
            with self.assertRaises(hp.HomePlanError):
                hp.bind_home(
                    tmp,
                    title="Plan B",
                    home_eddy_id=1,
                    river_channel_id=9,
                )
            with self.assertRaises(hp.HomePlanError):
                hp.bind_home(
                    tmp,
                    title="Plan C",
                    home_eddy_id=2,
                    river_channel_id=9,
                    artifact_path=first["artifact_path"],
                )

    def test_clear_keeps_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = hp.bind_home(
                tmp, title="Temp", home_eddy_id=5, river_channel_id=6
            )
            path = Path(tmp) / plan["artifact_path"]
            self.assertTrue(path.exists())
            removed = hp.clear_plan(tmp, plan["id"])
            self.assertIsNotNone(removed)
            self.assertTrue(path.exists())
            self.assertIsNone(hp.get_by_eddy(tmp, 5))

    def test_patch_append_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = hp.bind_home(
                tmp,
                title="Gym",
                home_eddy_id=7,
                river_channel_id=8,
                body="# Gym\n\n- row 1\n",
            )
            hp.patch_artifact(tmp, plan["id"], append_note="increased weight")
            text = (Path(tmp) / plan["artifact_path"]).read_text(encoding="utf-8")
            self.assertIn("increased weight", text)
            hp.patch_artifact(tmp, plan["id"], new_body="# Gym\n\nreplaced\n")
            text2 = (Path(tmp) / plan["artifact_path"]).read_text(encoding="utf-8")
            self.assertIn("replaced", text2)
            self.assertNotIn("increased weight", text2)

    def test_attunement_packet_mentions_file_not_sidebar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = hp.bind_home(
                tmp,
                title="North Star",
                home_eddy_id=42,
                river_channel_id=1,
                body="# North Star\n\nvision\n",
            )
            packet = hp.render_home_attunement_packet(tmp, 42)
            self.assertIn("North Star", packet)
            self.assertIn(plan["artifact_path"], packet)
            self.assertIn("vision", packet)
            self.assertIn("river pin", packet.lower())
            self.assertIn("Do not describe side-panels", packet)
            self.assertEqual(hp.render_home_attunement_packet(tmp, 999), "")


class TestPinCardPayload(unittest.TestCase):
    def test_card_button_labels_contract(self) -> None:
        import home_plan_ui as ui

        self.assertEqual(
            ui.PIN_CARD_BUTTON_LABELS, ("Continue", "Open", "Stop pinning")
        )


if __name__ == "__main__":
    unittest.main()
