"""Shared-space synthesis attributes authorship and narrates as witness.

INT-040: story synthesis was single-practitioner by construction — one
mage_name, one second-person "you", no authorship model. In a 2+-member space
it collapsed every member's contribution into one undifferentiated "you", so a
note surfaced to another member re-narrated their writing as his own.

Charter §3.3: branch on member cardinality. One sovereign keeps the intimate
second person; above one member the record narrates in third person with every
turn attributed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import mage
import story_notes


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "kermit": {"practice_dir": f"{tmp}/kermit", "address": "Kermit"},
            "partner": {
                "practice_dir": f"{tmp}/partner",
                "address": "Partner",
                "display_name": "riverhand",
            },
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["kermit", "partner"],
            },
        },
        "channels": {},
    }


SHARED_HISTORY = [
    {"role": "user", "content": "[kermit]: I think we should move the date."},
    {"role": "assistant", "content": "Noted."},
    {"role": "user", "content": "[riverhand]: That doesn't work for me."},
]


class TranscriptAttributionTests(unittest.TestCase):
    def test_shared_space_keeps_speakers_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                names = mage.member_address_map()
            out = story_notes._transcript(SHARED_HISTORY, "Family", names)

        self.assertIn("Kermit: I think we should move the date.", out)
        self.assertIn("Partner: That doesn't work for me.", out)
        self.assertIn("Turtle: Noted.", out)
        # The old renderer produced "Family: [riverhand]: ..." — a double label
        # whose outer frame collapsed both members into one voice.
        self.assertNotIn("Family:", out)
        self.assertNotIn("[riverhand]", out)

    def test_single_member_root_relabels_to_the_sovereign(self) -> None:
        """One reader, one referent — and the raw handle never reaches the prompt."""
        history = [{"role": "user", "content": "[riverhand]: I slept badly."}]
        out = story_notes._transcript(history, "Partner", None)
        self.assertEqual(out, "Partner: I slept badly.")

    def test_unprefixed_turn_falls_back_to_the_root_name(self) -> None:
        history = [{"role": "user", "content": "no prefix here"}]
        self.assertEqual(
            story_notes._transcript(history, "Kermit", None), "Kermit: no prefix here"
        )

    def test_unmapped_handle_passes_through_rather_than_being_invented(self) -> None:
        history = [{"role": "user", "content": "[someone_else]: hello"}]
        out = story_notes._transcript(history, "Family", {"kermit": "Kermit"})
        self.assertEqual(out, "someone_else: hello")


class AliasResolutionTests(unittest.TestCase):
    """Three name spaces — registry key, Discord username, Discord display name
    — reconciled only by discord_id. Live resolution keeps the map curated-free.
    """

    def _client_with(self, uid: int, **attrs) -> MagicMock:
        member = MagicMock()
        for k in ("name", "global_name", "display_name", "nick"):
            setattr(member, k, attrs.get(k))
        guild = MagicMock()
        guild.get_member = lambda i: member if i == uid else None
        client = MagicMock()
        client.guilds = [guild]
        return client

    def test_display_name_resolves_live_from_discord_id(self) -> None:
        registry = {
            "mages": {
                "partner": {"address": "Partner", "discord_id": "77"},
            },
            "spaces": {},
            "channels": {},
        }
        client = self._client_with(
            77, name="riverhand", global_name="riverhand", display_name="riverhand"
        )
        with (
            patch.object(mage, "_MAGE_REGISTRY", registry),
            patch.dict(sys.modules, {"state": MagicMock(client=client)}),
        ):
            names = mage.member_address_map()
        self.assertEqual(names.get("riverhand"), "Partner")

    def test_username_and_nick_both_resolve(self) -> None:
        """Kermit's display name is 'kermit' but his username is 'firlefance'."""
        registry = {
            "mages": {"kermit": {"address": "Kermit", "discord_id": "88"}},
            "spaces": {},
            "channels": {},
        }
        client = self._client_with(
            88, name="firlefance", global_name="kermit", display_name="kermit"
        )
        with (
            patch.object(mage, "_MAGE_REGISTRY", registry),
            patch.dict(sys.modules, {"state": MagicMock(client=client)}),
        ):
            names = mage.member_address_map()
        self.assertEqual(names.get("firlefance"), "Kermit")
        self.assertEqual(names.get("kermit"), "Kermit")

    def test_registry_display_name_overrides_live_lookup(self) -> None:
        registry = {
            "mages": {
                "guest": {
                    "address": "Guest",
                    "discord_id": "99",
                    "display_name": "Guest H",
                }
            },
            "spaces": {},
            "channels": {},
        }
        client = self._client_with(99, name="guest7001", display_name="stale")
        with (
            patch.object(mage, "_MAGE_REGISTRY", registry),
            patch.dict(sys.modules, {"state": MagicMock(client=client)}),
        ):
            names = mage.member_address_map()
        self.assertEqual(names.get("guest h"), "Guest")
        self.assertEqual(names.get("guest7001"), "Guest")

    def test_no_client_degrades_to_registry_only(self) -> None:
        """Offline / cold cache must not raise — it just maps less."""
        registry = {
            "mages": {"fares": {"address": "fares", "discord_id": "11"}},
            "spaces": {},
            "channels": {},
        }
        with (
            patch.object(mage, "_MAGE_REGISTRY", registry),
            patch.dict(sys.modules, {"state": MagicMock(client=None)}),
        ):
            names = mage.member_address_map()
        self.assertEqual(names.get("fares"), "fares")


