"""The noticer must be silent more easily than it speaks.

The asymmetry is the design: a missed proposal costs one idle cycle, and a wrong
proposal costs attention at the exact moment the practitioner is deciding what
to work on. So most of these tests assert `None`.

The grounding check gets a positive control of its own. Without one, a broken
`_grounded` that returned False for everything would pass every decline test in
this file and silently turn the noticer off — which is the failure this codebase
has now logged four times: a gate that looks healthy because it says no.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

import craft_readiness_noticer as noticer
from craft_readiness_noticer import Reading

NOTE = (
    "You and Turtle explored how turtleOS vocabulary balances poetic metaphors "
    "with user clarity, deciding to keep River as the agent name while treating "
    "channels by their functional descriptions rather than metaphorical ones. "
    "The conversation evolved into defining channel primitives that bundle "
    "channel structure, Turtle attunement, and River behaviour together. You "
    "agreed that this architecture warrants a formal specification before the "
    "details disperse."
)

CONDITION = "a formal specification of channel primitives exists in the spec"


def _reply(ready=True, condition=CONDITION, evidence="warrants a formal specification",
           missing=""):
    return json.dumps(
        {"ready": ready, "target_condition": condition, "evidence": evidence,
         "missing": missing}
    )


class ParseReplyTests(unittest.TestCase):
    def test_a_grounded_ready_reply_becomes_a_proposal(self) -> None:
        proposal = noticer.parse_reply(_reply(), NOTE)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.target_condition, CONDITION)
        self.assertIn("specification", proposal.evidence)

    def test_not_ready_is_a_decline(self) -> None:
        self.assertIsNone(noticer.parse_reply(_reply(ready=False, condition=""), NOTE))

    def test_ready_must_be_exactly_true(self) -> None:
        """`"true"` and `1` are what a small model returns when it is guessing."""
        for value in ("true", 1, "yes", None):
            with self.subTest(value=value):
                raw = json.dumps({"ready": value, "target_condition": CONDITION})
                self.assertIsNone(noticer.parse_reply(raw, NOTE))

    def test_unparseable_output_is_a_decline_not_a_crash(self) -> None:
        for raw in ("", "   ", "not json", "[]", '{"ready": true', None):
            with self.subTest(raw=raw):
                self.assertIsNone(noticer.parse_reply(raw, NOTE))

    def test_a_label_is_not_a_target_condition(self) -> None:
        self.assertIsNone(noticer.parse_reply(_reply(condition="write spec"), NOTE))

    def test_an_ungrounded_condition_is_dropped(self) -> None:
        """The failure that costs more than silence: fluent, confident, unrelated."""
        invented = "the billing dashboard ships with Stripe webhooks and invoices"
        self.assertIsNone(noticer.parse_reply(_reply(condition=invented), NOTE))

    def test_grounding_does_not_reject_the_notes_own_sentence(self) -> None:
        """Positive control on the grounding check.

        A `_grounded` that always returned False would pass every decline test
        above while turning the noticer off. This is the test that notices.
        """
        self.assertTrue(noticer._grounded(CONDITION, NOTE))
        self.assertFalse(noticer._grounded("stripe webhooks billing invoices", NOTE))

    def test_whitespace_in_the_condition_is_normalised(self) -> None:
        messy = "  a formal specification\n  of channel   primitives exists  "
        proposal = noticer.parse_reply(_reply(condition=messy), NOTE)
        self.assertEqual(
            proposal.target_condition, "a formal specification of channel primitives exists"
        )

    def test_missing_evidence_is_tolerated(self) -> None:
        raw = json.dumps({"ready": True, "target_condition": CONDITION})
        proposal = noticer.parse_reply(raw, NOTE)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.evidence, "")


class ReadingTests(unittest.TestCase):
    """The negative case stops being silence — but only when it is grounded."""

    def test_no_target_but_a_named_delta_becomes_a_spark(self) -> None:
        raw = _reply(
            ready=False,
            condition="",
            evidence="",
            missing="whether channel primitives are relational or thematic is undecided",
        )
        reading = noticer.parse_reading(raw, NOTE)
        self.assertIsNone(reading.proposal)
        self.assertIn("primitives", reading.spark)

    def test_a_delta_is_held_to_a_lower_bar_than_a_target(self) -> None:
        """Structural, not a concession — and the asymmetry is asserted.

        A delta names what the conversation lacks, so the words naming the
        absence are by construction words the note does not contain. The real
        case: "whether channel primitives are relational or thematic is
        undecided" scores 0.33 against a note it is plainly about.
        """
        delta = "whether channel primitives are relational or thematic is undecided"
        self.assertFalse(noticer._grounded(delta, NOTE))
        self.assertTrue(
            noticer._grounded(delta, NOTE, minimum=noticer.MIN_SPARK_GROUNDING_OVERLAP)
        )
        self.assertLess(noticer.MIN_SPARK_GROUNDING_OVERLAP, noticer.MIN_GROUNDING_OVERLAP)

    def test_an_ungrounded_delta_is_dropped(self) -> None:
        """It gets posted into his eddy, so it is held to the target's standard."""
        raw = _reply(ready=False, condition="", evidence="",
                     missing="the Stripe billing webhooks are not wired up yet")
        self.assertEqual(noticer.parse_reading(raw, NOTE).spark, "")

    def test_a_target_wins_over_a_delta(self) -> None:
        """A reading that has both is a reading that found a target."""
        raw = _reply(missing="something is missing here about channel primitives")
        reading = noticer.parse_reading(raw, NOTE)
        self.assertIsNotNone(reading.proposal)
        self.assertEqual(reading.spark, "")

    def test_a_malformed_reply_is_an_empty_reading(self) -> None:
        for raw in ("", "not json", "[]", None):
            with self.subTest(raw=raw):
                reading = noticer.parse_reading(raw, NOTE)
                self.assertIsNone(reading.proposal)
                self.assertEqual(reading.spark, "")

    def test_a_label_is_not_a_delta(self) -> None:
        raw = _reply(ready=False, condition="", evidence="", missing="unclear")
        self.assertEqual(noticer.parse_reading(raw, NOTE).spark, "")


class ReadNoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_thin_note_is_never_sent_to_the_model(self) -> None:
        with patch("llm.chat_ollama_json", new=AsyncMock()) as call:
            reading = await noticer.read_note("too short")
        self.assertIsNone(reading.proposal)
        self.assertEqual(reading.spark, "")
        call.assert_not_awaited()

    async def test_a_full_note_produces_a_proposal(self) -> None:
        with patch("llm.chat_ollama_json", new=AsyncMock(return_value=_reply())):
            reading = await noticer.read_note(NOTE)
        self.assertEqual(reading.proposal.target_condition, CONDITION)
        self.assertEqual(reading.spark, "", "a reading with a target needs no delta")

    async def test_a_model_failure_declines_rather_than_raising(self) -> None:
        """It runs inside the checkpoint that writes the practice record."""
        for boom in (TimeoutError("gate"), RuntimeError("ollama down"), ValueError("x")):
            with self.subTest(exc=type(boom).__name__):
                with patch("llm.chat_ollama_json", new=AsyncMock(side_effect=boom)):
                    reading = await noticer.read_note(NOTE)
                self.assertIsNone(reading.proposal)
                self.assertEqual(reading.spark, "")

    async def test_the_prompt_teaches_state_not_actor(self) -> None:
        """A wire test, and it was bought by a live control rather than reasoning.

        The first version of this prompt produced, from a real eddy note,
        "Kermit reviews specific files ... to verify if they match their
        intended concept" — grounded, fluent, and useless: a target whose actor
        is the practitioner is not a target an autonomous session can meet, it
        is the conversation continuing. Asserting the instruction is in the
        prompt is weaker than asserting the behaviour and is the only half a
        unit test can hold; the behaviour is checked by re-running the live
        control, recorded in design-craft-eddy-temperature.md.
        """
        self.assertIn("STATE OF THE WORLD", noticer.PROMPT)
        self.assertIn("never who performs it", noticer.PROMPT)

    async def test_the_note_is_what_gets_read(self) -> None:
        """Positive control on the prompt: the transcript is not in scope here."""
        with patch("llm.chat_ollama_json", new=AsyncMock(return_value=_reply())) as call:
            await noticer.read_note(NOTE)
        sent = call.await_args.args[0]
        self.assertIn("channel primitives", sent)
        self.assertIn("THE NOTE:", sent)


if __name__ == "__main__":
    unittest.main()
