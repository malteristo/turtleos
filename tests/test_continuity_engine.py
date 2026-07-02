"""Tests for the Continuity Engine — Slice 0 (current layer)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine import (
    compose_current,
    current_yaml_path,
    is_stale,
    read_current,
    refresh_and_render,
    render_current_block,
    write_current,
)

BERLIN = timezone(timedelta(hours=2))
# Thursday, 2026-07-02, 12:05 — afternoon, summer (northern hemisphere).
FIXED_NOW = datetime(2026, 7, 2, 12, 5, tzinfo=BERLIN)

# Ecology vocabulary that MUST NOT leak into the injected block (design §4).
FIREWALL_TERMS = ("bedrock", "sediment", "alive", "knot")


class ComposeCurrentTests(unittest.TestCase):
    def test_composes_time_fields(self) -> None:
        data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
        local = data["local"]
        self.assertEqual(local["weekday"], "Thursday")
        self.assertEqual(local["date"], "2026-07-02")
        self.assertEqual(local["day_part"], "afternoon")
        self.assertEqual(local["season"], "summer")
        self.assertEqual(data["version"], 1)
        self.assertIsNone(data["scope"])

    def test_dialogue_model_reflects_this_turn(self) -> None:
        # Hardware honesty (§3.2.3): the resolved per-turn model, not a default.
        data = compose_current(dialogue_model="claude-sonnet-4-6", use_api=True, now=FIXED_NOW)
        self.assertEqual(data["machine"]["dialogue_model"], "claude-sonnet-4-6")
        self.assertEqual(data["machine"]["inference"], "cloud")

    def test_local_model_is_local_inference(self) -> None:
        data = compose_current(dialogue_model="gemma4:31b", use_api=False, now=FIXED_NOW)
        self.assertEqual(data["machine"]["inference"], "local")

    def test_southern_hemisphere_flips_season(self) -> None:
        data = compose_current(now=FIXED_NOW, southern_hemisphere=True)
        self.assertEqual(data["local"]["season"], "winter")

    def test_host_label_override(self) -> None:
        data = compose_current(host_label="Mac Mini M4 Pro", now=FIXED_NOW)
        self.assertEqual(data["machine"]["host_label"], "Mac Mini M4 Pro")


class RenderBlockTests(unittest.TestCase):
    def test_block_has_when_and_machine(self) -> None:
        data = compose_current(dialogue_model="gemma4:31b", host_label="Mac Mini M4 Pro", now=FIXED_NOW)
        block = render_current_block(data)
        self.assertIn("Thursday afternoon", block)
        self.assertIn("2026-07-02", block)
        self.assertIn("gemma4:31b", block)
        self.assertIn("Mac Mini M4 Pro", block)

    def test_vocabulary_firewall(self) -> None:
        data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
        block = render_current_block(data).lower()
        for term in FIREWALL_TERMS:
            self.assertNotIn(term, block, f"ecology term leaked into inject: {term!r}")


class PersistenceTests(unittest.TestCase):
    def test_write_read_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
            path = write_current(tmp, data)
            self.assertEqual(path, current_yaml_path(tmp))
            self.assertTrue(path.exists())
            loaded = read_current(tmp)
            self.assertEqual(loaded["local"]["date"], "2026-07-02")

    def test_read_missing_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_current(tmp))

    def test_staleness(self) -> None:
        fresh = compose_current(now=FIXED_NOW)
        self.assertFalse(is_stale(fresh, now=FIXED_NOW + timedelta(minutes=5)))
        self.assertTrue(is_stale(fresh, now=FIXED_NOW + timedelta(minutes=20)))
        self.assertTrue(is_stale(None))

    def test_refresh_writes_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            block = refresh_and_render(tmp, dialogue_model="gemma4:31b")
            self.assertTrue(current_yaml_path(tmp).exists())
            self.assertIn("Local inference", block)


if __name__ == "__main__":
    unittest.main()
