"""Nightly log watch — planted lines, window, new-mark, weather collapse."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.log_watch import (
    classify_line,
    collect_log_watch,
    render_section,
    scan_lines,
)


NOW = datetime(2026, 9, 13, 16, 0, 0)


def _line(hour: int, minute: int, body: str) -> str:
    return f"[2026-09-13 {hour:02d}:{minute:02d}:00] {body}"


class ClassifyTests(unittest.TestCase):
    def test_skip_and_exception(self) -> None:
        self.assertEqual(
            classify_line(
                _line(14, 44, "Contextual offer skip (turtle_intent:parent_not_native) in #craft-eddy")
            ),
            ("skip:turtle_intent:parent_not_native", "craft-eddy"),
        )
        self.assertEqual(
            classify_line(
                _line(10, 0, "Eddy flow library touch failed: TypeError: unexpected keyword")
            )[0],
            "exception:Eddy flow library touch failed:TypeError",
        )

    def test_pre_poll_collapses(self) -> None:
        a = classify_line(
            _line(14, 47, "Contextual offer skip (pre_poll:save=no_external_url;checkpoint=no_checkpoint_intent) in #a")
        )
        b = classify_line(
            _line(14, 50, "Contextual offer skip (pre_poll:save=cached_in_link_resonance:https://x;checkpoint=no_checkpoint_intent) in #b")
        )
        self.assertEqual(a[0], "skip:pre_poll")
        self.assertEqual(b[0], "skip:pre_poll")

    def test_tool_noise_is_not_a_class(self) -> None:
        self.assertIsNone(
            classify_line(
                _line(
                    14,
                    39,
                    '  Tool (claude-sonnet-4-6): run_turtleos_shell -> ToolResult[system_error] Shell command failed: `rg`',
                )
            )
        )

    def test_dialogue_and_reflection(self) -> None:
        self.assertEqual(
            classify_line(
                _line(
                    8,
                    34,
                    "Dialogue error (claude-sonnet-4-6): BadRequestError: credit balance is too low",
                )
            )[0],
            "dialogue:credit",
        )
        self.assertEqual(
            classify_line(_line(9, 0, "Reflection loop failed for 42: ReadTimeout: "))[0],
            "reflection:ReadTimeout",
        )
        self.assertEqual(
            classify_line(_line(9, 1, "Reflection loop empty for 42"))[0],
            "reflection:empty",
        )


class WrongClientDetectorIsReadTests(unittest.TestCase):
    """The detector printed 18 times in five days and this reader saw none of them.

    Two reasons, both fixed here: no class matched the line, and a stderr print
    has no `[timestamp]` so the window cut discarded it before classification.
    """

    WRONG = (
        "WRONG-CLIENT: the River process constructed Turtle's state.client, which is "
        "not logged in here — awaits on it land on _MissingSentinel. Use the client "
        "that owns the interaction (see home_plan_ui.resolve_pin_client)."
    )
    REFUSED = (
        "WRONG-CLIENT: the River process asked for a channel from Turtle's client; "
        "refused, returning None without constructing anything."
    )

    def test_both_detector_messages_classify(self) -> None:
        self.assertEqual(classify_line(self.WRONG), ("wrong_client:constructed", "?"))
        self.assertEqual(classify_line(self.REFUSED), ("wrong_client:asked", "?"))

    def test_untimestamped_line_inherits_the_previous_timestamp(self) -> None:
        lines = [
            _line(11, 44, "River rejoined thread: x (1) in #craft-turtle"),
            self.WRONG,
            '  File "/Users/turtle/turtleos/discord_bot.py", line 51, in <module>',
        ]
        buckets = scan_lines(lines, since=NOW - timedelta(hours=24))
        self.assertEqual(buckets["wrong_client:constructed"]["count"], 1)
        self.assertEqual(buckets["wrong_client:constructed"]["first"], datetime(2026, 9, 13, 11, 44))

    def test_inherited_timestamp_still_respects_the_window(self) -> None:
        """Positive control: yesterday's detector hit stays out of today's report."""
        lines = [
            "[2026-09-12 11:44:00] River rejoined thread: x (1) in #craft-turtle",
            self.WRONG,
        ]
        self.assertEqual(scan_lines(lines, since=NOW - timedelta(hours=24)), {})

    def test_a_leading_untimestamped_line_is_dropped_not_guessed(self) -> None:
        self.assertEqual(scan_lines([self.WRONG], since=NOW - timedelta(hours=24)), {})

    def test_refused_is_weather_constructed_is_signal(self) -> None:
        """Live 2026-09-22 11:40: River's offer post trips the refusal by design each time."""
        lines = [_line(11, 40, "Contextual offer posted (turtle_checkpoint) in #x (1)"), self.REFUSED, self.WRONG]
        buckets = scan_lines(lines, since=NOW - timedelta(hours=24))
        self.assertTrue(buckets["wrong_client:asked"]["weather"])
        self.assertFalse(buckets["wrong_client:constructed"]["weather"])


