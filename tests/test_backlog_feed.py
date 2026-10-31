"""The backlog feed — one pitch at a time, Build or Drop.

Every claim in `backlog_feed.py` has a check here, and each check that says
"absent" has a positive control beside it that shows the same code returning
"present" — an empty result is not evidence of absence.
"""

import ast
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub(reload=("backlog_feed_ui",))

import backlog_feed as feed  # noqa: E402
import backlog_feed_ui as ui  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# The shapes the real file has: newest first, a hash-suffixed id, an id with no
# hash, indented sub-bullets under a row, done and dropped rows, a heading that
# ends the list, and a row with no id at all.
BACKLOG = """# Craft Backlog

Queue for the next chapter.

## Open

- [ ] [2026-09-25-newest-aaaaaa] **The newest open row.** Harvested today. He wants this.
  - Sub-bullet that belongs to the newest row.

- [x] [2026-09-24-shipped-bbbbbb] **A shipped row.** Done.

## Further down

- [ ] [2026-09-13-five-state-eddy-model] **Five-state eddy model.** Steps 2–3 shipped; step 4 remains.
- [d] [2026-09-04-dropped-cccccc] **A dropped row.** Not needed.
- [ ] **A row with no id.** It still needs a stable id.
- [ ] [2026-08-01-oldest-dddddd] **The oldest open row.** Waiting a long time.
- [2026-06-19-legacy-nocheck] **A legacy row with no checkbox.** The Forge reads it as open.
"""

OWNER, OWNER_ID = "kermit", 701
REGISTRY = {
    "mages": {OWNER: {"discord_id": str(OWNER_ID)}, "sam": {"discord_id": "9"}},
    "channels": {
        "500": {
            "type": "craft", "mage": OWNER,
            "backlog_feed": {"repo": "/nowhere.git", "path": "desk/craft/backlog.md"},
        },
        "600": {"type": "river", "mage": OWNER},
        "700": {"type": "craft", "mage": OWNER},
    },
}
NOW = datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)


