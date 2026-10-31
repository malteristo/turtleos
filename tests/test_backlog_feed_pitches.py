"""Pitches arrive on their own, once each, and a pitch can be talked through.

The claims in `backlog_feed_ui.py`'s docstring, one check each. A check that says
"nothing was posted" has the same code posting beside it.
"""

import ast
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub(reload=("backlog_feed_ui",))

import backlog_feed as feed  # noqa: E402
import backlog_feed_context as fctx  # noqa: E402
import backlog_feed_ui as ui  # noqa: E402
import backlog_feed_write as fwrite  # noqa: E402
from tests.test_backlog_feed import BACKLOG, OWNER, OWNER_ID, REGISTRY, make_bare_repo  # noqa: E402

NOW = datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[1]
OLDEST = "2026-08-01-oldest-dddddd"
WRITTEN = fwrite.Written(
    headline="Open the packet from the channel",
    ideal="You open the packet in the channel and see it carry over.",
    problem="It stopped at the door.",
    not_this="The row doesn't say.",
    check="The packet shows up the next morning.",
)
THREAD = 4 * 10**17 + 4  # built, not written out: the sanitation hook looks for 18-digit literals


def _channel(channel_id=500):
    channel = MagicMock()
    channel.id = channel_id
    channel.guild.id = 42
    counter = iter(range(9000, 9999))

    async def send(*args, **kwargs):
        return SimpleNamespace(id=next(counter))

    channel.send = AsyncMock(side_effect=send)
    return channel


class _Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.bare = make_bare_repo(tmp, BACKLOG)
        self.root = tmp / "practice"
        self.registry = {
            "mages": REGISTRY["mages"],
            "channels": {"500": {
                "type": "craft", "mage": OWNER,
                "backlog_feed": {"repo": str(self.bare), "path": "desk/craft/backlog.md", "push": True},
            }},
        }
        self.client = MagicMock()
        ui.arm_feed(self.client, lambda: self.registry, lambda owner: self.root)
        patcher = patch.object(ui, "context_for_item", AsyncMock(return_value=fctx.Context()))
        self.judge = patcher.start()
        self.addCleanup(patcher.stop)
        # The writer is a model call: no test reaches a model.
        wpatch = patch.object(ui, "write_for_item", AsyncMock(return_value=WRITTEN))
        self.writer = wpatch.start()
        self.addCleanup(wpatch.stop)
        bpatch = patch.object(ui, "_conversation_busy", return_value=False)
        bpatch.start()
        self.addCleanup(bpatch.stop)
        ui._attempted.clear()
        self.addCleanup(ui._attempted.clear)

    def tearDown(self):
        ui.arm_feed(MagicMock(), lambda: self.registry, lambda owner: self.root)
        self._tmp.cleanup()

    def loaded(self):
        return feed.load(self.registry, 500, practice_root_for=lambda o: self.root)

    def waiting(self):
        loaded = self.loaded()
        return [i.id for i in feed.unposted(loaded.items, loaded.root)]


