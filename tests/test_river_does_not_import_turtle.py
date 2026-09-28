"""River's process must not import ``discord_bot``: importing it builds Turtle's client.

``craft_intake`` reached `discord_bot` for helpers that live in ``dialogue_message``;
River ran craft intake, and the WRONG-CLIENT detector logged a constructed zombie
client (2026-09-21, and again 09-27 — the fix then was elsewhere on the same path).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KNOWN_IMPORTERS: set[str] = set()
IMPORT = re.compile(r"^\s*(from discord_bot import|import discord_bot)", re.M)


class NoTurtleImportTests(unittest.TestCase):
    def test_no_new_module_imports_discord_bot(self):
        importers = {
            str(p.relative_to(ROOT)) for p in ROOT.glob("*.py")
            if p.name not in ("discord_bot.py",) and IMPORT.search(p.read_text(encoding="utf-8"))
        }
        self.assertEqual(importers - KNOWN_IMPORTERS, set(), "import from the module that defines it")
        self.assertEqual(KNOWN_IMPORTERS - importers, set(), "one fewer — remove it from KNOWN_IMPORTERS")

    def test_craft_intake_is_clean(self):
        self.assertIsNone(IMPORT.search((ROOT / "craft_intake.py").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
