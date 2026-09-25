"""Tests for prepared-eddy disposition (open → ready → harvested)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core.prepared_eddies import (  # noqa: E402
    HARVESTED,
    OPEN,
    READY,
    disposition_of,
    ensure_determination,
    mark_harvested,
    mark_ready,
    read_determination,
    surface_of,
)
from core.workspace_refresh import workspace_for_thread  # noqa: E402

SURFACE = """# Prepared surface — question

## Live state

**Settled so far:** candidate C.

**Last updated:** 2026-08-09 by Turtle.

## The item

Body that must survive.
"""


class TestDeterminationEdit(unittest.TestCase):
    def test_inserts_after_live_state(self):
        out = ensure_determination(SURFACE, "C, with packet persistence as the test.")
        self.assertIn("## Determination", out)
        self.assertIn("packet persistence", out)
        self.assertIn("## The item", out)
        self.assertEqual(
            read_determination(out),
            "C, with packet persistence as the test.",
        )

    def test_replaces_existing_determination(self):
        first = ensure_determination(SURFACE, "first answer")
        second = ensure_determination(first, "second answer")
        self.assertEqual(read_determination(second), "second answer")
        self.assertNotIn("first answer", second)

    def test_empty_determination_is_refused(self):
        with self.assertRaises(ValueError):
            ensure_determination(SURFACE, "  ")


class TestDispositionLifecycle(unittest.TestCase):
    def _tree(self, tmp: str, disposition: str = OPEN) -> Path:
        root = Path(tmp)
        (root / "craft").mkdir()
        (root / "craft" / "surface-x.md").write_text(SURFACE, encoding="utf-8")
        sidecar = root / "thread-state" / "prepared_eddies.yaml"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(
            yaml.dump(
                {
                    "prepared": {
                        "42": {
                            "surface": "craft/surface-x.md",
                            "prepared_topic": "x",
                            "disposition": disposition,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return root

    def test_mark_ready_writes_workspace_and_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp)
            entry = mark_ready(root, 42, determination="Act on C.")
            self.assertEqual(entry["disposition"], READY)
            self.assertEqual(entry["determination_one_liner"], "Act on C.")
            text = (root / "craft" / "surface-x.md").read_text(encoding="utf-8")
            self.assertEqual(read_determination(text), "Act on C.")
            self.assertEqual(disposition_of(root, 42), READY)

    def test_refresh_stops_after_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp)
            self.assertEqual(workspace_for_thread(root, 42), "craft/surface-x.md")
            mark_ready(root, 42, determination="Done.")
            self.assertIsNone(workspace_for_thread(root, 42))
            self.assertEqual(
                workspace_for_thread(root, 42, for_refresh=False),
                "craft/surface-x.md",
            )

    def test_harvest_only_from_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp)
            with self.assertRaises(ValueError):
                mark_harvested(root, 42)
            mark_ready(root, 42, determination="Done.")
            mark_harvested(root, 42)
            self.assertEqual(disposition_of(root, 42), HARVESTED)
            with self.assertRaises(ValueError):
                mark_ready(root, 42, determination="again")

    def test_surface_refuses_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sidecar = root / "thread-state" / "prepared_eddies.yaml"
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text(
                yaml.dump({"prepared": {"1": {"surface": "/etc/passwd", "disposition": OPEN}}}),
                encoding="utf-8",
            )
            self.assertIsNone(surface_of(root, 1))


class TestOpenerFitsBeforeSpawn(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        sys.path.insert(0, str(scripts))
        import open_prepared_eddy as ope  # noqa: E402

        cls.ope = ope
        cls.src = (scripts / "open_prepared_eddy.py").read_text(encoding="utf-8")

    def test_short_opener_passes(self) -> None:
        body = "What should we keep?"
        content = self.ope.assert_opener_fits(body, "craft/surface-x.md")
        self.assertIn("What should we keep?", content)
        self.assertLessEqual(len(content), self.ope.DISCORD_LIMIT)

    def test_overlong_opener_is_refused(self) -> None:
        body = "x" * 2000
        with self.assertRaises(RuntimeError) as ctx:
            self.ope.assert_opener_fits(body, "craft/surface-x.md")
        self.assertIn("over Discord", str(ctx.exception))
        self.assertIn("footer takes", str(ctx.exception))

    def test_check_appears_before_spawn_in_source(self) -> None:
        check = self.src.index("assert_opener_fits(body, args.surface)")
        spawn = self.src.index("await spawn_blank_river_eddy")
        self.assertLess(check, spawn)

    def test_old_spawn_then_check_order_fails_the_source_test(self) -> None:
        """Positive control: the pre-lift order would fail the check above."""
        old = (
            "thread = await spawn_blank_river_eddy(\n"
            "    channel,\n)\n"
            "await post_opener(env, thread.id, body, args.surface)\n"
        )
        check = old.find("assert_opener_fits(body, args.surface)")
        spawn = old.find("await spawn_blank_river_eddy")
        self.assertEqual(check, -1)
        self.assertGreater(spawn, -1)


if __name__ == "__main__":
    unittest.main()
