"""Carried context ages honestly and names its author (INT-047 slices 2-3).

Two mechanisms carry between eddies and they are not the same kind of claim.

The checkpoint one-liner asserts *recency* — "where we left off". It does not
need consent, because it claims nothing is ongoing; it needs to stop presenting
a six-day-old moment as though the practitioner had just been there.

Alive threads assert the *present* — "this is in motion". They need consent,
and in a shared space they need an author, or a theme one member confirmed is
recited into the other's eddies as the room's own (INT-040, one layer below
the prose).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import continuity_engine as ce
import mage


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "ana": {
                "practice_dir": f"{tmp}/ana",
                "address": "Ana",
                "discord_id": "111",
            },
            "ben": {
                "practice_dir": f"{tmp}/ben",
                "address": "Ben",
                "discord_id": "222",
            },
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["ana", "ben"],
            },
        },
        "channels": {},
    }


NOW = datetime(2026, 7, 29, 12, 0, 0).astimezone()


class CheckpointAgeTests(unittest.TestCase):
    """Slice 2 — the line ages in the copy rather than lying about recency."""

    def test_fresh_line_is_unqualified(self) -> None:
        self.assertEqual(
            ce._checkpoint_age_phrase((NOW - timedelta(minutes=20)).isoformat(), NOW),
            "",
        )

    def test_hours_are_named(self) -> None:
        self.assertEqual(
            ce._checkpoint_age_phrase((NOW - timedelta(hours=5)).isoformat(), NOW),
            " (5 hours ago)",
        )

    def test_yesterday_reads_as_yesterday(self) -> None:
        self.assertEqual(
            ce._checkpoint_age_phrase((NOW - timedelta(hours=30)).isoformat(), NOW),
            " (yesterday)",
        )

    def test_days_are_named(self) -> None:
        self.assertEqual(
            ce._checkpoint_age_phrase((NOW - timedelta(days=6)).isoformat(), NOW),
            " (6 days ago)",
        )

    def test_very_old_is_dropped(self) -> None:
        self.assertIsNone(
            ce._checkpoint_age_phrase((NOW - timedelta(days=45)).isoformat(), NOW)
        )

    def test_unstamped_legacy_line_renders_unqualified(self) -> None:
        """Lines written before the stamp existed must not vanish or gain a lie."""
        self.assertEqual(ce._checkpoint_age_phrase(None, NOW), "")
        self.assertEqual(ce._checkpoint_age_phrase("not-a-date", NOW), "")

    def test_block_qualifies_an_aged_line(self) -> None:
        # render_substrate_block reads the live clock, so anchor on it — a
        # fixed NOW here silently drifts by one day as the day advances.
        live = datetime.now().astimezone()
        data = ce.compose_current(dialogue_model="gemma4:31b")
        data["last_checkpoint_one_liner"] = "You were mapping the birthday plan."
        data["last_checkpoint_at"] = (live - timedelta(days=3, hours=1)).isoformat()
        block = ce.render_substrate_block(data)
        self.assertIn("Last checkpoint (3 days ago): You were mapping", block)

    def test_block_drops_a_stale_line(self) -> None:
        live = datetime.now().astimezone()
        data = ce.compose_current(dialogue_model="gemma4:31b")
        data["last_checkpoint_one_liner"] = "Ancient history."
        data["last_checkpoint_at"] = (live - timedelta(days=90)).isoformat()
        self.assertNotIn("Last checkpoint", ce.render_substrate_block(data))

    def test_stamp_survives_recomposition(self) -> None:
        """The packet rewrites current.yaml; the age must not reset to now."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                pd = f"{tmp}/ana"
                ce.set_last_checkpoint(pd, "You were mapping the birthday plan.")
                stamped = (ce.read_current(pd) or {}).get("last_checkpoint_at")
                self.assertTrue(stamped)
                ce.render_substrate_packet(pd)
                self.assertEqual(
                    (ce.read_current(pd) or {}).get("last_checkpoint_at"), stamped
                )


