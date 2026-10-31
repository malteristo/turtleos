"""Pi's driver: a worktree, one session, abort, and a test it cannot edit.

The test writes the Spirit test itself. The sandboxed write must not. The
abort command is what the session sends, and the house key is not in the
child's environment.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import pi_driver
from workshop_tools import Refused


def git(cwd: Path, *argv: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "nobody",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "nobody",
    }
    subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True, text=True, env=env)


class Driver(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.live = base / "turtleos"
        self.live.mkdir()
        git(self.live, "init", "-q", "-b", "main")
        tests = self.live / "tests"
        tests.mkdir()
        (tests / "test_claim.py").write_text("original\n")
        (self.live / "readme.md").write_text("here\n")
        git(self.live, "add", "-A")
        git(self.live, "commit", "-q", "-m", "first")
        self.bare = base / "turtleos.git"
        subprocess.run(["git", "clone", "--bare", str(self.live), str(self.bare)], check=True, capture_output=True)
        self.dest = base / "wt"
        self.pi = base / "pi"
        self.pi.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json, os, sys
                seen = open("pi-saw.txt", "w")
                seen.write(json.dumps({"has_key": "ANTHROPIC_API_KEY" in os.environ}) + "\\n")
                seen.write(sys.stdin.readline())
                seen.close()
                """
            )
        )
        self.pi.chmod(self.pi.stat().st_mode | stat.S_IEXEC)
        self.addCleanup(self.tmp.cleanup)

    def test_the_worktree_is_not_the_live_checkout(self) -> None:
        with self.assertRaises(Refused):
            pi_driver.open_worktree(self.bare, self.live, "pi/claim", self.live)
        root = pi_driver.open_worktree(self.bare, self.dest, "pi/claim", self.live)
        self.assertTrue((root / "tests" / "test_claim.py").is_file())
        self.assertNotEqual(root.resolve(), self.live.resolve())

    def test_a_secret_in_the_worktree_is_not_started(self) -> None:
        pi_driver.open_worktree(self.bare, self.dest, "pi/claim", self.live)
        (self.dest / ".env").write_text("PLANTED_SECRET_VALUE\n")
        session = pi_driver.Session(
            self.dest, {"tests/test_claim.py"}, pi=str(self.pi), live=self.live
        )
        with self.assertRaises(Refused):
            session.start()
        self.assertFalse((self.dest / "pi-saw.txt").exists())

    def test_a_template_is_not_a_secret(self) -> None:
        (self.live / ".env.template").write_text("KEY=\n")
        self.assertFalse(pi_driver._secret(self.live))
        (self.live / ".env").write_text("PLANTED_SECRET_VALUE\n")
        self.assertTrue(pi_driver._secret(self.live))

    def test_the_sandboxed_write_does_not_change_the_spirit_test(self) -> None:
        pi_driver.open_worktree(self.bare, self.dest, "pi/claim", self.live)
        target = self.dest / "tests" / "test_claim.py"
        self.assertEqual(target.read_text(), "original\n")
        unsandboxed = subprocess.run(
            [sys.executable, "-c", "open('tests/test_claim.py','w').write('changed\\n')"],
            cwd=self.dest,
            capture_output=True,
            text=True,
        )
        self.assertEqual(unsandboxed.returncode, 0)
        self.assertEqual(target.read_text(), "changed\n")
        target.write_text("original\n")
        profile = pi_driver.sandbox_profile(self.dest, {"tests/test_claim.py"})
        sandboxed = subprocess.run(
            ["sandbox-exec", "-p", profile, sys.executable, "-c", "open('tests/test_claim.py','w').write('changed\\n')"],
            cwd=self.dest,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(sandboxed.returncode, 0)
        self.assertEqual(target.read_text(), "original\n")
        other = subprocess.run(
            ["sandbox-exec", "-p", profile, sys.executable, "-c", "open('notes.md','w').write('ok\\n')"],
            cwd=self.dest,
            capture_output=True,
            text=True,
        )
        self.assertEqual(other.returncode, 0)
        self.assertEqual((self.dest / "notes.md").read_text(), "ok\n")

    def test_an_edit_aborts_and_the_key_stays_out(self) -> None:
        pi_driver.open_worktree(self.bare, self.dest, "pi/claim", self.live)
        os.environ["ANTHROPIC_API_KEY"] = "PLANTED_KEY"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        cards: list[str] = []
        session = pi_driver.Session(
            self.dest,
            {"tests/test_claim.py"},
            pi=str(self.pi),
            live=self.live,
            branch="pi/claim",
            hear=cards.append,
        )
        session.start()
        self.addCleanup(session.close)
        said = session.consider(
            {
                "type": "tool_execution_start",
                "toolName": "edit",
                "args": {"path": "tests/test_claim.py"},
            }
        )
        self.assertEqual(said, "Pi does not edit Spirit's tests (`tests/test_claim.py`).")
        session.close()
        seen = (self.dest / "pi-saw.txt").read_text()
        self.assertIn('"has_key": false', seen)
        self.assertNotIn("PLANTED_KEY", seen)
        self.assertIn('"type": "abort"', seen)
        self.assertIn("Pi · starting", cards[0])
        self.assertIn("Pi · aborted", cards[-1])
        self.assertIn("branch `pi/claim`", cards[-1])
        self.assertIn("tests/test_claim.py", cards[-1])
        self.assertNotIn("PLANTED_KEY", "\n".join(cards))
        own = session.consider(
            {
                "type": "tool_execution_start",
                "toolName": "write",
                "args": {"path": "tests/test_pi_wrote.py"},
            }
        )
        self.assertIsNone(own)

    def test_a_second_session_is_refused_while_the_first_is_open(self) -> None:
        pi_driver.open_worktree(self.bare, self.dest, "pi/claim", self.live)
        first = pi_driver.Session(self.dest, set(), pi=str(self.pi), live=self.live)
        first.start()
        self.addCleanup(first.close)
        second = pi_driver.Session(self.dest, set(), pi=str(self.pi), live=self.live)
        with self.assertRaises(Refused):
            second.start()

    def test_the_card_counts_a_look_and_leaves_the_path_off(self) -> None:
        cards: list[str] = []
        session = pi_driver.Session(
            self.live, set(), pi=str(self.pi), live=self.live, branch="pi/claim", hear=cards.append
        )
        session.observe(
            {
                "type": "tool_execution_start",
                "toolName": "read",
                "args": {"path": "notes/PLANTED_SECRET_VALUE"},
            }
        )
        self.assertIn("Pi · working · 1", cards[-1])
        self.assertIn("reading", cards[-1])
        self.assertNotIn("PLANTED_SECRET_VALUE", cards[-1])

    def test_the_card_is_one_message_that_updates(self) -> None:
        from pi_engagement import Board, render

        sent = []

        def send(method, url, body):
            sent.append((method, url, body))
            return 200, {"id": "42"}

        board = Board("99", send)
        board.send_box(
            render(phase="starting", branch="pi/claim", progress="opening", failed=[], claims=[], looks=0),
            [{"type": 17}],
        )
        board.send_box(
            render(phase="working", branch="pi/claim", progress="reading", failed=[], claims=[], looks=2),
            [{"type": 17}],
        )
        self.assertEqual(sent[0][0], "POST")
        self.assertEqual(sent[1][0], "PATCH")
        self.assertIn("/messages/42", sent[1][1])
        self.assertEqual(sent[0][2]["flags"], 1 << 15)
        self.assertNotIn("content", sent[0][2])
        self.assertEqual(sent[1][2]["content"], "")

    def test_the_session_keeps_the_phase_and_not_each_look(self) -> None:
        from pi_engagement import Board, remember_card, render
        import session_record as sr

        root = Path(self.tmp.name) / "practice"
        (root / "state" / "sessions").mkdir(parents=True)
        sent = []

        def send(method, url, body):
            sent.append(method)
            return 200, {"id": "42"}

        board = Board("99", send, remember=lambda text: remember_card(root, "99", text))
        board.send_box(render(phase="starting", branch="pi/claim", progress="opening", failed=[], claims=[], looks=0), [])
        board.send_box(
            render(phase="working", branch="pi/claim", progress="reading", failed=[], claims=["a climb has not run"], looks=1),
            [],
        )
        board.send_box(
            render(phase="working", branch="pi/claim", progress="reading", failed=[], claims=["a climb has not run"], looks=2),
            [],
        )
        board.send_box(
            render(
                phase="aborted",
                branch="pi/claim",
                progress="aborted before a prompt",
                failed=[],
                claims=["a climb has not run"],
                looks=2,
            ),
            [],
        )
        rows = sr.read_turns(root, "99")
        self.assertEqual([row["kind"] for row in rows], ["pi", "pi", "pi"])
        self.assertIn("starting", rows[0]["text"])
        self.assertIn("working · 1", rows[1]["text"])
        self.assertNotIn("working · 2", "\n".join(row["text"] for row in rows))
        self.assertIn("aborted · 2", rows[2]["text"])
        self.assertNotIn("PLANTED_SECRET_VALUE", "\n".join(row["text"] for row in rows))
        self.assertEqual(sent, ["POST", "PATCH", "PATCH", "PATCH"])
