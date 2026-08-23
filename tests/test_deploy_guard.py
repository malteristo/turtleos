"""A deploy must not land on someone mid-sentence.

The rule, chosen by the operator 2026-08-15: *never interrupt a live conversation.*

Why it needed a mechanism rather than a note. The previous arrangement was approval,
and it failed the ordinary way — asked once, granted once, then read as standing for
the rest of the evening: four both-bot restarts on a single "deploy now", on a Friday
with family channels live. Nobody was careless. A question a human has to remember to
ask is not a guard, and the person deploying is the last person positioned to know
whether someone else is typing.

What is actually at stake, verified rather than assumed: nothing backfills practitioner
messages at boot (the only startup history reads are for control panels and the thread
registry), and Discord does not replay what a bot missed. So a message sent during a
restart is not delayed — it is never seen and never answered.

The tests here are about the two ways a detector like this rots:

1. **It stops being able to say no.** A guard that always reports quiet is worse than
   none, because it launders the risk. So the refusals are asserted, not just the
   approvals.
2. **It reads "cannot see" as "all clear."** The pre-push gate did exactly this a day
   earlier — treated empty input as nothing-to-check and allowed every push while
   printing a reassuring line. This one refuses when it finds no signal at all.
"""

from __future__ import annotations

import os
import stat
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import deploy_guard  # noqa: E402

RESTART = REPO / "restart.sh"


class _Workshops:
    """A throwaway practice tree, so the tests never read the real one."""

    def __init__(self) -> None:
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name)

    def turn(self, root: str = "kermit", channel: str = "123", age_seconds: float = 0) -> Path:
        d = self.path / root / "dialogue"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{channel}.json"
        f.write_text("[]", encoding="utf-8")
        when = time.time() - age_seconds
        os.utime(f, (when, when))
        return f

    def write_in_flight(self, root: str = "family", name: str = "eddy") -> Path:
        d = self.path / root / "story" / "eddies"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{name}.lock"
        f.write_text("", encoding="utf-8")
        return f

    def close(self) -> None:
        self._tmp.cleanup()


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = _Workshops()
        self.addCleanup(self.ws.close)

    def _assess(self, minutes: float = 10.0):
        return deploy_guard.assess(minutes, workshops=self.ws.path)

    def test_a_recent_turn_is_busy(self) -> None:
        """The case the rule exists for."""
        self.ws.turn(age_seconds=30)
        result = self._assess()
        self.assertFalse(result["quiet"])
        self.assertEqual(result["verdict"], "busy")

    def test_an_old_turn_is_quiet(self) -> None:
        self.ws.turn(age_seconds=3600)
        result = self._assess()
        self.assertTrue(result["quiet"])
        self.assertEqual(result["verdict"], "quiet")

    def test_the_newest_conversation_decides(self) -> None:
        """One live exchange blocks the deploy even if everything else is cold."""
        self.ws.turn(root="kermit", channel="1", age_seconds=7200)
        self.ws.turn(root="family", channel="2", age_seconds=20)
        result = self._assess()
        self.assertFalse(result["quiet"])
        self.assertEqual(result["where"], "family")

    def test_a_write_in_flight_is_busy(self) -> None:
        """A lock file means a turn is being written *right now*."""
        self.ws.turn(age_seconds=99999)
        self.ws.write_in_flight()
        result = self._assess()
        self.assertFalse(result["quiet"])
        self.assertIn("in flight", result["what"])

    def test_the_boundary_is_the_threshold(self) -> None:
        self.ws.turn(age_seconds=10 * 60 + 5)
        self.assertTrue(self._assess(10.0)["quiet"])
        self.assertFalse(self._assess(11.0)["quiet"])

    def test_it_reports_how_long_ago_and_where(self) -> None:
        """A refusal that does not say what it is protecting gets forced reflexively."""
        self.ws.turn(root="family", age_seconds=45)
        result = self._assess()
        self.assertIn("45", result["last_activity"])
        self.assertEqual(result["where"], "family")


