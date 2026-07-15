"""Tests for the eddy note writer (issue 034, TURTLE_SPEC §6.5 / §8.4)."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import yaml

import atomic_io
import story_notes


CHANNEL_ID = 424242

HISTORY = [
    {"role": "user", "content": "I slept terribly again last night."},
    {"role": "assistant", "content": "Rough. Any idea what kept you up?"},
    {"role": "user", "content": "Maybe the late walks. And we should plan the weekend trip."},
    {"role": "assistant", "content": "Earlier walks could help. For the trip: pack light."},
]


def _response(held: str, relation: str, topics: list[str] | None) -> str:
    topics_body = "\n".join(f"- {t}" for t in topics) if topics else "none"
    return (
        f"---HELD---\n{held}\n"
        f"---RELATION---\n{relation}\n"
        f"---RELATED-TOPICS---\n{topics_body}\n"
        "---END---"
    )


HELD_SLEEP = (
    "Kermit talked through another rough night of sleep and traced it to late "
    "evening walks. A plan emerged to move the walks earlier and see how the "
    "week goes."
)
HELD_TRIP = "Kermit sketched a packing list for the weekend trip. Nothing was left open."

RELATION_RESPONSE = _response(
    HELD_SLEEP, "This conversation touches your thread about health.", ["health"]
)
NO_RELATION_RESPONSE = _response(HELD_TRIP, "none", None)
FABRICATED_TOPIC_RESPONSE = _response(
    HELD_TRIP,
    "This conversation touches your thread about quantum computing.",
    ["quantum computing"],
)


def _write_alive(
    practice_dir: str,
    threads: tuple[str, ...] = ("health",),
    intentions: tuple[str, ...] = ("morning practice",),
) -> None:
    state_dir = Path(practice_dir) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    alive = {
        "version": 1,
        "updated_at": "2026-07-14T08:00:00+02:00",
        "active_threads": [
            {"id": t, "label": t, "since": "2026-07-01", "tone": "tending"} for t in threads
        ],
        "intention_snapshot": [{"name": i} for i in intentions],
    }
    (state_dir / "alive.yaml").write_text(
        yaml.safe_dump(alive, sort_keys=False), encoding="utf-8"
    )


_ENTRY_RE = re.compile(r"---\n(.*?)---\n\n", re.S)


def _parse_entries(content: str) -> list[tuple[dict, str]]:
    """Split a note file into (front_matter_dict, body) per checkpoint entry."""
    matches = list(_ENTRY_RE.finditer(content))
    entries = []
    for i, m in enumerate(matches):
        front = yaml.safe_load(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        entries.append((front, content[m.end():end].strip()))
    return entries


class EddyNoteWriterTests(unittest.IsolatedAsyncioTestCase):
    """CRITICAL test hygiene (issue 037): practice-root resolution is patched
    to a temp dir in every test — nothing may resolve or write ~/workshops/."""

    def _patched(self, practice_dir: str, llm: AsyncMock) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("story_notes.set_practice_context_for_channel"))
        stack.enter_context(patch("story_notes.get_pd", return_value=practice_dir))
        stack.enter_context(patch("story_notes.get_mage_name", return_value="Kermit"))
        stack.enter_context(
            patch("story_notes._resolve_thread_title", return_value="Health check-in")
        )
        stack.enter_context(patch("story_notes.chat_ollama", llm))
        return stack

    # ── relation present ─────────────────────────────────────────────

    async def test_relation_present_entry_structure_and_front_matter(self) -> None:
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            expected = Path(tmp) / "story" / "eddies" / f"{CHANNEL_ID}-health-check-in.md"
            self.assertEqual(result.note_path, expected)

            entries = _parse_entries(expected.read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 1)
            front, body = entries[0]

            # Front matter per entry: thread id, title, trigger, timestamp, related topics.
            self.assertEqual(front["thread"], str(CHANNEL_ID))
            self.assertEqual(front["title"], "Health check-in")
            self.assertEqual(front["trigger"], "idle")
            self.assertRegex(
                str(front["timestamp"]), r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
            )
            self.assertEqual(front["related-topics"], ["health"])

            # Entry body: what the eddy held + the relation sentence.
            self.assertIn("rough night of sleep", body)
            self.assertIn("This conversation touches your thread about health.", body)
            self.assertEqual(body, result.entry_text.split("---\n\n", 1)[1].strip())

            # Preview: relational sentence first, then the opening of the note.
            self.assertTrue(
                result.preview_text.startswith(
                    "This conversation touches your thread about health."
                )
            )
            self.assertIn("rough night of sleep", result.preview_text)

    # ── relation absent ──────────────────────────────────────────────

    async def test_relation_absent_describes_and_stops(self) -> None:
        llm = AsyncMock(return_value=NO_RELATION_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], [])
            self.assertNotIn("your thread about", body)
            self.assertIn("packing list", body)
            # Preview degrades to the first sentences of what the eddy held.
            self.assertTrue(result.preview_text.startswith("Kermit sketched a packing list"))

    # ── manual trigger weighting ─────────────────────────────────────

    async def test_manual_trigger_weights_recent_exchanges(self) -> None:
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="manual", since_index=2
                )

            messages = llm.await_args.args[1]
            prompt = messages[0]["content"]
            self.assertIn("SINCE THE LAST CHECKPOINT", prompt)
            background, focus = prompt.split("SINCE THE LAST CHECKPOINT", 1)
            # history[:2] is background only; history[2:] is the weighted focus.
            self.assertIn(HISTORY[0]["content"], background)
            self.assertNotIn(HISTORY[0]["content"], focus)
            self.assertIn(HISTORY[2]["content"], focus)
            self.assertNotIn(HISTORY[2]["content"], background)

            (front, _), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["trigger"], "manual")

    async def test_idle_trigger_sends_whole_conversation_unweighted(self) -> None:
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                await story_notes.write_eddy_note(CHANNEL_ID, HISTORY, trigger="idle")

            prompt = llm.await_args.args[1][0]["content"]
            self.assertNotIn("SINCE THE LAST CHECKPOINT", prompt)
            self.assertIn(HISTORY[0]["content"], prompt)
            self.assertIn(HISTORY[3]["content"], prompt)

    # ── quality floor (M1): degenerate output never reaches the note ─

    async def test_sentinel_reply_raises_and_writes_nothing(self) -> None:
        llm = AsyncMock(return_value="(no response generated)")
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                with self.assertRaises(story_notes.EddyNoteError):
                    await story_notes.write_eddy_note(CHANNEL_ID, HISTORY, trigger="idle")

            eddies_dir = Path(tmp) / "story" / "eddies"
            self.assertEqual(list(eddies_dir.glob("*.md")) if eddies_dir.exists() else [], [])

    async def test_short_degenerate_reply_raises(self) -> None:
        llm = AsyncMock(return_value="ok.")
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                with self.assertRaises(story_notes.EddyNoteError):
                    await story_notes.write_eddy_note(CHANNEL_ID, HISTORY, trigger="idle")

            eddies_dir = Path(tmp) / "story" / "eddies"
            self.assertEqual(list(eddies_dir.glob("*.md")) if eddies_dir.exists() else [], [])

    async def test_empty_held_section_raises(self) -> None:
        llm = AsyncMock(return_value=_response("", "none", None))
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                with self.assertRaises(story_notes.EddyNoteError):
                    await story_notes.write_eddy_note(CHANNEL_ID, HISTORY, trigger="idle")

    # ── honesty gate (M2): word-boundary matching, canonical names ───

    async def test_superstring_fabricated_topic_is_dropped(self) -> None:
        """Reviewer's case: alive 'health' must NOT validate 'healthcare …'."""
        llm = AsyncMock(
            return_value=_response(
                HELD_TRIP,
                "This conversation touches your thread about healthcare reform policy.",
                ["healthcare reform policy"],
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp, threads=("health",), intentions=())
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], [])
            self.assertNotIn("healthcare", body)
            self.assertNotIn("healthcare", result.preview_text)

    async def test_wordboundary_topic_kept_with_canonical_name(self) -> None:
        """'the health thread' matches alive 'health'; front matter carries
        the canonical alive-item name, not the model's raw string."""
        llm = AsyncMock(
            return_value=_response(
                HELD_SLEEP,
                "This conversation touches your thread about health.",
                ["the health thread"],
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp, threads=("health",), intentions=())
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], ["health"])
            self.assertIn("your thread about health", body)

    async def test_relation_to_topic_not_alive_is_dropped(self) -> None:
        llm = AsyncMock(return_value=FABRICATED_TOPIC_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], [])
            self.assertNotIn("quantum computing", body)

    # ── relation sentence / topics coherence (m3) ────────────────────

    async def test_partial_drop_sentence_referencing_dropped_topic_is_dropped(self) -> None:
        """One topic survives, one is dropped, and the sentence references only
        the dropped one → the whole relation goes; the note stays descriptive."""
        llm = AsyncMock(
            return_value=_response(
                HELD_SLEEP,
                "This connects to your interest in quantum computing.",
                ["health", "quantum computing"],
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp, threads=("health",), intentions=())
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], [])
            self.assertNotIn("quantum computing", body)
            self.assertNotIn("quantum computing", result.preview_text)
            self.assertTrue(result.preview_text.startswith("Kermit talked through"))

    async def test_partial_drop_sentence_referencing_survivor_is_kept(self) -> None:
        llm = AsyncMock(
            return_value=_response(
                HELD_SLEEP,
                "This conversation touches your thread about health.",
                ["health", "quantum computing"],
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp, threads=("health",), intentions=())
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], ["health"])
            self.assertIn("your thread about health", body)

    # ── empty alive layer degrades honestly ──────────────────────────

    async def test_empty_alive_layer_degrades_without_fabricated_relation(self) -> None:
        # Even if the model fabricates a relation, the composer layer must
        # drop it when nothing is alive to relate to.
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        with tempfile.TemporaryDirectory() as tmp:
            with self._patched(tmp, llm):
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            prompt = llm.await_args.args[1][0]["content"]
            self.assertNotIn("WHAT'S ALIVE", prompt)

            (front, body), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["related-topics"], [])
            self.assertNotIn("your thread about", body)
            self.assertNotIn("your thread about", result.preview_text)
            self.assertIn("rough night of sleep", body)

    # ── one file per eddy, appended per checkpoint ───────────────────

    async def test_file_created_then_appended_on_second_checkpoint(self) -> None:
        llm = AsyncMock(side_effect=[RELATION_RESPONSE, NO_RELATION_RESPONSE])
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm):
                first = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )
                # Retitled eddies must keep appending to the same file.
                with patch(
                    "story_notes._resolve_thread_title", return_value="Renamed eddy"
                ):
                    second = await story_notes.write_eddy_note(
                        CHANNEL_ID, HISTORY, trigger="manual", since_index=2
                    )

            self.assertEqual(first.note_path, second.note_path)
            entries = _parse_entries(first.note_path.read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0][0]["trigger"], "idle")
            self.assertEqual(entries[1][0]["trigger"], "manual")
            self.assertIn("rough night of sleep", entries[0][1])
            self.assertIn("packing list", entries[1][1])

    # ── atomic write path + per-eddy lock ────────────────────────────

    async def test_note_write_goes_through_atomic_path(self) -> None:
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        real_atomic_write = atomic_io.atomic_write_text
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm) as stack:
                spy = stack.enter_context(
                    patch("story_notes.atomic_write_text", side_effect=real_atomic_write)
                )
                stack.enter_context(
                    patch.object(
                        Path,
                        "write_text",
                        side_effect=AssertionError("direct write_text on the note file"),
                    )
                )
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )
                spy.assert_called_once()
                self.assertEqual(Path(spy.call_args.args[0]), result.note_path)

            self.assertIn("rough night of sleep", result.note_path.read_text(encoding="utf-8"))

    async def test_append_path_holds_per_eddy_lock(self) -> None:
        """m4: discovery + append happen under a channel-id-keyed lock, so two
        concurrent first checkpoints cannot fork the eddy's note file. This
        test fails if the locking is removed."""
        llm = AsyncMock(return_value=RELATION_RESPONSE)
        entered: list[Path] = []
        real_lock = atomic_io.file_lock

        @contextmanager
        def spy_lock(path):
            entered.append(Path(str(path)))
            with real_lock(path):
                yield

        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp)
            with self._patched(tmp, llm) as stack:
                stack.enter_context(patch("story_notes.file_lock", spy_lock))
                await story_notes.write_eddy_note(CHANNEL_ID, HISTORY, trigger="idle")

            eddy_lock_key = Path(tmp) / "story" / "eddies" / str(CHANNEL_ID)
            self.assertIn(eddy_lock_key, entered)

    # ── front matter robustness (yaml-safe values) ───────────────────

    async def test_front_matter_survives_special_characters(self) -> None:
        llm = AsyncMock(
            return_value=_response(
                HELD_SLEEP,
                "This conversation touches your thread about budget 2026.",
                ["budget 2026"],
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            _write_alive(tmp, threads=("budget: 2026 #planning",), intentions=())
            with self._patched(tmp, llm) as stack:
                stack.enter_context(
                    patch(
                        "story_notes._resolve_thread_title",
                        return_value='Trip: "plans" #1',
                    )
                )
                result = await story_notes.write_eddy_note(
                    CHANNEL_ID, HISTORY, trigger="idle"
                )

            # Must parse cleanly despite ':', '#', and quotes in values.
            (front, _), = _parse_entries(result.note_path.read_text(encoding="utf-8"))
            self.assertEqual(front["title"], 'Trip: "plans" #1')
            self.assertEqual(front["related-topics"], ["budget: 2026 #planning"])
            self.assertEqual(front["thread"], str(CHANNEL_ID))


if __name__ == "__main__":
    unittest.main()
