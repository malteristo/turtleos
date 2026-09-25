"""deploy_when_quiet.sh — pins HEAD, does not pull, times out, propagates restart."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "deploy_when_quiet.sh"


def _run(env: dict, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd or REPO,
        env=merged,
        capture_output=True,
        text=True,
    )


class Source(unittest.TestCase):
    def test_the_waiter_cannot_move_the_checkout(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^\s*git\s+(pull|fetch|checkout|reset|merge)\b")
        self.assertIn("--expect-sha", text)
        self.assertIn("TIMEOUT", text)


class Behaviour(unittest.TestCase):
    def _repo(self, tmp: Path) -> Path:
        repo = tmp / "turtleos"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        (repo / "ok").write_text("1", encoding="utf-8")
        subprocess.run(["git", "add", "ok"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
        return repo

    def _bin(self, path: Path, body: str) -> Path:
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def test_refuses_when_head_is_not_the_expected_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            proc = _run(
                {"TURTLEOS_REPO": str(repo)},
                "--expect-sha", "deadbeef" * 5,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertIn("wrong tree", proc.stderr)

    def test_restarts_when_quiet_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            guard = self._bin(root / "guard.py", "import sys; sys.exit(0)\n")
            restart = self._bin(root / "restart.sh", "exit 7\n")
            log = root / "wait.log"
            proc = _run(
                {
                    "TURTLEOS_REPO": str(repo),
                    "DEPLOY_GUARD_BIN": str(guard),
                    "RESTART_BIN": str(restart),
                },
                "--expect-sha", sha,
                "--timeout-hours", "1",
                "--poll-seconds", "1",
                "--log", str(log),
            )
            self.assertEqual(proc.returncode, 7)
            self.assertIn("restart exit 7", log.read_text(encoding="utf-8"))
            self.assertIn(sha, log.read_text(encoding="utf-8"))

    def test_times_out_nonzero_while_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            guard = self._bin(root / "guard.py", "import sys; sys.exit(1)\n")
            restart = self._bin(root / "restart.sh", "echo should-not-run; exit 0\n")
            log = root / "wait.log"
            proc = _run(
                {
                    "TURTLEOS_REPO": str(repo),
                    "DEPLOY_GUARD_BIN": str(guard),
                    "RESTART_BIN": str(restart),
                },
                "--expect-sha", sha,
                "--timeout-hours", "0",
                "--poll-seconds", "1",
                "--log", str(log),
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("TIMEOUT", log.read_text(encoding="utf-8"))
            self.assertNotIn("should-not-run", proc.stdout + proc.stderr + log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
