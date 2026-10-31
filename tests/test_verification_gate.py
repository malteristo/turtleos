"""The enforcement layer gets the same treatment it imposes.

Added 2026-08-14 with the pre-push hook and CI workflow. Both run a gate; a gate
is a claim ("nothing red leaves this machine"), and this repo's recurring defect is
a claim whose mechanism verifies something adjacent to it. So the gates are checked
for the two ways they rot:

1. **Drift** — the hook and the workflow each name an entrypoint. If one is changed
   to run something else, the local and clean-environment gates stop measuring the
   same thing, and the difference between them becomes noise instead of signal.
2. **Fail-open** — the hook's own skip path. The first version treated "no ref
   lines on stdin" as "nothing is being pushed" and exited 0, so it allowed every
   push while printing a reassuring line. A positive control caught it within a
   minute. The shape is now asserted here so it cannot come back.

What is *not* asserted: that the hook is installed on this machine. `.git/hooks` is
not tracked and a test cannot fix a missing install, so `scripts/install_hooks.sh`
plus CI is the answer to that — CI runs whether or not anybody ran the installer,
which is exactly why both layers exist.
"""

from __future__ import annotations

import re
import stat
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "hooks" / "pre-push"
WORKFLOW = REPO / ".github" / "workflows" / "verify.yml"
INSTALLER = REPO / "scripts" / "install_hooks.sh"
GATE = "scripts/spirit_verify.sh"


class GateExistsTests(unittest.TestCase):
    def test_the_tracked_hook_exists_and_is_executable(self) -> None:
        self.assertTrue(HOOK.is_file(), "hooks/pre-push is the tracked source of the gate")
        self.assertTrue(
            HOOK.stat().st_mode & stat.S_IXUSR,
            "a hook without the execute bit is skipped by git in silence",
        )

    def test_the_installer_exists_and_is_executable(self) -> None:
        self.assertTrue(INSTALLER.is_file())
        self.assertTrue(INSTALLER.stat().st_mode & stat.S_IXUSR)

    def test_the_workflow_exists(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), "the clean-environment half of the gate")


class BothGatesRunTheSameThingTests(unittest.TestCase):
    """Local and CI must measure the same behaviour, or their disagreement is noise."""

    def test_the_hook_runs_the_verify_entrypoint(self) -> None:
        self.assertIn(GATE, HOOK.read_text(encoding="utf-8"))

    def test_the_workflow_runs_the_verify_entrypoint(self) -> None:
        self.assertIn(GATE, WORKFLOW.read_text(encoding="utf-8"))

    def test_the_entrypoint_they_both_name_exists(self) -> None:
        path = REPO / GATE
        self.assertTrue(path.is_file(), f"{GATE} is named by both gates and must exist")
        self.assertTrue(path.stat().st_mode & stat.S_IXUSR)

    def test_the_workflow_installs_from_the_pinned_requirements(self) -> None:
        """The clean-environment run is only clean if it installs what production does."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("requirements.txt", text)
        reqs = (REPO / "requirements.txt").read_text(encoding="utf-8")
        unpinned = [
            line.strip()
            for line in reqs.splitlines()
            if line.strip() and not line.startswith("#") and not re.search(r"[~=<>]=", line)
        ]
        self.assertEqual(
            unpinned,
            [],
            "an unpinned dependency makes the clean-environment run non-reproducible, "
            f"which is most of its value: {unpinned}",
        )

    def test_the_workflow_covers_the_python_the_live_host_runs(self) -> None:
        """A gate that passes on a version production does not run is half a gate."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("3.14", text, "the live host runs 3.14 — CI must too")


