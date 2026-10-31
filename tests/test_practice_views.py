"""`!eddy`, `!live` and `...` in a channel: one pattern, run differently in each practice.

docs/design/curated-surfaces-v1.md, slices 2 and 3. Needs the real discord.py (a layout
message cannot be checked on a mock). Each guard has its positive control.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord  # noqa: F401
except ImportError:  # system Python without discord.py: skip, never pass by omission
    raise unittest.SkipTest("needs discord.py")

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import channel_primitives  # noqa: E402
import practice_views as pv  # noqa: E402
import ui_kit  # noqa: E402
from tests.test_mcp_list import alltext  # noqa: E402

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


def record(tid, name, state="live", age=3600):
    return {"thread_id": str(tid), "name": name, "state": state, "age_seconds": age, "line": name, "sidebar_rank": int(tid)}


def topic(tid, label, heat, *, threads=(), summary="", room="craft", conversations=3):
    return {
        "id": tid, "label": label, "summary": summary or f"About {label}.", "keywords": [label.lower()],
        "heat": heat, "conversations": conversations, "since": "2026-09-01", "last_seen": "2026-10-13",
        "rooms": [room], "formed_by": "keyword",
        "entries": [
            {"when": f"2026-10-1{i}T10:00+02:00", "thread": str(t), "title": f"t{t}", "room": room, "who": "", "source": "", "excerpt": "x"}
            for i, t in enumerate(threads, 1)
        ],
    }


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write_topics(self, topics, roots=None):
        folder = self.root / "memory"
        folder.mkdir(exist_ok=True)
        (folder / "topics.yaml").write_text(
            yaml.safe_dump({"topics": topics, "roots": roots or [{"room": "craft"}]}), encoding="utf-8"
        )

    def write_note(self, thread, text, stamp="2026-10-13T10:00:00+02:00"):
        folder = self.root / "story" / "eddies"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{thread}-slug.md").write_text(
            f"---\nthread: '{thread}'\ntitle: t\ntrigger: manual\ntimestamp: '{stamp}'\nrelated-topics: []\nproposed-themes: []\nsparks: []\n---\n\n{text}\n",
            encoding="utf-8",
        )

    def place(self, primitive="private", **kw):
        base = dict(
            parent=SimpleNamespace(name="craft-turtle", id=10, threads=[]),
            parent_id=10, name="#craft-turtle", guild_id=777,
            primitive=channel_primitives.primitive_definition(primitive),
            practice_dir=self.root, runtime_dir=self.root, locale="en", now=NOW,
            threads={"1": {"name": "Alpha"}, "2": {"name": "Beta"}, "3": {"name": "Gone", "harvest_status": "dissolved"}},
            records=[], coming=[],
        )
        base.update(kw)
        return pv.Place(**base)


class EddyCardTests(Home):
    def test_each_eddy_is_a_link_with_what_it_last_held_and_when(self):
        self.write_note(1, "We decided the card is the answer. Nothing else.")
        place = self.place(records=[record(1, "Alpha", age=7200), record(2, "Beta")])
        text = alltext(pv.eddies_view(place))
        self.assertIn("**[Alpha](https://discord.com/channels/777/1)**  We decided the card is the answer.", text)
        self.assertNotIn("Nothing else", text, "the first sentence only")
        self.assertIn("-# <t:1791961200:R>", text, "relative time that stays true")
        self.assertIn("No note yet", text, "an eddy with no checkpoint says so")
        self.assertEqual(ui_kit.violations(pv.eddies_view(place)), [])

    def test_newest_note_wins_and_a_long_sentence_is_clipped(self):
        self.write_note(1, "Old.", stamp="2026-10-01T10:00:00+02:00")
        self.write_note(1, "New " + "word " * 40, stamp="2026-10-13T10:00:00+02:00")
        line = pv.held_line(self.root, 1)
        self.assertTrue(line.startswith("New word"))
        self.assertLessEqual(len(line), ui_kit.ITEM_LINE_MAX)
        self.assertEqual(pv.held_line(self.root, 99), "")

    def test_a_bracket_in_a_name_cannot_break_the_link(self):
        place = self.place(records=[record(1, "Plan [draft] v2")])
        self.assertIn("[Plan (draft) v2](https://discord.com/channels/777/1)", alltext(pv.eddies_view(place)))

    def test_parked_eddies_are_a_count_until_asked_for(self):
        place = self.place(records=[record(1, "Alpha"), record(2, "Beta", state="resting"), record(3, "Gone", state="gone")])
        quiet = alltext(pv.eddies_view(place))
        self.assertIn("1 live · 1 parked", quiet)
        self.assertNotIn("Beta", quiet)
        asked = alltext(pv.eddies_view(place, show_all=True))
        self.assertIn("Beta", asked)
        self.assertNotIn("Gone", asked, "a dissolved eddy is not listed")

    def test_more_than_a_glance_says_how_many_and_how_to_see_them(self):
        place = self.place(records=[record(i, f"E{i}", age=i * 60) for i in range(1, 10)])
        text = alltext(pv.eddies_view(place))
        self.assertIn("…and 2 more. `!eddy all` lists them.", text)
        self.assertEqual(text.count("discord.com/channels"), pv.EDDY_LIST)

    def test_an_empty_channel_says_how_it_fills(self):
        text = alltext(pv.eddies_view(self.place()))
        self.assertIn("Press **new eddy** below", text)

    def test_a_spoken_window_is_a_filter(self):
        place = self.place(records=[record(1, "Alpha", age=3600), record(2, "Beta", age=86400 * 9)])
        text = alltext(pv.eddies_view(place, days=5))
        self.assertIn("Alpha", text)
        self.assertNotIn("Beta", text)

    def test_german(self):
        text = alltext(pv.eddies_view(self.place(locale="de", records=[record(1, "Alpha")])))
        self.assertIn("Deine Eddies hier", text)
        self.assertIn("Noch keine Notiz", text)
        self.assertEqual(ui_kit.parity(pv._TEXT), [])


class LiveTests(Home):
    def setUp(self):
        super().setUp()
        self.write_topics(
            [topic("a", "Voice", 9.0, threads=(1, 2)), topic("b", "Cards", 7.0), topic("c", "Bars", 5.0),
             topic("d", "Dates", 3.0), topic("e", "Models", 1.0, threads=(3,))]
        )

    def test_it_says_what_turtle_has_in_mind_and_what_waits_for_a_mention(self):
        text = alltext(pv.live_view(self.place()))
        self.assertIn("What is live in #craft-turtle", text)
        carried, rest = text.split("Turtle has these in mind")[1].split("Comes up when you mention it")
        for label in ("Voice", "Cards", "Bars"):
            self.assertIn(label, carried)
        self.assertIn("Dates", rest)
        self.assertIn("Models", rest)

    def test_what_is_called_carried_is_exactly_what_turtle_carries_every_turn(self):
        from memory_agent import live_topics, render_topic_memory_block

        considered: list = []
        render_topic_memory_block(self.root, "", considered=considered)
        passive = {c["topic"] for c in considered if c["selected"]}
        carried, rest, _ = live_topics(self.root)
        self.assertEqual({t["id"] for t in carried}, passive)
        self.assertTrue(passive and not ({t["id"] for t in rest} & passive))

    def test_the_guard_can_fail(self):
        from memory_agent import live_topics, render_topic_memory_block

        considered: list = []
        render_topic_memory_block(self.root, "", considered=considered)
        passive = {c["topic"] for c in considered if c["selected"]}
        carried, _, _ = live_topics(self.root)
        self.assertEqual({t["id"] for t in carried[:1]} == passive, False, "a card that carried fewer than Turtle does would be caught")

    def test_a_topic_names_its_eddies_that_still_exist_with_links(self):
        text = alltext(pv.live_view(self.place()))
        self.assertIn("[Alpha](https://discord.com/channels/777/1)", text)
        self.assertIn("[Beta](https://discord.com/channels/777/2)", text)
        self.assertNotIn("Gone", text, "a dissolved eddy is not offered")

    def test_an_aimed_glance_puts_what_it_matches_first(self):
        place = self.place()
        plain = alltext(pv.live_view(place)).split("Comes up when you mention it")[1]
        aimed = alltext(pv.live_view(place, toward="models"))
        self.assertIn("Toward **models**", aimed)
        self.assertLess(aimed.index("Models"), aimed.index("Dates"))
        self.assertLess(plain.index("Dates"), plain.index("Models"), "positive control: without it, heat order")

    def test_no_topics_says_how_they_form(self):
        (self.root / "memory" / "topics.yaml").unlink()
        text = alltext(pv.live_view(self.place()))
        self.assertIn("once two conversations return to the same thing", text)

    def test_a_craft_channel_does_not_see_the_shared_rooms(self):
        self.write_topics(
            [topic("a", "Mine", 9.0, room="craft", threads=(1,)), topic("f", "Family dinner", 8.0, room="family", threads=(2,))],
            roots=[{"room": "craft"}, {"room": "family"}],
        )
        craft = alltext(pv.live_view(self.place("craft")))
        self.assertIn("Mine", craft)
        self.assertNotIn("Family dinner", craft)
        private = alltext(pv.live_view(self.place("private")))
        self.assertIn("Family dinner", private, "positive control: the private river sees the merged index")

    def test_a_sensitive_room_shows_size_and_time_and_none_of_the_words(self):
        view = pv.live_view(self.place("health"))
        text = alltext(view)
        self.assertIn("Topic 1", text)
        self.assertNotIn("Voice", text)
        self.assertNotIn("About Voice", text)
        self.assertIn("3 conversations", text)
        self.assertIn("topics show their size and when", text)
        self.assertIn("Voice", alltext(pv.live_view(self.place("private"))), "positive control")

    def test_it_keeps_the_grammar_in_every_practice_and_both_languages(self):
        plant = [("Aufgabe", "Wartet auf dich")]
        for primitive in channel_primitives._DEFINITIONS:
            for locale in ("en", "de"):
                place = self.place(primitive, locale=locale, coming=plant, records=[record(1, "Alpha"), record(2, "Beta", state="resting")])
                with patch("core.craft_readiness.waiting_glance_rows", return_value=[{"name": "Alpha", "thread_id": "1", "move": "you"}]):
                    self.assertEqual(ui_kit.violations(pv.live_view(place)), [], (primitive, locale))

    def test_a_card_that_would_not_fit_says_so(self):
        many = [topic(str(i), f"T{i}", 20 - i, threads=(1,)) for i in range(12)]
        self.write_topics(many)
        place = self.place("craft", records=[record(i, f"E{i}") for i in range(1, 8)])
        with patch("core.craft_readiness.waiting_glance_rows", return_value=[{"name": f"W{i}", "thread_id": str(i), "move": "you"} for i in range(5)]):
            view = pv.live_view(place)
        self.assertLessEqual(ui_kit.count_parts(view), ui_kit.PART_BUDGET)


class EachPracticeAddsItsOwnTests(Home):
    def test_every_channel_primitive_decides_what_its_live_state_adds(self):
        names = set(channel_primitives._DEFINITIONS)
        self.assertEqual(set(pv.LIVE_EXTRAS) & set(pv.NO_LIVE_EXTRAS), set(), "in one table, not both")
        self.assertEqual(set(pv.LIVE_EXTRAS) | set(pv.NO_LIVE_EXTRAS), names, "a channel kind with no decision, or a decision for one that is gone")
        self.assertTrue(all(pv.NO_LIVE_EXTRAS.values()), "a practice that adds nothing says why")

    def test_the_check_can_fail(self):
        with patch.dict(pv.NO_LIVE_EXTRAS, {}, clear=True):
            self.assertNotEqual(set(pv.LIVE_EXTRAS) | set(pv.NO_LIVE_EXTRAS), set(channel_primitives._DEFINITIONS))

    def test_craft_adds_whose_move_it_is_and_nobody_else_does(self):
        rows = [
            {"name": "Alpha", "thread_id": "1", "move": "you"},
            {"name": "Beta", "thread_id": "2", "move": "session"},
            {"name": "Gamma", "thread_id": "3", "move": "confirm"},
            {"name": "Delta", "thread_id": "4", "move": "Spirit"},
        ]
        with patch("core.craft_readiness.waiting_glance_rows", return_value=rows):
            craft = alltext(pv.live_view(self.place("craft")))
            other = alltext(pv.live_view(self.place("shared")))
        for line in ("Your move", "Ready: waits for a session", "Waits for your yes", "Waits for Spirit"):
            self.assertIn(line, craft)
        self.assertNotIn("Waiting", other)

    def test_a_private_river_adds_the_dates_coming_up(self):
        place = self.place("private", coming=[("Dentist", "Fri, October 17, 2026")])
        self.assertIn("Dentist", alltext(pv.live_view(place)))
        self.assertIn("Coming up", alltext(pv.live_view(place)))
        self.assertNotIn("Dentist", alltext(pv.live_view(self.place("shared", coming=place.coming))))


class CommandsTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_commands_are_registered_and_a_member_may_run_them(self):
        import commands
        from cmd_dispatch import _PRACTITIONER_COMMANDS

        for name in ("eddy", "live", "threads"):
            self.assertIn(name, commands.DIRECT_COMMANDS)
        self.assertLessEqual({"eddy", "live"}, _PRACTITIONER_COMMANDS)

    async def test_eddy_and_live_answer_with_a_card_and_a_digest(self):
        import cmd_threads

        place = pv.Place(
            parent=SimpleNamespace(name="c", id=1, threads=[]), parent_id=1, name="#c", guild_id=5, primitive=None,
            practice_dir=None, runtime_dir=None, now=NOW, threads={}, records=[record(1, "Alpha")],
        )
        message = MagicMock()
        message.author.id = 1
        message.reply = AsyncMock()
        with patch.object(cmd_threads, "place_for", return_value=place):
            digest = await cmd_threads.cmd_eddy(message, [])
            self.assertIn("Alpha", alltext(message.reply.await_args.kwargs["view"]))
            self.assertIn("Alpha", digest)
            digest = await cmd_threads.cmd_live(message, [])
            self.assertIn("What is live in #c", alltext(message.reply.await_args.kwargs["view"]))

    async def test_a_channel_glance_is_the_live_card(self):
        import cmd_threads

        place = pv.Place(
            parent=SimpleNamespace(name="c", id=1, threads=[]), parent_id=1, name="#c", guild_id=5, primitive=None,
            practice_dir=None, runtime_dir=None, now=NOW, threads={}, records=[],
        )
        channel = MagicMock()
        channel.send = AsyncMock()
        with patch.object(cmd_threads, "place_for", return_value=place):
            await cmd_threads.post_channel_glance(channel, toward="x")
        self.assertIn("What is live in #c", alltext(channel.send.await_args.kwargs["view"]))
        self.assertIn("Toward **x**", alltext(channel.send.await_args.kwargs["view"]))

    async def test_the_channel_gesture_and_the_spoken_list_use_those_cards(self):
        import river_handler

        with patch("cmd_threads.post_channel_glance", new_callable=AsyncMock) as glance:
            await river_handler.post_parent_river_glance(MagicMock(), toward="t", user_id=3)
        glance.assert_awaited_once()
        message = MagicMock()
        with patch("cmd_threads.post_eddies", new_callable=AsyncMock) as eddies:
            await river_handler._reply_thread_display(message, days=5)
        eddies.assert_awaited_once_with(message, days=5)

    async def test_the_help_card_lists_the_new_commands_and_not_focus(self):
        import help_card

        text = alltext(help_card.render())
        self.assertIn("!eddy", text)
        self.assertIn("!live", text)
        self.assertNotIn("!focus", text)
        self.assertIn("focus", help_card.RETIRED)


if __name__ == "__main__":
    unittest.main()
