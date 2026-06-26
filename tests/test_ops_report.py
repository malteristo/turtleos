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


if __name__ == "__main__":
    unittest.main()
