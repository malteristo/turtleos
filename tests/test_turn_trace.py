"""turn_trace — the attunement line and the log clock."""

from __future__ import annotations

import io
import sys
import unittest
from datetime import datetime

sys.path.insert(0, ".")

import turn_trace as tt


class Duration(unittest.TestCase):
    def test_reads_like_a_person_would_say_it(self):
        self.assertEqual(tt.fmt_duration(3.21), "3.2 s")
        self.assertEqual(tt.fmt_duration(42.4), "42 s")
        self.assertEqual(tt.fmt_duration(209.4), "3 m 29 s")
        self.assertEqual(tt.fmt_duration(-1), "0.0 s")


class Trace(unittest.TestCase):
    def _steps(self):
        return tt.AttunementSteps(
            links=1, link_chars=8034,
            topics=["Mother-in-law", "Grief and burnout", "Childcare", "Birthday", "Salary"],
            room_notes=2, prompt_chars=15795,
        )

    def test_card_grows_with_the_turn_and_closes_as_the_record(self):
        steps = tt.attunement_step_list(self._steps())
        self.assertEqual([s.icon for s in steps], ["✅", "✅"])
        working = tt.render_card(steps, 12.0, "gemma4:31b")
        self.assertTrue(working.startswith("-# 🐢 working · 12 s"))
        self.assertIn("-# ✅ read 1 link (8,034 chars)", working)
        self.assertNotIn("remembering", working)
        self.assertNotIn("Mother-in-law", working)
        self.assertTrue(working.endswith("-# ✍️ gemma4:31b is composing…"))

    def test_card_does_not_recite_topics(self):
        """Positive control: planted hottest topics must not appear on the card."""
        steps = tt.attunement_step_list(self._steps())
        card = tt.render_card(steps, 12.0, "gemma4:31b")
        self.assertNotIn("remembering", card)
        self.assertNotIn("Mother-in-law", card)
        self.assertNotIn("Grief and burnout", card)
        self.assertIn("read 1 link", card)
        log = tt.render_log("family eddy", self._steps(), 12.0, "gemma4:31b", 100)
        self.assertIn("remembering: Mother-in-law", log)
        steps.append(tt.describe_tool("search_practice_files", {"query": "gray zone"},
                                      "**4 snippet(s)** for `gray zone` — open"))
        steps.append(tt.prose_step("Let me read the July conversation about the kitchen first."))
        steps.append(tt.describe_tool("read_practice_file", {"filename": "memory/topics/x.md"}, "..."))
        done = tt.render_card(steps, 209.4, "gemma4:31b", done=True)
        self.assertTrue(done.startswith("-# 🐢 attuned in 3 m 29 s"))
        self.assertIn('-# 🔎 searched notes for "gray zone" → 4 match(es)', done)
        self.assertIn("-# 💭 *Let me read the July conversation about the kitchen first.*", done)
        self.assertIn("-# 📖 read `memory/topics/x.md`", done)
        self.assertNotIn("composing", done)
        self.assertTrue(done.endswith("-# gemma4:31b"))

    def test_card_stays_readable_when_a_turn_wanders(self):
        steps = [tt.Step("🔧", f"step {i}") for i in range(30)]
        card = tt.render_card(steps, 5, "m")
        self.assertLessEqual(len(card.splitlines()), tt.CARD_MAX_LINES + 2)
        self.assertIn("more step(s)", card)
        long = tt.prose_step("word " * 100)
        self.assertLessEqual(len(long.text), tt.CARD_PROSE_CHARS + 2)
        self.assertTrue(long.text.endswith("…*"))
        self.assertIsNone(tt.prose_step("   "))

    def test_tools_are_described_as_a_person_would(self):
        self.assertEqual(
            tt.describe_tool("search_practice_files", {"query": "x"}, "No matches for `x`").text,
            'searched notes for "x" → nothing',
        )
        self.assertEqual(tt.describe_tool("list_practice_files", {}, "").text, "listed `/`")
        other = tt.describe_tool("run_shell", {"command": "ls"}, "first line\nsecond")
        self.assertEqual(other.icon, "🔧")
        self.assertEqual(other.text, "run_shell → first line")

    def test_blocked_shell_names_the_command_and_the_reason(self):
        raw = (
            "ToolResult[blocked] run_turtleos_shell: "
            "Shell command blocked: command not allowed: sed"
        )
        step = tt.describe_tool(
            "run_turtleos_shell",
            {"command": "sed -n '1,20p' mage.py"},
            raw,
        )
        self.assertEqual(step.icon, "🔧")
        self.assertIn("`sed -n '1,20p' mage.py`", step.text)
        self.assertIn("blocked: command not allowed: sed", step.text)
        self.assertNotIn("ToolResult[blocked]", step.text)
        ok = tt.describe_tool(
            "run_turtleos_shell",
            {"command": 'rg -i "model" docs/ --glob "*.md" -l'},
            '$ rg -i "model" docs/ --glob "*.md" -l\ndocs/a.md',
        )
        self.assertEqual(ok.text, '`rg -i "model" docs/ --glob "*.md" -l`')
        self.assertNotIn("ToolResult", ok.text)

    def test_exa_query_is_readable_and_bounded(self):
        long_q = (
            "Qwen 3.8 27B vs Gemma 4 local inference on a 64GB Mac Mini "
            "for River ambient intelligence and memory agent tool chaining"
        )
        step = tt.describe_tool(
            "exa_search",
            {"query": long_q},
            "Found 5 result(s) for 'Qwen 3.8 27B vs Gemma 4 local inference on a 64GB'",
        )
        self.assertEqual(step.icon, "🔎")
        self.assertIn("searched web for", step.text)
        self.assertIn("Qwen 3.8 27B vs Gemma 4", step.text)
        self.assertIn("→ 5 result(s)", step.text)
        self.assertLessEqual(len(step.text), tt.CARD_ASK_CHARS + 40)
        self.assertTrue("…" in step.text or len(long_q) <= tt.CARD_ASK_CHARS)
        self.assertNotIn("ToolResult", step.text)
        self.assertIsNone(tt._blocked_reason("Found 5 result(s) for 'x'"))

    def test_trace_is_honest_about_lookups(self):
        none = tt.render_trace(self._steps(), 209.4, "gemma4:31b", [])
        self.assertIn("attuned in 3 m 29 s", none)
        self.assertIn("no lookups", none)
        some = tt.render_trace(
            self._steps(), 12, "gemma4:31b", ["search_practice_files", "search_practice_files", "read_practice_file"]
        )
        self.assertIn("looked up: search_practice_files ×2, read_practice_file", some)
        self.assertNotIn("no lookups", some)

    def test_log_line_leads_with_the_duration(self):
        line = tt.render_log("family eddy", self._steps(), 209.4, "gemma4:31b", 1794)
        self.assertTrue(line.startswith("Turtle reply sent [family eddy]: 1794 chars in 3 m 29 s · prompt=15795 · gemma4:31b"))

    def test_tool_names_accept_the_loop_shapes(self):
        self.assertEqual(
            tt.tool_names([{"name": "a", "args": {}}, "b", type("T", (), {"name": "c"})()]),
            ["a", "b", "c"],
        )
        self.assertEqual(tt.tool_names(None), [])


