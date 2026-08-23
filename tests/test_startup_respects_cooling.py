"""A cooled eddy is archived on purpose, and startup used to undo it.

`on_ready`'s archived-thread sweep exists to rejoin threads Discord archived on
its own. It checked `is_dissolved` and not `is_eddy_cooled`, so every restart
unarchived anything cooled rather than dissolved — which is *"eddies age, don't
close"* (2026-07-20) reversed once per deploy, silently, by the code whose job is
to keep live threads live.

Found 2026-08-17 by asking whether a cool survives a restart, immediately after
using the new cool path on three finished craft eddies. It is the same shape as
the four `presence checked where function was meant` entries in the ledger: a
guard that covers one state and not the neighbouring one.

The sweep is a closure inside `on_ready` and cannot be called directly, so this
tests the decision rather than the loop — the two predicates that decide whether
a thread is left alone, and the fact that the module consults the cooled one at
all. A wire test plus an AST check is the honest coverage here; the alternative
is extracting the loop, which is a refactor of the boot path and wants its own
change.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT = REPO_ROOT / "discord_bot.py"


def _on_ready_source() -> str:
    tree = ast.parse(BOT.read_text(encoding="utf-8"), filename=str(BOT))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "on_ready":
            return ast.get_source_segment(BOT.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("on_ready not found — this test is about its archived sweep")


class StartupRespectsCoolingTests(unittest.TestCase):
    def test_the_sweep_consults_both_retirement_states(self) -> None:
        source = _on_ready_source()
        self.assertIn("is_dissolved(", source)
        self.assertIn(
            "is_eddy_cooled(",
            source,
            "startup unarchives cooled eddies — a cool that does not survive a "
            "restart is not a retirement, it is a pause nobody asked for",
        )

    def test_both_checks_skip_rather_than_unarchive(self) -> None:
        """The order matters: a check that logs and falls through changes nothing."""
        source = _on_ready_source()
        cooled_at = source.index("is_eddy_cooled(")
        unarchive_at = source.index("archived=False")
        self.assertLess(
            cooled_at,
            unarchive_at,
            "the cooled check must run before the unarchive, not after it",
        )
        tail = source[cooled_at:unarchive_at]
        self.assertIn("continue", tail, "the cooled branch must skip the thread")

    def test_the_cooled_predicate_exists_and_reads_the_registry(self) -> None:
        """Positive control on the predicate the guard now depends on.

        A guard calling a function that always returned False would pass the
        wire tests above while unarchiving every cooled eddy exactly as before.
        """
        import tempfile
        from unittest.mock import patch

        import thread_registry as tr

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.yaml"
            with patch.object(tr, "_registry_path", return_value=path):
                tr.clear_registry_cache_for_tests()
                tr.register_thread(4242, "a finished eddy", parent_channel="craft-turtle")
                self.assertFalse(tr.is_eddy_cooled(4242))
                tr.mark_cooled(4242)
                self.assertTrue(tr.is_eddy_cooled(4242))
                tr.clear_registry_cache_for_tests()


if __name__ == "__main__":
    unittest.main()
