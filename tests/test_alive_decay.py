"""The alive layer holds itself: it fills without being asked and empties on its own.

Audited 2026-08-05 across eight practice roots. The layer had a correct writer,
a correct honesty gate, and three live readers — and one unreachable stage
between them. ``add_active_thread`` was reachable only via the Keep-these
surface, offered after ``!checkpoint`` and ``!release`` and nowhere else; both
are typed commands. 106 of 112 real checkpoints fired on idle, and 32 of the
last 32 did, so nothing had entered the layer in three weeks.

The consequence was worse than the layer not existing. Where no ``alive.yaml``
was present the composer said the true thing — *nothing in motion, do not
invent a connection* — and 64 of 64 entries in one root came back clean. In the
two roots that had ever used the feature, every conversation was matched
against a frozen list: 11 of ~18 entries in one of them tagged to the same
three-week-old sleep routine.

So the two halves are one mechanism and are tested together: automatic
promotion without decay would fill the layer with three themes per checkpoint
and never empty it, and decay without promotion is what already exists.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import continuity_engine as ce
import story_notes


INFERRED_TTL = ce.INFERRED_THREAD_TTL_DAYS


def _now() -> datetime:
    """A frozen clock, and every read in this file must be told about it.

    ``read_alive`` prunes on read. Until 2026-08-08 it did so against the real
    calendar with no way to say otherwise, so these fixtures aged in wall-clock
    time and the file passed only while the real date stayed close enough to
    this one — a test that expired rather than failed.
    """
    return datetime(2026, 8, 5, 12, 0).astimezone()


def _days_ago(n: int) -> str:
    return (_now() - timedelta(days=n)).strftime("%Y-%m-%d")


class PruneTests(unittest.TestCase):
    def test_an_inferred_thread_expires_after_its_ttl(self) -> None:
        threads = [
            {"id": "a", "label": "a", "source": "inferred",
             "last_seen": _days_ago(ce.INFERRED_THREAD_TTL_DAYS + 1)},
        ]
        self.assertEqual(ce.prune_threads(threads, _now()), [])

    def test_a_confirmed_thread_outlives_the_inferred_ttl(self) -> None:
        """A member said "keep this in mind" — it should not need repeating weekly."""
        threads = [
            {"id": "a", "label": "a", "source": "confirmed",
             "last_seen": _days_ago(ce.INFERRED_THREAD_TTL_DAYS + 1)},
        ]
        self.assertEqual(len(ce.prune_threads(threads, _now())), 1)

    def test_a_confirmed_thread_still_expires_eventually(self) -> None:
        threads = [
            {"id": "a", "label": "a", "source": "confirmed",
             "last_seen": _days_ago(ce.CONFIRMED_THREAD_TTL_DAYS + 1)},
        ]
        self.assertEqual(ce.prune_threads(threads, _now()), [])

    def test_legacy_threads_age_from_since(self) -> None:
        """The frozen roots carried no last_seen; `since` is the honest fallback."""
        threads = [{"id": "a", "label": "a", "since": _days_ago(19)}]
        self.assertEqual(ce.prune_threads(threads, _now()), [])

    def test_an_undated_thread_is_kept_not_guessed_at(self) -> None:
        """Unmeasurable is not the same as stale — dropping it would invent an age."""
        threads = [{"id": "a", "label": "a"}]
        self.assertEqual(len(ce.prune_threads(threads, _now())), 1)

    def test_the_list_is_capped_newest_first(self) -> None:
        threads = [
            {"id": str(i), "label": str(i), "source": "inferred",
             "last_seen": _days_ago(i % ce.INFERRED_THREAD_TTL_DAYS)}
            for i in range(20)
        ]
        kept = ce.prune_threads(threads, _now())
        self.assertEqual(len(kept), ce.MAX_ACTIVE_THREADS)
        stamps = [t["last_seen"] for t in kept]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_reading_prunes_even_when_nothing_writes(self) -> None:
        """The failure being repaired: a layer that only prunes on write stays
        frozen exactly when nothing is writing it."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            ce.write_alive(root, {
                "version": 1,
                "active_threads": [
                    {"id": "old", "label": "old", "since": _days_ago(19)},
                    {"id": "new", "label": "new", "source": "inferred",
                     "last_seen": _days_ago(1)},
                ],
                "intention_snapshot": [],
            })
            labels = [t["label"] for t in (ce.read_alive(root, _now()) or {})["active_threads"]]
            self.assertEqual(labels, ["new"])