class LogClock(unittest.TestCase):
    def test_every_line_gets_a_stamp_and_partial_lines_only_one(self):
        buf = io.StringIO()
        ticks = iter([datetime(2026, 9, 3, 17, 25, 20), datetime(2026, 9, 3, 17, 28, 49), datetime(2026, 9, 3, 17, 28, 50)])
        stream = tt.TimestampedStream(buf, clock=lambda: next(ticks))
        stream.write("Turtle inbound [x]: hi\n")
        stream.write("Turtle reply ")
        stream.write("sent [x]: 1794 chars\nnext\n")
        self.assertEqual(
            buf.getvalue(),
            "[2026-09-03 17:25:20] Turtle inbound [x]: hi\n"
            "[2026-09-03 17:28:49] Turtle reply sent [x]: 1794 chars\n"
            "[2026-09-03 17:28:50] next\n",
        )

    def test_install_is_idempotent_and_forwards_the_rest(self):
        real = sys.stdout
        try:
            sys.stdout = io.StringIO()
            tt.install_timestamps()
            first = sys.stdout
            tt.install_timestamps()
            self.assertIs(sys.stdout, first)
            self.assertIsInstance(sys.stdout, tt.TimestampedStream)
            print("hello")
            self.assertRegex(first._stream.getvalue(), r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] hello\n$")
            self.assertTrue(hasattr(sys.stdout, "getvalue"))  # __getattr__ forwards
        finally:
            sys.stdout = real


if __name__ == "__main__":
    unittest.main()
