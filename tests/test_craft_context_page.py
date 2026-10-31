"""The craft context page points at eddies. It does not carry their bodies."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

from craft_context_page import (
    decision_surface,
    maintain_craft_context_page,
    refresh_craft_context_page,
)

TZ = ZoneInfo("Europe/Berlin")
BODY_REST = "The second sentence is the rest of the eddy and must not be copied."


def _note(thread: str, title: str, when: str, body: str, sparks: str) -> str:
    return (
        f"---\n"
        f"thread: '{thread}'\n"
        f"title: {title}\n"
        f"trigger: idle\n"
        f"timestamp: '{when}'\n"
        f"related-topics: []\n"
        f"proposed-themes: []\n"
        f"sparks:\n{sparks}"
        f"---\n\n"
        f"{body}\n"
    )


class CraftContextPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        eddies = self.root / "story" / "eddies"
        eddies.mkdir(parents=True)
        (eddies / "7-evenings.md").write_text(
            _note(
                "7",
                "Evenings",
                "2026-10-03T18:00:00+02:00",
                "The afternoon was short. " + BODY_REST,
                "- {id: evening-game, name: The evening game, topic: evenings, status: open}\n"
                "- {id: dropped-one, name: Dropped one, topic: evenings, status: dropped}\n",
            ),
            encoding="utf-8",
        )
        (eddies / "8-key.md").write_text(
            _note(
                "8",
                "The key split",
                "2026-10-05T09:00:00+02:00",
                "He decided to describe the split. " + BODY_REST,
                "- {id: ledger, name: The historical ledger, topic: the key, status: open}\n",
            ),
            encoding="utf-8",
        )
        health = self.root / "health" / "story" / "eddies"
        health.mkdir(parents=True)
        (health / "9-private.md").write_text(
            _note(
                "9",
                "Private health eddy",
                "2026-10-05T10:00:00+02:00",
                "This sentence belongs to health. " + BODY_REST,
                "",
            ),
            encoding="utf-8",
        )
        story = self.root / "story"
        (story / "craft-context-looked.txt").write_text(
            "2026-10-04T12:00:00+02:00\n", encoding="utf-8"
        )
        (story / "craft-intentions.yaml").write_text(
            "- name: The page\n"
            "  path: desk/intentions/ideal-state-craft-interface.md\n"
            "  passed: true\n"
            "  unbuilt: true\n"
            "  line: One page, then a deeper read.\n",
            encoding="utf-8",
        )
        (story / "craft-remarks.yaml").write_text(
            "- at: '2026-10-05T11:00:00+02:00'\n"
            "  pointer: '155-craft-chat'\n"
            "  line: The arrival should read the page.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_highlights_the_new_and_keeps_the_quiet(self) -> None:
        page = refresh_craft_context_page(
            self.root, updated=datetime(2026, 10, 5, 12, 0, tzinfo=TZ), tz=TZ
        )
        text = page.read_text(encoding="utf-8")
        since, standing = text.split("## Standing", 1)
        self.assertIn("The key split", since)
        self.assertNotIn("Evenings", since)
        self.assertIn("155-craft-chat", since)
        self.assertIn("Evenings", standing)
        self.assertIn("The page", standing)
        self.assertIn("passed, unbuilt", standing)
        self.assertIn("The evening game", standing)
        self.assertNotIn("Dropped one", standing)
        self.assertNotIn(BODY_REST, text)
        self.assertNotIn("Private health eddy", text)
        self.assertNotIn("This sentence belongs to health", text)

    def test_a_quiet_eddy_stays_on_the_page(self) -> None:
        """The quiet eddy is still choosable. Hiding it would be the highlight reel."""
        page = refresh_craft_context_page(
            self.root, updated=datetime(2026, 10, 5, 12, 0, tzinfo=TZ), tz=TZ
        )
        standing = page.read_text(encoding="utf-8").split("## Standing", 1)[1]
        self.assertIn("since last look: no", standing)
        self.assertIn("since last look: yes", standing)

    def test_other_rooms_do_not_write_the_page(self) -> None:
        wrote = maintain_craft_context_page(self.root, 1, lambda channel_id: False)
        self.assertFalse(wrote)
        self.assertFalse((self.root / "story" / "craft-context.md").exists())

    def test_the_craft_surface_writes_the_page(self) -> None:
        wrote = maintain_craft_context_page(self.root, 1, lambda channel_id: True)
        self.assertTrue(wrote)
        text = (self.root / "story" / "craft-context.md").read_text(encoding="utf-8")
        self.assertIn("# Craft context", text)
        self.assertNotIn(BODY_REST, text)


class WiringTests(unittest.TestCase):
    def test_the_note_writer_hands_over_its_own_predicate(self) -> None:
        """A forgotten argument is a TypeError the writer catches and prints, so the
        page would silently stop refreshing (the suite stays green)."""
        import ast
        from pathlib import Path

        tree = ast.parse((Path(__file__).resolve().parents[1] / "story_notes.py").read_text(encoding="utf-8"))
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "maintain_craft_context_page"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0].args), 3)


class DecisionSurfaceTests(unittest.TestCase):
    def test_the_surface_keeps_a_quiet_intention_and_leaves_the_oldest_eddy(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            eddies = root / "story" / "eddies"
            eddies.mkdir(parents=True)
            for n in range(20):
                when = f"2026-09-{(n % 28) + 1:02d}T08:00:00+02:00"
                (eddies / f"{n}-eddy.md").write_text(
                    _note(
                        str(n),
                        f"Eddy {n}",
                        when,
                        f"About {n}. " + BODY_REST,
                        "",
                    ),
                    encoding="utf-8",
                )
            (root / "story" / "craft-intentions.yaml").write_text(
                "- name: The outward client\n"
                "  path: desk/intentions/ideal-state-client.md\n"
                "  passed: true\n"
                "  unbuilt: true\n"
                "  line: X is the first server.\n",
                encoding="utf-8",
            )
            page_path = refresh_craft_context_page(
                root, updated=datetime(2026, 10, 5, 12, 0, tzinfo=TZ), tz=TZ
            )
            page = page_path.read_text(encoding="utf-8")
            surface = decision_surface(page)
            self.assertIn("Eddy 19", page)
            self.assertIn("Eddy 19", surface)
            self.assertIn("The outward client", surface)
            self.assertIn("passed, unbuilt", surface)
            self.assertNotIn("Eddy 0", surface)
            self.assertNotIn(BODY_REST, surface)
            self.assertIn("older eddies, on the page", surface)
        finally:
            import shutil
            shutil.rmtree(root)
