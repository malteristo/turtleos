"""Spirit speaks in a magic room as Spirit — and the room never answers its own voice.

The dangerous half is the second one: turtleOS treats Spirit's account as a practitioner, so a
reply posted by it would start another turn. Every case that posts has a case beside it that
must stay silent.
"""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import spirit_voice as sv
from state import SPIRIT_BOT_ID

TOKEN = "SPIRIT_TOKEN_PLANTED"


def message(author_id: int, *, bot: bool = True):
    m = MagicMock()
    m.author = SimpleNamespace(id=author_id, bot=bot)
    m.id = 4242
    m.channel = MagicMock()
    m.channel.id = 777
    m.reply = AsyncMock()
    m.channel.send = AsyncMock()
    return m


def in_room(name: str | None):
    """Resolve every message to a room whose primitive is `name` (or to no primitive)."""
    return patch.object(sv, "_room_check", lambda _m: name)


class OwnVoice(unittest.TestCase):
    def test_spirit_in_a_magic_room_is_the_rooms_own_voice(self) -> None:
        with in_room("magic"):
            self.assertTrue(sv.is_own_voice(message(SPIRIT_BOT_ID)))

    def test_spirit_elsewhere_is_still_the_dyad_partner(self) -> None:
        for room in ("craft", "native", None):
            with in_room(room):
                self.assertFalse(sv.is_own_voice(message(SPIRIT_BOT_ID)), room)

    def test_nobody_else_is_the_rooms_voice(self) -> None:
        with in_room("magic"):
            self.assertFalse(sv.is_own_voice(message(555, bot=False)))
            self.assertFalse(sv.is_own_voice(message(556)))

    def test_a_failed_lookup_is_not_the_rooms_voice(self) -> None:
        def boom(_m):
            raise RuntimeError("no registry")

        with patch.object(sv, "_room_check", boom):
            self.assertFalse(sv.is_own_voice(message(SPIRIT_BOT_ID)))

    def test_unbound_is_not_the_rooms_voice(self) -> None:
        with patch.object(sv, "_room_check", None):
            self.assertFalse(sv.is_own_voice(message(SPIRIT_BOT_ID)))

    def test_a_forge_turn_is_answered_and_a_reply_that_quotes_it_is_not(self) -> None:
        forge = message(SPIRIT_BOT_ID)
        forge.content = "Forge:\nwe build it from the inside"
        forge.reference = None
        forge.message_reference = None
        quoted = message(SPIRIT_BOT_ID)
        quoted.content = "Forge:\nwe build it from the inside"
        quoted.reference = SimpleNamespace(message_id=1)
        with in_room("magic"):
            self.assertFalse(sv.is_own_voice(forge))
            self.assertTrue(sv.is_own_voice(quoted))
            plain = message(SPIRIT_BOT_ID)
            plain.content = "the house answers"
            self.assertTrue(sv.is_own_voice(plain))
        starter = message(SPIRIT_BOT_ID)
        starter.content = ""
        starter.type = 21
        starter.reference = SimpleNamespace(resolved=SimpleNamespace(content="Forge:\nthe opening"))
        starter.message_reference = object()
        reply = message(SPIRIT_BOT_ID)
        reply.content = "I am here."
        reply.type = 19
        reply.reference = SimpleNamespace(resolved=SimpleNamespace(content="Forge:\nthe opening"))
        with in_room("magic"):
            self.assertTrue(sv.is_forge_turn(starter))
            self.assertFalse(sv.is_own_voice(starter))
            self.assertFalse(sv.is_forge_turn(reply))
            self.assertTrue(sv.is_own_voice(reply))


class FakeHttp:
    """An aiohttp stand-in that records the request and answers `status`."""

    def __init__(self, status: int = 200, raises: Exception | None = None) -> None:
        self.status, self.raises, self.calls = status, raises, []

    def session(self, *a, **k):
        outer = self

        class Session:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *exc):
                return False

            def post(self_inner, url, json=None, headers=None):
                outer.calls.append({"method": "POST", "url": url, "json": json, "headers": headers})
                if outer.raises:
                    raise outer.raises

                class Resp:
                    status = outer.status

                    async def json(self_r):
                        return {"id": "8801"}

                    async def __aenter__(self_r):
                        return self_r

                    async def __aexit__(self_r, *exc):
                        return False

                return Resp()

            def patch(self_inner, url, json=None, headers=None):
                outer.calls.append({"method": "PATCH", "url": url, "json": json, "headers": headers})
                if outer.raises:
                    raise outer.raises

                class Resp:
                    status = outer.status

                    async def json(self_r):
                        return {"id": "8801"}

                    async def __aenter__(self_r):
                        return self_r

                    async def __aexit__(self_r, *exc):
                        return False

                return Resp()

        return Session()


