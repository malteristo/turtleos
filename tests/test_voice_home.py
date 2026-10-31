"""A spoken sentence is delivered to the owner's voice eddy, and only that home.

The reader is `deliver`: the mirror is asked to post the sentence, dialogue is
asked to answer, and a phrase that lives only in the reply is returned whole
so the speaker rule can keep it out of what is said. Another member's home is
not selected.
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import house_speaker
import mage
import voice_door
import voice_home


def _registry() -> dict:
    return {
        "default_mage": "ada",
        "mages": {
            "ada": {"primary": True, "discord_id": "7"},
            "beau": {"discord_id": "8"},
        },
        "channels": {
            "1": {"mage": "beau", "primitive": "private"},
            "2": {"mage": "ada", "primitive": "river"},
        },
    }


class OwnerTests(unittest.TestCase):
    def test_the_primary_home_is_the_one_that_is_used(self) -> None:
        self.assertEqual(voice_home.voice_owner(_registry()), "ada")

    def test_another_members_home_is_not_used_when_the_owner_has_none(self) -> None:
        registry = _registry()
        del registry["channels"]["2"]
        self.assertIsNone(voice_home.voice_owner(registry))
        self.assertEqual(voice_home.home_channel_id(registry, "beau"), "1")


class EddyFileTests(unittest.TestCase):
    def test_a_saved_eddy_is_read_back_and_a_broken_file_is_not(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(voice_home.load_eddy_id(tmp))
            voice_home.save_eddy_id(tmp, 44, "2026-10-24")
            self.assertEqual(voice_home.load_eddy_id(tmp), 44)
            self.assertEqual(voice_home.load_voice_day(tmp), "2026-10-24")
            Path(tmp, "voice-eddy.json").write_text("not json", encoding="utf-8")
            self.assertIsNone(voice_home.load_eddy_id(tmp))
            self.assertIsNone(voice_home.load_voice_day(tmp))


    def test_the_speaker_instruction_is_plain_text(self) -> None:
        text = voice_home.HA_INSTRUCTION
        self.assertNotIn("{", text)
        self.assertNotIn("}", text)
        self.assertIn("spoken", text)


class DayTests(unittest.TestCase):
    def test_today_stays_and_another_day_opens(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime(2026, 10, 24, 23, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        today = voice_home.day_key(now)
        self.assertEqual(today, "2026-10-24")
        self.assertEqual(voice_home.day_title(now), "Saturday 24 Oct")
        self.assertEqual(voice_home.day_action(today, today), "stay")
        self.assertEqual(voice_home.day_action("2026-10-23", today), "open")
        self.assertEqual(voice_home.day_action(None, today), "open")
        stamped = voice_home.stamp_sentence("What now?", now)
        self.assertTrue(stamped.startswith("What now?\n-# Saturday 23:00"))
        self.assertIn("Day eddy", stamped)
        self.assertGreater(voice_home.seconds_until_next_day(now), 3000)

    def test_a_record_without_a_day_opens_a_new_one(self) -> None:
        with TemporaryDirectory() as tmp:
            voice_home.save_eddy_id(tmp, 44)
            self.assertIsNone(voice_home.load_voice_day(tmp))
            self.assertEqual(
                voice_home.day_action(voice_home.load_voice_day(tmp), "2026-10-24"),
                "open",
            )


class DeliverTests(unittest.TestCase):
    def test_the_sentence_is_posted_and_the_reply_comes_back(self) -> None:
        posted: list[str] = []
        seen: list[str] = []

        async def mirror(_thread, text: str) -> None:
            posted.append(text)

        async def dialogue(turn) -> None:
            seen.append(turn.content)
            await turn.reply("PAGE-SECRET\n\nThe talk\nThe afternoon is open.")

        reply = asyncio.run(
            voice_home.deliver(
                "What now?",
                thread=object(),
                author_name="Ada",
                author_id=7,
                mirror=mirror,
                dialogue=dialogue,
            )
        )
        self.assertEqual(posted, ["What now?"])
        self.assertEqual(seen, ["What now?"])
        self.assertIn("PAGE-SECRET", reply)
        heard = house_speaker.spoken(reply)
        self.assertEqual(heard, "The afternoon is open.")
        self.assertNotIn("PAGE-SECRET", heard or "")

    def test_a_failed_mirror_still_gets_a_reply(self) -> None:
        async def mirror(_thread, _text: str) -> None:
            raise RuntimeError("mirror down")

        async def dialogue(turn) -> None:
            await turn.reply("Still here.")

        reply = asyncio.run(
            voice_home.deliver(
                "hello",
                thread=object(),
                author_name="Ada",
                author_id=7,
                mirror=mirror,
                dialogue=dialogue,
            )
        )
        self.assertEqual(reply, "Still here.")

    def test_a_failed_post_of_the_reply_is_still_returned(self) -> None:
        class Channel:
            async def send(self, _text, **_kwargs):
                raise RuntimeError("discord down")

        async def mirror(_thread, _text: str) -> None:
            return None

        async def dialogue(turn) -> None:
            await turn.reply("Said anyway.")

        reply = asyncio.run(
            voice_home.deliver(
                "hello",
                thread=Channel(),
                author_name="Ada",
                author_id=7,
                mirror=mirror,
                dialogue=dialogue,
            )
        )
        self.assertEqual(reply, "Said anyway.")


class DoorTests(unittest.TestCase):
    def test_the_door_is_only_on_the_virtual_machine_bridge(self) -> None:
        self.assertEqual(voice_door.BIND_HOST, "192.168.64.1")
        self.assertNotEqual(voice_door.BIND_HOST, "0.0.0.0")

    def test_the_chat_body_the_speaker_reads_has_no_page(self) -> None:
        async def turn(_sentence: str) -> str:
            return "PAGE-SECRET\n\nThe talk\nCome back in."

        result, stream = asyncio.run(
            voice_door.chat_result(
                {
                    "stream": True,
                    "messages": [{"role": "user", "content": "I'm back."}],
                },
                turn,
            )
        )
        self.assertTrue(stream)
        self.assertEqual(result["message"]["content"], "Come back in.")
        self.assertNotIn("PAGE-SECRET", result["message"]["content"])

    def test_the_bot_starts_the_door(self) -> None:
        source = Path("discord_bot.py").read_text(encoding="utf-8")
        self.assertIn("start_voice_door", source)

    def test_note_actor_is_who_the_turn_reads(self) -> None:
        mage.note_actor("ada")
        self.assertEqual(mage.get_actor_key(), "ada")
        mage.note_actor(None)
        self.assertIsNone(mage.get_actor_key())


class _Line:
    def __init__(self, content: str):
        self.content = content


class _History:
    def __init__(self, lines: list[str]):
        self._lines = [_Line(line) for line in lines]

    def __aiter__(self):
        self._left = list(self._lines)
        return self

    async def __anext__(self):
        if not self._left:
            raise StopAsyncIteration
        return self._left.pop(0)


class _Thread:
    def __init__(self, name: str, lines: list[str] | None = None, *, broken: bool = False):
        self.name = name
        self.edits: list[dict] = []
        self._lines = lines or []
        self._broken = broken

    def history(self, limit: int = 20, oldest_first: bool = False):
        if self._broken:
            raise RuntimeError("history down")
        return _History(self._lines)

    async def edit(self, **kwargs):
        self.edits.append(kwargs)
        if "name" in kwargs:
            self.name = kwargs["name"]


class NameTests(unittest.TestCase):
    def test_a_sentence_is_cut_at_the_period(self) -> None:
        self.assertEqual(
            voice_home.title_from(
                "The speaker is connected. Reply in one short sentence."
            ),
            "The speaker is connected",
        )

    def test_a_long_sentence_is_cut_on_a_word(self) -> None:
        title = voice_home.title_from(" ".join(["alpha"] * 30))
        self.assertLess(len(title), 80)
        self.assertGreater(len(title), 0)
        self.assertEqual(set(title.split(" ")), {"alpha"})

    def test_an_empty_sentence_stays_voice(self) -> None:
        self.assertEqual(voice_home.title_from("   "), "voice")

    def test_the_placeholder_takes_the_sentence_that_opened_it(self) -> None:
        self.assertEqual(
            voice_home.name_for(
                current="voice",
                opening="The speaker is connected. Reply in one short sentence.",
                sentence="What now?",
                fresh=False,
            ),
            "The speaker is connected",
        )

    def test_a_conversation_that_already_has_a_name_keeps_it(self) -> None:
        self.assertIsNone(
            voice_home.name_for(
                current="The speaker is connected",
                opening="The speaker is connected. Reply in one short sentence.",
                sentence="What now?",
                fresh=False,
            )
        )

    def test_a_new_conversation_is_named_from_the_new_sentence(self) -> None:
        self.assertEqual(
            voice_home.name_for(
                current="voice",
                opening="The speaker is connected.",
                sentence="Can you say hello world?",
                fresh=True,
            ),
            "Can you say hello world",
        )

    def test_the_placeholder_thread_is_renamed_from_its_opening(self) -> None:
        thread = _Thread(
            "voice",
            ["The speaker is connected. Reply in one short sentence.", "Hello, world."],
        )
        asyncio.run(voice_home.name_placeholder(thread))
        self.assertEqual(thread.name, "The speaker is connected")
        asyncio.run(voice_home.name_placeholder(thread))
        self.assertEqual(len(thread.edits), 1)

    def test_a_named_thread_is_not_renamed(self) -> None:
        thread = _Thread("The speaker is connected", ["Something else."])
        asyncio.run(voice_home.name_placeholder(thread))
        self.assertEqual(thread.edits, [])

    def test_an_unreadable_opening_leaves_the_placeholder(self) -> None:
        thread = _Thread("voice", broken=True)
        asyncio.run(voice_home.name_placeholder(thread))
        self.assertEqual(thread.name, "voice")
        self.assertEqual(thread.edits, [])


class PressTests(unittest.TestCase):
    def setUp(self) -> None:
        voice_home.reset_presses()

    def tearDown(self) -> None:
        voice_home.reset_presses()

    def test_a_triple_does_not_open_a_conversation(self) -> None:
        self.assertTrue(voice_home.note_press({"event_type": "triple_press"}))
        self.assertFalse(voice_home.take_new_eddy())

    def test_one_press_and_the_wake_word_do_not_open_a_new_conversation(self) -> None:
        self.assertFalse(voice_home.note_press({"event_type": "double_press"}))
        self.assertFalse(voice_home.note_press({"event_type": "long_press"}))
        self.assertFalse(voice_home.note_press({}))
        voice_home.note_messages(
            [{"role": "user", "content": "What should I do with the afternoon?"}]
        )
        self.assertFalse(voice_home.take_new_eddy())

    def test_a_mark_does_not_open_a_conversation_and_the_page_stays_unspoken(self) -> None:
        stamp = str(time.time())
        body = {
            "messages": [
                {"role": "system", "content": f"voice_mark {stamp}"},
                {"role": "user", "content": "Start a new one."},
            ]
        }

        async def turn(sentence: str) -> str:
            self.assertEqual(sentence, "Start a new one.")
            self.assertFalse(voice_home.take_new_eddy())
            return "PAGE-SECRET\n\nThe talk\nOpened."

        result, _stream = asyncio.run(voice_door.chat_result(body, turn))
        self.assertEqual(result["message"]["content"], "Opened.")
        self.assertNotIn("PAGE-SECRET", result["message"]["content"])
        self.assertNotIn("voice_mark", result["message"]["content"])

    def test_an_empty_request_is_not_a_new_conversation(self) -> None:
        body = {"messages": [{"role": "system", "content": f"voice_mark {time.time()}"}]}
        heard, _stream = asyncio.run(
            voice_door.chat_result(body, lambda _sentence: "no")
        )
        self.assertEqual(heard["message"]["content"], house_speaker.DID_NOT_HEAR)
        self.assertFalse(voice_home.take_new_eddy())

    def test_the_door_accepts_a_triple(self) -> None:
        source = Path("voice_door.py").read_text(encoding="utf-8")
        self.assertIn('add_post("/press"', source)
        self.assertIn("note_messages", source)
        self.assertIn("ensure_day_eddy", source)

    def test_an_older_day_is_archived_and_today_opens(self) -> None:
        from unittest.mock import patch

        with TemporaryDirectory() as tmp:
            voice_home.save_eddy_id(tmp, 9, "2026-10-23")
            archived: list[int] = []
            created: list[str] = []

            class Thread:
                def __init__(self, tid: int, name: str) -> None:
                    self.id = tid
                    self.name = name
                    self.archived = False
                    self.parent = None

                async def edit(self, **kwargs) -> None:
                    if kwargs.get("archived"):
                        self.archived = True
                        archived.append(self.id)

            class Channel:
                async def create_thread(self, **kwargs) -> Thread:
                    created.append(kwargs["name"])
                    return Thread(100, kwargs["name"])

            class Client:
                async def fetch_channel(self, cid: int):
                    if int(cid) == 9:
                        return Thread(9, "Friday 23 Oct")
                    return Channel()

            with patch("mage.get_registry", return_value=_registry()), patch(
                "mage.get_runtime_dir", return_value=tmp
            ), patch("mage.note_actor"), patch("mage.set_practice_context_for_channel"):
                thread = asyncio.run(voice_home.ensure_day_eddy(Client()))

            self.assertEqual(archived, [9])
            self.assertEqual(created, [voice_home.day_title()])
            self.assertEqual(thread.id, 100)
            self.assertEqual(voice_home.load_voice_day(tmp), voice_home.day_key())
            self.assertEqual(voice_home.load_eddy_id(tmp), 100)


if __name__ == "__main__":
    unittest.main()
