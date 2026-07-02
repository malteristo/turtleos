"""Tests for the Continuity Engine — Slice 0 (current) + Slice 1 (alive + scope)."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine import (
    add_active_thread,
    alive_yaml_path,
    clear_scope,
    compose_current,
    current_yaml_path,
    find_active_thread,
    get_scope,
    is_stale,
    list_active_threads,
    read_alive,
    read_current,
    refresh_and_render,
    remove_active_thread,
    render_alive_headers,
    render_current_block,
    render_scope_block,
    render_substrate_block,
    render_substrate_packet,
    set_last_checkpoint,
    set_scope,
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


class AliveLayerTests(unittest.TestCase):
    def test_add_creates_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            thread = add_active_thread(tmp, "Continuity Engine", now=FIXED_NOW)
            self.assertEqual(thread["id"], "continuity-engine")
            self.assertEqual(thread["since"], "2026-07-02")
            self.assertTrue(alive_yaml_path(tmp).exists())
            self.assertEqual(len(list_active_threads(tmp)), 1)

    def test_add_is_idempotent_on_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Continuity Engine")
            add_active_thread(tmp, "Continuity Engine", tone="building")
            threads = list_active_threads(tmp)
            self.assertEqual(len(threads), 1)
            self.assertEqual(threads[0]["tone"], "building")

    def test_find_by_id_and_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Vocabulary firewall")
            self.assertIsNotNone(find_active_thread(tmp, "vocabulary-firewall"))
            self.assertIsNotNone(find_active_thread(tmp, "firewall"))
            self.assertIsNone(find_active_thread(tmp, "nonexistent-topic"))

    def test_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Heat party", thread_id="party")
            self.assertTrue(remove_active_thread(tmp, "party"))
            self.assertFalse(remove_active_thread(tmp, "party"))
            self.assertEqual(list_active_threads(tmp), [])

    def test_read_missing_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_alive(tmp))


class ScopeStoreTests(unittest.TestCase):
    def test_set_get_clear_per_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            set_scope(tmp, 111, "continuity-engine", now=FIXED_NOW)
            set_scope(tmp, 222, "heat-party", now=FIXED_NOW)
            # Per-eddy: narrowing one channel must not narrow the other.
            self.assertEqual(get_scope(tmp, 111), "continuity-engine")
            self.assertEqual(get_scope(tmp, 222), "heat-party")
            self.assertIsNone(get_scope(tmp, 333))
            self.assertTrue(clear_scope(tmp, 111))
            self.assertIsNone(get_scope(tmp, 111))
            self.assertEqual(get_scope(tmp, 222), "heat-party")

    def test_clear_absent_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(clear_scope(tmp, 999))


class AliveHeaderRenderTests(unittest.TestCase):
    def test_headers_use_plain_language(self) -> None:
        alive = {
            "active_threads": [
                {"id": "ce", "label": "Continuity engine", "tone": "building"},
                {"id": "party", "label": "Heat party", "tone": "unresolved"},
            ]
        }
        headers = render_alive_headers(alive)
        self.assertIn("In motion:", headers)
        self.assertIn("Continuity engine — building", headers)
        self.assertIn("(2) Heat party — unresolved", headers)

    def test_intention_snapshot_renders(self) -> None:
        alive = {
            "active_threads": [],
            "intention_snapshot": [
                {"name": "turtle", "current_focus": "substrate design"}
            ],
        }
        self.assertIn("Intention: turtle — substrate design", render_alive_headers(alive))

    def test_empty_alive_renders_nothing(self) -> None:
        self.assertEqual(render_alive_headers(None), "")
        self.assertEqual(render_alive_headers({"active_threads": []}), "")

    def test_headers_capped(self) -> None:
        alive = {"active_threads": [{"id": f"t{i}", "label": f"Thread {i}"} for i in range(9)]}
        headers = render_alive_headers(alive, max_threads=3)
        self.assertIn("(3)", headers)
        self.assertNotIn("(4)", headers)

    def test_firewall_on_headers(self) -> None:
        alive = {
            "active_threads": [{"id": "x", "label": "Some theme", "tone": "building"}],
            "intention_snapshot": [{"name": "turtle", "current_focus": "x"}],
        }
        lowered = render_alive_headers(alive).lower()
        for term in FIREWALL_TERMS:
            self.assertNotIn(term, lowered, f"ecology term leaked: {term!r}")


class ScopedSelfFeedTests(unittest.TestCase):
    def _seed_session(self, tmp: str, name: str, body: str) -> None:
        sdir = Path(tmp) / "sessions"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / name).write_text(body, encoding="utf-8")

    def test_pulls_matching_session_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._seed_session(
                tmp,
                "2026-06-30.md",
                "---\ntitle: x\n---\nWorked on the continuity engine layering today.",
            )
            self._seed_session(tmp, "2026-06-29.md", "Unrelated grocery list notes.")
            thread = {"id": "continuity-engine", "label": "Continuity engine"}
            block = render_scope_block(tmp, thread)
            self.assertIn('Focused on "Continuity engine"', block)
            self.assertIn("continuity engine layering", block)
            self.assertNotIn("grocery", block)

    def test_honest_when_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            thread = {"id": "brand-new", "label": "Brand new topic"}
            block = render_scope_block(tmp, thread)
            self.assertIn("no saved notes match", block)
            self.assertNotIn("- ", block)  # no fabricated excerpts

    def test_none_thread_renders_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(render_scope_block(tmp, None), "")


class SubstratePacketTests(unittest.TestCase):
    def test_packet_folds_current_and_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Continuity engine", tone="building", now=FIXED_NOW)
            block = render_substrate_packet(
                tmp, dialogue_model="gemma4:31b", host_label="Mac Mini"
            )
            self.assertIn("Local inference", block)
            self.assertIn("In motion:", block)
            self.assertIn("Continuity engine — building", block)
            # Single substrate header, not two concatenated blocks.
            self.assertEqual(block.count("[Practice substrate"), 1)

    def test_packet_scoped_adds_self_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "sessions"
            sdir.mkdir(parents=True)
            (sdir / "s.md").write_text("Deep notes on the vocabulary firewall idea.")
            add_active_thread(tmp, "Vocabulary firewall", thread_id="vocabulary-firewall")
            block = render_substrate_packet(tmp, scope="vocabulary-firewall")
            self.assertIn('Focused on "Vocabulary firewall"', block)
            self.assertIn("vocabulary firewall idea", block)

    def test_packet_carries_checkpoint_one_liner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            refresh_and_render(tmp, dialogue_model="gemma4:31b")
            set_last_checkpoint(tmp, "Discussed database vs substrate.")
            block = render_substrate_packet(tmp, dialogue_model="gemma4:31b")
            self.assertIn("Last checkpoint: Discussed database vs substrate.", block)

    def test_packet_firewall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Some theme", tone="building")
            set_scope(tmp, 1, "some-theme")
            block = render_substrate_packet(tmp, scope="some-theme").lower()
            for term in FIREWALL_TERMS:
                self.assertNotIn(term, block, f"ecology term leaked: {term!r}")

    def test_render_substrate_block_holistic_conduct(self) -> None:
        data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
        # No alive → Slice 0 conduct line; with alive → fuller conduct line.
        self.assertIn("never as a recital", render_substrate_block(data))
        with_alive = render_substrate_block(
            data, {"active_threads": [{"id": "a", "label": "A", "tone": "building"}]}
        )
        self.assertIn("what's in motion", with_alive)


if __name__ == "__main__":
    unittest.main()
