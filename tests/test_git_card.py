"""`!git` is the list of unkept workshop files. It is not the diff."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import git_card  # noqa: E402
import ui_kit  # noqa: E402


def _git(cwd: Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True, text=True)


class TheList(unittest.TestCase):
    def test_a_status_becomes_paths_and_a_hunk_does_not(self):
        text = git_card.render(
            "## magic-port\n"
            " M desk/state.md\n"
            "?? boom_takeup.py\n"
            "D  old.md\n"
            'R  "old name.md" -> "new name.md"\n'
            "@@ -1,3 +1,4 @@\n"
            "+a hunk that must not be listed\n"
        )
        self.assertIn("On magic-port", text)
        self.assertIn("modified  desk/state.md", text)
        self.assertIn("new  boom_takeup.py", text)
        self.assertIn("deleted  old.md", text)
        self.assertIn("renamed  old name.md → new name.md", text)
        self.assertNotIn("@@", text)
        self.assertNotIn("hunk", text)

    def test_a_clean_checkout_says_nothing_is_waiting(self):
        self.assertIn("Nothing is waiting", git_card.render("## main\n"))

    def test_a_long_list_keeps_the_last_path(self):
        lines = ["## main"] + [f" M f{i}.md" for i in range(40)]
        text = git_card.render("\n".join(lines))
        self.assertIn("modified  f0.md", text)
        self.assertIn("modified  f39.md", text)
        self.assertIn("more between", text)
        self.assertNotIn("modified  f20.md", text)

    def test_both_languages_name_the_same_facts(self):
        self.assertEqual(ui_kit.parity(git_card._TEXT), [])
        german = git_card.render("## main\n?? neu.md\n", locale="de")
        self.assertIn("Auf main", german)
        self.assertIn("neu  neu.md", german)

    def test_a_real_checkout_lists_a_file_that_was_written(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "t")
            (root / "kept.md").write_text("a\n", encoding="utf-8")
            _git(root, "add", "kept.md")
            _git(root, "commit", "-q", "-m", "kept")
            (root / "kept.md").write_text("b\n", encoding="utf-8")
            (root / "fresh.md").write_text("c\n", encoding="utf-8")
            text = git_card.reply_for(root)
        self.assertIn("modified  kept.md", text)
        self.assertIn("new  fresh.md", text)
        self.assertNotIn("@@", text)

    def test_the_reader_never_asks_for_a_diff(self):
        with patch("git_card.subprocess.run", return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="## main\n", stderr=""
        )) as run:
            git_card.read_status(Path("/tmp/workshop"))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["git", "-C", "/tmp/workshop", "status"])
        self.assertNotIn("diff", argv)

    def test_no_workshop_is_said(self):
        self.assertIn("no workshop", git_card.reply_for(None))


class TheDoor(unittest.IsolatedAsyncioTestCase):
    async def test_only_the_magic_room_gets_the_list(self):
        import commands

        message = MagicMock()
        message.author.id = 1
        message.reply = AsyncMock()
        prim = MagicMock()
        prim.name = "craft"
        with patch("mage.get_channel_primitive", return_value=prim), patch(
            "mage.resolve_dialogue_channel_id", return_value=1
        ), patch("room_models.locale_for", return_value="en"):
            await commands.cmd_git(message, "")
        self.assertIn("#magic", message.reply.await_args.args[0])

        message.reply.reset_mock()
        prim.name = "magic"
        with patch("mage.get_channel_primitive", return_value=prim), patch(
            "mage.resolve_dialogue_channel_id", return_value=9
        ), patch("room_models.locale_for", return_value="en"), patch(
            "mage.get_registry", return_value={}
        ), patch("room_connections.owner_of", return_value="ada"), patch(
            "workshop_tools.checkout_for", return_value=Path("/tmp/does-not-matter")
        ), patch("git_card.read_status", return_value="## main\n M desk/state.md\n"):
            await commands.cmd_git(message, ["diff", "HEAD"])
        posted = message.reply.await_args.args[0]
        self.assertIn("modified  desk/state.md", posted)
        self.assertNotIn("diff", posted)