class ReinforcementTests(unittest.TestCase):
    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "state").mkdir()
        return root

    def test_seeing_a_theme_again_refreshes_it(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            ce.add_active_thread(root, "a topic", source="inferred",
                                 now=_now() - timedelta(days=5))
            ce.add_active_thread(root, "a topic", source="inferred", now=_now())
            threads = (ce.read_alive(root, _now()) or {})["active_threads"]
            self.assertEqual(len(threads), 1, "reinforcement must not duplicate")
            self.assertEqual(threads[0]["last_seen"], _now().strftime("%Y-%m-%d"))
            self.assertEqual(threads[0]["since"],
                             (_now() - timedelta(days=5)).strftime("%Y-%m-%d"))

    def test_a_theme_returned_to_after_its_ttl_keeps_its_start_date(self) -> None:
        """The decay drops the thread; it must not drop when it began.

        `!fresh` prints *since <date>*. Before 2026-08-08 a theme with a slower
        cadence than its TTL came back as a brand-new thread, so a member was
        told that something they had circled for months began this morning.
        Mage's call: "in motion" means when they first raised it.
        """
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            long_ago = _now() - timedelta(days=INFERRED_TTL + 1)
            ce.add_active_thread(root, "a topic", source="inferred", now=long_ago)
            ce.add_active_thread(root, "a topic", source="inferred", now=_now())
            threads = (ce.read_alive(root, _now()) or {})["active_threads"]
            self.assertEqual(len(threads), 1)
            self.assertEqual(threads[0]["since"], long_ago.strftime("%Y-%m-%d"))
            self.assertEqual(threads[0]["last_seen"], _now().strftime("%Y-%m-%d"),
                             "last_seen stays the decay clock")

    def test_the_origin_is_the_earliest_date_not_the_latest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            first = _now() - timedelta(days=INFERRED_TTL * 3)
            middle = _now() - timedelta(days=INFERRED_TTL + 1)
            ce.add_active_thread(root, "a topic", source="inferred", now=first)
            ce.add_active_thread(root, "a topic", source="inferred", now=middle)
            ce.add_active_thread(root, "a topic", source="inferred", now=_now())
            threads = (ce.read_alive(root, _now()) or {})["active_threads"]
            self.assertEqual(threads[0]["since"], first.strftime("%Y-%m-%d"))

    def test_origins_outlive_the_seven_thread_cap(self) -> None:
        """The shelf holds 7; the reason a theme is old must survive the churn."""
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            first = _now() - timedelta(days=INFERRED_TTL * 2)
            ce.add_active_thread(root, "the old one", source="inferred", now=first)
            # A day behind, so the return wins the cap's sort on its own merit
            # rather than on how ties happen to break.
            yesterday = _now() - timedelta(days=1)
            for i in range(ce.MAX_ACTIVE_THREADS + 3):
                ce.add_active_thread(root, f"filler {i}", source="inferred",
                                     now=yesterday)
            labels = [t["label"] for t in ce.list_active_threads(root, _now())]
            self.assertNotIn("the old one", labels, "precondition: it fell off")
            ce.add_active_thread(root, "the old one", source="inferred", now=_now())
            back = [t for t in ce.list_active_threads(root, _now())
                    if t["label"] == "the old one"]
            self.assertEqual(len(back), 1)
            self.assertEqual(back[0]["since"], first.strftime("%Y-%m-%d"))

    def test_the_origins_map_is_capped(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            for i in range(ce.MAX_THREAD_ORIGINS + 20):
                ce.add_active_thread(root, f"topic {i}", source="inferred", now=_now())
            origins = (ce.read_alive(root, _now()) or {})["thread_origins"]
            self.assertLessEqual(len(origins), ce.MAX_THREAD_ORIGINS)

    def test_confirming_upgrades_an_inferred_thread_in_place(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            ce.add_active_thread(root, "a topic", source="inferred", now=_now())
            ce.add_active_thread(root, "a topic", source="confirmed", now=_now())
            threads = (ce.read_alive(root, _now()) or {})["active_threads"]
            self.assertEqual(len(threads), 1)
            self.assertEqual(threads[0]["source"], "confirmed")

    def test_a_later_inference_never_demotes_a_members_choice(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            ce.add_active_thread(root, "a topic", source="confirmed", now=_now())
            ce.add_active_thread(root, "a topic", source="inferred", now=_now())
            threads = (ce.read_alive(root, _now()) or {})["active_threads"]
            self.assertEqual(threads[0]["source"], "confirmed")


class PromotionTests(unittest.TestCase):
    """The reader for proposed-themes that the write-only audit kept missing."""

    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "state").mkdir()
        return root

    def test_an_idle_checkpoint_puts_themes_in_motion(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            story_notes._promote_proposed_themes(
                root, ["shifting from letters to chronicles"], "idle"
            )
            labels = [t["label"] for t in ce.list_active_threads(root)]
            self.assertIn("shifting from letters to chronicles", labels)

    def test_promoted_themes_are_marked_inferred_not_chosen(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            story_notes._promote_proposed_themes(root, ["a theme"], "idle")
            self.assertEqual(ce.list_active_threads(root)[0]["source"], "inferred")

    def test_backfill_never_resurrects_finished_threads(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._root(tmp)
            story_notes._promote_proposed_themes(root, ["an old theme"], "backfill")
            self.assertEqual(ce.list_active_threads(root), [])

    def test_promotion_failure_never_costs_the_note(self) -> None:
        """The note is the record; the alive layer is a side effect of it."""
        self.assertEqual(
            story_notes._promote_proposed_themes(
                Path("/nonexistent/root"), ["a theme"], "idle"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
