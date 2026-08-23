"""Tests for the Continuity Engine — Slice 0 (current) + Slice 1 (alive + scope)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Room memory reads eddy notes via story_notes, which pulls the discord runtime.
# Stub only when it is genuinely absent (dev machines without it installed), and
# never alias ``discord.ext`` to the package — sys.modules is process-global
# under discovery, so that shadows the real ext for every module after this one.
try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

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

    def test_no_root_level_scope_field(self) -> None:
        """Scope is per-eddy, so a per-root field cannot hold it.

        `current.yaml` carried a root-level `scope` from Slice 0 and it was
        superseded before it was ever filled: narrowing one conversation must
        not narrow the others, so scope moved to `scopes.yaml` keyed by channel
        id (module docstring, "Per-eddy scope, not per-root"). The field stayed
        behind at `None` — and the old test here asserted it *stays* None,
        which pinned a dead field in place rather than removing it.

        It was not free. On 2026-08-12 Turtle read `scope: null` in a live file
        as evidence that `current.yaml` had been designed as the practice's
        orientation document and never inhabited, and built a hypothesis on it.
        A vestige that reads as an unfilled intention is worse than clutter; it
        is a false signal to the next reader.
        """
        data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
        self.assertNotIn("scope", data)

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
            # Written at FIXED_NOW and read at wall-clock: reads prune by age,
            # so a thread stamped in the past is correctly gone. The write is
            # asserted on the returned thread and the file; presence in the
            # live list is asserted for a thread stamped now.
            self.assertEqual(list_active_threads(tmp), [])
            add_active_thread(tmp, "Continuity Engine")
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


class RoomMemoryTests(unittest.TestCase):
    """The room reads its own eddy notes, on every turn, unasked.

    This reader used to read ``sessions/*.md`` — retired 2026-07-15 — and only
    ran under ``!focus``, which no practitioner has ever used. Both are fixed
    here: live corpus, no command.
    """

    def _seed_eddy(
        self, tmp: str, thread: str, title: str, body: str, *, days_ago: int = 1,
        themes: str = "[]",
    ) -> None:
        edir = Path(tmp) / "story" / "eddies"
        edir.mkdir(parents=True, exist_ok=True)
        ts = (datetime.now(BERLIN) - timedelta(days=days_ago)).isoformat()
        (edir / f"{thread}-x.md").write_text(
            f"---\nthread: '{thread}'\ntitle: {title}\ntrigger: idle\n"
            f"timestamp: '{ts}'\nrelated-topics: []\nproposed-themes: {themes}\n"
            f"---\n\n{body}\n",
            encoding="utf-8",
        )

    def test_reads_recent_eddy_notes_without_a_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._seed_eddy(
                tmp, "111", "the birthday plan",
                "Ana described the food arrangements. Ben offered to call.",
                themes="[party logistics]",
            )
            block = render_scope_block(tmp, None)
            self.assertIn("What this space has been about recently", block)
            self.assertIn("the birthday plan", block)
            self.assertIn("Ana described", block)
            self.assertIn("party logistics", block)

    def test_current_eddy_is_excluded(self) -> None:
        """That conversation is already in the prompt as history."""
        with tempfile.TemporaryDirectory() as tmp:
            self._seed_eddy(tmp, "111", "this very eddy", "Talking right now.")
            block = render_scope_block(tmp, None, current_thread="111")
            self.assertNotIn("this very eddy", block)

    def test_entries_older_than_the_window_do_not_appear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._seed_eddy(
                tmp, "222", "ancient history", "Long ago and far away.", days_ago=40
            )
            block = render_scope_block(tmp, None)
            self.assertNotIn("ancient history", block)

    def test_focus_narrows_what_is_already_there(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._seed_eddy(
                tmp, "111", "grocery run", "Unrelated grocery list notes.", days_ago=1
            )
            self._seed_eddy(
                tmp, "222", "continuity engine",
                "Worked on the continuity engine layering today.", days_ago=2,
            )
            thread = {"id": "continuity-engine", "label": "Continuity engine"}
            block = render_scope_block(tmp, thread)
            self.assertIn('Focused on "Continuity engine"', block)
            # Narrowing reorders; it does not switch retrieval on or off.
            self.assertLess(block.index("continuity engine"), block.index("grocery"))

    def test_the_candidate_set_records_what_was_not_carried(self) -> None:
        """The road not taken. Without this, selection quality is unmeasurable.

        The control that matters is the *unselected* row: a record listing only
        what reached the prompt would pass a "did anything get written?" check
        while being useless for scoring a choice.
        """
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(7):
                self._seed_eddy(
                    tmp, f"{index}00", f"conversation {index}",
                    f"Something was discussed in number {index}.", days_ago=index,
                )
            considered: list[dict] = []
            render_scope_block(tmp, None, considered=considered)

            self.assertEqual(len(considered), 7)
            carried = [row for row in considered if row["selected"]]
            passed_over = [row for row in considered if not row["selected"]]
            self.assertEqual(len(carried), 5)
            self.assertEqual(len(passed_over), 2)
            # Named, not merely counted — a judge needs to know which ones.
            self.assertTrue(all(row["title"] for row in passed_over))

    def test_focus_can_reach_a_note_the_recency_cut_would_have_dropped(self) -> None:
        """Ranking after truncation is ranking nothing.

        Scoring used to run against a list already cut to five, so a focused
        thread could reorder the recent and never reach a sixth note that
        actually matched. The window comes first now; the cut comes after.
        """
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(5):
                self._seed_eddy(
                    tmp, f"{index}00", f"grocery run {index}",
                    "Unrelated grocery list notes.", days_ago=index + 1,
                )
            self._seed_eddy(
                tmp, "999", "continuity engine",
                "Worked on the continuity engine layering all day.", days_ago=6,
            )
            thread = {"id": "continuity-engine", "label": "Continuity engine"}
            considered: list[dict] = []
            block = render_scope_block(tmp, thread, considered=considered)

            self.assertIn("continuity engine", block)
            match = next(row for row in considered if row["title"] == "continuity engine")
            self.assertTrue(match["selected"])
            self.assertGreater(match["score"], 0)

    def test_honest_about_reach_when_the_room_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            block = render_scope_block(tmp, None)
            self.assertIn("cannot see it", block)
            self.assertIn("this space's own", block)
            self.assertNotIn("- ", block)  # no fabricated excerpts

    def test_one_conversation_cannot_fill_the_window(self) -> None:
        """The last N conversations, not the last N checkpoints.

        A long-running eddy checkpoints repeatedly; a flat recency window fills
        with its own history and the room appears to remember only its loudest
        week.
        """
        with tempfile.TemporaryDirectory() as tmp:
            edir = Path(tmp) / "story" / "eddies"
            edir.mkdir(parents=True)
            entries = "".join(
                f"---\nthread: '777'\ntitle: the loud one\ntrigger: idle\n"
                f"timestamp: '{(datetime.now(BERLIN) - timedelta(hours=h)).isoformat()}'\n"
                f"related-topics: []\nproposed-themes: []\n---\n\nCheckpoint {h}.\n\n"
                for h in range(1, 6)
            )
            (edir / "777-loud.md").write_text(entries, encoding="utf-8")
            self._seed_eddy(tmp, "888", "the quiet one", "Something else entirely.",
                            days_ago=2)

            block = render_scope_block(tmp, None)
            self.assertIn("the quiet one", block)
            self.assertEqual(block.count("the loud one"), 1)

    def test_never_reads_another_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mine = Path(tmp, "mine")
            theirs = Path(tmp, "theirs")
            mine.mkdir()
            theirs.mkdir()
            self._seed_eddy(str(theirs), "999", "their private eddy", "Their material.")
            block = render_scope_block(str(mine), None)
            self.assertNotIn("their private eddy", block)
            self.assertNotIn("Their material", block)


class SubstratePacketTests(unittest.TestCase):
    def test_packet_folds_current_and_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_active_thread(tmp, "Continuity engine", tone="building")
            block = render_substrate_packet(
                tmp, dialogue_model="gemma4:31b", host_label="Mac Mini"
            )
            self.assertIn("Local inference", block)
            # The alive layer is written and does not render — see
            # test_the_alive_layer_never_reaches_a_turn.
            self.assertNotIn("In motion:", block)
            self.assertNotIn("Continuity engine — building", block)
            self.assertEqual(len(list_active_threads(tmp)), 1)
            # Single substrate header, not two concatenated blocks.
            self.assertEqual(block.count("[Practice substrate"), 1)

    def test_packet_carries_room_memory_without_a_scope(self) -> None:
        """The whole point: no command, no focus, memory arrives anyway."""
        with tempfile.TemporaryDirectory() as tmp:
            edir = Path(tmp) / "story" / "eddies"
            edir.mkdir(parents=True)
            ts = (datetime.now(BERLIN) - timedelta(days=1)).isoformat()
            (edir / "1-x.md").write_text(
                f"---\nthread: '1'\ntitle: vocabulary firewall\ntrigger: idle\n"
                f"timestamp: '{ts}'\nrelated-topics: []\nproposed-themes: []\n"
                f"---\n\nDeep notes on the vocabulary firewall idea.\n"
            )
            block = render_substrate_packet(tmp)
            self.assertIn("What this space has been about recently", block)
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

    def test_the_alive_layer_never_reaches_a_turn(self) -> None:
        """Retrieval is the only memory the model sees.

        `what-a-shared-room-remembers.md` §4 replaced curated carry with
        retrieval and §9 settled it — nothing retrieved becomes state. The
        alive header line was the superseded design's last mouth, and the whole
        of its live cost: every false carry the 2026-08-05 audit found reached
        a practitioner through it. The layer is still written, because
        recurrence over weeks is what an intention is made of and a seven-day
        window cannot compute it; its readers are the relation gate and the
        intention offer, and neither is a turn.
        """
        data = compose_current(dialogue_model="gemma4:31b", now=FIXED_NOW)
        alive = {"active_threads": [
            {"id": "a", "label": "a distinctive label", "tone": "building"}
        ]}
        block = render_substrate_block(data, alive)
        self.assertNotIn("a distinctive label", block)
        self.assertNotIn("In motion", block)
        self.assertIn("never as a recital", block)


if __name__ == "__main__":
    unittest.main()
