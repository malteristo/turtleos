"""The only path by which Spirit can put something into an eddy.

Everything here is about refusing. The endpoint holds a live Discord client and
writes into a practitioner-visible channel, so the interesting assertions are the
ones that say no: not authorized, not a craft eddy, not a valid target condition.

The craft gate gets a positive control of its own. A gate that returned False for
every channel would pass every "must refuse" test in this file while making the
endpoint useless — the fourth time this week that a check saying no has looked
identical to a check working.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web

import intake_server
from core import craft_readiness as cr

CRAFT_PARENT = 101
THREAD = 102
CONDITION = "a channel-primitives section exists in the spec and the tests name it"


def _request(app, payload, *, remote="127.0.0.1"):
    req = MagicMock()
    req.app = app
    req.remote = remote
    req.headers = {}
    req.json = AsyncMock(return_value=payload)
    return req


class CraftWriteEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self._tmp.name)
        self.thread = MagicMock()
        self.thread.id = THREAD
        self.thread.parent_id = CRAFT_PARENT
        self.thread.send = AsyncMock()
        client = MagicMock()
        client.get_channel.return_value = self.thread
        self.app = {"discord_client": client}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _patches(self, *, craft=True):
        return (
            patch("mage.get_runtime_dir", return_value=str(self.runtime)),
            patch("mage.uses_craft_surface", return_value=craft),
        )

    async def _call(self, handler, payload, *, craft=True, remote="127.0.0.1"):
        started = [p for p in self._patches(craft=craft)]
        for p in started:
            p.start()
        try:
            return await handler(_request(self.app, payload, remote=remote))
        finally:
            for p in reversed(started):
                p.stop()

    # --- refusals ---------------------------------------------------------

    async def test_a_remote_caller_is_refused(self) -> None:
        """Local-only by the same rule as /shell — no new secret, no exposure."""
        resp = await self._call(
            intake_server.handle_craft_ready,
            {"thread_id": THREAD, "target_condition": CONDITION},
            remote="203.0.113.7",
        )
        self.assertEqual(resp.status, 403)
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    async def test_a_non_craft_thread_is_refused(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            await self._call(
                intake_server.handle_craft_ready,
                {"thread_id": THREAD, "target_condition": CONDITION},
                craft=False,
            )
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    async def test_a_missing_thread_id_is_refused(self) -> None:
        for bad in ({}, {"thread_id": ""}, {"thread_id": "not-a-number"}):
            with self.subTest(payload=bad):
                with self.assertRaises(web.HTTPBadRequest):
                    await self._call(intake_server.handle_craft_ready, bad)

    async def test_the_gate_still_refuses_a_label(self) -> None:
        """The endpoint does not get its own weaker copy of the target-condition rule."""
        resp = await self._call(
            intake_server.handle_craft_ready, {"thread_id": THREAD, "target_condition": "do it"}
        )
        self.assertEqual(resp.status, 422)
        self.assertIsNone(cr.state_of(self.runtime, THREAD))
        self.thread.send.assert_not_awaited()

    async def test_a_gap_is_required(self) -> None:
        resp = await self._call(intake_server.handle_craft_gap, {"thread_id": THREAD, "gap": " "})
        self.assertEqual(resp.status, 422)
        self.thread.send.assert_not_awaited()

    # --- the happy paths --------------------------------------------------

    async def test_ready_proposes_and_posts_the_confirm(self) -> None:
        with patch("craft_ready_ui.offer_ready_confirm", new=AsyncMock(return_value=True)) as offer:
            resp = await self._call(
                intake_server.handle_craft_ready,
                {"thread_id": THREAD, "target_condition": CONDITION, "evidence": "he agreed"},
            )
        self.assertEqual(resp.status, 200)
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), CONDITION)
        offer.assert_awaited_once()

    async def test_a_proposal_is_still_not_readiness(self) -> None:
        """Spirit's hand, his press. The endpoint must not be able to confirm."""
        with patch("craft_ready_ui.offer_ready_confirm", new=AsyncMock(return_value=True)):
            await self._call(
                intake_server.handle_craft_ready,
                {"thread_id": THREAD, "target_condition": CONDITION},
            )
        self.assertEqual(cr.list_by_state(self.runtime, cr.READY), [])

    async def test_gap_refuses_and_the_eddy_is_told(self) -> None:
        gap = "which channels are primitives and which are instances is undecided"
        resp = await self._call(intake_server.handle_craft_gap, {"thread_id": THREAD, "gap": gap})
        self.assertEqual(resp.status, 200)
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.REFUSED)
        self.thread.send.assert_awaited_once()
        self.assertIn(gap, self.thread.send.await_args.args[0])

    async def test_a_posted_gap_is_recorded_as_posted(self) -> None:
        """A refusal reached two ways must not be described one way."""
        await self._call(
            intake_server.handle_craft_gap,
            {"thread_id": THREAD, "gap": "the target is undecided in the thread"},
        )
        self.assertIn("gap_posted_at", cr.entry_for(self.runtime, THREAD))

    async def test_a_failed_send_is_not_recorded_as_posted(self) -> None:
        """The same lie in the other direction."""
        self.thread.send = AsyncMock(side_effect=RuntimeError("discord down"))
        with self.assertRaises(RuntimeError):
            await self._call(
                intake_server.handle_craft_gap, {"thread_id": THREAD, "gap": "a real gap here"}
            )
        entry = cr.entry_for(self.runtime, THREAD)
        self.assertEqual(entry["state"], cr.REFUSED)
        self.assertNotIn("gap_posted_at", entry)

    async def test_no_client_in_this_process_is_a_503_not_a_crash(self) -> None:
        self.app["discord_client"] = None
        with self.assertRaises(web.HTTPServiceUnavailable):
            await self._call(intake_server.handle_craft_gap, {"thread_id": THREAD, "gap": "a gap"})

    # --- cooling ----------------------------------------------------------

    async def test_cooling_marks_before_archiving(self) -> None:
        """The order is the safety argument, so it is the thing asserted.

        `close_eddy_from_archive_transition` returns early on `is_eddy_cooled`.
        Archive first and that guard is not yet true, so the handler is free to
        decide *full dissolve* — an LLM essence of a conversation whose result is
        already written down, plus a lifecycle post.
        """
        order: list[str] = []
        self.thread.archived = False
        self.thread.edit = AsyncMock(side_effect=lambda **kw: order.append("archive"))
        with patch("thread_registry.is_eddy_cooled", return_value=False):
            with patch("thread_registry.mark_cooled", side_effect=lambda _t: order.append("cool")):
                resp = await self._call(
                    intake_server.handle_craft_cool,
                    {"thread_id": THREAD, "reason": "outcome shipped in 793c5df"},
                )
        self.assertEqual(resp.status, 200)
        self.assertEqual(order, ["cool", "archive"])

    async def test_cooling_requires_a_reason(self) -> None:
        """An eddy retired with no reason is one that was dropped."""
        with patch("thread_registry.mark_cooled") as cool:
            resp = await self._call(intake_server.handle_craft_cool, {"thread_id": THREAD})
        self.assertEqual(resp.status, 422)
        cool.assert_not_called()

    async def test_a_failed_archive_still_reports_the_cool(self) -> None:
        self.thread.archived = False
        self.thread.edit = AsyncMock(side_effect=RuntimeError("missing permission"))
        with patch("thread_registry.is_eddy_cooled", return_value=False):
            with patch("thread_registry.mark_cooled"):
                resp = await self._call(
                    intake_server.handle_craft_cool,
                    {"thread_id": THREAD, "reason": "outcome shipped"},
                )
        body = json.loads(resp.body.decode())
        self.assertTrue(body["cooled"])
        self.assertFalse(body["archived"])

    async def test_a_non_craft_thread_cannot_be_cooled(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            await self._call(
                intake_server.handle_craft_cool,
                {"thread_id": THREAD, "reason": "done"},
                craft=False,
            )

    # --- revision ---------------------------------------------------------

    async def _make_ready(self):
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)

    async def test_a_refinement_updates_and_tells_the_eddy(self) -> None:
        """A target that moves silently is the defect this fixes, one level up."""
        await self._make_ready()
        sharper = CONDITION + ", and topics are eddies that may graduate"
        resp = await self._call(
            intake_server.handle_craft_revise,
            {"thread_id": THREAD, "target_condition": sharper, "kind": "refine"},
        )
        self.assertEqual(resp.status, 200)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), sharper)
        self.thread.send.assert_awaited_once()
        self.assertIn("sharpened", self.thread.send.await_args.args[0].lower())

    async def test_a_replacement_says_so_in_the_eddy(self) -> None:
        await self._make_ready()
        await self._call(
            intake_server.handle_craft_revise,
            {
                "thread_id": THREAD,
                "target_condition": "the eddy bar renders temperature on the parent",
                "kind": "replace",
            },
        )
        self.assertIn("replaced", self.thread.send.await_args.args[0].lower())
        self.assertFalse(cr.target_survived(cr.entry_for(self.runtime, THREAD)))

    async def test_revising_an_unconfirmed_row_is_refused(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        resp = await self._call(
            intake_server.handle_craft_revise,
            {"thread_id": THREAD, "target_condition": "a different target here"},
        )
        self.assertEqual(resp.status, 422)
        self.thread.send.assert_not_awaited()

    async def test_the_action_gate_still_applies_to_a_machine_revision(self) -> None:
        await self._make_ready()
        resp = await self._call(
            intake_server.handle_craft_revise,
            {"thread_id": THREAD, "target_condition": "write the primitives spec properly"},
        )
        self.assertEqual(resp.status, 422)

    # --- controls ---------------------------------------------------------

    async def test_the_craft_gate_is_actually_consulted(self) -> None:
        """Positive control. A gate that always said no would pass every test above."""
        with patch("mage.get_runtime_dir", return_value=str(self.runtime)):
            with patch("mage.uses_craft_surface", return_value=True) as gate:
                await intake_server._resolve_craft_thread(
                    _request(self.app, {}), THREAD
                )
        gate.assert_called_once_with(CRAFT_PARENT)

    def test_both_routes_are_registered(self) -> None:
        """A handler nothing routes to is a feature with no door."""
        app = intake_server.create_intake_app()
        paths = {str(r.resource) for r in app.router.routes()}
        self.assertTrue(any("/craft/ready" in p for p in paths))
        self.assertTrue(any("/craft/gap" in p for p in paths))
        self.assertTrue(any("/craft/cool" in p for p in paths))
        self.assertTrue(any("/craft/revise" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