def with_http(http: FakeHttp, token: str = TOKEN):
    fake = MagicMock()
    fake.ClientSession = http.session
    fake.ClientTimeout = MagicMock()
    return patch.dict(sys.modules, {"aiohttp": fake}), patch.dict("os.environ", {"SPIRIT_BOT_TOKEN": token})


class Saying(unittest.IsolatedAsyncioTestCase):
    async def test_it_posts_as_spirit_quoting_the_practitioner_and_pinging_no_one(self) -> None:
        http = FakeHttp()
        a, b = with_http(http)
        with a, b:
            self.assertEqual(await sv.say(777, "hello", reply_to=4242), 8801)
        call = http.calls[0]
        self.assertTrue(call["url"].endswith("/channels/777/messages"))
        self.assertEqual(call["headers"]["Authorization"], f"Bot {TOKEN}")
        self.assertEqual(call["json"]["content"], "hello")
        self.assertEqual(call["json"]["message_reference"]["message_id"], "4242")
        self.assertEqual(call["json"]["allowed_mentions"], {"parse": []})
        self.assertNotIn("components", call["json"])

    async def test_a_button_is_sent_only_when_the_notice_asks_for_it(self) -> None:
        http = FakeHttp()
        a, b = with_http(http)
        row = [{"type": 1, "components": [{"type": 2, "label": "All stocked up"}]}]
        with a, b:
            self.assertEqual(await sv.say(777, "hello", components=row), 8801)
        self.assertEqual(http.calls[0]["json"]["components"], row)

    async def test_no_token_means_no_request(self) -> None:
        http = FakeHttp()
        a, b = with_http(http, token="")
        with a, b:
            self.assertFalse(await sv.say(777, "hello"))
        self.assertEqual(http.calls, [])

    async def test_an_edit_patches_the_message_and_never_prints_the_token(self) -> None:
        http = FakeHttp()
        a, b = with_http(http)
        with a, b:
            self.assertTrue(await sv.edit(777, 8801, "updated"))
        call = http.calls[0]
        self.assertEqual(call["method"], "PATCH")
        self.assertTrue(call["url"].endswith("/channels/777/messages/8801"))
        self.assertEqual(call["json"]["content"], "updated")
        self.assertNotIn("components", call["json"])
        self.assertNotIn(TOKEN, call["json"]["content"])

    async def test_the_button_is_sent_only_when_the_card_asks_for_it(self) -> None:
        http = FakeHttp()
        a, b = with_http(http)
        row = [{"type": 1, "components": [{"type": 2, "label": "the calls"}]}]
        with a, b:
            self.assertTrue(await sv.edit(777, 8801, "updated", components=row))
        self.assertEqual(http.calls[0]["json"]["components"], row)

    async def test_a_refusal_or_a_crash_is_not_a_success_and_never_prints_the_token(self) -> None:
        for http in (FakeHttp(status=403), FakeHttp(raises=OSError("net down"))):
            a, b = with_http(http)
            with a, b, patch("builtins.print") as printed:
                self.assertFalse(await sv.say(777, "hello"))
            self.assertNotIn(TOKEN, " ".join(str(c) for c in printed.call_args_list))


