"""The offer path: craft-gated, note-driven, proposal-only, and never fatal.

The two tests that matter most are the negative ones. `_maybe_offer_craft_readiness`
runs inside `checkpoint_session` *after* the eddy note has been written and
*before* the checkpoint anchor advances, so an exception escaping it would turn
a missing suggestion into a lost practice record — the 2026-08-07 defect class,
approached from a new direction. And it must not fire outside craft: a family
river has no forge to be ready for, and a readiness offer landing in one would
be the eddy-bar-in-the-wrong-channel mistake with worse content.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sessions
from core import craft_readiness as cr
from craft_readiness_noticer import Proposal, Reading

THREAD = 4242
CRAFT_PARENT = 101
CONDITION = "a formal specification of channel primitives exists in the spec"


class CraftReadinessOfferTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self._tmp.name)
        self.result = MagicMock()
        self.result.eddy_note.entry_text = "a note long enough to be worth reading " * 8

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _patches(self, *, craft=True, proposal=Reading(proposal=Proposal(CONDITION, "warrants a spec"))):
        thread = MagicMock()
        thread.id = THREAD
        return (
            patch("mage.get_runtime_dir", return_value=str(self.runtime)),
            patch("mage.uses_craft_surface", return_value=craft),
            patch("craft_readiness_noticer.read_note", new=AsyncMock(return_value=proposal)),
            patch("craft_ready_ui.offer_ready_confirm", new=AsyncMock(return_value=True)),
            patch.object(sessions.state, "client", MagicMock(get_channel=lambda _cid: thread)),
        )

    async def _run(self, **kw):
        patches = self._patches(**kw)
        for p in patches:
            p.start()
        try:
            await sessions._maybe_offer_craft_readiness(THREAD, self.result, CRAFT_PARENT)
        finally:
            for p in reversed(patches):
                p.stop()

    async def test_a_craft_eddy_gets_a_proposal_and_an_offer(self) -> None:
        with patch("craft_ready_ui.offer_ready_confirm", new=AsyncMock()) as offer:
            patches = self._patches()[:3] + (
                patch("craft_ready_ui.offer_ready_confirm", new=offer),
                self._patches()[4],
            )
            for p in patches:
                p.start()
            try:
                await sessions._maybe_offer_craft_readiness(THREAD, self.result, CRAFT_PARENT)
            finally:
                for p in reversed(patches):
                    p.stop()
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), CONDITION)
        offer.assert_awaited_once()

    async def test_a_non_craft_eddy_is_never_read(self) -> None:
        """Positive control on the gate: the model is not even asked."""
        with patch("craft_readiness_noticer.read_note", new=AsyncMock()) as read:
            with patch("mage.get_runtime_dir", return_value=str(self.runtime)):
                with patch("mage.uses_craft_surface", return_value=False):
                    await sessions._maybe_offer_craft_readiness(THREAD, self.result, 999)
        read.assert_not_awaited()
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    async def test_a_declined_read_records_nothing(self) -> None:
        await self._run(proposal=Reading())
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    async def test_an_already_confirmed_eddy_is_not_re_read(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        with patch("craft_readiness_noticer.read_note", new=AsyncMock()) as read:
            with patch("mage.get_runtime_dir", return_value=str(self.runtime)):
                with patch("mage.uses_craft_surface", return_value=True):
                    await sessions._maybe_offer_craft_readiness(THREAD, self.result, CRAFT_PARENT)
        read.assert_not_awaited()
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.READY)

    async def test_nothing_escapes_into_the_checkpoint(self) -> None:
        """The checkpoint owns the practice record; this is a suggestion."""
        for boom in (RuntimeError("posting failed"), TimeoutError("gate"), OSError("disk")):
            with self.subTest(exc=type(boom).__name__):
                with patch("mage.get_runtime_dir", side_effect=boom):
                    await sessions._maybe_offer_craft_readiness(
                        THREAD, self.result, CRAFT_PARENT
                    )

    async def test_an_unresolvable_thread_still_records_the_proposal(self) -> None:
        """A proposal that could not be posted is still a proposal Spirit can read."""
        patches = (
            patch("mage.get_runtime_dir", return_value=str(self.runtime)),
            patch("mage.uses_craft_surface", return_value=True),
            patch(
                "craft_readiness_noticer.read_note",
                new=AsyncMock(return_value=Reading(proposal=Proposal(CONDITION, ""))),
            ),
            patch.object(sessions.state, "client", MagicMock(get_channel=lambda _cid: None)),
        )
        for p in patches:
            p.start()
        try:
            await sessions._maybe_offer_craft_readiness(THREAD, self.result, CRAFT_PARENT)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)


class OfferCopyTests(unittest.TestCase):
    def test_the_offer_states_the_target_and_asks(self) -> None:
        import craft_ready_ui

        text = craft_ready_ui.compose_offer_text(CONDITION, "warrants a formal specification")
        self.assertIn(CONDITION, text)
        self.assertIn("warrants a formal specification", text)

    def test_the_offer_survives_missing_evidence(self) -> None:
        import craft_ready_ui

        self.assertIn(CONDITION, craft_ready_ui.compose_offer_text(CONDITION))

    def test_the_offer_kind_is_declared_and_counted(self) -> None:
        """An offer the ledger cannot see is the defect this registry ended."""
        from runtime.offers import counted_kinds, label_for

        self.assertIn("eddy_ready", counted_kinds())
        self.assertTrue(label_for("eddy_ready"))


if __name__ == "__main__":
    unittest.main()