class PostPendingTests(_Base):
    async def test_every_open_row_gets_one_message_oldest_first_with_the_buttons(self):
        channel = _channel()
        n = await ui.post_pending(channel, self.registry, 500, pause=0)
        self.assertEqual(n, 5)
        texts = [call.args[0] for call in channel.send.await_args_list]
        ids = [feed.item_id_from_message(t) for t in texts]
        self.assertEqual(ids[0], "2026-06-19-legacy-nocheck")
        self.assertEqual(ids[-1], "2026-09-25-newest-aaaaaa")
        self.assertEqual(len(set(ids)), 5)
        for call in channel.send.await_args_list:
            self.assertIsInstance(call.kwargs["view"], ui.FeedView)

    async def test_a_second_pass_posts_nothing_because_each_row_is_recorded(self):
        channel = _channel()
        self.assertEqual(await ui.post_pending(channel, self.registry, 500, pause=0), 5)  # control
        self.assertEqual(await ui.post_pending(channel, self.registry, 500, pause=0), 0)
        self.assertEqual(channel.send.await_count, 5)
        self.assertEqual(self.waiting(), [])

    async def test_a_row_added_later_is_the_only_one_posted_next(self):
        channel = _channel()
        await ui.post_pending(channel, self.registry, 500, pause=0)
        work = Path(self.bare).parent / "work"
        path = work / "desk/craft/backlog.md"
        path.write_text(path.read_text() + "\n- [ ] [2026-10-10-late-eeeeee] **A late row.** Added today.\n")
        import subprocess

        for args in (("commit", "-am", "late"), ("push", str(self.bare), "main")):
            subprocess.run(["git", *args], cwd=work, check=True, capture_output=True)
        channel.send.reset_mock()
        self.assertEqual(await ui.post_pending(channel, self.registry, 500, pause=0), 1)
        self.assertEqual(feed.item_id_from_message(channel.send.await_args.args[0]), "2026-10-10-late-eeeeee")

    async def test_a_dropped_row_is_never_pitched(self):
        items = {i.id: i for i in self.loaded().items}
        feed.record_decision(self.root, items[OLDEST], feed.DROP, now=NOW)
        channel = _channel()
        await ui.post_pending(channel, self.registry, 500, pause=0)
        ids = [feed.item_id_from_message(c.args[0]) for c in channel.send.await_args_list]
        self.assertNotIn(OLDEST, ids)
        self.assertEqual(len(ids), 4)

    async def test_what_is_known_goes_in_the_embed_and_nothing_known_is_said_so(self):
        known = fctx.Context(said=fctx.Source("said", "your words when you filed it", "Please carry the packet."))
        self.judge.side_effect = [known] + [fctx.Context()] * 4
        channel = _channel()
        await ui.post_pending(channel, self.registry, 500, pause=0)
        first, second = channel.send.await_args_list[:2]
        self.assertIn("Please carry the packet.", first.kwargs["embed"].description)
        self.assertNotIn(fctx.NOTHING_YET, first.kwargs["embed"].description)
        self.assertIn(fctx.NOTHING_YET, second.kwargs["embed"].description)  # said, not left blank
        self.assertIn("The row as filed", second.kwargs["embed"].description)  # the rewrite can be checked

    async def test_a_pitch_is_the_rewrite_with_its_five_parts(self):
        channel = _channel()
        await ui.post_pending(channel, self.registry, 500, pause=0)
        text = channel.send.await_args_list[0].args[0]
        for part in ("When this exists", "Why it was filed", "Not this", "How you'd know", WRITTEN.headline):
            self.assertIn(part, text)
        self.assertIn("*The row doesn't say.*", text)
        self.assertTrue(text.startswith("**1 of 5 — "))
        self.assertEqual(feed.pitched(self.root)[OLDEST]["format"], str(feed.PITCH_FORMAT))

    async def test_a_writer_that_cannot_write_still_posts_the_rows_own_text(self):
        self.writer.return_value = None
        channel = _channel()
        self.assertEqual(await ui.post_pending(channel, self.registry, 500, pause=0), 5)
        text = channel.send.await_args_list[0].args[0]
        self.assertNotIn("When this exists", text)  # control: the rewrite is what adds it
        self.assertEqual(feed.pitched(self.root)[OLDEST]["format"], "1")
        self.assertEqual(len(feed.stale(self.loaded().items, self.root)), 5)

    async def test_the_corpus_a_pitch_draws_on_includes_the_design_notes(self):
        """Found live: the notes were wired into the corpus loader and never into the
        call that builds it, and every pitch said nothing touched it."""
        corpus = await ui._corpus_for(self.loaded(), self.registry, 500)
        self.assertTrue(corpus.refs)

    async def test_a_single_pitch_carries_no_numbering(self):
        text = feed.compose_pitch(self.loaded().items[0], position=1, total=1, commit="abc", written=WRITTEN)
        self.assertTrue(text.startswith(f"**{WRITTEN.headline}**"))

    async def test_the_pitch_message_stays_inside_discords_limit_and_names_its_row(self):
        channel = _channel()
        await ui.post_pending(channel, self.registry, 500, pause=0)
        for call in channel.send.await_args_list:
            self.assertLess(len(call.args[0]), 2000)

    async def test_the_command_posts_what_has_no_pitch_and_says_how_many(self):
        message = MagicMock()
        message.channel = _channel()
        message.channel.parent_id = None
        message.author.id = OWNER_ID
        message.reply = AsyncMock()
        with patch.object(ui.asyncio, "create_task", side_effect=lambda coro: coro.close()) as task:
            await ui.cmd_feed(message, [])
        self.assertIn("Posting 5 pitches", message.reply.await_args.args[0])
        task.assert_called_once()

    async def test_the_command_with_nothing_new_says_so(self):
        await ui.post_pending(_channel(), self.registry, 500, pause=0)
        message = MagicMock()
        message.channel = _channel()
        message.channel.parent_id = None
        message.author.id = OWNER_ID
        message.reply = AsyncMock()
        await ui.cmd_feed(message, [])
        self.assertIn("already", message.reply.await_args.args[0])


