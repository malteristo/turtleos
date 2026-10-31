"""The hook that keeps the house's checkout on what was just pushed to main.

Real repositories: a bare house, a checkout that pulls from it, and a laptop that pushes to it.
Each case where the checkout must move sits beside one where it must not.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "workshop_post_receive.sh"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "n", "GIT_AUTHOR_EMAIL": "n", "GIT_COMMITTER_NAME": "n", "GIT_COMMITTER_EMAIL": "n"}


def git(cwd: Path, *argv: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *argv], capture_output=True, text=True, env=ENV, check=True).stdout.strip()


class Hook(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.house = base / "house.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.house)], check=True)
        self.laptop = base / "laptop"
        subprocess.run(["git", "clone", "-q", str(self.house), str(self.laptop)], check=True, capture_output=True)
        (self.laptop / "a.md").write_text("one\n")
        git(self.laptop, "add", "-A")
        git(self.laptop, "commit", "-q", "-m", "first")
        git(self.laptop, "push", "-q", "origin", "main")
        self.shop = base / "workshop"
        subprocess.run(["git", "clone", "-q", "-o", "turtle", str(self.house), str(self.shop)], check=True, capture_output=True)
        hook = self.house / "hooks" / "post-receive"
        hook.write_text(HOOK.read_text())
        hook.chmod(0o755)
        self.env = {**ENV, "WORKSHOP_CHECKOUT": str(self.shop)}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def push(self, branch: str = "main") -> str:
        done = subprocess.run(["git", "-C", str(self.laptop), "push", "-q", "origin", f"HEAD:{branch}"], capture_output=True, text=True, env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stderr + done.stdout

    def commit(self, name: str = "b.md") -> str:
        (self.laptop / name).write_text("x\n")
        git(self.laptop, "add", "-A")
        git(self.laptop, "commit", "-q", "-m", f"add {name}")
        return git(self.laptop, "rev-parse", "HEAD")

    def head(self) -> str:
        return git(self.shop, "rev-parse", "HEAD")

    def test_a_push_to_main_brings_the_checkout_up(self) -> None:
        new = self.commit()
        self.assertNotEqual(self.head(), new)
        out = self.push()
        self.assertEqual(self.head(), new)
        self.assertIn("checkout now at", out)

    def test_a_push_of_another_branch_leaves_it(self) -> None:
        before = self.head()
        self.commit()
        self.push("house/work")
        self.assertEqual(self.head(), before)

    def test_a_checkout_on_a_branch_is_left_and_the_push_still_goes_through(self) -> None:
        git(self.shop, "switch", "-q", "-c", "house/work")
        before = self.head()
        new = self.commit()
        out = self.push()
        self.assertEqual(self.head(), before)
        self.assertIn("not main", out)
        self.assertEqual(git(self.house, "rev-parse", "main"), new)

    def test_a_checkout_with_commits_of_its_own_is_not_merged_over(self) -> None:
        (self.shop / "mine.md").write_text("mine\n")
        git(self.shop, "add", "-A")
        git(self.shop, "commit", "-q", "-m", "mine")
        mine = self.head()
        new = self.commit()
        out = self.push()
        self.assertEqual(self.head(), mine, "no merge commit was made")
        self.assertIn("could not fast-forward", out)
        self.assertEqual(git(self.house, "rev-parse", "main"), new)

    def test_uncommitted_work_in_the_checkout_survives(self) -> None:
        (self.shop / "a.md").write_text("edited in the house\n")
        new = self.commit("c.md")
        self.push()
        self.assertEqual((self.shop / "a.md").read_text(), "edited in the house\n")
        self.assertEqual(self.head(), new)

    def test_a_missing_checkout_does_not_fail_the_push(self) -> None:
        self.env["WORKSHOP_CHECKOUT"] = str(Path(self.tmp.name) / "nowhere")
        self.commit()
        self.assertIn("no checkout", self.push())


if __name__ == "__main__":
    unittest.main()
