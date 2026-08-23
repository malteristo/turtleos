"""Tests for Fresh Eyes surface assembly + shipped flow (§10.2)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import yaml

import continuity_engine as ce
import fresh_eyes
from flow_runner import (
    build_flow_prompt_sections,
    list_resolvable_flow_ids,
    load_flow_spec,
)


class TestFreshEyesSurface(unittest.TestCase):
    def test_compose_empty_practice_is_honest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = fresh_eyes.compose_fresh_eyes_surface(tmp)
        self.assertIn("nothing confirmed in motion yet", text)
        self.assertIn("no recent checkpoint note", text)
        self.assertIn("no conversation notes yet", text)
        self.assertIn("no day notes yet", text)
        lower = text.lower()
        self.assertNotIn("alive.yaml", lower)
        self.assertNotIn("knot", lower)

    def test_compose_includes_alive_eddies_daily_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pd = Path(tmp)
            ce.add_active_thread(pd, "Adjusting walking schedule", tone="active")
            ce.set_last_checkpoint(pd, "Talked about earlier walks before the trip.")
            eddies = pd / "story" / "eddies"
            eddies.mkdir(parents=True)
            (eddies / "1-walks.md").write_text(
                "---\n"
                "thread: '1'\n"
                "title: earlier walks\n"
                "trigger: manual\n"
                "timestamp: '2026-07-16T12:00:00+02:00'\n"
                "related-topics: []\n"
                "---\n\n"
                "You decided to walk earlier for sleep. The weekend trip packing can wait.\n",
                encoding="utf-8",
            )
            daily = pd / "story" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-07-16.md").write_text(
                "A quiet day of sorting sleep and packing thoughts.\n",
                encoding="utf-8",
            )

            text = fresh_eyes.compose_fresh_eyes_surface(pd)

        self.assertIn("Adjusting walking schedule", text)
        self.assertIn("earlier walks", text)
        self.assertIn("walk earlier for sleep", text)
        self.assertIn("Talked about earlier walks", text)
        self.assertIn("2026-07-16", text)
        self.assertIn("sorting sleep", text)

    def test_materialize_writes_surface_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = fresh_eyes.materialize_fresh_eyes_surface(tmp)
            self.assertTrue(path.is_file())
            self.assertEqual(path.name, "fresh-eyes-surface.md")
            self.assertIn("In motion", path.read_text(encoding="utf-8"))


class TestFreshEyesFlow(unittest.TestCase):
    def test_shipped_flow_listed_and_loads(self) -> None:
        self.assertIn("fresh_eyes", list_resolvable_flow_ids())
        spec = load_flow_spec("fresh_eyes")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.title, "Fresh Eyes")
        self.assertIn(fresh_eyes.SURFACE_REL, spec.reads)
        self.assertIn("state/notes/fresh-eyes-last.md", spec.writes)
        self.assertIn("Illumination", spec.body)
        self.assertIn("not urgency", spec.body.lower())

    def test_build_prompt_materializes_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ce.add_active_thread(tmp, "Calmer wind-down routine")
            sections, spec = build_flow_prompt_sections("fresh_eyes", tmp)
            self.assertIsNotNone(spec)
            surface = Path(tmp) / fresh_eyes.SURFACE_REL
            self.assertTrue(surface.is_file())
            joined = "\n".join(sections)
            self.assertIn("Calmer wind-down routine", joined)
            self.assertIn("Fresh Eyes", joined)


if __name__ == "__main__":
    unittest.main()