class ThreadAttributionTests(unittest.TestCase):
    """Slice 3 — a shared room names who put each theme in motion."""

    def test_confirmed_by_is_stored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = ce.add_active_thread(tmp, "the birthday plan", confirmed_by="Ben")
            self.assertEqual(t["confirmed_by"], "Ben")

    def test_first_confirmer_is_preserved_on_refresh(self) -> None:
        """Whoever put it in motion keeps it — same rule as ``since``."""
        with tempfile.TemporaryDirectory() as tmp:
            ce.add_active_thread(tmp, "the birthday plan", confirmed_by="Ben")
            t = ce.add_active_thread(tmp, "the birthday plan", confirmed_by="Ana")
            self.assertEqual(t["confirmed_by"], "Ben")

    def test_unattributed_thread_renders_as_before(self) -> None:
        alive = {"active_threads": [{"id": "a", "label": "the plan", "tone": "active"}]}
        self.assertIn(
            "(1) the plan — active", ce.render_alive_headers(alive, attribute=True)
        )

    def test_personal_root_does_not_name_anyone(self) -> None:
        """A solo river has one referent; attribution would be noise."""
        alive = {
            "active_threads": [
                {"id": "a", "label": "the plan", "tone": "active", "confirmed_by": "Ana"}
            ]
        }
        self.assertNotIn("Ana", ce.render_alive_headers(alive))

    def test_shared_root_names_the_confirmer(self) -> None:
        alive = {
            "active_threads": [
                {
                    "id": "a",
                    "label": "the birthday plan",
                    "tone": "active",
                    "confirmed_by": "Ben",
                }
            ]
        }
        self.assertIn(
            "(1) the birthday plan — Ben, active",
            ce.render_alive_headers(alive, attribute=True),
        )

    def test_no_thread_reaches_a_shared_rooms_turn_attributed_or_not(self) -> None:
        """Attribution was the fix for carrying threads into a shared room.

        Retrieval replaced the carry itself (`what-a-shared-room-remembers.md`
        §4/§9), so the room's memory is its own attributed eddy notes and the
        header line is gone. `confirmed_by` is still recorded — it is what
        distinguishes a member's choice from an inference, and it earns the
        long TTL — but it no longer has a rendering path to defend.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.add_active_thread(
                    f"{tmp}/family", "the birthday plan", confirmed_by="Ben"
                )
                packet = ce.render_substrate_packet(f"{tmp}/family")
                self.assertNotIn("the birthday plan", packet)
                self.assertNotIn("Ben", packet)
                stored = ce.list_active_threads(f"{tmp}/family")[0]
                self.assertEqual(stored["confirmed_by"], "Ben")

    def test_packet_does_not_attribute_in_a_personal_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.add_active_thread(
                    f"{tmp}/ana", "the birthday plan", confirmed_by="Ana"
                )
                self.assertNotIn(
                    "— Ana", ce.render_substrate_packet(f"{tmp}/ana")
                )

    def test_firewall_holds_with_attribution(self) -> None:
        """The name must read as a name, not leak the layer it came from."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.add_active_thread(
                    f"{tmp}/family", "the birthday plan", confirmed_by="Ben"
                )
                block = ce.render_substrate_packet(f"{tmp}/family").lower()
                for term in ("confirmed_by", "alive.yaml", "active_threads"):
                    self.assertNotIn(term, block)


class ConfirmAttributionTests(unittest.TestCase):
    """The Keep press carries the presser's name into durable state."""

    def test_keep_records_who_pressed(self) -> None:
        import continuity_confirm as cc

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                cc.apply_keep_themes(
                    f"{tmp}/family", ["the birthday plan"], confirmed_by="Ben"
                )
                threads = ce.list_active_threads(f"{tmp}/family")
                self.assertEqual(threads[0]["confirmed_by"], "Ben")

    def test_address_resolves_from_discord_id(self) -> None:
        import continuity_confirm as cc

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                user = MagicMock()
                user.id = 222
                self.assertEqual(cc.address_for_user(user), "Ben")

    def test_unregistered_confirmer_is_left_unnamed(self) -> None:
        """A missing name is honest; an invented one lands in durable state."""
        import continuity_confirm as cc

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                user = MagicMock()
                user.id = 999
                self.assertIsNone(cc.address_for_user(user))


if __name__ == "__main__":
    unittest.main()
