"""Turtle's claims are Turtle's — never the practitioner's testimony.

INT-041: a hosted practitioner asked Turtle to look over the family channel.
Turtle has no access to that space from her root; it answered anyway, opening
with a staged review gesture and later asserting "sowohl hier als auch im
Familien-Chat". The story layer then wrote that into her permanent record as
"You shared a deep reflection…", and her correction was recorded as her
correcting her own dynamics rather than Turtle retracting an invention.

The transcript was never the problem: ``_speaker_and_body`` labels assistant
turns ``Turtle`` and has done all along, so the speaker boundary reaches the
prompt intact. What was missing was any instruction to keep it.

INT-040 branched on *member* cardinality and gave the multi-member case a full
attribution rule. A solo river has one member and two speakers, so the branch
where Turtle's voice is most easily absorbed — private, second person, warm —
was the only one without one.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

# Stub only when genuinely absent, and never alias discord.ext to the package.
try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import story_daily
import story_notes


class SpeakerBoundaryTests(unittest.TestCase):
    """The wire: the transcript already distinguishes the two speakers."""

    def test_assistant_turns_are_labelled_turtle_in_a_solo_river(self) -> None:
        history = [
            {"role": "user", "content": "Can you look over the family chat?"},
            {"role": "assistant", "content": "Ich schaue mir die Dynamiken an…"},
        ]
        transcript = story_notes._transcript(history, "Ana", None)

        self.assertIn("Ana: Can you look over the family chat?", transcript)
        self.assertIn("Turtle: Ich schaue mir die Dynamiken an", transcript)

    def test_assistant_turns_are_labelled_turtle_in_a_shared_space(self) -> None:
        history = [
            {"role": "user", "content": "[riverhand]: I said this."},
            {"role": "assistant", "content": "Turtle's reading of it."},
        ]
        transcript = story_notes._transcript(
            history, "Family", {"riverhand": "Ana"}
        )

        self.assertIn("Ana: I said this.", transcript)
        self.assertIn("Turtle: Turtle's reading of it.", transcript)

    def test_the_boundary_survives_into_the_prompt(self) -> None:
        history = [
            {"role": "user", "content": "What do you make of it?"},
            {"role": "assistant", "content": "I reviewed the other channel."},
        ]
        prompt = story_notes._build_prompt(history, "Ana", [], "idle", None)

        self.assertIn("Turtle: I reviewed the other channel.", prompt)


class AttributionRuleParityTests(unittest.TestCase):
    """Every prompt that writes a practitioner-facing record carries the rule.

    Stated as an invariant over all record-writing prompts rather than as four
    separate string checks, so that a branch added later fails this test by
    existing rather than by being remembered.
    """

    RECORD_PROMPTS = {
        "eddy note, solo river": story_notes._SYSTEM_PROMPT,
        "eddy note, shared space": story_notes._WITNESS_SYSTEM_PROMPT,
        "daily note, solo river": story_daily._SYSTEM_PROMPT,
        "daily note, shared space": story_daily._WITNESS_SYSTEM_PROMPT,
    }

    def test_every_record_prompt_attributes_turtles_own_claims(self) -> None:
        for name, prompt in self.RECORD_PROMPTS.items():
            with self.subTest(prompt=name):
                self.assertIn(
                    story_notes._TURTLE_VOICE_RULE,
                    prompt,
                    f"{name} can absorb Turtle's claims into the practitioner's "
                    "account (INT-041)",
                )

    def test_every_record_prompt_holds_accounts_as_perception(self) -> None:
        for name, prompt in self.RECORD_PROMPTS.items():
            with self.subTest(prompt=name):
                self.assertIn(story_notes._PERCEPTION_RULE, prompt, name)

    def test_every_record_prompt_binds_who_you_is(self) -> None:
        """Either "you" is banned outright, or it is bound to the practitioner.

        INT-049: the shared prompt banned second person; the solo prompt was
        told to *use* it and never told who it referred to. A practitioner
        discussing someone else's burnout had it written back as his own day —
        "your years within <name>'s family dynamic … her husband and his
        mother" — addressed to the third party. The eddy note it derived from was
        clean third person, so the inversion was created by the synthesis.

        Stated as a disjunction over all four prompts rather than as a check on
        the two solo ones: a subset is a list someone has to remember to add to.
        """
        for name, prompt in self.RECORD_PROMPTS.items():
            with self.subTest(prompt=name):
                bans_second_person = story_notes._NO_SECOND_PERSON_RULE in prompt
                binds_second_person = story_notes._THIRD_PARTY_RULE in prompt
                self.assertTrue(
                    bans_second_person or binds_second_person,
                    f"{name} writes a practitioner-facing record without "
                    "settling who \"you\" refers to (INT-049)",
                )

    def test_the_two_you_rules_are_never_both_present(self) -> None:
        """They contradict: one bans second person, the other requires it."""
        for name, prompt in self.RECORD_PROMPTS.items():
            with self.subTest(prompt=name):
                self.assertFalse(
                    story_notes._NO_SECOND_PERSON_RULE in prompt
                    and story_notes._THIRD_PARTY_RULE in prompt,
                    f"{name} both bans and requires \"you\"",
                )

    def test_the_rule_names_the_source_claim_case(self) -> None:
        """The specific failure that warranted it, not just generic attribution."""
        rule = story_notes._TURTLE_VOICE_RULE.lower()
        self.assertIn("claimed to have", rule)
        self.assertIn("not", rule)
        for verb in ("seen", "read", "reviewed"):
            self.assertIn(verb, rule)


class WithdrawnFromContinuityTests(unittest.TestCase):
    """A defective note stops propagating without being rewritten.

    INT-049: `_RECENT_DAILY_COUNT = 3` feeds recent dailies back into the next
    daily's prompt, so an inverted note is prompt input for three further days
    and can reproduce itself after the rule that caused it is fixed. The note
    itself is left intact — it is the honest record of what was written.
    """

    def _write(self, daily_dir, name: str, frontmatter: str, body: str) -> None:
        (daily_dir / name).write_text(
            f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8"
        )

    def test_a_withdrawn_note_leaves_the_continuity_window(self) -> None:
        import tempfile
        from datetime import date
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            daily = Path(tmp) / "story" / "daily"
            daily.mkdir(parents=True)
            self._write(daily, "2026-07-28.md", "date: '2026-07-28'", "kept text")
            self._write(daily, "2026-07-27.md", "date: '2026-07-27'", "also kept")

            ctx = story_daily._recent_daily_context(Path(tmp), date(2026, 7, 29))
            self.assertIn("kept text", ctx)
            self.assertIn("also kept", ctx)

            self._write(
                daily,
                "2026-07-28.md",
                "date: '2026-07-28'\nwithdrawn: 'INT-049'",
                "kept text",
            )
            ctx = story_daily._recent_daily_context(Path(tmp), date(2026, 7, 29))
            self.assertNotIn("kept text", ctx)
            self.assertIn("also kept", ctx, "withdrawal must not drop other days")

    def test_the_note_itself_is_never_rewritten(self) -> None:
        """Withdrawal is metadata; the prose is left as the record of what was said."""
        import tempfile
        from datetime import date
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            daily = Path(tmp) / "story" / "daily"
            daily.mkdir(parents=True)
            path = daily / "2026-07-28.md"
            self._write(
                daily, "2026-07-28.md", "date: '2026-07-28'\nwithdrawn: 'x'", "the words"
            )
            before = path.read_text(encoding="utf-8")
            story_daily._recent_daily_context(Path(tmp), date(2026, 7, 29))
            self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_malformed_frontmatter_does_not_crash_continuity(self) -> None:
        import tempfile
        from datetime import date
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            daily = Path(tmp) / "story" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-07-28.md").write_text(
                "---\n:::not: valid: yaml:\n---\n\nbody survives\n", encoding="utf-8"
            )
            ctx = story_daily._recent_daily_context(Path(tmp), date(2026, 7, 29))
            self.assertIn("body survives", ctx)


class PractitionerReferentTests(unittest.TestCase):
    """The rule says who "you" is *not*. Nothing said who "you" **is**.

    Fifth face of the ownership law, and the first that is a binding defect
    rather than a missing rule. ``_THIRD_PARTY_RULE`` — *"You" is the
    practitioner and no one else* — has been in both solo prompts since
    INT-049, and ``test_every_record_prompt_binds_who_you_is`` has been green
    the whole time. It checks that the rule is *written*, never that a
    referent is *supplied*.

    Meanwhile ``_transcript`` labels the practitioner's turns with a concrete
    ``mage_name`` while ``_build_prompt`` describes them abstractly as "THE
    PRACTITIONER". The model is left to bind the two itself, and does so
    inconsistently — same root, same morning, one hour apart:

        10:14  "**You** asked Turtle whether the daily notes should shift…"
        11:12  "**<name>** shared two distinct drafts… Turtle responded by…"

    ``story_daily`` then synthesizes over both and inherits the drift, which is
    how an operator's own river came to read *"Today, you followed <name> as he
    stepped back…"* — "you" resolved to Turtle, the observer, so the record of
    his day addressed someone watching him.

    Reported from the running system by the operator, not found by the suite.

    These assert the **assembled prompt**, not the constant: a rule with no
    referent is a reader that does not exist yet.
    """

    MAGE = "Ana"

    def _solo_eddy_prompt(self) -> str:
        return story_notes._build_prompt(
            [
                {"role": "user", "content": "Should daily notes become journals?"},
                {"role": "assistant", "content": "That would make them a chronicle."},
            ],
            self.MAGE,
            ["entwined cognition over utility"],
            "idle",
            None,
        )

    def test_solo_eddy_prompt_names_the_practitioner(self) -> None:
        self.assertIn(
            self.MAGE,
            self._solo_eddy_prompt(),
            'the solo eddy prompt requires "you" but never names who it is',
        )

    def test_solo_eddy_prompt_binds_you_to_the_practitioner(self) -> None:
        """Naming them in the transcript is not binding them to the pronoun."""
        prompt = self._solo_eddy_prompt()
        binding = [
            line
            for line in prompt.splitlines()
            if self.MAGE in line and '"you"' in line.lower()
        ]
        self.assertTrue(
            binding,
            'no line in the solo eddy prompt ties "you" to the named '
            "practitioner — the model is left to infer the referent",
        )

    def test_shared_eddy_prompt_supplies_no_such_binding(self) -> None:
        """The witness family bans "you" outright; binding it would contradict."""
        prompt = story_notes._build_prompt(
            [{"role": "user", "content": "[Ana]: the cats need a sitter"}],
            "family",
            [],
            "idle",
            None,
            names={"ana": "Ana"},
        )
        self.assertNotIn('"you"', prompt.lower())

    def test_solo_daily_prompt_names_the_practitioner(self) -> None:
        from datetime import datetime
        from pathlib import Path

        entry = story_notes.EddyEntry(
            thread="1",
            title="journal entries",
            trigger="idle",
            timestamp=datetime(2026, 8, 5, 10, 14),
            related_topics=[],
            body="Ana asked whether daily notes should become journals.",
            source_path=Path("x.md"),
        )
        prompt = story_daily._build_prompt(
            [entry], "", None, __import__("datetime").date(2026, 8, 5),
            practitioner=self.MAGE,
        )
        self.assertIn(
            self.MAGE,
            prompt,
            "the daily synthesis sees only eddy bodies — if none of them "
            'happens to name the practitioner, "you" has no referent at all',
        )


if __name__ == "__main__":
    unittest.main()
