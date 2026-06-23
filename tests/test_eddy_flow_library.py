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

    def test_spawn_posts_flow_library_for_blank_eddy(self) -> None:
        src = (REPO / "eddy_spawn.py").read_text(encoding="utf-8")
        self.assertIn("post_eddy_flow_library", src)
        self.assertIn("if not flow_id:", src)

    def test_prepare_flow_uses_bootstrap(self) -> None:
        src = (REPO / "eddy_spawn.py").read_text(encoding="utf-8")
        block = src.split("async def prepare_flow_eddy_entry")[1].split("async def spawn_river_eddy")[0]
        self.assertIn("start_flow_bootstrap", block)
        self.assertNotIn("post_flow_intake_orientation", block)


if __name__ == "__main__":
    unittest.main()
