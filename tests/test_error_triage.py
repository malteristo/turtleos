"""Nightly error triage: only new kinds of error, judged, reported when they need someone."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import error_triage as et

NIGHT = datetime(2026, 9, 29, 5, 30)


class SignatureTests(unittest.TestCase):
    def test_ids_names_and_quotes_fold_into_one_shape(self):
        a = et.signature("[2026-09-28 09:46:14] auto-admit on join failed for robin: HTTP 403 'Missing Access'")
        b = et.signature("[2026-09-29 01:02:03] auto-admit on join failed for sam: HTTP 404 'Unknown'")
        self.assertEqual(a, b)
        self.assertNotIn("robin", a)


class NightlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.logs, self.issues = root / "logs", root / "issues"
        self.logs.mkdir()
        self.issues.mkdir()
        (self.issues / "048-registry.md").write_text("# 048 — Registry saves\n")
        self.env = patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": str(root / "house")})
        self.env.start()
        self.asked = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _log(self, *lines):
        with open(self.logs / "river.log", "a") as fh:
            fh.write("\n".join(lines) + "\n")

    async def _ask(self, prompt):
        self.asked.append(prompt)
        return json.dumps({"items": [{"id": 0, "class": "registry save lost", "issue": "048-registry.md",
                                      "needs_person": True, "why": "a change was written away"}]})

    def _run(self, when):
        return asyncio.run(et.run_nightly(self.logs, self.issues, self._ask, now=when))

    def test_first_night_records_what_is_there_as_known(self):
        self._log("[x] Old thing failed: boom")
        line = self._run(NIGHT)
        self.assertIn("recorded as known", line)
        self.assertEqual(self.asked, [])

    def test_a_new_kind_of_error_is_judged_and_reported(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        self._log("[x] Old thing failed: boom again", "[y] Registry save failed: lost 3 keys")
        line = self._run(datetime(2026, 9, 30, 5, 30))
        self.assertEqual(len(self.asked), 1)
        self.assertIn("Registry save failed", self.asked[0])
        self.assertNotIn("Old thing", self.asked[0])
        self.assertIn("registry save lost", line)
        self.assertIn("048-registry.md", line)

    def test_nothing_new_posts_nothing_and_asks_nothing(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        self._log("[x] Old thing failed: boom")
        self.assertIsNone(self._run(datetime(2026, 9, 30, 5, 30)))
        self.assertEqual(self.asked, [])

    def test_once_a_night_and_only_at_night(self):
        self._log("[x] Old thing failed: boom")
        self.assertIsNone(self._run(datetime(2026, 9, 29, 14, 0)))
        self._run(NIGHT)
        self._log("[y] New thing failed: x")
        self.assertIsNone(self._run(datetime(2026, 9, 29, 6, 30)))

    def test_new_classes_from_the_ops_report_are_judged_too(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        report = Path(self.tmp.name) / "ops.json"
        report.write_text(json.dumps({"log_watch": {"classes": [
            {"class_id": "wrong_client:constructed", "count": 3, "new": True, "weather": False, "last": "2026-09-29 21:15:09"},
            {"class_id": "wrong_client:asked", "count": 9, "new": True, "weather": True, "last": "2026-09-29 21:15:09"},
        ]}}))
        line = asyncio.run(et.run_nightly(self.logs, self.issues, self._ask, report_json=report,
                                          now=datetime(2026, 9, 30, 5, 30)))
        self.assertIn("wrong_client:constructed", self.asked[0])
        self.assertNotIn("wrong_client:asked", self.asked[0])
        self.assertIsNotNone(line)

    def test_noise_is_kept_in_the_inbox_not_reported(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        self._log("[y] Blip failed: timeout")

        async def noise(prompt):
            return json.dumps({"items": [{"id": 0, "class": "network blip", "issue": None,
                                          "needs_person": False, "why": "retried fine"}]})

        self.assertIsNone(asyncio.run(et.run_nightly(self.logs, self.issues, noise, now=datetime(2026, 9, 30, 5, 30))))
        self.assertIn("network blip", (Path(os.environ["TURTLEOS_HOUSE_DIR"]) / "error_triage.md").read_text())

    def test_a_bad_model_answer_still_surfaces_the_error(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        self._log("[y] New thing failed: x")

        async def garbage(prompt):
            return "not json"

        line = asyncio.run(et.run_nightly(self.logs, self.issues, garbage, now=datetime(2026, 9, 30, 5, 30)))
        self.assertIn("unjudged", line)

    def test_an_issue_the_model_invents_is_not_named(self):
        self._log("[x] Old thing failed: boom")
        self._run(NIGHT)
        self._log("[y] New thing failed: x")

        async def invents(prompt):
            return json.dumps({"items": [{"id": 0, "class": "c", "issue": "999-made-up.md", "needs_person": True, "why": "w"}]})

        line = asyncio.run(et.run_nightly(self.logs, self.issues, invents, now=datetime(2026, 9, 30, 5, 30)))
        self.assertIn("no issue yet", line)


if __name__ == "__main__":
    unittest.main()
