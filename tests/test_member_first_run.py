"""Member first-run is one action. The hosted welcome is the positive control."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from member_first_run import (
    FIRST_RUN_MAX_CHARS,
    FIRST_RUN_PATH,
    REQUIRED_PHRASE,
    first_run_problems,
    first_run_text,
)


HOSTED_WELCOME = (
    Path(__file__).resolve().parents[1]
    / "template"
    / "practitioner"
    / "onboarding_en.md"
)


class MemberFirstRunTests(unittest.TestCase):
    def test_shipped_copy_meets_dest(self) -> None:
        text = first_run_text()
        self.assertEqual(first_run_problems(text), [])
        self.assertIn(REQUIRED_PHRASE, text.lower())
        self.assertLessEqual(len(text), FIRST_RUN_MAX_CHARS)

    def test_hosted_welcome_fails_as_first_run(self) -> None:
        """Positive control: yesterday's manual must not pass criterion 3."""
        hosted = HOSTED_WELCOME.read_text(encoding="utf-8")
        problems = first_run_problems(hosted)
        self.assertTrue(problems, "hosted welcome passed — the guard cannot fail")
        self.assertTrue(
            any("too long" in p or "teaches" in p for p in problems),
            problems,
        )

    def test_empty_and_bound_fail(self) -> None:
        self.assertIn("empty", first_run_problems(""))
        self.assertTrue(first_run_problems("Bound. Welcome to your river."))

    def test_file_is_the_source(self) -> None:
        self.assertTrue(FIRST_RUN_PATH.is_file())
        self.assertEqual(
            first_run_text(),
            FIRST_RUN_PATH.read_text(encoding="utf-8").strip(),
        )


class PostMemberFirstRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_first_run(self) -> None:
        from member_first_run import post_member_first_run

        channel = MagicMock()
        channel.id = 99
        channel.send = AsyncMock(return_value=MagicMock(id=7, pin=AsyncMock()))

        msg = await post_member_first_run(channel)

        self.assertIsNotNone(msg)
        sent = channel.send.await_args.args[0]
        self.assertEqual(sent, first_run_text())
        self.assertNotIn("Bound", sent)


class MemberPathTeachingTests(unittest.TestCase):
    """Criterion 4: the administrator's only act was the Discord invite.

    Hosted-guest docs may still teach `!admin invite`. Member-path docs may not.
    """

    MEMBER_PATH = (
        "README.md",
        "docs/ux/faq.md",
        "docs/ux/onboarding.md",
        "docs/install/SKILL.md",
        "template/practitioner/first_run_en.md",
    )
    HOSTED_DOOR = "docs/ux/hosted-tester-program.md"

    def test_member_path_does_not_teach_admin_invite(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        leftover = []
        for rel in self.MEMBER_PATH:
            text = (repo / rel).read_text(encoding="utf-8")
            if "!admin invite" in text:
                leftover.append(rel)
        self.assertEqual(leftover, [], leftover)

    def test_hosted_door_still_teaches_invite(self) -> None:
        """Positive control: the scan is not 'invite nowhere'."""
        repo = Path(__file__).resolve().parents[1]
        hosted = (repo / self.HOSTED_DOOR).read_text(encoding="utf-8")
        self.assertIn("!admin invite", hosted)


class InstallModelNameTests(unittest.TestCase):
    INSTALL_PATH = (
        "README.md",
        "docs/install/SKILL.md",
        "docs/ux/faq.md",
        "docs/ux/onboarding.md",
        "docs/ux/install-journey.md",
    )

    def test_install_docs_name_the_live_turtle_default(self) -> None:
        from core.models import TURTLE_MODEL

        repo = Path(__file__).resolve().parents[1]
        for rel in ("README.md", "docs/install/SKILL.md"):
            text = (repo / rel).read_text(encoding="utf-8")
            self.assertIn(TURTLE_MODEL, text, rel)
            self.assertNotIn("gemma3:27b", text, rel)

    def test_install_docs_name_the_lighter_turtle(self) -> None:
        from core.models import LIGHTER_TURTLE_MODEL, TURTLE_MODEL

        self.assertEqual(LIGHTER_TURTLE_MODEL, "gemma4:12b")
        self.assertNotEqual(LIGHTER_TURTLE_MODEL, TURTLE_MODEL)

        repo = Path(__file__).resolve().parents[1]
        missing = []
        for rel in self.INSTALL_PATH:
            text = (repo / rel).read_text(encoding="utf-8")
            if LIGHTER_TURTLE_MODEL not in text:
                missing.append(rel)
        self.assertEqual(missing, [], missing)

    def test_lighter_alias_is_first_class(self) -> None:
        from core.models import KNOWN_MODELS, LIGHTER_TURTLE_MODEL

        self.assertEqual(KNOWN_MODELS["gemma-12b"], LIGHTER_TURTLE_MODEL)

    def test_old_docs_that_only_named_thirty_one_would_fail(self) -> None:
        """Positive control: a 31B-only page is not a Lighter path."""
        from core.models import LIGHTER_TURTLE_MODEL, TURTLE_MODEL

        stale = f"ollama pull {TURTLE_MODEL}\n"
        self.assertNotIn(LIGHTER_TURTLE_MODEL, stale)


if __name__ == "__main__":
    unittest.main()
