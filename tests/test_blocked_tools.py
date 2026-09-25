"""blocked_tools — the named query over the ledger that already exists."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")

import blocked_tools as bt


class Normalize(unittest.TestCase):
    def test_strips_wrappers_keeps_the_policy(self):
        self.assertEqual(
            bt.normalize_reason("Shell command blocked: command not allowed: sed"),
            "command not allowed: sed",
        )
        self.assertEqual(
            bt.normalize_reason("ToolResult[blocked] run_turtleos_shell: Shell command blocked: command not allowed: rm"),
            "command not allowed: rm",
        )
        self.assertEqual(bt.normalize_reason(""), "(no reason)")


class Grouping(unittest.TestCase):
    def test_groups_by_tool_and_reason_and_ignores_success(self):
        rows = [
            {"tool": "run_turtleos_shell", "kind": "blocked",
             "summary": "Shell command blocked: command not allowed: sed"},
            {"tool": "run_turtleos_shell", "kind": "blocked",
             "summary": "Shell command blocked: command not allowed: sed"},
            {"tool": "exa_search", "kind": "success", "summary": "Found 5"},
        ]
        groups = bt.group(rows)
        self.assertEqual(groups, [("run_turtleos_shell", "command not allowed: sed", 2)])


class SelfTest(unittest.TestCase):
    def test_script_self_test_passes_and_can_fail(self):
        repo = Path(__file__).resolve().parents[1]
        out = subprocess.run(
            [sys.executable, str(repo / "scripts" / "blocked_tools.py"), "--self-test"],
            check=True, capture_output=True, text=True,
        )
        self.assertIn("ok", out.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tool-actions.jsonl"
            path.write_text(json.dumps({"tool": "x", "kind": "success", "summary": "ok"}) + "\n")
            rows = bt.load_blocked([path])
            self.assertEqual(bt.group(rows), [])


if __name__ == "__main__":
    unittest.main()