class FailClosedTests(unittest.TestCase):
    """Cannot-see must not read as all-clear."""

    def test_no_signal_at_all_refuses(self) -> None:
        ws = _Workshops()
        self.addCleanup(ws.close)
        result = deploy_guard.assess(10.0, workshops=ws.path)
        self.assertEqual(result["verdict"], "unknown")
        self.assertFalse(
            result["quiet"],
            "a detector that found nothing reported quiet — this is the pre-push "
            "gate's failure repeated: empty input read as permission",
        )

    def test_a_missing_workshops_directory_refuses(self) -> None:
        result = deploy_guard.assess(10.0, workshops=Path("/nonexistent/workshops"))
        self.assertFalse(result["quiet"])
        self.assertEqual(result["verdict"], "unknown")

    def test_the_refusal_explains_itself(self) -> None:
        result = deploy_guard.assess(10.0, workshops=Path("/nonexistent/workshops"))
        self.assertIn("cannot see", result["reason"].lower())


class ExitCodeTests(unittest.TestCase):
    """`restart.sh` branches on the exit code, so it is the real interface."""

    def test_busy_exits_nonzero(self) -> None:
        ws = _Workshops()
        self.addCleanup(ws.close)
        (ws.path / "workshops").mkdir()
        import subprocess

        d = ws.path / "workshops" / "kermit" / "dialogue"
        d.mkdir(parents=True)
        (d / "1.json").write_text("[]", encoding="utf-8")
        env = dict(os.environ, HOME=str(ws.path))
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "deploy_guard.py")],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("BUSY", proc.stdout)

    def test_quiet_exits_zero(self) -> None:
        ws = _Workshops()
        self.addCleanup(ws.close)
        d = ws.path / "workshops" / "kermit" / "dialogue"
        d.mkdir(parents=True)
        f = d / "1.json"
        f.write_text("[]", encoding="utf-8")
        old = time.time() - 7200
        os.utime(f, (old, old))
        import subprocess

        env = dict(os.environ, HOME=str(ws.path))
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "deploy_guard.py")],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("QUIET", proc.stdout)


class RestartScriptTests(unittest.TestCase):
    """The guard only matters if the thing that restarts actually consults it."""

    def setUp(self) -> None:
        self.text = RESTART.read_text(encoding="utf-8")

    def test_restart_runs_the_guard(self) -> None:
        self.assertIn("deploy_guard.py", self.text)

    def test_restart_aborts_when_the_guard_refuses(self) -> None:
        self.assertRegex(
            self.text,
            r"if\s+!\s+python3[^\n]*deploy_guard\.py[^\n]*;\s*then",
            "the guard's exit code must gate the restart, not merely be printed",
        )

    def test_the_guard_runs_before_anything_is_kickstarted(self) -> None:
        guard_at = self.text.index("deploy_guard.py")
        first_kick = self.text.index("kickstart_label com.turtle")
        self.assertLess(
            guard_at, first_kick, "checking after the bounce protects nobody"
        )

    def test_there_is_an_escape_hatch_and_it_is_named(self) -> None:
        """Deploying a fix for something already broken must stay possible."""
        self.assertIn("--force", self.text)

    def test_the_bypass_is_logged(self) -> None:
        """A bypass nobody can count is how a guard becomes decoration."""
        self.assertRegex(self.text, r"bypassed[^\n]*>>\s*\"\$\{LOG\}\"")

    def test_the_script_is_executable(self) -> None:
        self.assertTrue(RESTART.stat().st_mode & stat.S_IXUSR)
        self.assertTrue(
            (REPO / "scripts" / "deploy_guard.py").stat().st_mode & stat.S_IXUSR
        )

    def test_the_reason_is_written_where_the_next_person_reads_it(self) -> None:
        """The rule is a decision, and a decision with no recorded reason gets reverted."""
        self.assertIn("never seen and never answered", self.text.lower().replace("—", "—"))


class ThresholdIsJustifiedTests(unittest.TestCase):
    def test_the_default_covers_an_in_flight_local_turn(self) -> None:
        """A 31B local reply was measured at up to 172s. The window must exceed it."""
        self.assertGreaterEqual(
            deploy_guard.DEFAULT_QUIET_MINUTES * 60,
            172 * 2,
            "the quiet window must comfortably cover a reply already being generated, "
            "or the guard clears a deploy while Turtle is mid-answer",
        )

    def test_the_threshold_is_not_so_long_that_it_never_clears(self) -> None:
        self.assertLessEqual(
            deploy_guard.DEFAULT_QUIET_MINUTES,
            30,
            "a guard that is never satisfiable gets forced every time, which is the "
            "same as not having one",
        )


if __name__ == "__main__":
    unittest.main()
