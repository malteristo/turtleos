"""Unit tests for versioned river update announcements."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from announcements import (
    RETURN_VISIT_ANNOUNCEMENT_ID,
    fanout_announcement,
    is_posted,
    list_announcement_channel_ids,
    list_announcement_ids,
    load_announcement,
    mark_posted,
)


class AnnouncementLoadTests(unittest.TestCase):
    def test_list_includes_nesrine_ready(self) -> None:
        ids = list_announcement_ids()
        self.assertIn(RETURN_VISIT_ANNOUNCEMENT_ID, ids)
        self.assertNotIn("_example", ids)

    def test_load_en_and_de(self) -> None:
        en = load_announcement(RETURN_VISIT_ANNOUNCEMENT_ID, "en")
        de = load_announcement(RETURN_VISIT_ANNOUNCEMENT_ID, "de")
        self.assertIsNotNone(en)
        self.assertIsNotNone(de)
        assert en is not None and de is not None
        self.assertEqual(en.announcement_id, RETURN_VISIT_ANNOUNCEMENT_ID)
        self.assertEqual(en.locale, "en")
        self.assertEqual(de.locale, "de")
        self.assertIn("Fresh Eyes", en.body)
        self.assertIn("Fresh Eyes", de.body)

    def test_missing_locale_falls_back_to_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "only-en.en.md").write_text(
                "---\nid: only-en\ntitle: Only EN\n---\n\n# Only EN\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("only-en", "de", announcements_dir=base)
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertEqual(spec.locale, "en")
            self.assertEqual(spec.title, "Only EN")


class AnnouncementStateTests(unittest.TestCase):
    def test_is_posted_mark_posted_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "announcements.json"
            with patch("announcements._state_path", return_value=state_file):
                self.assertFalse(is_posted(1, "a1"))
                mark_posted(1, "a1", message_id=99)
                self.assertTrue(is_posted(1, "a1"))
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self.assertEqual(data["posted"]["a1"]["message_id"], 99)


class AnnouncementIteratorTests(unittest.TestCase):
    @patch("mage.reload_mage_registry")
    @patch("mage.get_registry")
    def test_iterator_river_and_hosted_skips_archived_shared(
        self, mock_registry, _reload
    ) -> None:
        mock_registry.return_value = {
            "channels": {
                "111": {"type": "river"},
                "222": {"type": "hosted-river"},
                "333": {"type": "shared-river"},
                "444": {"type": "hosted-river", "archived": True},
                "555": {"type": "craft"},
            }
        }
        ids = list_announcement_channel_ids()
        self.assertEqual(ids, [111, 222])


class AnnouncementDryRunTests(unittest.TestCase):
    @patch("announcements.list_announcement_channel_ids", return_value=[42])
    @patch("announcements.locale_for_channel", return_value="en")
    @patch("announcements.is_posted", return_value=False)
    def test_dry_run_posts_nothing(self, _posted, _locale, _channels) -> None:
        with patch.dict(os.environ, {"RIVER_BOT_TOKEN": "fake-token"}):
            results = asyncio.run(
                fanout_announcement(
                    RETURN_VISIT_ANNOUNCEMENT_ID,
                    dry_run=True,
                )
            )
        self.assertEqual(results.get("dry-run"), [42])
        self.assertEqual(results.get("ok"), [])
        self.assertEqual(results.get("fail"), [])


if __name__ == "__main__":
    unittest.main()