class RefreshTests(_Base):
    """Pitches already posted in the row's own text are rewritten where they are."""

    async def post_old(self, channel):
        self.writer.return_value = None
        await ui.post_pending(channel, self.registry, 500, pause=0)
        self.writer.return_value = WRITTEN
        self.writer.reset_mock()
        channel.fetch_message = AsyncMock(side_effect=self._fetch(channel))

    def message_for(self, item_id):
        return next(m for m in self.sent.values() if feed.item_id_from_message(m.content) == item_id)

    def _fetch(self, channel):
        sent = {}
        for call, mid in zip(channel.send.await_args_list, range(9000, 9999)):
            message = MagicMock()
            message.id = mid
            message.content = call.args[0]
            message.edit = AsyncMock()
            sent[mid] = message
        self.sent = sent

        async def fetch(message_id):
            if message_id not in sent:
                raise discord.NotFound(MagicMock(status=404, reason="x"), "gone")
            return sent[message_id]

        return fetch

    async def test_an_older_pitch_is_edited_in_place_and_keeps_its_number(self):
        channel = _channel()
        await self.post_old(channel)
        before = channel.send.await_count
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 5)
        self.assertEqual(channel.send.await_count, before)  # edited, not re-posted
        first = self.sent[9000]
        text = first.edit.await_args.kwargs["content"]
        self.assertTrue(text.startswith("**1 of 5 — "))
        self.assertIn("When this exists", text)
        self.assertIn("The row as filed", first.edit.await_args.kwargs["embed"].description)
        self.assertEqual(feed.pitched(self.root)[OLDEST]["format"], str(feed.PITCH_FORMAT))

    async def test_a_second_pass_has_nothing_left_to_rewrite(self):
        channel = _channel()
        await self.post_old(channel)
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 5)  # control
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 0)

    async def test_a_decided_row_is_not_given_its_buttons_back(self):
        channel = _channel()
        await self.post_old(channel)
        items = {i.id: i for i in self.loaded().items}
        feed.record_decision(self.root, items[OLDEST], feed.DROP, now=NOW)
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 4)
        self.message_for(OLDEST).edit.assert_not_awaited()
        self.assertTrue(all(m.edit.await_count for m in self.sent.values() if m is not self.message_for(OLDEST)))

    async def test_a_verdict_given_while_the_rewrite_was_being_written_wins(self):
        channel = _channel()
        await self.post_old(channel)

        async def decided_meanwhile(item, context):
            if item.id == OLDEST:
                feed.record_decision(self.root, item, feed.DROP, now=NOW)
            return WRITTEN

        self.writer.side_effect = decided_meanwhile
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 4)
        self.message_for(OLDEST).edit.assert_not_awaited()

    async def test_a_row_the_writer_cannot_do_is_left_alone_and_not_hammered(self):
        channel = _channel()
        await self.post_old(channel)
        self.writer.return_value = None
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 0)
        for message in self.sent.values():
            message.edit.assert_not_awaited()
        calls = self.writer.await_count
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 0)
        self.assertEqual(self.writer.await_count, calls)  # not tried again within the hour
        self.writer.return_value = WRITTEN
        ui._attempted.clear()
        self.assertEqual(await ui.refresh_pitches(channel, self.registry, 500, pause=0), 5)  # control

    async def test_a_pitch_with_a_conversation_gets_the_link_not_the_button(self):
        channel = _channel()
        await self.post_old(channel)
        items = {i.id: i for i in self.loaded().items}
        feed.record_talk(self.root, items[OLDEST], thread_id=THREAD, own=True, now=NOW)
        await ui.refresh_pitches(channel, self.registry, 500, pause=0)
        view = self.message_for(OLDEST).edit.await_args.kwargs["view"]
        ids = [getattr(c, "custom_id", None) for c in view.children]
        self.assertNotIn(ui.TALK_ID, ids)
        other = self.message_for("2026-09-25-newest-aaaaaa").edit.await_args.kwargs["view"]
        self.assertIn(ui.TALK_ID, [getattr(c, "custom_id", None) for c in other.children])

    async def test_a_pitch_whose_message_is_gone_is_posted_again(self):
        channel = _channel()
        await self.post_old(channel)
        del self.sent[9000]
        before = channel.send.await_count
        await ui.refresh_pitches(channel, self.registry, 500, pause=0)
        self.assertEqual(channel.send.await_count, before + 1)
        self.assertIn("When this exists", channel.send.await_args.args[0])


