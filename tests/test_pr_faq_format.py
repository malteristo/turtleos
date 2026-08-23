"""A PR/FAQ instance missing a required heading is incomplete — the check must say so."""

from __future__ import annotations

import unittest
from pathlib import Path

import pr_faq

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pr_faq_incomplete.md"


class RequiredHeadingsTests(unittest.TestCase):
    def test_the_readme_names_every_required_heading(self) -> None:
        readme = (pr_faq.REPO / "docs" / "pr-faq" / "README.md").read_text(
            encoding="utf-8"
        )
        for name in pr_faq.REQUIRED_HEADINGS:
            self.assertIn(
                f"**{name}**",
                readme,
                f"README no longer names {name!r} — the check and the doc drifted",
            )

    def test_every_instance_has_every_required_heading(self) -> None:
        paths = pr_faq.instance_paths()
        self.assertTrue(paths, "docs/pr-faq/instances/ has no instances")
        for path in paths:
            missing = pr_faq.missing_headings(path.read_text(encoding="utf-8"))
            self.assertEqual(
                missing,
                [],
                f"{path.name} is missing headings: {missing}",
            )

    def test_a_deliberately_incomplete_instance_is_rejected(self) -> None:
        """Positive control: if this goes green, the checker stopped being able to fail."""
        text = FIXTURE.read_text(encoding="utf-8")
        missing = pr_faq.missing_headings(text)
        self.assertTrue(
            missing,
            "incomplete fixture was accepted — the check cannot fail",
        )
        self.assertIn("Solution", missing)
        self.assertIn("Risks", missing)


if __name__ == "__main__":
    unittest.main()
