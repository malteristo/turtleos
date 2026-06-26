"""Tests for Mini ops report formatting (Layer 1)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class OpsReportTests(unittest.TestCase):
    def test_format_ops_markdown_pass(self) -> None:
        from scripts.write_ops_report import format_ops_markdown

        bundle = {
            "meta": {
                "job": "test",
                "generated_at": "2026-06-26T12:00:00+00:00",
                "hostname": "test-host",
            },
            "ops_overall": "pass",
            "shake_report": {"functional_gate": "pass", "artifacts": []},
            "canary": {"overall": "green", "checks": []},
            "updates": {
                "turtleos_summary": "main @ abc12345, divergence=synced",
                "workshop_summary": "no git clone",
            },
            "suite_steps": [],
        }
        md = format_ops_markdown(bundle)
        self.assertIn("Spirit Ops Report", md)
        self.assertIn("PASS", md)
        self.assertIn("Functional gate: **pass**", md)

    def test_format_ops_markdown_includes_diagnosis(self) -> None:
        from scripts.write_ops_report import format_ops_markdown

        bundle = {
            "meta": {"job": "test", "generated_at": "t", "hostname": "h"},
            "ops_overall": "fail",
            "shake_report": {
                "functional_gate": "fail",
                "spirit_failed_artifacts": ["shake-river-latest.json"],
                "artifacts": [],
            },
            "canary": {"overall": "green", "checks": []},
            "updates": {"turtleos_summary": "x", "workshop_summary": "y"},
            "suite_steps": [{"name": "shake_river", "exit_code": 1, "stderr": "boom"}],
            "local_diagnosis": "- River shake failed",
        }
        md = format_ops_markdown(bundle)
        self.assertIn("FAIL", md)
        self.assertIn("Local diagnosis (qwen)", md)
        self.assertIn("River shake failed", md)

    def test_write_ops_artifacts(self) -> None:
        import tempfile

        from scripts.write_ops_report import write_ops_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "automation-reports"
            bundle = {
                "meta": {"job": "unittest", "generated_at": "t", "hostname": "h"},
                "ops_overall": "pass",
                "shake_report": {"functional_gate": "pass"},
                "canary": {"overall": "green"},
                "updates": {},
                "suite_steps": [],
            }
            paths = write_ops_artifacts(bundle, reports_dir=reports)
            self.assertTrue(Path(paths["latest_md"]).is_file())
            self.assertTrue(Path(paths["latest_json"]).is_file())
            latest = Path(paths["latest_md"]).read_text(encoding="utf-8")
            self.assertIn("Spirit Ops Report", latest)


    def test_resolve_desk_root_when_practice_dir_is_desk(self) -> None:
        from scripts.ops_paths import _resolve_desk_root

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            desk = Path(tmp) / "desk"
            desk.mkdir()
            (desk / "boom.md").write_text("boom", encoding="utf-8")
            self.assertEqual(_resolve_desk_root(desk), desk)

    def test_resolve_desk_root_when_practice_dir_is_parent(self) -> None:
        from scripts.ops_paths import _resolve_desk_root

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desk = root / "desk"
            desk.mkdir()
            (desk / "boom.md").write_text("boom", encoding="utf-8")
            self.assertEqual(_resolve_desk_root(root), desk)

    def test_sync_ops_harvest_commits_and_pushes(self) -> None:
        import subprocess
        import tempfile

        from scripts.ops_harvest_sync import sync_ops_harvest
        from scripts.write_ops_report import write_ops_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bare = base / "magic.git"
            repo = base / "workshop"
            reports = repo / "desk" / "craft" / "automation-reports"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "ops@test"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "ops"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True, capture_output=True)
            (repo / "desk" / "craft").mkdir(parents=True)
            (repo / "README.md").write_text("workshop", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

            bundle = {
                "meta": {"job": "unittest", "generated_at": "t", "hostname": "h"},
                "ops_overall": "pass",
                "shake_report": {"functional_gate": "pass"},
                "canary": {"overall": "green"},
                "updates": {},
                "suite_steps": [],
            }
            paths = write_ops_artifacts(bundle, reports_dir=reports)
            result = sync_ops_harvest(paths, bundle=bundle)
            self.assertEqual(result["status"], "pushed")
            self.assertIn("desk/craft/automation-reports/latest.md", result["paths"])

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout.strip(), "")

            bare_head = subprocess.run(
                ["git", "rev-parse", "main"],
                cwd=bare,
                capture_output=True,
                text=True,
                check=True,
            )
            repo_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(bare_head.stdout.strip(), repo_head.stdout.strip())