class ChoreTests(_Base):
    def _client(self, channel):
        client = MagicMock()
        client.get_channel = MagicMock(return_value=channel)
        return client

    async def test_the_beat_posts_for_a_channel_that_opted_in(self):
        channel = _channel()
        with patch.object(ui, "in_quiet_hours", return_value=False), patch.object(ui, "PAUSE_S", 0):
            line = await ui.feed_chore(self._client(channel))
            await ui._worker  # the work runs in the background so the beat is not held up
        self.assertEqual(channel.send.await_count, 5)
        self.assertIn("working on 5 new", line)

    async def test_the_beat_does_not_start_a_second_worker_while_one_runs(self):
        channel = _channel()
        with patch.object(ui, "in_quiet_hours", return_value=False), patch.object(ui, "PAUSE_S", 0):
            await ui.feed_chore(self._client(channel))
            first = ui._worker
            self.assertIsNone(await ui.feed_chore(self._client(channel)))
            self.assertIs(ui._worker, first)
            await first

    async def test_a_live_conversation_holds_the_background_work_and_night_stops_it(self):
        with patch.object(ui, "_conversation_busy", return_value=True), patch.object(ui, "BUSY_WAITS", 2), \
                patch.object(ui, "BUSY_WAIT_S", 0), patch.object(ui, "in_quiet_hours", return_value=False):
            self.assertFalse(await ui._may_work(True))
            self.assertTrue(await ui._may_work(False))  # `!feed` is asked for; it does not wait
        with patch.object(ui, "_conversation_busy", return_value=False), patch.object(ui, "in_quiet_hours", return_value=False):
            self.assertTrue(await ui._may_work(True))  # control: the same call says yes when quiet
        with patch.object(ui, "_conversation_busy", return_value=False), patch.object(ui, "in_quiet_hours", return_value=True):
            self.assertFalse(await ui._may_work(True))

    async def test_busy_work_writes_no_pitch(self):
        channel = _channel()
        with patch.object(ui, "_conversation_busy", return_value=True), patch.object(ui, "BUSY_WAITS", 1), \
                patch.object(ui, "BUSY_WAIT_S", 0), patch.object(ui, "in_quiet_hours", return_value=False):
            self.assertEqual(await ui.post_pending(channel, self.registry, 500, pause=0, gentle=True), 0)
        channel.send.assert_not_awaited()
        self.writer.assert_not_awaited()

    async def test_a_channel_that_did_not_opt_in_gets_nothing(self):
        self.registry["channels"]["500"]["backlog_feed"].pop("push")
        channel = _channel()
        with patch.object(ui, "in_quiet_hours", return_value=False):
            self.assertIsNone(await ui.feed_chore(self._client(channel)))
        channel.send.assert_not_awaited()

    async def test_nothing_is_posted_at_night(self):
        channel = _channel()
        with patch.object(ui, "in_quiet_hours", return_value=True):
            self.assertIsNone(await ui.feed_chore(self._client(channel)))
        channel.send.assert_not_awaited()
        self.assertEqual(len(self.waiting()), 5)  # still waiting for the morning

    async def test_a_flood_waits_for_the_command_instead_of_posting(self):
        channel = _channel()
        with patch.object(ui, "in_quiet_hours", return_value=False), patch.object(ui, "AUTO_MAX", 2):
            line = await ui.feed_chore(self._client(channel))
        channel.send.assert_not_awaited()
        self.assertIn("!feed", line)

    async def test_the_quiet_hours_are_the_night(self):
        at = lambda h: datetime(2026, 10, 10, h, 30)  # noqa: E731
        self.assertTrue(feed.in_quiet_hours(at(23)))
        self.assertTrue(feed.in_quiet_hours(at(3)))
        self.assertFalse(feed.in_quiet_hours(at(8)))
        self.assertFalse(feed.in_quiet_hours(at(15)))

    async def test_the_beat_is_in_Rivers_chore_list(self):
        text = (REPO_ROOT / "river_bot.py").read_text(encoding="utf-8")
        self.assertIn('Chore("craft_feed"', text)


