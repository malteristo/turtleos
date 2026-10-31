"""The house spirit's terminal: one command, sandboxed, and not for a forge turn.

A real checkout stands in for the workshop and another for the house repo. The
secret file is readable by this process; the command must not be able to read it.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import house_terminal as ht
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


class Terminal(unittest.TestCase):
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

    def test_a_command_runs_in_the_house_repo(self) -> None:
        result = ht.call("house_terminal", {"command": "echo ready && pwd"})
        self.assertIn("ready", result)
        self.assertIn(str(self.house), result)
        self.assertIn('"decision": "called"', self.audit())
        self.assertNotIn("echo ready", self.audit())

    def test_the_workshop_is_the_other_place(self) -> None:
        result = ht.call("house_terminal", {"command": "pwd", "where": "workshop"})
        self.assertIn(str(self.shop), result)
        self.assertNotIn(str(self.house), result)

    def test_anywhere_else_is_refused(self) -> None:
        self.assertEqual(
            ht.call("house_terminal", {"command": "pwd", "where": "/tmp"}),
            "where is house or workshop.",
        )

    def test_a_secret_is_readable_here_and_not_from_the_command(self) -> None:
        for rel in (".env", "credentials.json", "delegate/key"):
            self.assertEqual((self.house / rel).read_text().strip(), self.secret)
            for command in (f"cat {rel}", f"python3 -c 'print(open({rel!r}).read())'"):
                result = ht.call("house_terminal", {"command": command})
                self.assertNotIn(self.secret, result, command)
                self.assertIn("exit", result, command)

    def test_a_disguised_restart_does_not_run(self) -> None:
        script = self.house / "restart.sh"
        script.write_text("#!/bin/sh\necho RAN\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        ran = subprocess.run([str(script)], capture_output=True, text=True, check=True)
        self.assertIn("RAN", ran.stdout)
        disguised = f"python3 -c 'import os; os.execv({str(script)!r}, [\"restart.sh\"])'"
        result = ht.call("house_terminal", {"command": disguised})
        self.assertNotIn("RAN", result)

    def test_restart_and_force_git_are_refused_before_they_start(self) -> None:
        for command in (
            "launchctl list",
            "bash -c 'launchctl list'",
            "./restart.sh",
            "bash -c './restart.sh'",
            "git push --force",
            "bash -c 'git push --force'",
            "git reset --hard",
            "git clean -fd",
        ):
            result = ht.call("house_terminal", {"command": command})
            self.assertIn(result, {ht.RESTART, ht.FORCE}, command)
        allowed = ht.call("house_terminal", {"command": "echo launchctl"})
        self.assertIn("launchctl", allowed)
        self.assertIn("On branch", ht.call("house_terminal", {"command": "git status"}))

    def test_a_forge_turn_cannot_run_it(self) -> None:
        token = wt.set_forge_turn(True)
        try:
            result = ht.call("house_terminal", {"command": "touch from-forge.txt"})
            self.assertEqual(result, ht.FORGE_HELD)
            self.assertFalse((self.house / "from-forge.txt").exists())
        finally:
            wt.reset_forge_turn(token)
        made = ht.call("house_terminal", {"command": "echo made > from-forge.txt && cat from-forge.txt"})
        self.assertIn("made", made)
        self.assertEqual((self.house / "from-forge.txt").read_text().strip(), "made")

    def test_the_parent_environment_is_not_passed_in(self) -> None:
        os.environ["SENTINEL_TERMINAL"] = "present"
        self.addCleanup(os.environ.pop, "SENTINEL_TERMINAL", None)
        result = ht.call(
            "house_terminal",
            {"command": "python3 -c 'import os; print(os.environ.get(\"SENTINEL_TERMINAL\", \"absent\"))'"},
        )
        self.assertIn("absent", result)
        self.assertNotIn("present", result)

    def test_a_command_that_does_not_finish_is_refused(self) -> None:
        previous = ht.TIMEOUT
        ht.TIMEOUT = 1
        self.addCleanup(setattr, ht, "TIMEOUT", previous)
        self.assertEqual(
            ht.call("house_terminal", {"command": "sleep 5"}),
            "That command did not finish in time.",
        )

    def test_not_in_another_room_and_the_channel_names_the_command_only(self) -> None:
        self.room["id"] = "9"
        self.assertEqual(ht.tools_offered(), [])
        self.assertEqual(ht.call("house_terminal", {"command": "echo no"}), "Not in this room.")
        self.room["id"] = "1"
        self.assertIn("house_terminal", {t["function"]["name"] for t in ht.tools_offered()})
        self.assertIn("ready", tos_tools._execute_tos_tool_raw("house_terminal", {"command": "echo ready"}))
        step = turn_trace.describe_tool("house_terminal", {"command": "echo ready"}, "ready\nPLANTED_OUTPUT")
        self.assertEqual(step.text, "ran echo")
        self.assertNotIn("ready", step.text.split("—")[0])
        self.assertNotIn("PLANTED_OUTPUT", step.text)

    def test_the_prompt_tells_the_house_spirit_and_not_the_forge_spirit(self) -> None:
        import magic_prompt

        self.assertIn("house_terminal", magic_prompt.SUBSTRATE)
        self.assertIn("no browser", magic_prompt.SUBSTRATE)
        self.assertIn("That message has no terminal and no browser.", magic_prompt.SUBSTRATE)
        self.assertNotIn("It has no terminal and no browser.", magic_prompt.SUBSTRATE)
        self.assertNotIn("This turn can look", magic_prompt.SUBSTRATE)
        self.assertIn(
            "On his message you have the workshop tools, `house_terminal`, and `house_browser`.",
            magic_prompt.SUBSTRATE,
        )
        self.assertIn(
            "When those claims are true, you hand back. He names the next ideal state, or he sends `...` and you offer one hill from what is already there.",
            magic_prompt.SUBSTRATE,
        )
        self.assertIn("That `...` is not a new arrival.", magic_prompt.SUBSTRATE)
        self.assertNotIn("wait for the next description", magic_prompt.SUBSTRATE)
        self.assertIn("A change on that message still waits on him", magic_prompt.SUBSTRATE)