def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_bare_repo(tmp: Path, text: str, path="desk/craft/backlog.md") -> Path:
    bare, work = tmp / "magic.git", tmp / "work"
    _git("init", "--bare", "-b", "main", str(bare))
    _git("init", "-b", "main", str(work))
    _git("config", "user.email", "t@example.org", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    target = work / path
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    _git("add", ".", cwd=work)
    _git("commit", "-m", "backlog", cwd=work)
    _git("push", str(bare), "main", cwd=work)
    return bare


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.items = feed.parse_backlog(BACKLOG)

    def test_every_row_is_found_with_its_state(self):
        states = {i.id: i.state for i in self.items}
        self.assertEqual(states["2026-09-25-newest-aaaaaa"], "open")
        self.assertEqual(states["2026-09-24-shipped-bbbbbb"], "done")
        self.assertEqual(states["2026-09-04-dropped-cccccc"], "dropped")
        self.assertEqual(len(self.items), 7)

    def test_a_row_carries_its_indented_lines_and_nothing_after_a_heading(self):
        newest = next(i for i in self.items if i.id == "2026-09-25-newest-aaaaaa")
        self.assertIn("Sub-bullet that belongs", newest.body)
        self.assertEqual(newest.title, "The newest open row")
        shipped = next(i for i in self.items if i.id.endswith("bbbbbb"))
        self.assertNotIn("Further down", shipped.body)
        # A heading does not hide the rows beneath it.
        self.assertIn("2026-09-13-five-state-eddy-model", [i.id for i in self.items])

    def test_a_row_with_no_id_gets_a_stable_one(self):
        again = feed.parse_backlog(BACKLOG)
        noid = [i.id for i in self.items if i.title.startswith("A row with no id")]
        self.assertEqual(len(noid), 1)
        self.assertTrue(noid[0].startswith("row-"))
        self.assertIn(noid[0], [i.id for i in again])

    def test_a_row_with_no_checkbox_is_open_as_the_forge_reads_it(self):
        legacy = next(i for i in self.items if i.id == "2026-06-19-legacy-nocheck")
        self.assertEqual(legacy.state, "open")
        self.assertEqual(legacy.title, "A legacy row with no checkbox")

    def test_a_bullet_that_is_not_a_row_is_not_a_row(self):
        text = "- [a link](https://example.org) in prose\n- plain bullet\n"
        self.assertEqual(feed.parse_backlog(text), [])

    def test_the_parser_can_return_nothing(self):
        """Positive control for the empty cases below: text with no rows is empty."""
        self.assertEqual(feed.parse_backlog("# Heading\n\nProse only.\n"), [])


class ReadBacklogTests(unittest.TestCase):
    def test_reads_the_head_of_a_bare_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = make_bare_repo(Path(tmp), BACKLOG)
            text, commit = feed.read_backlog(bare, "desk/craft/backlog.md")
            self.assertEqual(text, BACKLOG)
            self.assertRegex(commit, r"^[0-9a-f]{7,}$")

    def test_reads_what_was_pushed_last_and_not_a_cached_tree(self):
        """Mutation target: serve a remembered copy and this fails."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bare = make_bare_repo(tmp, BACKLOG)
            first, c1 = feed.read_backlog(bare, "desk/craft/backlog.md")
            work = tmp / "work"
            (work / "desk/craft/backlog.md").write_text(BACKLOG + "\n- [ ] [new-one] **Pushed later.** x\n")
            _git("commit", "-am", "more", cwd=work)
            _git("push", str(bare), "main", cwd=work)
            second, c2 = feed.read_backlog(bare, "desk/craft/backlog.md")
            self.assertNotEqual(c1, c2)
            self.assertIn("Pushed later", second)
            self.assertNotIn("Pushed later", first)

    def test_a_missing_path_and_a_missing_repo_say_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = make_bare_repo(Path(tmp), BACKLOG)
            with self.assertRaises(feed.FeedUnavailable):
                feed.read_backlog(bare, "desk/craft/nope.md")
            with self.assertRaises(feed.FeedUnavailable):
                feed.read_backlog(Path(tmp) / "absent.git", "x")


class ConfigurationTests(unittest.TestCase):
    def test_a_craft_channel_with_a_backlog_resolves(self):
        owner, repo, path = feed.feed_source(REGISTRY, 500)
        self.assertEqual((owner, path), (OWNER, "desk/craft/backlog.md"))

    def test_other_rooms_have_no_feed(self):
        with self.assertRaises(feed.FeedUnavailable):
            feed.feed_source(REGISTRY, 600)

    def test_a_craft_channel_without_a_backlog_says_what_it_needs(self):
        with self.assertRaises(feed.FeedUnavailable) as raised:
            feed.feed_source(REGISTRY, 700)
        self.assertIn("backlog_feed", str(raised.exception))

    def test_only_the_owner_decides(self):
        self.assertTrue(feed.may_decide(REGISTRY, 500, OWNER_ID))
        self.assertFalse(feed.may_decide(REGISTRY, 500, 9))
        self.assertFalse(feed.may_decide(REGISTRY, 500, ""))
        self.assertFalse(feed.may_decide({}, 500, OWNER_ID))


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.items = feed.parse_backlog(BACKLOG)
        self.by_id = {i.id: i for i in self.items}

    def tearDown(self):
        self._tmp.cleanup()

    def test_pitches_run_oldest_first_and_skip_closed_rows(self):
        ids = [i.id for i in feed.pending(self.items, self.root)]
        self.assertEqual(ids[0], "2026-06-19-legacy-nocheck")
        self.assertEqual(ids[1], "2026-08-01-oldest-dddddd")
        self.assertEqual(ids[-1], "2026-09-25-newest-aaaaaa")
        self.assertNotIn("2026-09-24-shipped-bbbbbb", ids)
        self.assertNotIn("2026-09-04-dropped-cccccc", ids)
        self.assertEqual(len(ids), 5)

    def test_a_drop_is_final(self):
        victim = self.by_id["2026-08-01-oldest-dddddd"]
        self.assertIn(victim.id, [i.id for i in feed.pending(self.items, self.root)])  # control
        feed.record_decision(self.root, victim, feed.DROP, now=NOW)
        self.assertNotIn(victim.id, [i.id for i in feed.pending(self.items, self.root)])
        # Re-read from scratch, as after a restart.
        self.assertNotIn(victim.id, [i.id for i in feed.pending(feed.parse_backlog(BACKLOG), self.root)])

    def test_a_build_does_not_come_back_and_is_in_the_queue(self):
        row = self.by_id["2026-09-13-five-state-eddy-model"]
        feed.record_decision(self.root, row, feed.BUILD, now=NOW)
        self.assertNotIn(row.id, [i.id for i in feed.pending(self.items, self.root)])
        self.assertEqual([i.id for i in feed.build_queue(self.items, self.root)], [row.id])

    def test_a_shipped_build_leaves_the_queue_on_its_own(self):
        row = self.by_id["2026-09-13-five-state-eddy-model"]
        feed.record_decision(self.root, row, feed.BUILD, now=NOW)
        shipped = BACKLOG.replace("- [ ] [2026-09-13-five-state-eddy-model]", "- [x] [2026-09-13-five-state-eddy-model]")
        self.assertEqual(feed.build_queue(feed.parse_backlog(shipped), self.root), [])

    def test_a_second_verdict_on_the_same_row_changes_nothing(self):
        row = self.by_id["2026-08-01-oldest-dddddd"]
        path, new = feed.record_decision(self.root, row, feed.DROP, now=NOW)
        again, new_again = feed.record_decision(self.root, row, feed.BUILD, now=NOW)
        self.assertTrue(new)
        self.assertFalse(new_again)
        self.assertEqual(path, again)
        self.assertEqual(feed.decisions(self.root)[row.id]["decision"], feed.DROP)
        self.assertEqual(len(list((self.root / feed.FEED_DIR).glob("*.md"))), 1)

    def test_a_drop_outranks_a_build_written_by_another_hand(self):
        row = self.by_id["2026-08-01-oldest-dddddd"]
        folder = self.root / feed.FEED_DIR
        folder.mkdir(parents=True)
        for stamp, verdict in (("2026-10-10T100000", "drop"), ("2026-10-10T110000", "build")):
            (folder / f"{stamp}-{verdict}-x.md").write_text(
                f"---\nid: {row.id}\ndecision: {verdict}\n---\n", encoding="utf-8"
            )
        self.assertEqual(feed.decisions(self.root)[row.id]["decision"], "drop")

    def test_the_verdict_file_is_what_the_forge_reads(self):
        row = self.by_id["2026-08-01-oldest-dddddd"]
        path, _ = feed.record_decision(self.root, row, feed.DROP, now=NOW)
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nid: 2026-08-01-oldest-dddddd\ndecision: drop\n"))
        self.assertEqual(path.parent, self.root / feed.FEED_DIR)

    def test_counts_name_every_waiting_row(self):
        row = self.by_id["2026-08-01-oldest-dddddd"]
        feed.record_decision(self.root, row, feed.DROP, now=NOW)
        c = feed.counts(self.items, self.root)
        self.assertEqual(c, {"open": 5, "waiting": 4, "build": 0, "drop": 1})


class PitchWordsTests(unittest.TestCase):
    def test_the_footer_survives_a_long_row_and_names_the_row(self):
        long_item = feed.FeedItem("some-id-aaaaaa", "Long", "word " * 1000, "open")
        text = feed.compose_pitch(long_item, position=3, total=18, commit="abc1234")
        self.assertLess(len(text), 2000)
        self.assertEqual(feed.item_id_from_message(text), "some-id-aaaaaa")
        self.assertIn("3 of 18", text)

    def test_a_message_without_a_footer_names_no_row(self):
        self.assertIsNone(feed.item_id_from_message("Dropped — something."))


def _interaction(*, user_id, content, channel_id=500):
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.channel = MagicMock(id=channel_id, parent_id=None)
    interaction.message.content = content
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class PressTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.bare = make_bare_repo(tmp, BACKLOG)
        self.root = tmp / "practice"
        self.registry = {
            "mages": REGISTRY["mages"],
            "channels": {"500": {
                "type": "craft", "mage": OWNER,
                "backlog_feed": {"repo": str(self.bare), "path": "desk/craft/backlog.md"},
            }},
        }
        client = MagicMock()
        ui.arm_feed(client, lambda: self.registry, lambda owner: self.root)
        self.client = client

    def tearDown(self):
        ui.arm_feed(MagicMock(), lambda: self.registry, lambda owner: self.root)
        self._tmp.cleanup()

    def _pitch_text(self, item_id="2026-08-01-oldest-dddddd"):
        return f"**1 of 4** — x\n\nbody\n\n-# backlog id: {item_id} · workshop abc"

    async def test_build_records_it_and_edits_the_pitch_in_place(self):
        interaction = _interaction(user_id=OWNER_ID, content=self._pitch_text())
        await ui.FeedView()._build(interaction)
        verdicts = feed.decisions(self.root)
        self.assertEqual(verdicts["2026-08-01-oldest-dddddd"]["decision"], "build")
        edited = interaction.response.edit_message.await_args.kwargs
        self.assertIn("Build", edited["content"])
        self.assertIn("left to decide", edited["content"])
        self.assertIsNone(edited["view"])
        self.assertIsNone(edited["embed"])  # the context goes with the buttons
        # Every pitch is already in the channel; a press posts nothing further.
        interaction.followup.send.assert_not_awaited()

    async def test_drop_is_final_across_a_restart(self):
        await ui.FeedView()._drop(_interaction(user_id=OWNER_ID, content=self._pitch_text()))
        loaded = feed.load(self.registry, 500, practice_root_for=lambda o: self.root)
        self.assertNotIn(
            "2026-08-01-oldest-dddddd", [i.id for i in feed.pending(loaded.items, loaded.root)]
        )

    async def test_someone_else_pressing_records_nothing(self):
        interaction = _interaction(user_id=9, content=self._pitch_text())
        await ui.FeedView()._drop(interaction)
        self.assertEqual(feed.decisions(self.root), {})
        interaction.response.send_message.assert_awaited_once()
        interaction.response.edit_message.assert_not_awaited()

    async def test_a_row_that_closed_meanwhile_records_nothing_and_says_so(self):
        interaction = _interaction(user_id=OWNER_ID, content=self._pitch_text("2026-09-24-shipped-bbbbbb"))
        await ui.FeedView()._build(interaction)
        self.assertEqual(feed.decisions(self.root), {})
        self.assertIn("no longer open", interaction.response.edit_message.await_args.kwargs["content"])

    async def test_a_message_that_names_no_row_records_nothing(self):
        interaction = _interaction(user_id=OWNER_ID, content="no footer here")
        await ui.FeedView()._drop(interaction)
        self.assertEqual(feed.decisions(self.root), {})

    async def test_a_restart_needs_one_registration_and_the_ids_are_fixed(self):
        """Rehydration: armed once at startup, the buttons answer every pitch ever posted."""
        added = self.client.add_view.call_args.args[0]
        ids = sorted(child.custom_id for child in added.children)
        self.assertEqual(ids, ["craft:feed:build", "craft:feed:drop", "craft:feed:talk"])

    async def test_queue_is_read_back_through_the_command(self):
        row = next(i for i in feed.parse_backlog(BACKLOG) if i.id == "2026-09-13-five-state-eddy-model")
        feed.record_decision(self.root, row, feed.BUILD, now=NOW)
        message = MagicMock()
        message.channel = MagicMock(id=500, parent_id=None)
        message.author.id = OWNER_ID
        message.reply = AsyncMock()
        await ui.cmd_feed(message, ["queue"])
        self.assertIn("Five-state eddy model", message.reply.await_args.args[0])

    async def test_the_command_refuses_another_person(self):
        message = MagicMock()
        message.channel = MagicMock(id=500, parent_id=None)
        message.author.id = 9
        message.reply = AsyncMock()
        await ui.cmd_feed(message, [])
        self.assertIn("owner", message.reply.await_args.args[0])

class BoundaryTests(unittest.TestCase):
    def test_the_feed_writes_no_offer_ledger_row(self):
        """A decision is not an offer. `backlog_feed.py` says why; this keeps it true."""
        for name in ("backlog_feed.py", "backlog_feed_ui.py", "backlog_feed_context.py", "backlog_feed_judge.py", "backlog_feed_write.py"):
            tree = ast.parse((REPO_ROOT / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn("offer_ledger", node.module or "", name)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn("offer_ledger", alias.name, name)

    def test_the_pure_modules_import_no_transport(self):
        for name in ("backlog_feed.py", "backlog_feed_context.py", "backlog_feed_judge.py", "backlog_feed_write.py"):
            tree = ast.parse((REPO_ROOT / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("discord"), name)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertFalse(alias.name.startswith("discord"), name)

    def test_the_command_is_registered_where_the_dispatcher_looks(self):
        import cmd_dispatch
        from commands import DIRECT_COMMANDS

        self.assertIn("feed", DIRECT_COMMANDS)
        self.assertIn("feed", cmd_dispatch.COMMAND_ACT_FALLBACK)


if __name__ == "__main__":
    unittest.main()