class MemberResolutionTests(unittest.TestCase):
    def test_space_root_lists_members_personal_root_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for n in ("kermit", "partner", "family"):
                Path(tmp, n).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertEqual(
                    mage.space_members_for_practice_dir(f"{tmp}/family"),
                    ["kermit", "partner"],
                )
                self.assertEqual(
                    mage.space_members_for_practice_dir(f"{tmp}/kermit"), []
                )


class WitnessBranchTests(unittest.IsolatedAsyncioTestCase):
    async def _capture_system_prompt(self, root_name: str) -> str:
        captured = {}

        async def fake_chat(system, messages, **kwargs):
            captured["system"] = system
            captured["prompt"] = messages[0]["content"]
            return (
                f"{story_notes._HELD}\nSomething was held here for a while.\n"
                f"{story_notes._RELATION}\nnone\n"
                f"{story_notes._TOPICS}\nnone\n"
                f"{story_notes._PROPOSED}\nnone\n"
                f"{story_notes._END}"
            )

        with tempfile.TemporaryDirectory() as tmp:
            for n in ("kermit", "partner", "family"):
                Path(tmp, n).mkdir()
            root = f"{tmp}/{root_name}"
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch("story_notes.set_practice_context_for_channel"),
                patch("story_notes.get_pd", return_value=root),
                patch("story_notes.get_mage_name", return_value="Family"),
                patch("story_notes.chat_ollama", side_effect=fake_chat),
                patch("story_notes._resolve_thread_title", return_value="eddy"),
            ):
                await story_notes.write_eddy_note(
                    42, SHARED_HISTORY, trigger="idle"
                )
        return captured["system"], captured["prompt"]

    async def test_shared_space_uses_witness_voice(self) -> None:
        system, prompt = await self._capture_system_prompt("family")
        self.assertEqual(system, story_notes._WITNESS_SYSTEM_PROMPT)
        self.assertIn("THIRD PERSON", system)
        self.assertIn("Kermit:", prompt)
        self.assertIn("Partner:", prompt)

    async def test_personal_root_keeps_second_person(self) -> None:
        system, _ = await self._capture_system_prompt("kermit")
        self.assertEqual(system, story_notes._SYSTEM_PROMPT)


class DailyWitnessBranchTests(unittest.IsolatedAsyncioTestCase):
    async def _system_for(self, root_name: str) -> str:
        import story_daily

        captured = {}

        async def fake_chat(system, messages, **kwargs):
            captured.setdefault("systems", []).append(system)
            return "A long enough body to clear the daily quality floor here."

        entry = story_notes.EddyEntry(
            thread="1",
            title="t",
            trigger="idle",
            timestamp=MagicMock(),
            related_topics=[],
            body="held",
            source_path=Path("x"),
        )
        entry.timestamp.strftime.return_value = "10:00"

        with tempfile.TemporaryDirectory() as tmp:
            for n in ("kermit", "family"):
                Path(tmp, n).mkdir()
            root = Path(tmp, root_name)
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch(
                    "story_daily.collect_eddy_entries_for_date", return_value=[entry]
                ),
                patch("story_daily.chat_ollama", side_effect=fake_chat),
                patch("story_daily.read_alive_snapshot", return_value={}),
            ):
                await story_daily.write_daily_note(
                    date(2026, 7, 28), practice_dir=root
                )
        return captured["systems"]

    async def test_shared_space_daily_is_witness_voice(self) -> None:
        import story_daily

        systems = await self._system_for("family")
        # First call is the communal record; the rest are per-member readings.
        self.assertEqual(systems[0], story_daily._WITNESS_SYSTEM_PROMPT)

    async def test_shared_space_synthesis_is_one_call_and_one_record(self) -> None:
        """Was: one communal record plus one note per member.

        The per-member layer is withdrawn (INT-048) — it re-centred an
        attributed record on one address and inverted whose day it told. A
        shared space now produces exactly what a personal root does: one
        synthesis, one record. Only the voice differs.
        """
        systems = await self._system_for("family")
        self.assertEqual(len(systems), 1)

    async def test_personal_daily_is_second_person_and_has_no_member_notes(self) -> None:
        import story_daily

        systems = await self._system_for("kermit")
        self.assertEqual(systems, [story_daily._SYSTEM_PROMPT])


class ThemesRuleReachesBothPromptsTests(unittest.TestCase):
    """The rule was written twice and the copies disagreed.

    The shared prompt said "never a verdict on a member"; the solo prompt said
    nothing at all — so the guard was missing from precisely the notes written
    into a person's own private river. One constant now, and this fails if
    either family stops carrying it or if a third prompt is added without it.
    """

    def test_both_note_prompts_carry_the_themes_rule(self) -> None:
        import story_notes

        for name in ("_SYSTEM_PROMPT", "_WITNESS_SYSTEM_PROMPT"):
            with self.subTest(prompt=name):
                self.assertIn(story_notes._THEMES_RULE, getattr(story_notes, name))

    def test_no_prompt_reintroduces_a_second_copy(self) -> None:
        """A near-duplicate is how the two copies drifted apart in the first place."""
        import story_notes

        source = Path(story_notes.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            source.count("Up to 3 short labels"), 1,
            "the themes instruction must live in _THEMES_RULE only",
        )

    def test_the_rule_covers_people_who_are_not_members(self) -> None:
        """"A member" was the wrong class — the live violations were about
        someone discussed but not present."""
        import story_notes

        rule = story_notes._THEMES_RULE.lower()
        self.assertIn("not only the people", rule)
        self.assertIn("not present", rule)


if __name__ == "__main__":
    unittest.main()
