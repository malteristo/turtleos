"""Tests for in-eddy flow library (Slice 1)."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class EddyFlowLibraryTests(unittest.TestCase):
    def test_river_bar_new_eddy_only(self) -> None:
        src = (REPO / "river_handler.py").read_text(encoding="utf-8")
        bar_block = src.split("class RiverEddyBarView")[1].split("class RiverEddyView")[0]
        self.assertIn("new eddy", bar_block)
        self.assertNotIn("flow menu", bar_block)
        self.assertNotIn("_on_flow_menu", bar_block)

    def test_eddy_flow_library_module(self) -> None:
        src = (REPO / "eddy_flow_library.py").read_text(encoding="utf-8")
        self.assertIn("class EddyFlowLibraryView", src)
        self.assertIn("Load a guided flow", src)
        self.assertIn("async def load_flow_in_eddy", src)
        self.assertIn("post_eddy_flow_library", src)

    def test_spawn_defers_flow_library_until_first_message(self) -> None:
        src = (REPO / "eddy_spawn.py").read_text(encoding="utf-8")
        spawn_block = src.split("async def spawn_river_eddy")[1].split("async def spawn_blank_river_eddy")[0]
        self.assertNotIn("post_eddy_flow_library", spawn_block)
        river_src = (REPO / "river_bot.py").read_text(encoding="utf-8")
        self.assertNotIn("migrate_eddy_flow_library_to_bottom", river_src)
        self.assertNotIn("touch_eddy_flow_library_bar", river_src)

    def test_flow_library_on_demand_via_command(self) -> None:
        cmd_src = (REPO / "commands.py").read_text(encoding="utf-8")
        self.assertIn('"flow":', cmd_src)
        dispatch_src = (REPO / "cmd_dispatch.py").read_text(encoding="utf-8")
        self.assertNotIn("touch_eddy_flow_library_bar", dispatch_src)

    def test_prepare_flow_uses_bootstrap(self) -> None:
        src = (REPO / "eddy_spawn.py").read_text(encoding="utf-8")
        block = src.split("async def prepare_flow_eddy_entry")[1].split("async def spawn_river_eddy")[0]
        self.assertIn("start_flow_bootstrap", block)
        self.assertNotIn("post_flow_intake_orientation", block)
        self.assertIn("lens", block)

    def test_lens_load_module(self) -> None:
        src = (REPO / "eddy_flow_library.py").read_text(encoding="utf-8")
        self.assertIn("def is_lens_load", src)
        self.assertIn("FlowRenameOfferView", src)
        self.assertIn("post_flow_rename_offer", src)

    def test_bottom_flow_library_bar(self) -> None:
        src = (REPO / "eddy_flow_library.py").read_text(encoding="utf-8")
        for needle in (
            "EddyFlowLibraryBarView",
            "post_eddy_flow_library_bar",
            "touch_eddy_flow_library_bar",
            "migrate_eddy_flow_library_to_bottom",
        ):
            self.assertIn(needle, src)

    def test_bar_anchor_prefers_flow_library_on_native(self) -> None:
        src = (REPO / "bar_anchor.py").read_text(encoding="utf-8")
        self.assertIn("flow_library_bar", src)
        self.assertIn("standing_lifecycle_bar_enabled", src)


if __name__ == "__main__":
    unittest.main()
