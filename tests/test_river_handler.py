import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Pure-function tests should not require discord.py installed.
sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from river_handler import (
    finalize_parent_river_acts,
    parse_river_output,
    list_installed_flows,
)


class RiverHandlerTests(unittest.TestCase):
    def test_parse_valid_json(self) -> None:
        raw = '{"acts": [{"type": "acknowledge", "emoji": "👋"}, {"type": "offer_eddy", "title": "hi", "button_label": "Materialize eddy"}]}'
        acts, reason = parse_river_output(raw)
        self.assertIsNone(reason)
        self.assertEqual(len(acts), 2)
        self.assertEqual(acts[0]["type"], "acknowledge")

    def test_parse_rejects_prose(self) -> None:
        acts, reason = parse_river_output("Hello! I can help you with that.")
        self.assertEqual(acts, [])
        self.assertIn("prose", reason or "")

    def test_parse_strips_markdown_fence(self) -> None:
        raw = '```json\n{"acts": [{"type": "offer_eddy", "title": "x", "button_label": "Go"}]}\n```'
        acts, reason = parse_river_output(raw)
        self.assertIsNone(reason)
        self.assertEqual(acts[0]["title"], "x")

    def test_finalize_parent_river_acts_strips_offer_eddy(self) -> None:
        acts = [
            {"type": "acknowledge", "emoji": "👋"},
            {"type": "offer_eddy", "title": "x", "button_label": "Go"},
            {"type": "offer_flow_menu", "flows": ["Shelter"]},
        ]
        out = finalize_parent_river_acts(acts)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "offer_flow_menu")

    def test_finalize_parent_river_acts_strips_acknowledge(self) -> None:
        acts = [{"type": "acknowledge", "emoji": "👋"}]
        out = finalize_parent_river_acts(acts)
        self.assertEqual(out, [])

    def test_finalize_parent_river_acts_default_empty(self) -> None:
        out = finalize_parent_river_acts([])
        self.assertEqual(out, [])

    def test_classify_pipeline_no_offer_eddy(self) -> None:
        acts = [{"type": "acknowledge", "emoji": "👋"}]
        out = finalize_parent_river_acts(acts)
        self.assertEqual(out, [])
        self.assertFalse(any(a.get("type") == "offer_eddy" for a in out))

    def test_list_installed_flows_defaults(self) -> None:
        flows = list_installed_flows("/nonexistent/practice")
        self.assertIn("Shelter", flows)


class AwaitingTitleTests(unittest.TestCase):
    def test_write_pop_awaiting_title(self) -> None:
        from eddy_spawn import is_awaiting_title, pop_awaiting_title, write_awaiting_title
        from unittest.mock import patch

        with patch("eddy_spawn._awaiting_title_path") as mock_path:
            tmp = Path("/tmp/test_awaiting_title.json")
            tmp.unlink(missing_ok=True)
            mock_path.return_value = tmp
            write_awaiting_title(99, 456, {"flow_id": "shelter"})
            self.assertTrue(is_awaiting_title(99, 456))
            out = pop_awaiting_title(99, 456)
            self.assertEqual(out["flow_id"], "shelter")
            self.assertFalse(is_awaiting_title(99, 456))


class PendingEddyTests(unittest.TestCase):
    def test_write_and_pop_pending(self) -> None:
        from eddy_spawn import pop_pending_native_eddy, write_pending_native_eddy
        from unittest.mock import patch

        with patch("eddy_spawn._pending_native_eddy_path") as mock_path:
            tmp = Path("/tmp/test_pending_eddy.json")
            tmp.unlink(missing_ok=True)
            mock_path.return_value = tmp
            payload = {"topic": "shake", "eddy_type": "standard", "model": "local"}
            write_pending_native_eddy(123, 456, payload)
            self.assertTrue(tmp.exists())
            out = pop_pending_native_eddy(123, 456)
            self.assertEqual(out["topic"], "shake")
            self.assertFalse(tmp.exists())
            self.assertIsNone(pop_pending_native_eddy(123, 456))


class NativeRiverEddyRoutingTests(unittest.TestCase):
    def test_new_eddy_name_not_intake_when_awaiting_title(self) -> None:
        from eddy_spawn import is_intake_thread, is_native_river_eddy, write_awaiting_title
        from unittest.mock import MagicMock, patch

        thread = MagicMock()
        thread.name = "new eddy"
        thread.id = 555
        thread.parent_id = 999

        with patch("eddy_spawn._awaiting_title_path") as mock_path:
            tmp = Path("/tmp/test_native_eddy_routing.json")
            tmp.unlink(missing_ok=True)
            mock_path.return_value = tmp
            write_awaiting_title(555, 999)
            self.assertTrue(is_native_river_eddy(thread))
            self.assertFalse(is_intake_thread(thread))
            tmp.unlink(missing_ok=True)

    def test_new_eddy_name_is_intake_without_native_marker(self) -> None:
        from eddy_spawn import is_intake_thread
        from unittest.mock import MagicMock

        thread = MagicMock()
        thread.name = "new eddy"
        thread.id = 556
        thread.parent_id = 999
        self.assertTrue(is_intake_thread(thread))


if __name__ == "__main__":
    unittest.main()
