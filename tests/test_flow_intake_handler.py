import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TalkingEndsTheIntakeWaitTests(unittest.TestCase):
    """The first message is the skip, because the Skip button is gone.

    That button was the only exit from `awaiting_intake`, and eight call sites
    gate on it: `handle_eddy_first_message` returned *before* clearing it, so an
    eddy whose practitioner just started typing stayed frozen — no rename, no
    Turtle, no bar. Removing the button without this is how "ignoring is enough"
    becomes "ignoring breaks the eddy".
    """

    def _open_wait(self, mock_path, flow_id: str = "navigator") -> None:
        """Stage an open intake wait. The path mock must be armed before writing."""
        from eddy_spawn import write_awaiting_title

        path = Path(f"/tmp/test_intake_wait_{flow_id}.json")
        path.unlink(missing_ok=True)
        mock_path.return_value = path
        write_awaiting_title(77, 456, {"flow_id": flow_id, "awaiting_intake": True})

    def test_talking_clears_a_skippable_wait(self) -> None:
        from eddy_spawn import is_awaiting_flow_intake
        from flow_intake_handler import practitioner_message_ends_intake_wait

        with patch("eddy_spawn._awaiting_title_path") as mock_path:
            self._open_wait(mock_path)
            self.assertTrue(is_awaiting_flow_intake(77, 456))
            self.assertTrue(practitioner_message_ends_intake_wait(77, 456))
            self.assertFalse(is_awaiting_flow_intake(77, 456))

    def test_it_is_idempotent(self) -> None:
        """Three gates call this on the same message; only one should act."""
        from flow_intake_handler import practitioner_message_ends_intake_wait

        with patch("eddy_spawn._awaiting_title_path") as mock_path:
            self._open_wait(mock_path)
            self.assertTrue(practitioner_message_ends_intake_wait(77, 456))
            self.assertFalse(practitioner_message_ends_intake_wait(77, 456))

    def test_no_wait_open_is_not_reported_as_cleared(self) -> None:
        from flow_intake_handler import practitioner_message_ends_intake_wait

        with patch("eddy_spawn._awaiting_title_path") as mock_path:
            path = Path("/tmp/test_intake_wait_absent.json")
            path.unlink(missing_ok=True)
            mock_path.return_value = path
            self.assertFalse(practitioner_message_ends_intake_wait(77, 456))

    def test_a_required_intake_survives_talking(self) -> None:
        """Negative control — `skippable: false` is a step, not an offer.

        "Ignoring is enough" is a rule about offers. A flow that declares its
        intake mandatory is not making one, and this must not quietly relax it.
        """
        from eddy_spawn import is_awaiting_flow_intake
        from flow_intake_handler import practitioner_message_ends_intake_wait

        spec = MagicMock()
        spec.intake.skippable = False
        with patch("eddy_spawn._awaiting_title_path") as mock_path, patch(
            "flow_intake_handler.load_flow_spec", return_value=spec
        ):
            self._open_wait(mock_path, "required")
            self.assertFalse(practitioner_message_ends_intake_wait(77, 456))
            self.assertTrue(is_awaiting_flow_intake(77, 456))

    def test_the_orientation_view_offers_only_prepare(self) -> None:
        import flow_intake_handler as fih

        source = Path(fih.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Skip — I'll talk", source)
        self.assertNotIn("intake:skip", source)


if __name__ == "__main__":
    unittest.main()
