"""Shell harness widenings for craft-turtle architecture surveys."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import shell_harness as sh


class ValidateArgsSurveyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cwd = sh.TURTLEOS_ROOT

    def test_ls_one_column_allowed(self) -> None:
        ok, err = sh._validate_args(["ls", "-1"], self.cwd)
        self.assertTrue(ok, err)

    def test_git_log_short_count(self) -> None:
        ok, err = sh._validate_args(["git", "log", "--oneline", "-5"], self.cwd)
        self.assertTrue(ok, err)

    def test_git_log_name_only(self) -> None:
        ok, err = sh._validate_args(
            ["git", "log", "--oneline", "--max-count=5", "--name-only"], self.cwd
        )
        self.assertTrue(ok, err)

    def test_git_log_stat(self) -> None:
        ok, err = sh._validate_args(
            ["git", "log", "--oneline", "-n", "10", "--stat"], self.cwd
        )
        self.assertTrue(ok, err)

    def test_head_and_tail(self) -> None:
        ok, err = sh._validate_args(["head", "-n", "20", "dialogue_runtime.py"], self.cwd)
        self.assertTrue(ok, err)
        ok, err = sh._validate_args(["tail", "-40", "dialogue_runtime.py"], self.cwd)
        self.assertTrue(ok, err)

    def test_head_rejects_huge_line_count(self) -> None:
        ok, err = sh._validate_args(["head", "-n", "999", "dialogue_runtime.py"], self.cwd)
        self.assertFalse(ok)
        self.assertIn("1..", err)

    def test_rg_type_and_regex_pipe(self) -> None:
        ok, err = sh._validate_args(
            ["rg", "-n", "^class |^def ", "dialogue_runtime.py"], self.cwd
        )
        self.assertTrue(ok, err)
        ok, err = sh._validate_args(
            ["rg", "--type", "py", "-n", "class", "dialogue_runtime.py"], self.cwd
        )
        self.assertTrue(ok, err)

    def test_rg_files_with_matches_and_count(self) -> None:
        for flag in ("-l", "--files-with-matches", "-c", "--count"):
            ok, err = sh._validate_args(["rg", flag, "intention"], self.cwd)
            self.assertTrue(ok, f"{flag}: {err}")

    def test_rg_replace_refused_with_the_grep_ism_named(self) -> None:
        """``-r`` is --replace, so allowing it would corrupt output and exit 0."""
        for args in (["rg", "-rn", "intention"], ["rg", "-r", "n", "intention"],
                     ["rg", "--replace", "n", "intention"]):
            ok, err = sh._validate_args(args, self.cwd)
            self.assertFalse(ok, args)
            self.assertIn("replace", err)

    def test_pipe_still_blocked_outside_rg(self) -> None:
        ok, err = sh._validate_args(["ls", "|", "wc"], self.cwd)
        self.assertFalse(ok)


class InspectModuleTests(unittest.TestCase):
    def test_inspect_returns_signatures(self) -> None:
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module("shell_harness.py", head_lines=15)
        self.assertIn("## Signatures", out)
        self.assertIn("def run_shell_command", out)
        self.assertIn("## Lines 1–15", out)

    def test_window_can_start_in_the_middle_of_a_file(self) -> None:
        """The read that was refused on 2026-08-14.

        Turtle had the schema at line 292 and the dispatch at 496 from ``rg -n``
        and could not read the span: ``head -n 340`` is over the harness cap and
        no permitted call could place a window past line 1. One call now covers
        it, and the lines carry their own numbers so the next hop is navigable.
        """
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module(
            "tos_tools.py", start_line=280, line_count=240
        )
        self.assertIn("## Lines 280–519", out)
        self.assertIn("280: ", out)
        self.assertIn("519: ", out)
        self.assertNotIn("\n1: ", out.split("## Lines")[-1])

    def test_truncated_window_names_the_next_start_line(self) -> None:
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module("tos_tools.py", start_line=1, line_count=10)
        self.assertIn("call again with start_line=11", out)

    def test_window_is_capped_and_says_so(self) -> None:
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module(
            "tos_tools.py", start_line=1, line_count=10_000
        )
        self.assertIn("## Lines 1–400", out)
        self.assertIn("window capped at 400 lines", out)

    def test_start_past_end_of_file_is_reported_not_silent(self) -> None:
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module("shell_harness.py", start_line=99_999)
        self.assertIn("past the end of the file", out)
        self.assertIn("## Signatures", out)

    def test_zero_line_count_returns_outline_only(self) -> None:
        from tos_tools import _inspect_turtleos_module

        out = _inspect_turtleos_module("shell_harness.py", line_count=0)
        self.assertIn("## Signatures", out)
        self.assertNotIn("## Lines", out)

    def test_dispatch_passes_the_window_arguments(self) -> None:
        """A schema property nothing forwards is the defect this pins."""
        import tos_tools

        out = tos_tools._execute_tos_tool_raw(
            "inspect_turtleos_module",
            {"filename": "shell_harness.py", "start_line": 50, "line_count": 5},
        )
        self.assertIn("## Lines 50–54", out)

    def test_list_root_modules(self) -> None:
        from tos_tools import _list_turtleos_modules

        out = _list_turtleos_modules("")
        self.assertIn("shell_harness.py", out)
        # Non-recursive root listing — no nested test paths.
        self.assertTrue(
            all("/" not in line or line.startswith("…") for line in out.splitlines())
        )

    def test_list_recursive(self) -> None:
        from tos_tools import _list_turtleos_modules

        out = _list_turtleos_modules(".")
        self.assertIn("tests/", out)


if __name__ == "__main__":
    unittest.main()
