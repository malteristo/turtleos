"""The acceptance catalogue and the shake report must describe the same system.

`docs/acceptance/README.md` defines the scenario ids; `scripts/shake_report.py`
maps verdict artifacts to the ids they gate and names the ids that are Mage
gates. Nothing joined the three, so the catalogue could go stale silently — and
did: the artifact-viewer and pinned-home-eddy shakes shipped 2026-08-06, ran in
the nightly gate, and were mapped to *no scenario at all*, while the catalogue
had no section for either feature for 41 commits. The gate was green and the
catalogue was wrong, which is the worst combination available.

This is `docs/development.md` §12 applied to a document instead of a feature:
can it fail in week three? A prose catalogue whose only cadence is a sentence
asking someone to remember cannot. A join that fails the suite can.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = REPO_ROOT / "docs" / "acceptance" / "README.md"
SHAKE_REPORT = REPO_ROOT / "scripts" / "shake_report.py"

ROW_ID_RE = re.compile(r"^\|\s*\**\s*([A-Z]\d+[a-z]?)\s*\**\s*\|")

# Scenarios the catalogue defines that no shake gates and that are not Mage-gate
# rows in `shake_report.MAGE_UX_SCENARIOS` — each with the reason. This is the
# honest inventory of what nothing automatic confirms. It should shrink, and it
# can only grow by someone deliberately writing a reason here.
UNVERIFIED: dict[str, str] = {
    "F1": "retired 2026-06-20 — Shelter removed from the ship set",
    "F2": "retired 2026-06-20 — Shelter removed from the ship set",
    "F3": "retired 2026-06-20 — superseded by J2/J3",
    "J4": "no shake — mid-conversation lens load from thread history",
    "T3": "live-only — a reminder arriving on its lead day cannot be shaken offline",
    "O1": "shake_hosted_river.py runs but writes no verdict artifact yet",
    "O2": "shake_hosted_river.py runs but writes no verdict artifact yet",
    "S2": "blocked on shared-river",
    "S3": "blocked on shared-river",
    "S4": "blocked on shared-river",
    "S5": "blocked on shared-river",
    "S6": "blocked on shared-river",
    "X3": "asserted by test_link_read, not by a shake verdict",
    "X4": "asserted by test_eddy_lifecycle_bar, not by a shake verdict",
}


def _module_dict(name: str) -> dict:
    """Read a module-level dict literal from shake_report without importing it."""
    tree = ast.parse(SHAKE_REPORT.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {SHAKE_REPORT.name}")


def catalogue_ids() -> set[str]:
    ids = set()
    for line in CATALOGUE.read_text(encoding="utf-8").splitlines():
        match = ROW_ID_RE.match(line)
        if match:
            ids.add(match.group(1))
    return ids


def gated_by_shake() -> dict[str, list[str]]:
    """script (or artifact filename) -> scenario ids it gates."""
    out = {}
    for filename, meta in _module_dict("SHAKE_ARTIFACTS").items():
        label = meta.get("script") or filename
        out[label] = list(meta.get("spirit_scenarios") or [])
    return out


def mage_gate_ids() -> set[str]:
    return set(_module_dict("MAGE_UX_SCENARIOS"))


def all_gated_ids() -> set[str]:
    return {sid for ids in gated_by_shake().values() for sid in ids}


class ParsingControlTests(unittest.TestCase):
    """Positive controls. A silent parse failure would pass every join below."""

    def test_the_catalogue_parses_into_scenarios(self) -> None:
        ids = catalogue_ids()
        self.assertGreater(len(ids), 20)
        for known in ("H1", "R4", "D2b", "T1", "X1", "A1", "P1"):
            self.assertIn(known, ids)

    def test_the_report_parses_into_claims(self) -> None:
        claims = gated_by_shake()
        self.assertGreater(len(claims), 5)
        self.assertIn("R1", all_gated_ids())
        self.assertGreater(len(mage_gate_ids()), 3)

    def test_a_missing_map_is_an_error_not_an_empty_set(self) -> None:
        with self.assertRaises(AssertionError):
            _module_dict("NO_SUCH_MAP")


class CatalogueJoinTests(unittest.TestCase):
    def test_every_gated_scenario_is_defined(self) -> None:
        defined = catalogue_ids()
        undefined = {
            script: sorted(set(ids) - defined)
            for script, ids in gated_by_shake().items()
            if set(ids) - defined
        }
        self.assertEqual(
            undefined,
            {},
            "a shake gates a scenario the catalogue never defines — define it in "
            f"docs/acceptance/README.md: {undefined}",
        )

    def test_every_mage_gate_scenario_is_defined(self) -> None:
        unknown = sorted(mage_gate_ids() - catalogue_ids())
        self.assertEqual(
            unknown,
            [],
            f"MAGE_UX_SCENARIOS names scenarios the catalogue does not define: {unknown}",
        )

    def test_every_defined_scenario_is_gated_or_declared(self) -> None:
        orphans = sorted(
            catalogue_ids() - all_gated_ids() - mage_gate_ids() - set(UNVERIFIED)
        )
        self.assertEqual(
            orphans,
            [],
            "these scenarios are defined but nothing verifies them. Write a shake, "
            "add them to shake_report.MAGE_UX_SCENARIOS, or add each to UNVERIFIED "
            f"in this file with the reason a human must confirm it: {orphans}",
        )

    def test_no_shake_artifact_gates_nothing(self) -> None:
        """A verdict mapped to no scenario is a green light for nothing.

        The exact state of shake-artifacts and shake-home-plans between
        2026-08-06 and 2026-08-14.
        """
        empty = sorted(script for script, ids in gated_by_shake().items() if not ids)
        self.assertEqual(
            empty,
            [],
            "these shakes run in the nightly gate but map to no acceptance "
            f"scenario, so their green means nothing nameable: {empty}",
        )


class UnverifiedInventoryTests(unittest.TestCase):
    def test_no_stale_entries(self) -> None:
        stale = sorted(set(UNVERIFIED) & (all_gated_ids() | mage_gate_ids()))
        self.assertEqual(
            stale,
            [],
            f"these are covered now — drop them from UNVERIFIED: {stale}",
        )

    def test_no_unknown_scenarios(self) -> None:
        unknown = sorted(set(UNVERIFIED) - catalogue_ids())
        self.assertEqual(
            unknown,
            [],
            f"UNVERIFIED names scenarios the catalogue does not define: {unknown}",
        )

    def test_every_entry_gives_a_reason(self) -> None:
        for sid, reason in UNVERIFIED.items():
            self.assertGreater(len(reason.strip()), 10, f"{sid} needs a real reason")


if __name__ == "__main__":
    unittest.main()
