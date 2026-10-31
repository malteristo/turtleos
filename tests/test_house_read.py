"""One file in the house repo, including on a forge turn.

The secret is readable by this process. The tool must not return it. A link
that leaves the repo is the same refusal.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import house_read as hr
import magic_prompt
import outgoing_connections as door
import tos_tools
import turn_trace
import workshop_tools as wt


def git(cwd: Path, *argv: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "nobody",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "nobody",
    }
    subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True, text=True, env=env)


class HouseRead(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.shop = base / "workshop"
        self.house = base / "turtleos"
        for root in (self.shop, self.house):
            root.mkdir()
            git(root, "init", "-q", "-b", "main")
            (root / "readme.md").write_text("here\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "first")
        self.secret = "PLANTED_SECRET_VALUE"
        (self.house / ".env").write_text(self.secret + "\n")
        (self.house / "credentials.json").write_text(self.secret + "\n")
        (self.house / "delegate").mkdir()
        (self.house / "delegate" / "key").write_text(self.secret + "\n")
        notes = self.house / "docs" / "design"
        notes.mkdir(parents=True)
        (notes / "magic-port.md").write_text("step one is a working copy\n")
        outside = base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text(self.secret + "\n")
        (self.house / "leak").symlink_to(outside / "secret.txt")
        self.runtime = base / "runtime"
        self.runtime.mkdir()
        self.registry = {
            "mages": {"ada": {"workshop": {"checkout": str(self.shop)}}},
            "channels": {"1": {"type": "magic", "name": "magic", "mage": "ada"}},
        }
        self.room = {"id": "1"}
        door.bind(
            door.Shell(
                lambda: self.registry,
                lambda: "ada",
                lambda: str(self.runtime),
                lambda: [],
                lambda: self.room["id"],
            )
        )
        self.addCleanup(door.bind, None)
        self._repo = os.environ.get("TURTLEOS_REPO")
        os.environ["TURTLEOS_REPO"] = str(self.house)
        self.addCleanup(self._restore_repo)

    def _restore_repo(self) -> None:
        if self._repo is None:
            os.environ.pop("TURTLEOS_REPO", None)
        else:
            os.environ["TURTLEOS_REPO"] = self._repo

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def audit(self) -> str:
        path = self.runtime / "state" / wt.AUDIT_NAME
        return path.read_text() if path.exists() else ""

    def test_a_house_file_is_read_and_a_secret_is_not(self) -> None:
        self.assertEqual((self.house / ".env").read_text().strip(), self.secret)
        body = hr.call("house_read", {"path": "docs/design/magic-port.md"})
        self.assertIn("step one is a working copy", body)
        self.assertNotIn(self.secret, body)
        self.assertIn('"decision": "called"', self.audit())
        self.assertNotIn(self.secret, self.audit())
        self.assertNotIn("magic-port", self.audit())
        for rel in (".env", "credentials.json", "delegate/key", ".git/config", "leak", "../outside/secret.txt"):
            result = hr.call("house_read", {"path": rel})
            self.assertNotIn(self.secret, result, rel)
            self.assertNotIn("step one", result, rel)

    def test_a_forge_turn_can_read_the_file(self) -> None:
        token = wt.set_forge_turn(True)
        self.addCleanup(wt.reset_forge_turn, token)
        body = hr.call("house_read", {"path": "docs/design/magic-port.md"})
        self.assertIn("step one is a working copy", body)
        self.assertNotIn(self.secret, hr.call("house_read", {"path": ".env"}))

    def test_the_channel_names_the_path(self) -> None:
        self.assertEqual(
            hr.channel_line("house_read", {"path": "docs/design/magic-port.md"}),
            "read `docs/design/magic-port.md`",
        )
        self.assertIn("house_read", magic_prompt.SUBSTRATE)
        self.assertIn("That message has no terminal and no browser.", magic_prompt.SUBSTRATE)
        self.assertIn("house_read", {t["function"]["name"] for t in hr.tools_offered()})
        seen = tos_tools._execute_tos_tool_raw("house_read", {"path": "docs/design/magic-port.md"})
        self.assertIn("step one is a working copy", seen)
        step = turn_trace.describe_tool("house_read", {"path": "docs/design/magic-port.md"}, "step one")
        self.assertIn("read `docs/design/magic-port.md`", step.text)

    def test_another_room_is_refused(self) -> None:
        self.registry["channels"]["1"]["type"] = "chat"
        self.assertEqual(hr.call("house_read", {"path": "readme.md"}), "Not in this room.")
        self.assertEqual(hr.tools_offered(), [])
