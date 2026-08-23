"""Durable artifacts in a multi-member space must not carry verdicts.

The conduct file governs what the witness *says*. It is not read by the note
composer or the title generator, so the heavy-moments rule and the label ban
stopped at the reply boundary while the record kept producing exactly what the
reply was forbidden to produce. These tests pin the rules to the components
that actually emit the durable artifact.
"""

import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import eddy_spawn
import mage
from story_notes import _SYSTEM_PROMPT, _WITNESS_SYSTEM_PROMPT


class WitnessNotePromptTests(unittest.TestCase):
    def test_witness_prompt_bans_labels_in_anything_persisted(self) -> None:
        for term in ("gaslighting", "toxic", "triangulation", "narcissistic"):
            self.assertIn(term, _WITNESS_SYSTEM_PROMPT.lower())
        self.assertIn("not in the themes", _WITNESS_SYSTEM_PROMPT.lower())

    def test_witness_prompt_carries_heavy_moment_restraint(self) -> None:
        lowered = _WITNESS_SYSTEM_PROMPT.lower()
        self.assertIn("shorter and plainer, not deeper", lowered)
        self.assertIn("who is doing what", lowered)

    def test_proposed_themes_must_name_subject_not_verdict(self) -> None:
        # Was "never a verdict on a member" until 2026-08-08. Wrong class:
        # every live violation was a verdict about someone who is *not* a
        # member, or about the situation, so the rule read as satisfied while
        # the shared root filled with "distinguishing avoidance from active
        # appeasement" and its neighbours. The rule now refuses the shape,
        # whoever it lands on.
        self.assertIn("never a conclusion about how anyone behaves",
                      _WITNESS_SYSTEM_PROMPT)
        self.assertIn("not only the people in this space", _WITNESS_SYSTEM_PROMPT)

    def test_solo_prompt_also_carries_the_label_ban_and_hot_moment_rule(self) -> None:
        # Inverted 2026-08-10. This test previously asserted the opposite:
        # the solo prompt was deliberately exempt, on the reasoning that a
        # practitioner's private processing surface composts by design.
        #
        # That reasoning holds for someone processing their own material. It
        # fails for a solo root whose sustained subject is a third party — the
        # composting argument protects the practitioner's own bad hours and
        # licenses nothing about writing a diagnosis of a person who is not in
        # the room. Measured in a live hosted river: a note composed from an
        # acute conversation about two absent people, with no label ban and no
        # heavy-moment restraint reaching it, because both rules lived behind
        # the cardinality branch.
        self.assertIn("wound with an address", _SYSTEM_PROMPT)
        for term in ("gaslighting", "toxic", "narcissistic", "manipulative"):
            self.assertIn(term, _SYSTEM_PROMPT.lower())
        self.assertIn("shorter and plainer, not deeper", _SYSTEM_PROMPT.lower())

    def test_label_ban_protects_people_outside_the_conversation(self) -> None:
        # The class is any person the note could name, not the participants.
        for prompt in (_SYSTEM_PROMPT, _WITNESS_SYSTEM_PROMPT):
            self.assertIn("not in the conversation", prompt.lower())


class NeutralTitlingTests(unittest.TestCase):
    def _generate(self, *, neutral: bool) -> str:
        captured = {}

        async def fake_chat(system, messages, **kwargs):
            captured["content"] = messages[0]["content"]
            return "a title"

        with patch.object(eddy_spawn, "chat_ollama", fake_chat):
            asyncio.run(eddy_spawn.generate_topic("some content", neutral=neutral))
        return captured["content"]

    def test_default_titling_is_unchanged(self) -> None:
        self.assertNotIn("Several people share this space", self._generate(neutral=False))

    def test_neutral_titling_names_the_subject_not_the_stance(self) -> None:
        prompt = self._generate(neutral=True)
        self.assertIn("Title the SUBJECT, never the stance", prompt)
        self.assertIn("Name no one as the cause of anything", prompt)


class TitlingCallSiteTests(unittest.TestCase):
    """Every path that names a thread must decide neutrality. Name the class.

    The 07-29 deploy tested the prompt and the cardinality helper and no call
    site, so it read as shipped while three of six titling paths never passed
    ``neutral=`` at all — including ``handle_eddy_first_message``, the eddy
    bar's normal route. Measured 2026-08-09: ten stance- or person-shaped
    titles landed in a two-member channel in the eleven days *after* the fix.
    A guard that does not enumerate its own class passes by finding nothing.
    """

    #: Call sites that resolve neutrality some way other than a keyword
    #: literal at the call, with the reason each is exempt.
    _EXEMPT = {
        # Titles come from a fetched article, not from anyone's account of
        # anyone — a different hazard, handled by should_rename_thread_from_fetch.
        ("link_read.py", "maybe_refine_thread_name_from_fetch"),
    }

    def _call_sites(self):
        import ast
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        found = []
        for path in sorted(root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name != "generate_topic":
                    continue
                kwargs = {kw.arg for kw in node.keywords}
                found.append((path.name, node.lineno, "neutral" in kwargs))
        return found

    def test_every_generate_topic_call_resolves_neutrality(self) -> None:
        sites = self._call_sites()
        self.assertTrue(sites, "positive control: the scan found no call sites at all")
        missing = [(f, ln) for f, ln, has in sites if not has]
        self.assertEqual(
            missing, [],
            "these titling paths never decide neutrality, so a shared space "
            f"gets stance titles from them: {missing}",
        )

    def test_scan_would_catch_a_bare_call(self) -> None:
        # Negative control: the scan must fail on the shape it exists to find.
        import ast

        tree = ast.parse("await generate_topic(content)")
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
        self.assertNotIn("neutral", {kw.arg for kw in call.keywords})


class SharedSpaceCardinalityTests(unittest.TestCase):
    def test_two_member_space_is_shared(self) -> None:
        with patch.object(mage, "_get_channel_mage", return_value="family"), patch.object(
            mage, "_MAGE_REGISTRY", {"spaces": {"family": {"members": ["a", "b"]}}}
        ):
            self.assertTrue(mage.channel_is_shared_space(123))

    def test_single_member_space_is_not_shared(self) -> None:
        with patch.object(mage, "_get_channel_mage", return_value="solo"), patch.object(
            mage, "_MAGE_REGISTRY", {"spaces": {"solo": {"members": ["a"]}}}
        ):
            self.assertFalse(mage.channel_is_shared_space(123))

    def test_personal_river_is_not_shared(self) -> None:
        with patch.object(mage, "_get_channel_mage", return_value="kermit"), patch.object(
            mage, "_MAGE_REGISTRY", {"spaces": {}, "mages": {"kermit": {}}}
        ):
            self.assertFalse(mage.channel_is_shared_space(123))

    def test_unmapped_channel_is_not_shared(self) -> None:
        with patch.object(mage, "_get_channel_mage", return_value=None):
            self.assertFalse(mage.channel_is_shared_space(999))


if __name__ == "__main__":
    unittest.main()
