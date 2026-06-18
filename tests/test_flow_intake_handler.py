import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from flow_intake_handler import (
    _intake_summary_message_id,
    intake_topic_seed,
    should_rename_thread_from_intake,
)


class FlowIntakeHandlerTests(unittest.TestCase):
    def test_intake_summary_message_id_parsing(self) -> None:
        self.assertIsNone(_intake_summary_message_id(None))
        self.assertIsNone(_intake_summary_message_id({}))
        self.assertIsNone(_intake_summary_message_id({"intake_summary_message_id": "nope"}))
        self.assertIsNone(_intake_summary_message_id({"intake_summary_message_id": 0}))
        self.assertEqual(
            _intake_summary_message_id({"intake_summary_message_id": 123456789}),
            123456789,
        )
        self.assertEqual(
            _intake_summary_message_id({"intake_summary_message_id": "987654321"}),
            987654321,
        )


class FlowIntakeRenameTests(unittest.TestCase):
    def test_intake_topic_seed_both_fields(self) -> None:
        seed = intake_topic_seed(
            {"intention": "Ship turtleOS", "territory": "Install friction"}
        )
        self.assertIn("Ship turtleOS", seed)
        self.assertIn("Install friction", seed)

    def test_intake_topic_seed_intention_only(self) -> None:
        self.assertEqual(intake_topic_seed({"intention": "Focus week"}), "Focus week")

    def test_should_rename_from_flow_title(self) -> None:
        self.assertTrue(should_rename_thread_from_intake("Navigator", "Navigator"))
        self.assertTrue(should_rename_thread_from_intake("new eddy", "Navigator"))
        self.assertFalse(
            should_rename_thread_from_intake("chiang machine consciousness", "Navigator")
        )


if __name__ == "__main__":
    unittest.main()
