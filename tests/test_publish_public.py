"""The publish script is a derivation of the public surface, not a second list.

Dry-run is the ordinary command. --publish is the visibility act and must
refuse the Mini's origin. A script that defaults to push, or that will push
to origin when the public remote is missing, is the defect this test is for.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / "scripts" / "publish_public_turtleos.sh"
SURFACE = ROOT / "scripts" / "public_surface.sh"
MAGIC_SANITIZE = ROOT.parent / "magic" / "scripts" / "sanitize.sh"


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("TURTLEOS_PUBLIC_REMOTE", None)
    extra_env = kwargs.pop("env", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        **kwargs,
    )


def _surface_paths() -> list[str]:
    out = subprocess.check_output([str(SURFACE), "--list"], cwd=ROOT, text=True)
    return [line for line in out.splitlines() if line]


class PublishPublicTests(unittest.TestCase):
    def test_default_is_dry_run_and_matches_surface(self) -> None:
        listed = _surface_paths()
        proc = _run([str(PUBLISH)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Dry run", proc.stderr)
        self.assertNotIn("Published", proc.stderr)
        got = [line for line in proc.stdout.splitlines() if line]
        self.assertEqual(set(got), set(listed))
        self.assertGreater(len(got), 100)

    def test_dry_run_excludes_instance_facts(self) -> None:
        proc = _run([str(PUBLISH), "--dry-run"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("docs/live-runtime.md", proc.stdout)
        self.assertNotIn("docs/learnings.md", proc.stdout)
        self.assertIn("README.md", proc.stdout)

    def test_pre_push_gate_is_origin_only(self) -> None:
        """Positive control: a public-subset push is not a Mini deploy."""
        hook = (ROOT / "hooks" / "pre-push").read_text(encoding="utf-8")
        self.assertIn('"$REMOTE_NAME" != "origin"', hook)
        self.assertIn("skipping the live-host gate", hook)

    def test_publish_without_remote_refuses(self) -> None:
        proc = _run([str(PUBLISH), "--publish"])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not configured", proc.stderr)
        self.assertNotIn("Published", proc.stderr)

    def test_readme_points_at_the_public_clone_url(self) -> None:
        """Testers follow the README. The private origin must not be the clone URL."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (ROOT / "docs" / "install" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "github.com/malteristo/turtleos",
            readme,
            "README still clones the private origin",
        )
        self.assertNotIn(
            "github.com/malteristo/turtleos",
            skill,
            "install skill still clones the private origin",
        )
        self.assertIn("github.com/malteristo/turtle-os", readme)
        self.assertIn("docs/ux/faq.md", readme)

    def test_publish_refuses_origin(self) -> None:
        """Positive control: origin is the Mini's pull. An empty refuse is decoration."""
        proc = _run(
            [str(PUBLISH), "--publish"],
            env={"TURTLEOS_PUBLIC_REMOTE": "origin"},
        )
        self.assertNotEqual(
            proc.returncode,
            0,
            "publish to origin succeeded — the refuse is decoration",
        )
        self.assertIn("origin", proc.stderr.lower())
        self.assertNotIn("Published", proc.stderr)

    @unittest.skipUnless(MAGIC_SANITIZE.is_file(), "workshop sibling not present")
    def test_ordinary_sanitize_full_includes_tests(self) -> None:
        """The publication checklist is the ordinary hook, not an env var.

        Positive control: SANITIZE_INCLUDE_TESTS is unset. If the tests/
        skip returned, the script would say 'tests skipped' and a fixture
        with a name would commit clean.
        """
        env = os.environ.copy()
        env.pop("SANITIZE_INCLUDE_TESTS", None)
        proc = subprocess.run(
            [str(MAGIC_SANITIZE), "--full"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn("tests included", combined)
        self.assertNotIn("tests skipped", combined)


if __name__ == "__main__":
    unittest.main()