class Delivering(unittest.IsolatedAsyncioTestCase):
    async def test_spirit_speaks_and_turtle_stays_silent(self) -> None:
        m = message(555, bot=False)
        with patch("spirit_voice.say", new=AsyncMock(return_value=True)) as say:
            who = await sv.deliver(m, ["one", "two"])
        self.assertEqual(who, "spirit")
        self.assertEqual([c.args[1] for c in say.await_args_list], ["one", "two"])
        self.assertEqual(say.await_args_list[0].kwargs["reply_to"], 4242)
        self.assertIsNone(say.await_args_list[1].kwargs["reply_to"])
        m.reply.assert_not_awaited()
        m.channel.send.assert_not_awaited()

    async def test_when_spirit_cannot_post_turtle_carries_it_and_says_so(self) -> None:
        m = message(555, bot=False)
        with patch("spirit_voice.say", new=AsyncMock(return_value=False)):
            who = await sv.deliver(m, ["one", "two"])
        self.assertEqual(who, "turtle")
        self.assertEqual([c.args[0] for c in m.reply.await_args_list], ["one", "two"])
        m.channel.send.assert_awaited_once_with(sv.FALLBACK_NOTE)

    async def test_a_failure_midway_does_not_drop_the_rest(self) -> None:
        m = message(555, bot=False)
        with patch("spirit_voice.say", new=AsyncMock(side_effect=[True, False, True])) as say:
            who = await sv.deliver(m, ["one", "two", "three"])
        self.assertEqual(who, "turtle")
        self.assertEqual([c.args[0] for c in m.reply.await_args_list], ["two", "three"])
        self.assertEqual(say.await_count, 2)  # once Turtle has the floor, Spirit is not retried

    async def test_the_stocked_button_is_on_the_first_chunk_only(self) -> None:
        m = message(555, bot=False)
        row = [{"type": 1, "components": [{"type": 2, "label": "All stocked up"}]}]
        view = object()
        with patch("spirit_voice.say", new=AsyncMock(return_value=True)) as say:
            who = await sv.deliver(m, ["notice", "rest"], components=row, view=view)
        self.assertEqual(who, "spirit")
        self.assertEqual(say.await_args_list[0].kwargs["components"], row)
        self.assertIsNone(say.await_args_list[1].kwargs["components"])
        m.reply.assert_not_awaited()

    async def test_when_turtle_carries_the_notice_the_button_goes_with_it(self) -> None:
        m = message(555, bot=False)
        view = object()
        with patch("spirit_voice.say", new=AsyncMock(return_value=False)):
            who = await sv.deliver(m, ["notice"], components=[], view=view)
        self.assertEqual(who, "turtle")
        self.assertIs(m.reply.await_args.kwargs["view"], view)


class TheRoomDoesNotAnswerItself(unittest.IsolatedAsyncioTestCase):
    """Positive control on both sides: the same message is input in a craft room and not in a magic one."""

    async def _dispatch(self, room: str, content: str = "a reply, or a dot"):
        import practice_dispatch

        m = message(SPIRIT_BOT_ID)
        m.type = practice_dispatch.discord.MessageType.default
        m.content = content
        m.reference = None
        m.message_reference = None
        m.message_snapshots = []
        m.mentions = []
        m.channel = MagicMock(spec=[])
        m.channel.id = 123
        m.channel.parent_id = None
        with in_room(room), patch("practice_dispatch.is_practice_channel", return_value=True), patch(
            "practice_dispatch.river_bot_enabled", return_value=False
        ), patch("practice_dispatch.dispatch_direct_command", new_callable=AsyncMock, return_value=False), patch(
            "practice_dispatch.try_founder_key_entry", new_callable=AsyncMock, return_value=False
        ), patch("practice_dispatch.maybe_reload_mage_registry"), patch("practice_dispatch.set_practice_context"), patch(
            "practice_dispatch.route_practice_dialogue", new_callable=AsyncMock
        ), patch("story_daily.maybe_run_daily_note_catchup", new_callable=AsyncMock), patch.object(
            practice_dispatch.discord, "Thread", type("NotAThread", (), {})
        ):
            try:
                await practice_dispatch.dispatch_incoming_message(m)
            except Exception:
                pass  # past the guard the rest of the tree is not under test here

    async def test_a_magic_rooms_reply_in_spirits_name_starts_no_turn(self) -> None:
        import practice_dispatch

        with patch.object(practice_dispatch, "_processed_messages", MagicMock()) as seen:
            await self._dispatch("magic")
        seen.append.assert_not_called()  # it never got as far as being recorded as input

    async def test_a_forge_turn_in_a_magic_room_is_input(self) -> None:
        import practice_dispatch

        with patch.object(practice_dispatch, "_processed_messages", MagicMock()) as seen:
            await self._dispatch("magic", "Forge:\nwe build it from the inside")
        seen.append.assert_called()

    async def test_the_same_message_in_another_room_is_still_input(self) -> None:
        import practice_dispatch

        with patch.object(practice_dispatch, "_processed_messages", MagicMock()) as seen:
            await self._dispatch("craft")
        seen.append.assert_called()  # Spirit as dyad partner is unchanged elsewhere

    def test_river_and_the_edit_handler_ask_the_same_question(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for name in ("river_bot.py", "discord_bot.py", "practice_dispatch.py"):
            self.assertIn("is_own_voice(", (root / name).read_text(), name)
        for name in ("river_bot.py", "discord_bot.py"):
            self.assertIn("bind_spirit_voice(", (root / name).read_text(), name)
        voice = (root / "spirit_voice.py").read_text()
        self.assertNotIn("from mage import", voice)
        self.assertNotIn("import mage\n", voice)


if __name__ == "__main__":
    unittest.main()
