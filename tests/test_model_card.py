"""`!model` in the turtleOS design language: who answers here, what that means, the menu that changes it.

The picks and who may make them are tests/test_own_channel_model.py. This is what a person sees
and what a press does. Needs the real discord.py: a layout message cannot be checked against a mock.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord
except ImportError:  # system Python without discord.py: skip, never pass by omission
    raise unittest.SkipTest("needs discord.py")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import room_models  # noqa: E402
import ui_kit  # noqa: E402
from tests.test_mcp_list import alltext, buttons  # noqa: E402
from tests.test_own_channel_model import ALEX, REGISTRY, ROBIN, SAM, _RoomEnv  # noqa: E402


def menu(view) -> dict:
    return next(n for n in ui_kit._walk(view.to_components()) if n.get("type") == 3)


def values(view) -> list[str]:
    return [o["value"] for o in menu(view)["options"]]


class CardTests(_RoomEnv):
    def render(self, parent=100, current="gemma4:31b", **kw):
        base = dict(locale="en", anthropic=True, gemini=False)
        base.update(kw)
        return room_models.render(parent, current, REGISTRY, **base)

    def test_it_says_who_answers_what_that_means_and_offers_the_menu_on_one_card(self):
        view = self.render()
        text = alltext(view)
        self.assertIn("Who answers here", text)
        self.assertIn("Gemma 4 31B (local)", text)
        self.assertIn("answering here", text)
        self.assertIn("Nothing leaves the house.", text)
        self.assertIn("Good for: conversation", text)
        self.assertIn("River", text)
        self.assertIn("Memory", text)
        self.assertIn("Gemini is not connected.", text)
        self.assertIn("Claude is not connected.", alltext(self.render(anthropic=False, gemini=True)))
        self.assertIn("API models are not connected.", alltext(self.render(anthropic=False, gemini=False)))
        self.assertNotIn("health board", text)
        self.assertIn("provider's servers", text, "a local room is warned once what a cloud pick would mean")
        self.assertEqual(ui_kit.violations(view), [])
        self.assertEqual(menu(view)["custom_id"], room_models.MODEL_SELECT_ID)
        self.assertEqual(menu(view)["placeholder"], "Change this channel's model")

    def test_the_menu_offers_what_has_a_route_and_marks_the_current_one(self):
        view = self.render()
        self.assertIn("local", values(view))
        self.assertIn("sonnet", values(view))
        self.assertIn("sonnet-5.5", values(view))
        self.assertNotIn("gemini", values(view))
        self.assertNotIn("qwen", values(view))
        self.assertEqual([o["value"] for o in menu(view)["options"] if o.get("default")], ["local"])
        descriptions = {o["value"]: o["description"] for o in menu(view)["options"]}
        self.assertEqual(descriptions["local"], "House · stays on this machine")
        self.assertEqual(descriptions["sonnet"], "Cloud · community account · reads this room")

    def test_a_cloud_model_says_its_consequence_on_its_own_row(self):
        view = self.render(current="claude-sonnet-5")
        text = alltext(view)
        self.assertIn("Reads what you say here on the provider's servers.", text)
        self.assertNotIn("A cloud model is paid", text, "said once, on the row, not again below it")
        self.assertNotIn("Nothing leaves the house.", text)

    def test_a_health_room_says_what_the_provider_would_read_before_and_after_the_pick(self):
        before = alltext(self.render(parent=600))
        self.assertIn("health board", before)
        self.assertIn("Uploads are still read in the house", before)
        after = alltext(self.render(parent=600, current="claude-sonnet-5"))
        self.assertIn("health board", after)
        self.assertNotIn("health board", alltext(self.render(parent=100)))

    def test_a_shared_room_says_any_member_may_change_it(self):
        text = alltext(self.render(parent=300, shared=True))
        self.assertIn("Any member of this room can change it.", text)
        self.assertNotIn("Any member", alltext(self.render()))

    def test_a_list_past_25_is_a_card_with_no_menu_and_says_how_to_type(self):
        planted = [(f"w{i}", "gemma4:31b") for i in range(26)]
        with patch.object(room_models, "menu_rows", return_value=planted):
            view = self.render()
        self.assertEqual([n for n in ui_kit._walk(view.to_components()) if n.get("type") == 3], [])
        self.assertIn("too long for a menu", alltext(view))

    def test_a_room_nobody_owns_shows_the_card_without_a_menu_and_says_why(self):
        view = self.render(parent=999, can_pick=False, notice=room_models._t("en")["no_room"])
        self.assertEqual([n for n in ui_kit._walk(view.to_components()) if n.get("type") == 3], [])
        self.assertIn("no owner or members", alltext(view))
        self.assertNotIn("provider's servers", alltext(view), "no cloud warning for a menu that is not there")

    def test_german_has_the_same_card_and_keeps_the_grammar(self):
        for kw in ({}, {"parent": 600}, {"current": "claude-opus-5-5"}, {"parent": 300, "shared": True}):
            view = self.render(locale="de", **kw)
            self.assertIn("Wer hier antwortet", alltext(view))
            self.assertEqual(ui_kit.violations(view), [], kw)
        self.assertEqual(ui_kit.parity(room_models._TEXT), [])

    def test_every_state_keeps_the_grammar(self):
        for kw in (
            {}, {"parent": 600}, {"parent": 300, "shared": True}, {"current": "claude-opus-5-5"},
            {"current": "claude-opus-5-5", "parent": 600}, {"changed": "Claude Opus 5.5 answers here from now on."},
            {"anthropic": False}, {"anthropic": True, "gemini": True},
        ):
            self.assertEqual(ui_kit.violations(self.render(**kw)), [], kw)


class CommandTests(_RoomEnv):
    def message(self, author, channel_id=100, name="Someone", parent=None):
        msg = MagicMock()
        msg.author.id = author
        msg.author.display_name = name
        msg.channel.parent = parent
        msg.reply = AsyncMock()
        return msg

    def run_command(self, author, channel, args, name="Someone", parent=None):
        msg = self.message(author, channel, name, parent)
        with patch.object(room_models, "provider_flags", return_value=(True, False)):
            asyncio.run(room_models.cmd_model(msg, args, parent_id=channel, registry=REGISTRY, default="gemma4:31b"))
        return msg

    def reply_view(self, msg):
        return msg.reply.await_args.kwargs["view"]

    def test_bare_command_replies_with_the_card(self):
        msg = self.run_command(SAM, 100, [], "Sam")
        self.assertIn("Who answers here", alltext(self.reply_view(msg)))
        self.assertIsNone(self.reply_view(msg).timeout)
        self.assertEqual(msg.reply.await_args.args, (), "a layout message carries no text beside it")

    def test_a_typed_pick_replies_with_the_card_already_changed(self):
        msg = self.run_command(SAM, 100, ["sonnet"], "Sam")
        view = self.reply_view(msg)
        self.assertEqual(room_models.pick_for(100), "claude-sonnet-5")
        self.assertIn("Claude Sonnet 5 answers here from now on.", alltext(view))
        self.assertIn("provider's servers", alltext(view))
        self.assertEqual([o["value"] for o in menu(view)["options"] if o.get("default")], ["sonnet"])

    def test_a_refusal_is_a_sentence_and_changes_nothing(self):
        msg = self.run_command(ALEX, 100, ["opus"])
        self.assertIn("Only the owner", msg.reply.await_args.args[0])
        self.assertIsNone(room_models.pick_for(100))
        msg = self.run_command(SAM, 100, ["gpt"])
        self.assertIn("I don't know that one", msg.reply.await_args.args[0])

    def test_a_room_with_no_owner_says_so_on_the_card(self):
        msg = self.run_command(SAM, 999, [])
        self.assertIn("no owner or members", alltext(self.reply_view(msg)))

    def test_any_member_changes_a_shared_room_and_the_card_says_who(self):
        msg = self.run_command(ALEX, 300, ["opus"], "Alex")
        self.assertIn("Alex set this room to Claude Opus 5.5.", alltext(self.reply_view(msg)))
        self.assertEqual(room_models.read_picks()["300"]["set_by"], "alex")

    def test_nobody_picks_for_a_shared_room_they_are_not_in(self):
        msg = self.run_command(SAM, 300, ["opus"])
        self.assertIn("Only members of this room", msg.reply.await_args.args[0])
        self.assertIsNone(room_models.pick_for(300))

    def test_a_change_made_in_an_eddy_is_also_said_in_the_room(self):
        parent = MagicMock(id=300, send=AsyncMock())
        self.run_command(ROBIN, 300, ["sonnet"], "Robin", parent=parent)
        parent.send.assert_awaited_once()
        self.assertIn("Robin set this room to Claude Sonnet 5.", parent.send.await_args.args[0])

    def test_german_speaker_gets_german(self):
        registry = {**REGISTRY, "mages": {**REGISTRY["mages"], "sam": {"discord_id": str(SAM), "locale": "de"}}}
        msg = self.message(SAM)
        with patch.object(room_models, "provider_flags", return_value=(True, False)):
            asyncio.run(room_models.cmd_model(msg, [], parent_id=100, registry=registry, default="gemma4:31b"))
        self.assertIn("Wer hier antwortet", alltext(self.reply_view(msg)))


class PressTests(_RoomEnv):
    def setUp(self):
        super().setUp()
        self.saved = (room_models._get_registry, room_models._resolve_channel)
        self.addCleanup(room_models.bind_room_lookup, *self.saved)
        room_models.bind_room_lookup(lambda: REGISTRY, lambda interaction: interaction.channel.parent_id)
        flags = patch.object(room_models, "provider_flags", return_value=(True, False))
        flags.start()
        self.addCleanup(flags.stop)

    def interaction(self, *, user=ALEX, parent=300, card=True, value="opus", name="Alex"):
        press = SimpleNamespace(
            data={"values": [value]},
            user=SimpleNamespace(id=user, display_name=name),
            channel=SimpleNamespace(id=999, parent_id=parent, parent=MagicMock(id=parent, send=AsyncMock())),
            message=SimpleNamespace(id=5, flags=SimpleNamespace(components_v2=card)),
            response=SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock()),
        )
        return press

    def test_the_press_changes_the_card_in_place_and_that_is_the_receipt(self):
        press = self.interaction()
        asyncio.run(room_models._on_pick(press))
        self.assertEqual(room_models.pick_for(300), "claude-opus-5-5")
        press.response.send_message.assert_not_awaited()
        view = press.response.edit_message.await_args.kwargs["view"]
        self.assertIn("Alex set this room to Claude Opus 5.5.", alltext(view))
        self.assertEqual([o["value"] for o in menu(view)["options"] if o.get("default")], ["opus"])
        press.channel.parent.send.assert_awaited()  # shared room: the room is told who

    def test_a_menu_posted_before_the_card_cannot_be_edited_so_the_answer_is_a_new_card(self):
        press = self.interaction(card=False)
        asyncio.run(room_models._on_pick(press))
        press.response.edit_message.assert_not_awaited()
        self.assertIn("Claude Opus 5.5", alltext(press.response.send_message.await_args.kwargs["view"]))
        self.assertEqual(room_models.pick_for(300), "claude-opus-5-5")

    def test_a_refused_press_is_for_the_presser_alone_and_writes_nothing(self):
        press = self.interaction(user=SAM)  # not a member of the family room
        asyncio.run(room_models._on_pick(press))
        self.assertTrue(press.response.send_message.await_args.kwargs["ephemeral"])
        self.assertIn("Only members", press.response.send_message.await_args.args[0])
        self.assertIsNone(room_models.pick_for(300))
        press.response.edit_message.assert_not_awaited()

    def test_a_press_before_the_posting_process_is_armed_says_not_ready(self):
        room_models.bind_room_lookup(None, None)
        press = self.interaction()
        asyncio.run(room_models._on_pick(press))
        self.assertIn("not ready", press.response.send_message.await_args.args[0])
        self.assertTrue(press.response.send_message.await_args.kwargs["ephemeral"])
        self.assertIsNone(room_models.pick_for(300))

    def test_one_listener_answers_every_menu_after_a_restart(self):
        client = MagicMock()
        room_models.register_model_view(client)
        view = client.add_view.call_args.args[0]
        self.assertTrue(view.is_persistent())
        self.assertEqual(menu(view)["custom_id"], room_models.MODEL_SELECT_ID)
        rendered = room_models.render(100, "gemma4:31b", REGISTRY, anthropic=True, gemini=False)
        self.assertEqual(menu(rendered)["custom_id"], menu(view)["custom_id"], "the card's menu is the one the listener answers")
        self.assertTrue(rendered.is_persistent())
        self.assertEqual(buttons(rendered), [])

    def test_arming_the_posting_process_makes_the_press_land(self):
        room_models.bind_room_lookup(None, None)
        client = MagicMock()
        room_models.arm_model_menu(client, lambda: REGISTRY, lambda interaction: interaction.channel.parent_id)
        press = self.interaction()
        asyncio.run(room_models._on_pick(press))
        self.assertEqual(room_models.pick_for(300), "claude-opus-5-5")
        self.assertEqual(client.add_view.call_count, 3, "the model menu, the `!` list's button, the menu checklist")


if __name__ == "__main__":
    unittest.main()
