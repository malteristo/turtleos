"""The public surface is a derivation of scripts/public_surface.conf.

A declaration that live-runtime and the operator chronicle do not ship is a
defect unless something fails when they would. This test is that something.

Positive control: the same --check is run against a path that must be private
and must come back private. An empty or always-public checker is a decoration.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "public_surface.sh"


def _check(path: str) -> str:
    out = subprocess.check_output(
        [str(SCRIPT), "--check", path],
        cwd=ROOT,
        text=True,
    ).strip()
    return out


class PublicSurfaceTests(unittest.TestCase):
    def test_self_test_green(self):
        proc = subprocess.run(
            [str(SCRIPT), "--self-test"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_product_docs_ship(self):
        self.assertEqual(_check("README.md"), "public")
        self.assertEqual(_check("TURTLE_SPEC.md"), "public")
        self.assertEqual(_check("discord_bot.py"), "public")
        self.assertEqual(_check("docs/chapters/design-practitioner-ready.md"), "public")
        self.assertEqual(_check("docs/ux/faq.md"), "public")
        self.assertEqual(
            _check("template/announcements/2026-07-16-return-visit.en.md"),
            "public",
        )

    def test_every_tracked_top_level_directory_is_decided(self):
        """A new top-level package is private by default, silently.

        mcp_server.py shipped while mcp_access/ did not: a public tree that
        cannot import. Each tracked top-level directory must be named DIR or
        DENY, so a new one fails here until someone decides.
        """
        conf = (ROOT / "scripts" / "public_surface.conf").read_text().splitlines()
        named = set()
        for line in conf:
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("DIR", "DENY"):
                named.add(parts[1].rstrip("/"))
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        top = {p.split("/", 1)[0] for p in tracked if "/" in p}
        self.assertEqual(sorted(top - named), [])
        self.assertEqual(_check("mcp_access/protocol.py"), "public")

    def test_instance_facts_do_not_ship(self):
        self.assertEqual(_check("docs/live-runtime.md"), "private")
        self.assertEqual(_check("docs/learnings.md"), "private")

    def test_positive_control_live_runtime_is_not_public(self):
        self.assertNotEqual(
            _check("docs/live-runtime.md"),
            "public",
            "live-runtime classified public — the deny is decoration",
        )

    def test_list_includes_readme_excludes_live_runtime(self):
        listed = subprocess.check_output(
            [str(SCRIPT), "--list"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        self.assertIn("README.md", listed)
        self.assertNotIn("docs/live-runtime.md", listed)
        self.assertNotIn("docs/learnings.md", listed)
        self.assertGreater(len(listed), 100)


if __name__ == "__main__":
    unittest.main()
