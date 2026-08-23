"""A tool result is graded by its status line, never by its payload.

Every payload below is a real one, taken from the live tool-action ledger on
2026-08-14 — each was recorded as a *failure* of a read that had succeeded.
"""

from __future__ import annotations

import unittest

from tool_result import BLOCKED, NOT_FOUND, SUCCESS, TRANSIENT, USER_ERROR, classify_tool_text


class SuccessfulReadsAreNotFailures(unittest.TestCase):
    """The payload mentions errors because the payload is about errors."""

    def test_reading_a_file_that_says_connection_is_not_transient(self) -> None:
        r = classify_tool_text(
            "read_practice_file",
            "[CLAUDE.md]\n\n# Magic Practice\n\nMCP topology is variant-dependent; verify the connection.",
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["kind"], SUCCESS)
        self.assertFalse(r["retryable"])

    def test_listing_files_whose_names_contain_error_is_not_a_system_error(self) -> None:
        r = classify_tool_text(
            "list_practice_files",
            "proposals/009_link_as_wormhole.md (7000 bytes)\n"
            "proposals/013_turtleos_error_recovery.md (9152 bytes)",
        )
        self.assertTrue(r["ok"])

    def test_inspecting_a_module_with_exception_handling_is_not_a_failure(self) -> None:
        r = classify_tool_text(
            "inspect_turtleos_module",
            "# llm.py\n\nexcept Exception as e:\n    print(f'Gemini chat error: {e}')\n"
            "    # retry on timeout / connection reset",
        )
        self.assertTrue(r["ok"])

    def test_search_hits_are_not_transient(self) -> None:
        r = classify_tool_text(
            "search_practice_files",
            "Found 27 match(es):\nboom/bright.md:87: timeout handling for the founding member flow",
        )
        self.assertTrue(r["ok"])

    def test_shell_success_is_judged_by_the_command_line(self) -> None:
        r = classify_tool_text(
            "run_turtleos_shell",
            "$ rg -n -i 'artifacts' --glob '*.py'\n"
            "llm.py:304: print(f'Gemini chat error: {e}')\n"
            "[stderr]\nwarning: some paths were not found",
        )
        self.assertTrue(r["ok"])

    def test_capability_and_skill_reads_need_no_special_case(self) -> None:
        """The two per-tool exemptions were spot-patches for this same bug."""
        self.assertTrue(classify_tool_text(
            "read_turtle_capability", "[skill:diagnose]\n\nOn timeout, retry once.")["ok"])
        self.assertTrue(classify_tool_text(
            "list_turtle_capabilities", "- `diagnose` — stack health after a connection error")["ok"])


class RealFailuresStillClassify(unittest.TestCase):
    def test_blocked(self) -> None:
        r = classify_tool_text(
            "run_turtleos_shell", "Shell command blocked: command not allowed: sed")
        self.assertFalse(r["ok"])
        self.assertEqual(r["kind"], BLOCKED)

    def test_shell_failure_marker_is_on_the_first_line(self) -> None:
        r = classify_tool_text(
            "run_turtleos_shell", "Shell command failed: `ls proposals`\nexit 1")
        self.assertFalse(r["ok"])

    def test_missing_section(self) -> None:
        r = classify_tool_text(
            "read_practice_file",
            "Section 'Runtime' not found in AGENTS.md. Available headings: Quick Start",
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["kind"], NOT_FOUND)

    def test_not_writable(self) -> None:
        r = classify_tool_text(
            "patch_practice_file", "Cannot patch x.md — not a writable practice file")
        self.assertEqual(r["kind"], BLOCKED)

    def test_unknown_tool(self) -> None:
        self.assertEqual(classify_tool_text("nope", "Unknown tool: nope")["kind"], USER_ERROR)

    def test_delegate_edit_failure(self) -> None:
        r = classify_tool_text(
            "delegate_edit", "Delegate edit failed — local model returned empty/short result. Try again.")
        self.assertFalse(r["ok"])

    def test_a_real_timeout_is_still_retryable(self) -> None:
        r = classify_tool_text("read_practice_file", "read failed: ReadTimeout: ")
        self.assertEqual(r["kind"], TRANSIENT)
        self.assertTrue(r["retryable"])

    def test_module_listing_refusals_are_no_longer_silent_successes(self) -> None:
        """These sentences matched no marker at all — an escaped path read as a listing."""
        for text in (
            "path escapes ~/turtleos: ../../etc",
            "not a directory: llm.py",
            "directory must be relative to ~/turtleos",
        ):
            with self.subTest(text=text):
                self.assertFalse(classify_tool_text("list_turtleos_modules", text)["ok"])


if __name__ == "__main__":
    unittest.main()
