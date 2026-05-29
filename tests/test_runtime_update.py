from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime.update import check_update, classify_changed_files, plan_update


class RuntimeUpdateTests(unittest.TestCase):
    def test_classify_changed_files_escalates_to_highest_consequence(self) -> None:
        impact = classify_changed_files(
            [
                "docs/development.md",
                "discord_bot.py",
                "requirements.txt",
                "TURTLE_SPEC.md",
                ".env.template",
            ]
        )

        self.assertEqual(impact["tier"], "explicit_mage_operator_approval")
        self.assertEqual(impact["buckets"]["docs_only"], ["docs/development.md"])
        self.assertEqual(impact["buckets"]["runtime_code"], ["discord_bot.py"])
        self.assertEqual(impact["buckets"]["dependencies"], ["requirements.txt"])
        self.assertEqual(impact["buckets"]["protected_or_governance"], ["TURTLE_SPEC.md"])

    def test_plan_update_reports_behind_runtime_change_without_applying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "remote.git"
            live = base / "live"
            publisher = base / "publisher"

            self._run(base, "git", "init", "--bare", str(remote))
            self._run(base, "git", "clone", str(remote), str(live))
            self._configure_repo(live)
            (live / "discord_bot.py").write_text("print('v1')\n", encoding="utf-8")
            self._run(live, "git", "add", "discord_bot.py")
            self._run(live, "git", "commit", "-m", "initial")
            self._run(live, "git", "branch", "-M", "main")
            self._run(live, "git", "push", "-u", "origin", "main")

            self._run(base, "git", "clone", "--branch", "main", str(remote), str(publisher))
            self._configure_repo(publisher)
            (publisher / "runtime").mkdir()
            (publisher / "runtime" / "update.py").write_text("VALUE = 1\n", encoding="utf-8")
            self._run(publisher, "git", "add", "runtime/update.py")
            self._run(publisher, "git", "commit", "-m", "add update runtime")
            self._run(publisher, "git", "push", "origin", "main")

            self._run(live, "git", "fetch", "origin")
            before = self._run(live, "git", "rev-parse", "HEAD").stdout.strip()
            check = check_update(repo=live)
            plan = plan_update(repo=live)
            after = self._run(live, "git", "rev-parse", "HEAD").stdout.strip()

        self.assertEqual(before, after)
        self.assertEqual(check["divergence"]["state"], "behind")
        self.assertEqual(plan["changed_files"], ["runtime/update.py"])
        self.assertEqual(plan["impact"]["tier"], "spirit_operator_approval")
        self.assertEqual(plan["restart"]["needed"], "maybe")
        self.assertFalse(plan["safe_to_apply"])

    def _configure_repo(self, repo: Path) -> None:
        self._run(repo, "git", "config", "user.email", "turtleos-test@example.invalid")
        self._run(repo, "git", "config", "user.name", "turtleOS Test")

    def _run(self, cwd: Path, *cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=15, check=True)


if __name__ == "__main__":
    unittest.main()
