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
    locale_for_channel,
    mark_posted,
)


class AnnouncementLoadTests(unittest.TestCase):
    def test_list_includes_partner_ready(self) -> None:
        ids = list_announcement_ids()
        self.assertIn(RETURN_VISIT_ANNOUNCEMENT_ID, ids)
        self.assertNotIn("_example", ids)

    def test_front_matter_id_survives_filename_rename(self) -> None:
        """Filename is a container. The shipped id lives in front matter.

        Positive control: a stem that is not the id still lists and loads
        under the front-matter id, and does not list the stem. An empty
        result here would mean the loader still treats the path as the id.
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "return-visit.en.md").write_text(
                "---\nid: shipped-ready\ntitle: Ready\n---\n\n# Ready\n\nBody.\n",
                encoding="utf-8",
            )
            (base / "return-visit.de.md").write_text(
                "---\nid: shipped-ready\ntitle: Bereit\n---\n\n# Bereit\n\nText.\n",
                encoding="utf-8",
            )
            ids = list_announcement_ids(announcements_dir=base)
            self.assertEqual(ids, ["shipped-ready"])
            self.assertNotIn("return-visit", ids)
            en = load_announcement("shipped-ready", "en", announcements_dir=base)
            de = load_announcement("shipped-ready", "de", announcements_dir=base)
            self.assertIsNotNone(en)
            self.assertIsNotNone(de)
            assert en is not None and de is not None
            self.assertEqual(en.announcement_id, "shipped-ready")
            self.assertEqual(de.locale, "de")
            self.assertIsNone(
                load_announcement("return-visit", "en", announcements_dir=base)
            )

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

    def test_audience_defaults_to_rivers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "plain.en.md").write_text(
                "---\nid: plain\ntitle: Plain\n---\n\n# Plain\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("plain", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience, "rivers")

    def test_audience_shared_parsed_from_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "fam.en.md").write_text(
                "---\nid: fam\ntitle: Fam\naudience: shared\n---\n\n# Fam\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("fam", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience, "shared")

    def test_unknown_audience_falls_back_to_rivers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "odd.en.md").write_text(
                "---\nid: odd\ntitle: Odd\naudience: everyone\n---\n\n# Odd\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("odd", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience, "rivers")

    def test_audience_named_spaces_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "fam.en.md").write_text(
                "---\nid: fam\ntitle: Fam\naudience: shared:family, band\n---\n\n# Fam\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("fam", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience, "shared")
            self.assertEqual(spec.audience_spaces, ("family", "band"))

    def test_bare_shared_audience_keeps_every_shared_room(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "fam.en.md").write_text(
                "---\nid: fam\ntitle: Fam\naudience: shared\n---\n\n# Fam\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("fam", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience_spaces, ())

    def test_unknown_kind_with_spaces_still_falls_back_to_rivers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "odd.en.md").write_text(
                "---\nid: odd\ntitle: Odd\naudience: everyone:family\n---\n\n# Odd\n\nBody.\n",
                encoding="utf-8",
            )
            spec = load_announcement("odd", "en", announcements_dir=base)
            assert spec is not None
            self.assertEqual(spec.audience, "rivers")
            self.assertEqual(spec.audience_spaces, ())


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
    _REGISTRY = {
        "channels": {
            "111": {"type": "river"},
            "222": {"type": "hosted-river"},
            "333": {"type": "shared-river"},
            "444": {"type": "hosted-river", "archived": True},
            "555": {"type": "craft"},
            "666": {"type": "shared-river", "archived": True},
        }
    }

    @patch("mage.reload_mage_registry")
    @patch("mage.get_registry")
    def test_iterator_river_and_hosted_skips_archived_shared(
        self, mock_registry, _reload
    ) -> None:
        mock_registry.return_value = self._REGISTRY
        ids = list_announcement_channel_ids()
        self.assertEqual(ids, [111, 222])

    @patch("mage.reload_mage_registry")
    @patch("mage.get_registry")
    def test_iterator_include_shared_adds_active_shared_rivers_only(
        self, mock_registry, _reload
    ) -> None:
        mock_registry.return_value = self._REGISTRY
        ids = list_announcement_channel_ids(include_shared=True)
        self.assertEqual(ids, [111, 222, 333])

    @patch("mage.reload_mage_registry")
    @patch("mage.get_registry")
    def test_iterator_named_spaces_narrow_shared_rivers(
        self, mock_registry, _reload
    ) -> None:
        mock_registry.return_value = {
            "channels": {
                "111": {"type": "river"},
                "333": {"type": "shared-river", "mage": "family"},
                "777": {"type": "shared-river", "mage": "sandbox"},
            }
        }
        ids = list_announcement_channel_ids(
            include_shared=True, shared_spaces=("family",)
        )
        self.assertEqual(ids, [111, 333])

    @patch("mage.reload_mage_registry")
    @patch("mage.get_registry")
    def test_iterator_named_spaces_leave_solo_rivers_untouched(
        self, mock_registry, _reload
    ) -> None:
        mock_registry.return_value = {
            "channels": {
                "111": {"type": "river"},
                "222": {"type": "hosted-river"},
                "777": {"type": "shared-river", "mage": "sandbox"},
            }
        }
        ids = list_announcement_channel_ids(
            include_shared=True, shared_spaces=("family",)
        )
        self.assertEqual(ids, [111, 222])


class AnnouncementLocaleTests(unittest.TestCase):
    @patch("mage.set_practice_context_for_channel")
    @patch("mage._get_channel_mage", return_value="family")
    @patch("mage.get_registry")
    def test_space_locale_resolves(self, mock_registry, _mage, _ctx) -> None:
        mock_registry.return_value = {
            "mages": {},
            "spaces": {"family": {"locale": "de"}},
        }
        self.assertEqual(locale_for_channel(333), "de")

    @patch("mage.set_practice_context_for_channel")
    @patch("mage._get_channel_mage", return_value="family")
    @patch("mage.get_registry")
    def test_space_without_locale_defaults_en(self, mock_registry, _mage, _ctx) -> None:
        mock_registry.return_value = {"mages": {}, "spaces": {"family": {}}}
        self.assertEqual(locale_for_channel(333), "en")

    @patch("mage.set_practice_context_for_channel")
    @patch("mage._get_channel_mage", return_value="guest")
    @patch("mage.get_registry")
    def test_mage_locale_still_resolves(self, mock_registry, _mage, _ctx) -> None:
        mock_registry.return_value = {
            "mages": {"guest": {"locale": "de"}},
            "spaces": {},
        }
        self.assertEqual(locale_for_channel(222), "de")


class AnnouncementFanoutAudienceTests(unittest.TestCase):
    @patch("announcements.list_announcement_channel_ids")
    @patch("announcements.locale_for_channel", return_value="en")
    @patch("announcements.is_posted", return_value=False)
    def test_fanout_shared_audience_includes_shared_rivers(
        self, _posted, _locale, mock_channels
    ) -> None:
        mock_channels.return_value = [111, 222, 333]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "fam.en.md").write_text(
                "---\nid: fam\ntitle: Fam\naudience: shared\n---\n\n# Fam\n\nBody.\n",
                encoding="utf-8",
            )
            with patch("announcements.ANNOUNCEMENTS_DIR", base):
                results = asyncio.run(fanout_announcement("fam", dry_run=True))
        mock_channels.assert_called_once_with(include_shared=True, shared_spaces=())
        self.assertEqual(results.get("dry-run"), [111, 222, 333])

    @patch("announcements.list_announcement_channel_ids")
    @patch("announcements.locale_for_channel", return_value="en")
    @patch("announcements.is_posted", return_value=False)
    def test_fanout_named_space_audience_targets_that_space(
        self, _posted, _locale, mock_channels
    ) -> None:
        mock_channels.return_value = [111, 222, 333]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "fam.en.md").write_text(
                "---\nid: fam\ntitle: Fam\naudience: shared:family\n---\n\n# Fam\n\nBody.\n",
                encoding="utf-8",
            )
            with patch("announcements.ANNOUNCEMENTS_DIR", base):
                asyncio.run(fanout_announcement("fam", dry_run=True))
        mock_channels.assert_called_once_with(
            include_shared=True, shared_spaces=("family",)
        )

    @patch("announcements.list_announcement_channel_ids")
    @patch("announcements.locale_for_channel", return_value="en")
    @patch("announcements.is_posted", return_value=False)
    def test_fanout_default_audience_excludes_shared(
        self, _posted, _locale, mock_channels
    ) -> None:
        mock_channels.return_value = [111, 222]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "plain.en.md").write_text(
                "---\nid: plain\ntitle: Plain\n---\n\n# Plain\n\nBody.\n",
                encoding="utf-8",
            )
            with patch("announcements.ANNOUNCEMENTS_DIR", base):
                results = asyncio.run(fanout_announcement("plain", dry_run=True))
        mock_channels.assert_called_once_with(include_shared=False, shared_spaces=())
        self.assertEqual(results.get("dry-run"), [111, 222])


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
