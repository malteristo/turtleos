import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core.workspace_refresh import (  # noqa: E402
    BEGIN,
    END,
    apply_refresh,
    build_block,
    refresh_workspace_file,
    workspace_for_thread,
)

SURFACE = """# Prepared surface — question

## Live state

**Settled so far:** nothing yet.

**Last updated:** not yet — staged 2026-08-08.

## The item

Body text that must survive.
"""


def block(stamp="09:30", note="story/eddies/1-x.md", text="Turtle and Kermit agreed on X."):
    return build_block(stamp=stamp, note_rel=note, entry_text=text)


class TestApplyRefresh(unittest.TestCase):
    def test_inserts_inside_live_state_not_at_the_end(self):
        out = apply_refresh(SURFACE, block(), "09:30")
        self.assertLess(out.index(BEGIN), out.index("## The item"))
        self.assertIn("Body text that must survive.", out)

    def test_updates_the_last_updated_line(self):
        out = apply_refresh(SURFACE, block(), "09:30")
        self.assertIn("**Last updated:** 09:30 (checkpoint)", out)
        self.assertNotIn("not yet — staged", out)

    def test_second_refresh_replaces_rather_than_stacks(self):
        once = apply_refresh(SURFACE, block(stamp="09:30"), "09:30")
        twice = apply_refresh(once, block(stamp="09:45", text="Later state."), "09:45")
        self.assertEqual(twice.count(BEGIN), 1)
        self.assertEqual(twice.count(END), 1)
        self.assertIn("Later state.", twice)
        self.assertNotIn("Turtle and Kermit agreed on X.", twice)

    def test_turtles_own_prose_is_preserved(self):
        edited = SURFACE.replace(
            "**Settled so far:** nothing yet.",
            "**Settled so far:** he wants the interview, not a verdict.",
        )
        out = apply_refresh(edited, block(), "09:30")
        self.assertIn("he wants the interview, not a verdict.", out)

    def test_turtle_edits_between_checkpoints_survive_the_next_one(self):
        once = apply_refresh(SURFACE, block(stamp="09:30"), "09:30")
        edited = once.replace("**Settled so far:** nothing yet.", "**Settled so far:** candidate A is out.")
        twice = apply_refresh(edited, block(stamp="09:45"), "09:45")
        self.assertIn("candidate A is out.", twice)

    def test_missing_live_state_section_is_created(self):
        out = apply_refresh("# Title\n\nBody.\n", block(), "09:30")
        self.assertIn("## Live state", out)
        self.assertIn(BEGIN, out)
        self.assertIn("Body.", out)


class TestBuildBlock(unittest.TestCase):
    def test_names_its_provenance(self):
        text = block()
        self.assertIn("idle checkpoint", text)
        self.assertIn("not by Turtle", text)
        self.assertIn("story/eddies/1-x.md", text)

    def test_empty_synthesis_says_so_rather_than_looking_written(self):
        self.assertIn("no synthesis", build_block(stamp="1", note_rel=None, entry_text="  "))


class TestSidecarLookup(unittest.TestCase):
    def test_finds_the_workspace_for_a_prepared_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thread-state" / "prepared_eddies.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(yaml.dump({"prepared": {"42": {"surface": "craft/surface-x.md"}}}))
            self.assertEqual(workspace_for_thread(tmp, 42), "craft/surface-x.md")

    def test_unprepared_thread_and_missing_sidecar_are_both_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(workspace_for_thread(tmp, 42))
            path = Path(tmp) / "thread-state" / "prepared_eddies.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(yaml.dump({"prepared": {"7": {"surface": "craft/a.md"}}}))
            self.assertIsNone(workspace_for_thread(tmp, 42))

    def test_non_markdown_surface_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thread-state" / "prepared_eddies.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(yaml.dump({"prepared": {"42": {"surface": "/etc/passwd"}}}))
            self.assertIsNone(workspace_for_thread(tmp, 42))


class TestRefreshFile(unittest.TestCase):
    def test_writes_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "surface.md"
            target.write_text(SURFACE)
            ok = refresh_workspace_file(
                target, stamp="09:30", note_rel="story/eddies/1-x.md", entry_text="State."
            )
            self.assertTrue(ok)
            self.assertIn("State.", target.read_text())

    def test_missing_file_is_false_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(
                refresh_workspace_file(
                    Path(tmp) / "nope.md", stamp="09:30", note_rel=None, entry_text="x"
                )
            )


if __name__ == "__main__":
    unittest.main()
