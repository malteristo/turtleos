"""Space-awareness wrappers return rows on a populated registry, not an empty list."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import space_survey
import tos_tools


def _registry() -> dict:
    return {
        "mages": {
            "operator": {"address": "Practitioner", "practice_dir": "/tmp/k"},
        },
        "spaces": {
            "family": {"members": ["ana", "ben"], "practice_dir": "/tmp/f"},
        },
        "channels": {
            "111": {
                "mage": "operator",
                "type": "craft",
                "attunement": "craft",
                "description": "Craft Turtle builder surface",
            },
            "222": {
                "mage": "family",
                "type": "shared-river",
                "description": "Family river",
            },
        },
    }


def _threads() -> dict:
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=3)).isoformat()
    old = (now - timedelta(days=20)).isoformat()
    return {
        "threads": {
            "501": {
                "name": "identity",
                "parent_channel": "craft-turtle",
                "last_activity": fresh,
                "message_count": 12,
                "harvest_status": "pending",
            },
            "502": {
                "name": "architecture",
                "parent_channel": "craft-turtle",
                "last_activity": old,
                "message_count": 40,
                "harvest_status": "pending",
            },
            "503": {
                "name": "done topic",
                "parent_channel": "family",
                "last_activity": fresh,
                "message_count": 2,
                "harvest_status": "cooled",
            },
        }
    }


class SurveySpaceTests(unittest.TestCase):
    def test_populated_registry_is_not_empty(self) -> None:
        rows = space_survey.survey_space(_registry())
        self.assertEqual(len(rows), 2)
        ids = {r["channel_id"] for r in rows}
        self.assertEqual(ids, {"111", "222"})
        craft = next(r for r in rows if r["channel_id"] == "111")
        self.assertEqual(craft["type"], "craft")
        self.assertEqual(craft["member_count"], 1)
        family = next(r for r in rows if r["channel_id"] == "222")
        self.assertEqual(family["member_count"], 2)

    def test_empty_registry_returns_empty(self) -> None:
        """Honest empty, not a disguised always-empty wrapper."""
        self.assertEqual(space_survey.survey_space({"channels": {}}), [])

    def test_a_wrapper_that_returns_empty_on_this_fixture_would_fail(self) -> None:
        rows = space_survey.survey_space(_registry())
        with self.assertRaises(AssertionError):
            self.assertEqual(rows, [])


class SurveyEddiesTests(unittest.TestCase):
    def test_populated_registry_is_not_empty(self) -> None:
        with patch("thread_registry.load_registry", return_value=_threads()):
            rows = space_survey.survey_eddies()
        self.assertEqual(len(rows), 3)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["501"]["status"], "active")
        self.assertEqual(by_id["502"]["status"], "quiet")
        self.assertEqual(by_id["503"]["status"], "cooled")

    def test_status_and_parent_filters(self) -> None:
        with patch("thread_registry.load_registry", return_value=_threads()):
            active = space_survey.survey_eddies(status="active")
            craft = space_survey.survey_eddies(channel_id="craft-turtle")
        self.assertEqual({r["id"] for r in active}, {"501"})
        self.assertEqual({r["id"] for r in craft}, {"501", "502"})

    def test_empty_registry_returns_empty(self) -> None:
        with patch("thread_registry.load_registry", return_value={"threads": {}}):
            self.assertEqual(space_survey.survey_eddies(), [])


class ToolDispatchTests(unittest.TestCase):
    def test_survey_tools_are_offered_and_dispatched(self) -> None:
        names = {
            (t.get("function") or {}).get("name") for t in tos_tools.TOS_TOOLS
        }
        self.assertIn("survey_space", names)
        self.assertIn("survey_eddies", names)
        with patch.object(tos_tools, "get_registry", return_value=_registry()):
            text = tos_tools._execute_tos_tool_raw("survey_space", {})
        self.assertIn("111", text)
        self.assertNotEqual(text, "No registered channels.")
        parsed = json.loads(text)
        self.assertEqual(len(parsed), 2)


if __name__ == "__main__":
    unittest.main()
