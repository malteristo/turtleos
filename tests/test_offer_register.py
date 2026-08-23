"""Register gate — whether an operational offer is welcome in this conversation.

The fixtures are drawn from the seventeen eddies the working-plan offer
actually fired into between June and August 2026, titles only. One of them was
worth offering to. The other sixteen are the reason this module exists.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import offer_register as reg


class ParseTests(unittest.TestCase):
    def test_operational_only_on_the_exact_word(self) -> None:
        self.assertEqual(reg.parse_register('{"register": "operational"}'), reg.OPERATIONAL)
        self.assertEqual(reg.parse_register('{"register": "OPERATIONAL"}'), reg.OPERATIONAL)

    def test_everything_unrecognised_is_care(self) -> None:
        for raw in (
            '{"register": "care"}',
            '{"register": "unsure"}',
            '{"register": ""}',
            "{}",
            "not json at all",
            "",
            '["operational"]',
            '{"register": null}',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(reg.parse_register(raw), reg.CARE)

    def test_prompt_carries_title_and_truncates_text(self) -> None:
        prompt = reg.build_prompt("x" * 5000, title="a" * 500)
        self.assertIn("a" * 100, prompt)
        self.assertLess(len(prompt), 3000)
        # The instruction that decides every ambiguous case must be present.
        self.assertIn('unsure, answer "care"', prompt)


class ClassifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_text_never_calls_the_model(self) -> None:
        with patch("httpx.AsyncClient") as client:
            self.assertEqual(await reg.classify_register("   "), reg.CARE)
            client.assert_not_called()

    async def test_model_failure_holds_the_offer(self) -> None:
        """Fail-closed. A missed offer is invisible; a misplaced one is not."""
        with patch("httpx.AsyncClient", side_effect=RuntimeError("ollama down")):
            self.assertEqual(
                await reg.classify_register("let's plan the trip"), reg.CARE
            )

    async def _answer(self, register: str) -> str:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(
            return_value={"message": {"content": '{"register": "%s"}' % register}}
        )
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=client):
            return await reg.classify_register("some text", title="a title")

    async def test_operational_answer_allows_the_offer(self) -> None:
        self.assertEqual(await self._answer("operational"), reg.OPERATIONAL)

    async def test_care_answer_holds_the_offer(self) -> None:
        self.assertEqual(await self._answer("care"), reg.CARE)

    async def test_offer_is_welcome_is_true_only_for_operational(self) -> None:
        with patch.object(reg, "classify_register", AsyncMock(return_value=reg.OPERATIONAL)):
            self.assertTrue(await reg.offer_is_welcome("x"))
        with patch.object(reg, "classify_register", AsyncMock(return_value=reg.CARE)):
            self.assertFalse(await reg.offer_is_welcome("x"))


class SeneschalWiringTests(unittest.IsolatedAsyncioTestCase):
    """The gate must sit in the path, and its refusal must be recorded."""

    async def test_care_register_blocks_the_offer_and_is_logged(self) -> None:
        import river_eddy_seneschal as res

        channel = MagicMock()
        channel.id = 4242
        # Failure shape, not the material: the real eddy titles stay in the
        # private practice record. This is the same shape as one of them.
        channel.name = "a family member struggling with adhd daily life"
        channel.parent_id = 1

        recorded: list[tuple] = []
        with patch.object(res, "river_bot_enabled", create=True), patch(
            "prompts.uses_native_turtle_prompt", return_value=True
        ), patch.object(
            res, "_dialogue_history_snapshot", return_value=[], create=True
        ), patch.object(
            res, "home_plan_offer_skip_reason", return_value=None
        ), patch.object(
            res, "_latest_assistant_after_turn", return_value="- a\n- b\n- c", create=True
        ), patch(
            "offer_register.offer_is_welcome", AsyncMock(return_value=False)
        ), patch.object(
            res, "_log_contextual_skip", lambda ch, kind, why: recorded.append((kind, why))
        ), patch.object(
            res, "_record_offer_suppressed", lambda ch, kind, why: recorded.append(("ledger", why))
        ), patch(
            "mage.river_bot_enabled", return_value=True
        ), patch("mage.get_pd", return_value="/tmp/nope"):
            offered = await res.maybe_offer_home_plan_after_turtle_reply(
                channel, practitioner_text="i can't stop crying today"
            )

        self.assertFalse(offered)
        self.assertIn(("home_plan", "care_register"), recorded)
        self.assertIn(("ledger", "care_register"), recorded)


if __name__ == "__main__":
    unittest.main()