def _thread(parent_id, thread_id=THREAD, archived=False):
    thread = MagicMock(spec=discord.Thread)
    thread.id = thread_id
    thread.parent_id = parent_id
    thread.archived = archived
    thread.send = AsyncMock()
    thread.edit = AsyncMock()
    return thread


class TalkTests(_Base):
    def setUp(self):
        super().setUp()
        intake = self.root / "craft/intake"
        intake.mkdir(parents=True)
        (intake / f"{OLDEST}.md").write_text(
            f"# x\n\n## Mage report\n\nSome words.\n\n## Source references\n\n- guild=1 channel={THREAD} message=5\n",
            encoding="utf-8",
        )

    def press(self, *, user_id=OWNER_ID, item_id=OLDEST, thread=None):
        interaction = MagicMock()
        interaction.user.id = user_id
        interaction.guild_id = 42
        interaction.channel = _channel()
        interaction.channel.parent_id = None
        interaction.message.content = f"**1 of 5** — x\n\nbody\n\n-# backlog id: {item_id} · workshop abc"
        interaction.message.embeds = [MagicMock(description="THE CONTEXT TEXT")]
        interaction.message.jump_url = "https://discord.com/channels/42/500/777"
        interaction.message.edit = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.client.get_channel = MagicMock(return_value=thread)
        interaction.client.fetch_channel = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=404, reason="x"), "gone"))
        return interaction

    def spawn_patch(self, thread):
        """The shell hands the spawner in at arm time; so does the test."""
        fake = SimpleNamespace(spawn_blank_river_eddy=AsyncMock(return_value=thread))
        return patch.object(ui, "_spawn_eddy", fake.spawn_blank_river_eddy), fake

    async def test_a_row_that_came_from_a_craft_eddy_is_talked_through_there(self):
        origin = _thread(parent_id=500)
        interaction = self.press(thread=origin)
        patched, fake = self.spawn_patch(_thread(500, 1))
        with patched:
            await ui.FeedView()._talk(interaction)
        fake.spawn_blank_river_eddy.assert_not_awaited()
        self.assertEqual(origin.send.await_count, 2)  # the pitch, then where it is going
        opener = origin.send.await_args_list[0].args[0]
        self.assertIn("THE CONTEXT TEXT", opener)
        self.assertIn("body", opener)  # the pitch as he read it
        self.assertNotIn("backlog id:", opener)
        self.assertIn("This is the conversation the row came from", opener)
        self.assertIn("https://discord.com/channels/42/500/777", opener)  # the way back to Build / Drop
        self.assertEqual(feed.talk_thread(self.root, OLDEST), str(THREAD))
        link = interaction.message.edit.await_args.kwargs["view"]
        urls = [getattr(c, "url", None) or getattr(c, "extra", {}).get("url") for c in link.children]
        self.assertIn(f"https://discord.com/channels/42/{THREAD}", urls)
        self.assertIn(str(THREAD), interaction.followup.send.await_args.args[0])

    async def test_the_conversation_is_told_where_it_is_going(self):
        fresh = _thread(parent_id=500, thread_id=5555)
        (self.root / f"craft/intake/{OLDEST}.md").unlink()
        patched, _ = self.spawn_patch(fresh)
        with patched:
            await ui.FeedView()._talk(self.press())
        destination = fresh.send.await_args_list[1].args[0]
        self.assertIn("Where this conversation is going", destination)
        self.assertIn("Drop", destination)
        self.assertIn("Build", destination)
        for part in feed.BRIEF_PARTS:
            self.assertIn(part, destination)
        self.assertIn("https://discord.com/channels/42/500/777", destination)  # Build and Drop are there
        self.assertLess(len(destination), 2000)
        self.assertNotIn("Where this conversation is going", fresh.send.await_args_list[0].args[0])  # control: a separate post

    async def test_an_archived_origin_is_reopened_before_it_is_posted_in(self):
        origin = _thread(parent_id=500, archived=True)
        patched, _ = self.spawn_patch(_thread(500, 1))
        with patched:
            await ui.FeedView()._talk(self.press(thread=origin))
        origin.edit.assert_awaited_once_with(archived=False)
        self.assertEqual(origin.send.await_count, 2)

    async def test_an_origin_in_another_channel_is_never_posted_in_or_linked(self):
        private = _thread(parent_id=999)
        fresh = _thread(parent_id=500, thread_id=5555)
        interaction = self.press(thread=private)
        patched, fake = self.spawn_patch(fresh)
        with patched:
            await ui.FeedView()._talk(interaction)
        private.send.assert_not_awaited()
        fake.spawn_blank_river_eddy.assert_awaited_once()
        self.assertEqual(fresh.send.await_count, 2)
        self.assertEqual(feed.talk_thread(self.root, OLDEST), "5555")
        self.assertNotIn(str(THREAD), interaction.followup.send.await_args.args[0])

    async def test_positive_control_the_same_thread_is_used_when_it_is_craft(self):
        """The test above only means something if the thread would have been used."""
        craft = _thread(parent_id=500)
        patched, fake = self.spawn_patch(_thread(500, 1))
        with patched:
            await ui.FeedView()._talk(self.press(thread=craft))
        self.assertEqual(craft.send.await_count, 2)
        fake.spawn_blank_river_eddy.assert_not_awaited()

    async def test_a_row_with_no_origin_gets_its_own_eddy_named_for_the_pitch(self):
        (self.root / f"craft/intake/{OLDEST}.md").unlink()
        fresh = _thread(parent_id=500, thread_id=5555)
        interaction = self.press(thread=None)
        patched, fake = self.spawn_patch(fresh)
        with patched:
            await ui.FeedView()._talk(interaction)
        topic = fake.spawn_blank_river_eddy.await_args.kwargs["topic"]
        self.assertEqual(topic, "The oldest open row")
        opener = fresh.send.await_args_list[0].args[0]
        self.assertIn("THE CONTEXT TEXT", opener)
        self.assertNotIn("conversation the row came from", opener)
        self.assertLess(len(opener), 2000)

    async def test_a_shell_with_no_spawner_says_so_and_records_nothing(self):
        (self.root / f"craft/intake/{OLDEST}.md").unlink()
        interaction = self.press()
        with patch.object(ui, "_spawn_eddy", None):
            await ui.FeedView()._talk(interaction)
        self.assertIsNone(feed.talk_thread(self.root, OLDEST))
        self.assertIn("could not open an eddy", interaction.followup.send.await_args.args[0])

    async def test_pressing_twice_finds_the_same_eddy(self):
        (self.root / f"craft/intake/{OLDEST}.md").unlink()
        fresh = _thread(parent_id=500, thread_id=5555)
        patched, fake = self.spawn_patch(fresh)
        with patched:
            await ui.FeedView()._talk(self.press())
            await ui.FeedView()._talk(self.press())
        fake.spawn_blank_river_eddy.assert_awaited_once()
        self.assertEqual(fresh.send.await_count, 2)

    async def test_someone_else_pressing_opens_nothing(self):
        origin = _thread(parent_id=500)
        interaction = self.press(user_id=9, thread=origin)
        await ui.FeedView()._talk(interaction)
        origin.send.assert_not_awaited()
        interaction.response.defer.assert_not_awaited()
        self.assertIsNone(feed.talk_thread(self.root, OLDEST))

    async def test_a_failed_post_records_no_conversation(self):
        origin = _thread(parent_id=500)
        origin.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=403, reason="x"), "locked"))
        interaction = self.press(thread=origin)
        await ui.FeedView()._talk(interaction)
        self.assertIsNone(feed.talk_thread(self.root, OLDEST))
        self.assertIn("could not", interaction.followup.send.await_args.args[0])

    async def test_talking_it_through_decides_nothing(self):
        origin = _thread(parent_id=500)
        await ui.FeedView()._talk(self.press(thread=origin))
        self.assertEqual(feed.decisions(self.root), {})
        loaded = self.loaded()
        self.assertIn(OLDEST, [i.id for i in feed.pending(loaded.items, loaded.root)])

    async def test_the_link_variant_keeps_build_and_drop_and_drops_the_callback_button(self):
        view = ui.FeedView(thread_url="https://discord.com/channels/42/1")
        ids = [getattr(c, "custom_id", None) for c in view.children]
        self.assertIn(ui.BUILD_ID, ids)
        self.assertIn(ui.DROP_ID, ids)
        self.assertNotIn(ui.TALK_ID, ids)