class WhichRemotesAreGatedTests(unittest.TestCase):
    """Run the real hook in a scratch repository (issue 054).

    The gate is the Mini's pull, and the Mini's pull is a repository, not a name:
    a remote with `origin`'s URL must be gated whatever it is called. The "gate" in
    the scratch repo is a script that leaves a mark, so *ran* and *did not run* are
    both observable (the positive control is the remote that must run it).
    """

    MINI = "ssh://mini.invalid/repos/turtleos.git"
    PUBLIC = "https://public.invalid/turtleos.git"

    def setUp(self) -> None:
        import subprocess
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        run = lambda *a: subprocess.run(a, cwd=self.repo, check=True, capture_output=True)  # noqa: E731
        run("git", "init", "-q")
        run("git", "remote", "add", "origin", self.MINI)
        run("git", "remote", "add", "turtle", self.MINI)
        run("git", "remote", "add", "public", self.PUBLIC)
        (self.repo / "scripts").mkdir()
        gate = self.repo / "scripts" / "spirit_verify.sh"
        gate.write_text("#!/usr/bin/env bash\ntouch gate-ran\nexit ${GATE_EXIT:-0}\n")
        gate.chmod(0o755)
        self.hook = self.repo / "pre-push"
        self.hook.write_text(HOOK.read_text(encoding="utf-8"))
        self.hook.chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def push(self, name: str, url: str, *, gate_exit: str = "0"):
        import os
        import subprocess

        sha = "1" * 40
        result = subprocess.run(
            [str(self.hook), name, url],
            cwd=self.repo,
            input=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n",
            text=True,
            capture_output=True,
            env={**os.environ, "GATE_EXIT": gate_exit},
        )
        return result, (self.repo / "gate-ran").exists()

    def test_origin_is_gated(self) -> None:
        _result, ran = self.push("origin", self.MINI)
        self.assertTrue(ran)

    def test_a_remote_with_another_name_and_the_origin_url_is_gated(self) -> None:
        """The hole: `turtle` was the Mini's repository and the gate was skipped."""
        _result, ran = self.push("turtle", self.MINI)
        self.assertTrue(ran)

    def test_the_public_remote_is_not_gated(self) -> None:
        _result, ran = self.push("public", self.PUBLIC)
        self.assertFalse(ran)

    def test_a_red_gate_refuses_a_push_to_the_mini_under_any_name(self) -> None:
        result, ran = self.push("turtle", self.MINI, gate_exit="1")
        self.assertTrue(ran)
        self.assertNotEqual(result.returncode, 0)

    def test_a_remote_with_no_url_is_not_assumed_to_be_the_mini(self) -> None:
        _result, ran = self.push("elsewhere", "")
        self.assertFalse(ran)


class FailClosedTests(unittest.TestCase):
    """The skip path is the dangerous part of any gate."""

    def test_the_skip_requires_a_ref_to_have_been_read(self) -> None:
        """Regression: empty stdin used to reach the skip and allow the push."""
        text = HOOK.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"saw_ref.*-eq 1.*deletions_only.*-eq 1|deletions_only.*-eq 1.*saw_ref.*-eq 1",
            "the skip must require both that refs were read AND that all were "
            "deletions — either condition alone is reachable by accident",
        )

    def test_the_hook_does_not_exit_zero_before_running_the_gate(self) -> None:
        """Any `exit 0` above the gate call is a path that skips verification."""
        lines = HOOK.read_text(encoding="utf-8").splitlines()
        gate_line = next(i for i, ln in enumerate(lines) if GATE in ln)
        early_exits = [
            (i + 1, ln.strip())
            for i, ln in enumerate(lines[:gate_line])
            if re.match(r"^\s*exit 0\s*$", ln)
        ]
        self.assertEqual(
            len(early_exits),
            2,
            "two early exits are expected — deletions-only, and remotes that are "
            "not origin (the Mini chronicle). A third is another way to push "
            f"without verifying: {early_exits}",
        )
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("deletions only", hook)
        self.assertIn('"$REMOTE_NAME" != "origin"', hook)
        self.assertIn("ORIGIN_URL", hook)

    def test_the_bypass_is_named_but_not_encouraged(self) -> None:
        text = HOOK.read_text(encoding="utf-8")
        self.assertIn("--no-verify", text, "hiding the bypass makes people find worse ones")
        self.assertIn("decoration", text, "and the message must say what using it costs")


class InstallerSafetyTests(unittest.TestCase):
    """The installer must not cost the repo its publication guard."""

    def test_the_installer_refuses_to_clobber_a_foreign_hook(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("skipping", text)
        self.assertIn(
            "turtleos tracked hook",
            text,
            "the installer identifies its own hooks so it can leave others alone",
        )

    def test_the_installer_warns_about_hookspath(self) -> None:
        """`core.hooksPath` would silently disable the pre-commit sanitation guard.

        That guard is machine-local on purpose — it needs a private name list this
        repository does not contain — so replacing the hook directory trades a
        tidier install for a repo that stops checking whether real people's names
        are about to be published.
        """
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("core.hooksPath", text)
        self.assertIn("pre-commit", text)


if __name__ == "__main__":
    unittest.main()
