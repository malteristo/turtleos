"""Tests for scripts/shake_report.py."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class ShakeReportTests(unittest.TestCase):
    def test_build_report_with_existing_artifacts(self) -> None:
        from scripts.shake_report import build_report

        report = build_report()
        self.assertIn("functional_gate", report)
        self.assertIn("mage_ux_queue", report)
        self.assertTrue(report["mage_ux_queue"])

    def test_parse_pass_and_fail(self) -> None:
        from scripts.shake_report import _parse_verdict

        self.assertEqual(_parse_verdict({"status": "pass"})[0], "pass")
        self.assertEqual(_parse_verdict({"pass": True})[0], "pass")
        self.assertEqual(_parse_verdict({"status": "fail"})[0], "fail")


if __name__ == "__main__":
    unittest.main()
