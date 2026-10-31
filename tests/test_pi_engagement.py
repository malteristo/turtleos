"""The Pi engagement is a bordered card. Colour means the phase.

Blue while it works, green when it finishes clean, amber when something is
still false. A planted path is not on it. English and German have the same keys.
"""

from __future__ import annotations

import json
import unittest

import ui_kit
from pi_engagement import _TEXT, accent, engagement_view


class EngagementCard(unittest.TestCase):
    def test_working_is_blue_and_a_path_stays_off(self) -> None:
        view = engagement_view(
            phase="working",
            branch="pi/claim",
            progress="reading",
            failed=[],
            claims=[],
            looks=3,
        )
        self.assertEqual(ui_kit.violations(view), [])
        blob = json.dumps(ui_kit.components(view))
        self.assertIn(str(ui_kit.ACCENTS["info"]), blob)
        self.assertIn("Working", blob)
        self.assertIn("3 looks", blob)
        self.assertIn("pi/claim", blob)
        self.assertNotIn("PLANTED_SECRET_VALUE", blob)

    def test_a_clean_finish_is_green_and_a_false_claim_is_amber(self) -> None:
        clean = engagement_view(phase="done", branch="pi/claim", progress="finished", failed=[], claims=[], looks=1)
        waiting = engagement_view(
            phase="aborted",
            branch="pi/show-once",
            progress="aborted before a prompt",
            failed=[],
            claims=["a climb has not run"],
            looks=0,
        )
        self.assertEqual(ui_kit.violations(clean), [])
        self.assertEqual(ui_kit.violations(waiting), [])
        self.assertIn(str(ui_kit.ACCENTS["done"]), json.dumps(ui_kit.components(clean)))
        self.assertIn(str(ui_kit.ACCENTS["attention"]), json.dumps(ui_kit.components(waiting)))
        self.assertEqual(accent("working", [], ["still"]), "info")
        self.assertEqual(accent("done", [], []), "done")
        self.assertEqual(accent("aborted", ["tests/test_claim.py"], []), "attention")

    def test_both_languages_have_the_same_words(self) -> None:
        self.assertEqual(ui_kit.parity(_TEXT), [])
