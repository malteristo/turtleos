"""B-calibration instrument — the gate fails when the judge is wrong."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Invented facts only. A new fixture must extend this set — that is how a
# real person's words are kept out of the bank.
_INVENTED_FACTS = {"the garden shed lock", "the kettle is on the stove"}


def _mod():
    import scripts.shake_continuity as sc

    return sc


class JudgeTests(unittest.TestCase):
    def test_present_tense_stale_flags_b(self) -> None:
        sc = _mod()
        held = [{"fact": "the garden shed lock", "current": False, "last_true": "2026-07-16"}]
        self.assertTrue(sc.flags_b(held, "In motion: the garden shed lock."))

    def test_age_attached_clears_b(self) -> None:
        sc = _mod()
        held = [{"fact": "the garden shed lock", "current": False, "last_true": "2026-07-16"}]
        self.assertFalse(
            sc.flags_b(
                held,
                "Last noted the garden shed lock on 16 July (three weeks ago).",
            )
        )

    def test_iso_last_true_in_the_window_clears_b(self) -> None:
        sc = _mod()
        held = [{"fact": "the garden shed lock", "current": False, "last_true": "2026-07-16"}]
        self.assertFalse(sc.flags_b(held, "the garden shed lock (2026-07-16)"))

    def test_current_fact_in_present_tense_is_not_b(self) -> None:
        sc = _mod()
        held = [{"fact": "the kettle is on the stove", "current": True}]
        self.assertFalse(sc.flags_b(held, "The kettle is on the stove."))

    def test_unmentioned_stale_fact_is_not_b(self) -> None:
        sc = _mod()
        held = [{"fact": "the garden shed lock", "current": False, "last_true": "2026-07-16"}]
        self.assertFalse(sc.flags_b(held, "The kettle is on the stove."))


class BankedPairTests(unittest.TestCase):
    def test_banked_pair_classifies(self) -> None:
        sc = _mod()
        report = sc.build_report(sc.load_fixtures())
        self.assertEqual(report["status"], "pass", report["errors"])
        ids = {row["id"] for row in report["checks"]}
        self.assertEqual(ids, {"b-stale-present", "b-aged-carry"})

    def test_trivial_baselines_lose(self) -> None:
        sc = _mod()
        report = sc.build_report(sc.load_fixtures())
        self.assertFalse(report["baselines"]["always_pass"]["ok"])
        self.assertFalse(report["baselines"]["always_flag_b"]["ok"])

    def test_inverted_judge_fails_the_gate(self) -> None:
        sc = _mod()
        planted = sc.build_report(sc.load_fixtures(), invert=True)
        self.assertEqual(planted["status"], "fail")
        self.assertTrue(planted["errors"])

    def test_self_test_proves_the_gate_can_fail(self) -> None:
        sc = _mod()
        self.assertEqual(sc.self_test(), 0)

    def test_fixtures_use_only_invented_facts(self) -> None:
        for path in (REPO / "scripts" / "fixtures" / "continuity").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            facts = {item["fact"] for item in data.get("held") or []}
            extra = facts - _INVENTED_FACTS
            self.assertFalse(extra, f"{path.name} is not the invented bank: {extra}")

    def test_main_writes_a_verdict_the_report_can_read(self) -> None:
        sc = _mod()
        self.assertEqual(sc.main([]), 0)
        raw = json.loads(sc.VERDICT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["status"], "pass")
        self.assertEqual(raw["instrument"], "B-calibration")
        self.assertNotIn("eval", raw["instrument"].lower())


if __name__ == "__main__":
    unittest.main()