class ScanTests(unittest.TestCase):
    def test_window_drops_yesterday(self) -> None:
        lines = [
            "[2026-09-12 15:00:00] Eddy bar spawn failed: ImportError: gone",
            _line(15, 0, "Eddy bar spawn failed: ImportError: gone"),
        ]
        buckets = scan_lines(lines, since=NOW - timedelta(hours=24))
        self.assertEqual(buckets["exception:Eddy bar spawn failed:ImportError"]["count"], 1)

    def test_recurrence_counts_threads(self) -> None:
        lines = [
            _line(14, 44, "Contextual offer skip (turtle_intent:parent_not_native) in #one"),
            _line(14, 47, "Contextual offer skip (turtle_intent:parent_not_native) in #two"),
            _line(14, 50, "Contextual offer skip (turtle_intent:parent_not_native) in #one"),
        ]
        row = scan_lines(lines, since=NOW - timedelta(hours=24))[
            "skip:turtle_intent:parent_not_native"
        ]
        self.assertEqual(row["count"], 3)
        self.assertEqual(row["threads"], {"one", "two"})

    def test_previous_ids_mark_new(self) -> None:
        lines = [_line(15, 0, "Reflection loop empty for 7")]
        fresh = scan_lines(lines, since=NOW - timedelta(hours=24))
        self.assertTrue(fresh["reflection:empty"]["new"])
        seen = scan_lines(
            lines, since=NOW - timedelta(hours=24), previous_ids=["reflection:empty"]
        )
        self.assertFalse(seen["reflection:empty"]["new"])

    def test_old_windowless_scan_would_keep_yesterday(self) -> None:
        """Positive control: without a since-cut the historical line stays."""
        lines = ["[2026-09-12 15:00:00] Eddy bar spawn failed: ImportError: gone"]
        uncut = scan_lines(lines, since=datetime(2000, 1, 1))
        self.assertIn("exception:Eddy bar spawn failed:ImportError", uncut)
        cut = scan_lines(lines, since=NOW - timedelta(hours=24))
        self.assertEqual(cut, {})


class RenderTests(unittest.TestCase):
    def test_empty_window_still_names_the_instrument(self) -> None:
        section = render_section({}, window_hours=24, logs_found=2)
        self.assertIn("Log watch", section)
        self.assertIn("No classes in the window", section)

    def test_collect_reads_planted_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "discord.log").write_text(
                _line(15, 0, "Reflection loop empty for 99") + "\n",
                encoding="utf-8",
            )
            (root / "river.log").write_text("", encoding="utf-8")
            out = collect_log_watch(
                [root / "discord.log", root / "river.log"],
                now=NOW,
                previous_ids=[],
            )
        self.assertIn("reflection:empty", out["class_ids"])
        self.assertIn("reflection:empty", out["section"])
        self.assertIn("**new**", out["section"])

    def test_missing_log_is_unmeasured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "discord.log").write_text(
                _line(15, 0, "Reflection loop empty for 1") + "\n",
                encoding="utf-8",
            )
            out = collect_log_watch(
                [root / "discord.log", root / "river.log"],
                now=NOW,
            )
        self.assertEqual(out["logs_found"], 1)
        self.assertIn("unmeasured", out["section"])


class WiringTests(unittest.TestCase):
    def test_the_report_reads_the_logs(self) -> None:
        repo = Path(__file__).resolve().parent.parent
        runner = (repo / "scripts" / "ops_runner.py").read_text(encoding="utf-8")
        report = (repo / "scripts" / "write_ops_report.py").read_text(encoding="utf-8")
        self.assertIn("_collect_log_watch", runner)
        self.assertIn('"log_watch": _collect_log_watch()', runner)
        self.assertIn('bundle.get("log_watch")', report)
        collect_at = runner.find('"log_watch": _collect_log_watch()')
        write_at = runner.find("write_ops_artifacts(bundle)")
        self.assertGreater(collect_at, 0)
        self.assertGreater(write_at, collect_at)
        fn = runner[runner.find("def _collect_log_watch") : runner.find("def _collect_record_gaps")]
        self.assertIn("ops-report-latest.json", fn)


if __name__ == "__main__":
    unittest.main()
