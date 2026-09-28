"""Own-channel model picks and the pull guard — docs/design/own-channel-model.md."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub()

import room_models  # noqa: E402
from discord_ref_read import (  # noqa: E402
    FRONTIER_BUDGET,
    LOCAL_BUDGET,
    UNKNOWN,
    UNSEEN,
    _fetch_one_target,
    format_discord_ref_for_dialogue,
    pull_refusal,
    pull_widens,
    read_channel_activity,
)

SAM, ALEX, ROBIN = 11, 22, 33
REGISTRY = {
    "mages": {
        "sam": {"discord_id": str(SAM)},
        "alex": {"discord_id": str(ALEX)},
        "robin": {"discord_id": str(ROBIN)},
    },
    "channels": {
        "100": {"type": "hosted-river", "mage": "sam"},
        "200": {"type": "river", "mage": "alex"},
        "300": {"type": "shared-river", "mage": "family"},
        "400": {"type": "shared-river", "mage": "community"},
        "500": {"type": "river", "mage": "robin", "archived": True},
        "600": {"type": "health", "primitive": "health", "mage": "care"},
        "620": {"type": "craft", "primitive": "craft", "mage": "sam"},
        "610": {"type": "health", "primitive": "health", "mage": "sam",
                "subject": "sam", "base": "solo"},
    },
    "spaces": {
        "family": {"members": ["alex", "robin"], "memory": "own_root",
                   "share_policy": "members_only"},
        "care": {"members": ["robin", "sam"], "subject": "sam", "steward": "robin",
                 "memory": "isolated", "share_policy": "members_only"},
    },
}


def _use_api(model):
    return str(model).startswith("claude-")


class _RoomEnv(unittest.TestCase):
    def setUp(self):
        self.house = tempfile.TemporaryDirectory()
        patches = [
            patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": self.house.name}),
            patch.object(room_models, "_use_api", side_effect=_use_api),
            patch.object(room_models, "_local_model", return_value="gemma4:31b"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.house.cleanup)

    def picks_file(self):
        return os.path.join(self.house.name, room_models.PICKS_FILE)


class OwnerPickTests(_RoomEnv):
    def test_owner_pick_reaches_an_eddy_opened_before_it(self):
        stamped_at_spawn = {"model": "gemma4:31b", "use_api": False}
        before = room_models.resolve_room_model(100, stamped_at_spawn, "gemma4:31b")
        self.assertEqual(before[:2], ("gemma4:31b", False))

        room_models.set_pick(100, SAM, "sonnet", REGISTRY)

        model, use_api, source = room_models.resolve_room_model(100, stamped_at_spawn, "gemma4:31b")
        self.assertEqual((model, use_api, source), ("claude-sonnet-5", True, "pick"))

    def test_someone_else_cannot_pick_for_her_channel_and_nothing_is_written(self):
        with self.assertRaises(room_models.PickRefused) as refused:
            room_models.set_pick(100, ALEX, "opus", REGISTRY)
        self.assertEqual(str(refused.exception), "not_owner")
        self.assertFalse(os.path.exists(self.picks_file()))

    def test_shared_and_archived_rooms_are_not_owner_picked(self):
        for room in (300, 400, 500, 999):
            with self.assertRaises(room_models.PickRefused):
                room_models.set_pick(room, SAM, "sonnet", REGISTRY)
        self.assertFalse(os.path.exists(self.picks_file()))

    def test_a_health_channel_is_its_owners_to_pick_even_with_support_in_it(self):
        # 2026-09-27: `!model` in a member's health channel answered "shared
        # room" — health was read by channel type, and only river types were owned.
        self.assertEqual(room_models.set_pick(600, SAM, "sonnet", REGISTRY), "claude-sonnet-5")
        self.assertEqual(room_models.set_pick(610, SAM, "opus", REGISTRY), "claude-opus-5-5")
        with self.assertRaises(room_models.PickRefused) as refused:
            room_models.set_pick(600, ROBIN, "local", REGISTRY)
        self.assertEqual(str(refused.exception), "not_owner")
        self.assertEqual(room_models.pick_for(600), "claude-sonnet-5")

    def test_local_clears_the_pick(self):
        room_models.set_pick(100, SAM, "opus", REGISTRY)
        self.assertEqual(room_models.pick_for(100), "claude-opus-5-5")
        room_models.set_pick(100, SAM, "local", REGISTRY)
        self.assertIsNone(room_models.pick_for(100))
        with open(self.picks_file()) as fh:
            self.assertEqual(json.loads(fh.read()), {})

    def test_unknown_word_refused(self):
        with self.assertRaises(room_models.PickRefused) as refused:
            room_models.set_pick(100, SAM, "gpt", REGISTRY)
        self.assertEqual(str(refused.exception), "unknown")

    def test_explicit_eddy_override_beats_the_room_pick(self):
        room_models.set_pick(100, SAM, "sonnet", REGISTRY)
        cfg = {"model": "gemma4:12b", "use_api": False, "model_source": "explicit"}
        self.assertEqual(
            room_models.resolve_room_model(100, cfg, "gemma4:31b"),
            ("gemma4:12b", False, "explicit"),
        )

    def test_craft_eddy_stamped_with_an_old_model_follows_the_current_default(self):
        cfg = {"model": "claude-sonnet-4-6", "use_api": True}
        self.assertEqual(
            room_models.resolve_room_model(700, cfg, "claude-sonnet-5"),
            ("claude-sonnet-5", True, "default"),
        )

    def test_cloud_pick_without_a_working_key_answers_locally(self):
        room_models.set_pick(100, SAM, "sonnet", REGISTRY)
        with patch.object(room_models, "_use_api", return_value=False):
            self.assertEqual(
                room_models.resolve_room_model(100, None, "gemma4:31b")[:2], ("gemma4:31b", False))

    def test_link_budget_follows_the_room_model(self):
        self.assertFalse(room_models.room_reads_on_cloud(100, None, "gemma4:31b"))
        room_models.set_pick(100, SAM, "sonnet", REGISTRY)
        self.assertTrue(room_models.room_reads_on_cloud(100, None, "gemma4:31b"))

    def test_owner_line_only_in_owned_rooms(self):
        self.assertIn("!model", room_models.owner_line(100, REGISTRY))
        # 2026-09-27: asked what it could see elsewhere, the home Turtle said it
        # could not see other channels at all — while it would read any link pasted.
        self.assertIn("Discord link", room_models.owner_line(100, REGISTRY))
        self.assertEqual(room_models.owner_line(400, REGISTRY), "")


class CommandTests(_RoomEnv):
    def _message(self, author, channel_id):
        msg = MagicMock()
        msg.author.id = author
        msg.reply = AsyncMock()
        return msg, channel_id

    async def _run(self, author, channel_id, args, name="Someone"):
        msg, ch = self._message(author, channel_id)
        msg.author.display_name = name
        msg.channel.parent = None
        await room_models.cmd_model(
            msg, args, parent_id=ch, registry=REGISTRY, default="gemma4:31b")
        return msg.reply.await_args.args[0]

    def test_pick_confirms_and_names_the_provider_leg(self):
        import asyncio

        text = asyncio.run(self._run(SAM, 100, ["sonnet"]))
        self.assertIn("Claude Sonnet 5", text)
        self.assertIn("provider's servers", text)
        self.assertEqual(room_models.pick_for(100), "claude-sonnet-5")

    def test_bare_command_lists_the_choices(self):
        import asyncio

        text = asyncio.run(self._run(SAM, 100, []))
        for word in ("!model sonnet", "!model opus", "!model local"):
            self.assertIn(word, text)

    def test_any_member_changes_a_shared_room_and_the_room_is_told_who(self):
        import asyncio

        text = asyncio.run(self._run(ALEX, 300, ["opus"], name="Alex"))
        self.assertIn("**Alex** set this room to", text)
        self.assertIn("community account pays", text)
        self.assertEqual(room_models.pick_for(300), "claude-opus-5-5")
        self.assertEqual(room_models.read_picks()["300"]["set_by"], "alex")

    def test_nobody_picks_for_a_shared_room_they_are_not_in(self):
        import asyncio

        text = asyncio.run(self._run(SAM, 300, ["opus"]))
        self.assertIn("Only members of this room", text)
        self.assertIsNone(room_models.pick_for(300))

    def test_a_change_made_in_an_eddy_is_also_said_in_the_room(self):
        import asyncio

        msg, _ = self._message(ROBIN, 300)
        msg.author.display_name = "Robin"
        msg.channel.parent = MagicMock(id=300, send=AsyncMock())
        asyncio.run(room_models.cmd_model(
            msg, ["sonnet"], parent_id=300, registry=REGISTRY, default="gemma4:31b"))
        msg.channel.parent.send.assert_awaited_once()
        self.assertIn("**Robin** set this room to", msg.channel.parent.send.await_args.args[0])

    def test_a_solo_craft_room_is_its_members_to_pick(self):
        self.assertEqual(room_models.set_pick(620, SAM, "opus", REGISTRY), "claude-opus-5-5")
        with self.assertRaises(room_models.PickRefused):
            room_models.set_pick(620, ALEX, "local", REGISTRY)

    def test_shared_room_prompt_says_members_choose(self):
        self.assertIn("members' choice", room_models.owner_line(300, REGISTRY))
        self.assertEqual(room_models.owner_line(400, REGISTRY), "")

    def test_health_picker_says_what_the_provider_would_read(self):
        import asyncio

        listing = asyncio.run(self._run(SAM, 600, []))
        self.assertIn("health board", listing)
        self.assertIn("Uploads are still read in the house", listing)
        confirm = asyncio.run(self._run(SAM, 600, ["sonnet"]))
        self.assertIn("health board", confirm)
        plain = asyncio.run(self._run(SAM, 100, []))
        self.assertNotIn("health board", plain)


# ── pull guard ──────────────────────────────────────────────────


class _Perms:
    def __init__(self, ok):
        self.view_channel = ok
        self.read_message_history = ok


class _Member:
    def __init__(self, uid, bot=False):
        self.id = uid
        self.bot = bot


class _Guild:
    def __init__(self, members):
        self.id = 1
        self.members = members

    def get_member(self, uid):
        return next((m for m in self.members if m.id == uid), None)

    async def fetch_member(self, uid):
        raise LookupError("unknown member")


class _Room:
    def __init__(self, cid, guild, readers, *, type_=None, parent=None, thread_members=None):
        self.id = cid
        self.guild = guild
        self._readers = set(readers)
        self.type = type_ if type_ is not None else discord.ChannelType.text
        self.parent = parent
        self.owner_id = None
        self._thread_members = thread_members

    def permissions_for(self, member):
        room = self.parent if self.parent is not None else self
        return _Perms(member.id in room._readers)

    async def fetch_member(self, uid):
        if self._thread_members is None or uid not in self._thread_members:
            raise LookupError("not a member")
        return _Member(uid)


class PullGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = _Guild([_Member(SAM), _Member(ALEX), _Member(ROBIN), _Member(9, bot=True)])
        g = self.guild
        self.sam_private = _Room(100, g, {SAM})
        self.alex_private = _Room(200, g, {ALEX})
        self.family = _Room(300, g, {SAM, ALEX})
        self.atrium = _Room(400, g, {SAM, ALEX, ROBIN})

    def eddy(self, parent, **kw):
        return _Room(parent.id * 10 + 1, self.guild, set(), parent=parent,
                     type_=kw.pop("type_", discord.ChannelType.public_thread), **kw)

    async def test_she_brings_a_shared_room_into_her_own_channel(self):
        self.assertIsNone(await pull_refusal(self.family, self.sam_private, SAM))
        self.assertIsNone(await pull_refusal(self.eddy(self.atrium), self.eddy(self.sam_private), SAM))

    async def test_a_link_to_someone_elses_private_channel_is_not_read(self):
        self.assertEqual(await pull_refusal(self.alex_private, self.sam_private, SAM), UNSEEN)
        self.assertEqual(await pull_refusal(self.eddy(self.alex_private), self.atrium, SAM), UNSEEN)

    async def test_a_member_may_bring_a_shared_room_anywhere_and_is_told_when_it_widens(self):
        # The commons (2026-09-27): what a member brings where is their judgement.
        # Nothing refuses it; the widening is named instead.
        for source, dest in (
            (self.eddy(self.family), self.atrium),
            (self.eddy(self.sam_private), self.atrium),
            (self.eddy(self.family), self.sam_private),
        ):
            self.assertIsNone(await pull_refusal(source, dest, SAM))
        self.assertTrue(await pull_widens(self.eddy(self.family), self.atrium))
        self.assertFalse(await pull_widens(self.eddy(self.family), self.sam_private))
        self.assertFalse(await pull_widens(self.eddy(self.atrium), self.atrium))

    async def test_a_widening_read_says_so_to_the_room_and_the_model(self):
        msg = MagicMock()
        msg.content = "we booked the train"
        msg.author.display_name = "Alex"
        msg.author.bot = False
        msg.attachments = []
        msg.id = 5
        msg.channel = self.family
        self.family.fetch_message = AsyncMock(return_value=msg)
        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=self.family)
        wide = await _fetch_one_target(client, 1, 300, 5, label="x", destination=self.atrium, user_id=SAM)
        narrow = await _fetch_one_target(client, 1, 300, 5, label="x", destination=self.sam_private, user_id=SAM)
        self.assertTrue(wide.ok and wide.widened)
        self.assertFalse(narrow.widened)
        self.assertIn("can't see where this link points", format_discord_ref_for_dialogue(wide))
        self.assertNotIn("can't see where this link points", format_discord_ref_for_dialogue(narrow))
        from discord_ref_read import _status_embed_single

        with patch("discord_ref_read.discord.Embed", side_effect=lambda **kw: kw):
            self.assertIn("Heads-up", _status_embed_single(wide)["description"])
            self.assertNotIn("Heads-up", _status_embed_single(narrow)["description"])

    async def test_private_thread_needs_membership(self):
        secret = self.eddy(self.family, type_=discord.ChannelType.private_thread, thread_members={ALEX})
        self.assertEqual(await pull_refusal(secret, self.sam_private, SAM), UNSEEN)
        mine = self.eddy(self.family, type_=discord.ChannelType.private_thread, thread_members={SAM})
        self.assertIsNone(await pull_refusal(mine, self.sam_private, SAM))

    async def test_what_cannot_be_established_refuses(self):
        self.assertEqual(await pull_refusal(self.family, self.sam_private, None), UNKNOWN)
        self.assertEqual(await pull_refusal(self.family, self.sam_private, 777), UNSEEN)
        homeless = _Room(600, None, set())
        self.assertEqual(await pull_refusal(homeless, self.sam_private, SAM), UNKNOWN)

    async def test_a_refused_link_is_never_read(self):
        """Positive control on the wiring: refusal stops the read, not just the label."""
        source = self.alex_private
        source.fetch_message = AsyncMock()
        source.history = MagicMock()
        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=source)
        result = await _fetch_one_target(
            client, 1, 200, 5, label="x", destination=self.sam_private, user_id=SAM)
        self.assertFalse(result.ok)
        self.assertEqual(result.refused, UNSEEN)
        source.fetch_message.assert_not_awaited()
        source.history.assert_not_called()
        block = format_discord_ref_for_dialogue(result)
        self.assertIn("not read", block)
        self.assertNotIn("alex", block.lower())

    async def test_an_allowed_link_is_read(self):
        msg = MagicMock()
        msg.content = "we booked the train"
        msg.author.display_name = "Alex"
        msg.author.bot = False
        msg.attachments = []
        msg.id = 5
        msg.channel = self.family
        self.family.fetch_message = AsyncMock(return_value=msg)
        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=self.family)
        result = await _fetch_one_target(
            client, 1, 300, 5, label="x", destination=self.sam_private, user_id=SAM)
        self.assertTrue(result.ok)
        self.assertIn("booked the train", result.content)


async def _aiter(items):
    for item in items:
        yield item


def _msg(text, who="Alex"):
    m = MagicMock()
    m.content = text
    m.author.display_name = who
    m.author.bot = False
    m.attachments = []
    return m


class ChannelReadTests(unittest.IsolatedAsyncioTestCase):
    def _channel(self, eddies):
        ch = MagicMock()
        ch.id = 300
        ch.name = "family"
        ch.history = lambda limit, after=None, oldest_first=False: _aiter([_msg("top-level note")])
        ch.threads = eddies
        ch.archived_threads = lambda limit=50: _aiter([])
        return ch

    def _eddy(self, name, days_ago, lines):
        t = MagicMock()
        t.id = hash(name) & 0xFFFF
        t.name = name
        t.type = discord.ChannelType.public_thread
        t.last_message_id = None
        t.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        t.history = lambda limit, after=None, oldest_first=False: _aiter(
            [_msg(x) for x in reversed(lines)][:limit])
        return t

    async def test_channel_link_reads_recent_eddies_not_old_ones(self):
        ch = self._channel([
            self._eddy("Antrag Unterlagen", 1, ["first", "second"]),
            self._eddy("Holiday", 30, ["old news"]),
        ])
        result = await read_channel_activity(ch, 1, LOCAL_BUDGET)
        self.assertEqual(result.scope, "channel")
        self.assertIn("Eddy: Antrag Unterlagen", result.content)
        self.assertIn("top-level note", result.content)
        self.assertNotIn("old news", result.content)
        self.assertLess(result.content.index("first"), result.content.index("second"))

    async def test_frontier_budget_reads_long_activity_without_a_local_summary(self):
        long_lines = [f"line {i} " + "x" * 400 for i in range(40)]
        ch = self._channel([self._eddy("Long", 1, long_lines)])
        summarize = AsyncMock(return_value="short")
        with patch("discord_ref_read.summarize_thread_lines", new=summarize):
            local = await read_channel_activity(ch, 1, LOCAL_BUDGET)
            frontier = await read_channel_activity(ch, 1, FRONTIER_BUDGET)
        self.assertLess(local.message_count, frontier.message_count)
        self.assertFalse(frontier.summarized)
        self.assertIn("line 39", frontier.content)
        self.assertGreater(FRONTIER_BUDGET.inject_max, LOCAL_BUDGET.inject_max)


if __name__ == "__main__":
    unittest.main()