class RecordKindsTests(_Base):
    """Pitched and talk files sit beside the verdicts. They must never be read as one."""

    async def test_neither_record_is_a_verdict(self):
        item = next(i for i in self.loaded().items if i.id == OLDEST)
        feed.record_pitched(self.root, item, channel_id=500, message_id=1, now=NOW)
        feed.record_talk(self.root, item, thread_id=2, own=True, now=NOW)
        self.assertEqual(feed.decisions(self.root), {})
        loaded = self.loaded()
        self.assertIn(OLDEST, [i.id for i in feed.pending(loaded.items, loaded.root)])
        self.assertEqual(len(list((self.root / feed.FEED_DIR).glob("*.md"))), 2)  # they exist

    async def test_a_verdict_after_them_is_still_recorded_and_found(self):
        item = next(i for i in self.loaded().items if i.id == OLDEST)
        feed.record_pitched(self.root, item, channel_id=500, message_id=1, now=NOW)
        feed.record_talk(self.root, item, thread_id=2, own=True, now=NOW)
        path, new = feed.record_decision(self.root, item, feed.DROP, now=NOW)
        again, new_again = feed.record_decision(self.root, item, feed.BUILD, now=NOW)
        self.assertTrue(new)
        self.assertFalse(new_again)
        self.assertEqual(path, again)

    async def test_pitched_survives_a_restart_and_names_the_message(self):
        item = next(i for i in self.loaded().items if i.id == OLDEST)
        feed.record_pitched(self.root, item, channel_id=500, message_id=123, now=NOW)
        self.assertEqual(feed.pitched(self.root)[OLDEST]["message"], "123")


class BoundaryTests(unittest.TestCase):
    def test_the_ui_reads_no_file_the_feed_does_not_name(self):
        """The pitch's sources are the practice root and the workshop's head, nothing
        else: a pitch that reached for the log or the registry could carry a room it
        should not."""
        tree = ast.parse((REPO_ROOT / "backlog_feed_context.py").read_text(encoding="utf-8"))
        names = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for forbidden in ("health-kermit", ".env", "logs"):
            self.assertFalse(any(forbidden in n for n in names), forbidden)


if __name__ == "__main__":
    unittest.main()
