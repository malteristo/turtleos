"""Tests for practice artifact allowlist (TURTLE_SPEC §11.5)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import artifact_viewer as av


class TestArtifactAllowlist(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pd = self.tmp.name
        os.makedirs(os.path.join(self.pd, "sessions"), exist_ok=True)
        os.makedirs(os.path.join(self.pd, "proposals"), exist_ok=True)
        os.makedirs(os.path.join(self.pd, "thread-state"), exist_ok=True)
        open(os.path.join(self.pd, "sessions", "2026-06-29.md"), "w").close()
        open(os.path.join(self.pd, "proposals", "secret.md"), "w").close()
        open(os.path.join(self.pd, "bright.md"), "w").close()
        open(os.path.join(self.pd, "thread-state", "card.md"), "w").close()
        self.runtime = os.path.join(self.pd, "runtime")
        os.makedirs(os.path.join(self.runtime, "link-resonance"), exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_practitioner_can_read_sessions(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            self.assertTrue(av.is_artifact_readable("sessions/2026-06-29.md"))

    def test_practitioner_denied_proposals(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            self.assertFalse(av.is_artifact_readable("proposals/secret.md"))

    def test_operator_can_read_proposals(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="mage"):
            self.assertTrue(av.is_artifact_readable("proposals/secret.md"))

    def test_thread_state_denied(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            self.assertFalse(av.is_artifact_readable("thread-state/card.md"))

    def test_list_shelves_hides_proposals_for_practitioner(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            keys = [s.key for s, _ in av.list_shelves(mage_type="practitioner")]
            self.assertNotIn("proposals", keys)
            self.assertIn("sessions", keys)

    def test_list_shelf_artifacts_sessions(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            paths = av.list_shelf_artifacts("sessions", mage_type="practitioner")
            self.assertEqual(paths, ["sessions/2026-06-29.md"])

    def test_discoverability_unlocks_on_corpus(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"), patch(
            "artifact_viewer._discoverability_path",
            return_value=os.path.join(self.runtime, "artifact_discoverability.json"),
        ):
            self.assertTrue(av.artifacts_ui_eligible(mage_type="practitioner"))

    def test_checkpoint_hint(self) -> None:
        hint = av.checkpoint_artifact_hint(session_note="2026-06-29.md", flow_write=None)
        self.assertIn("!artifacts sessions", hint or "")


class TestSearchFormatting(unittest.TestCase):
    def test_format_includes_open_link_not_full_body(self) -> None:
        hits = [
            av.SearchHit("sessions/a.md", 1, "# Title"),
            av.SearchHit("sessions/a.md", 5, "some matching line here"),
        ]
        with patch("practice_io.PRACTICE_WEB_BASE", "http://127.0.0.1:8080"), patch(
            "practice_io.get_mage_key", return_value="kermit"
        ):
            text = av.format_search_results(hits, "match")
        self.assertIn("snippet", text.lower())
        self.assertIn("!read sessions/a.md", text)
        self.assertIn("http://127.0.0.1:8080/kermit/sessions/a.md", text)
        self.assertNotIn("# Title\n\nsome matching", text)


class TestCmdArtifacts(unittest.IsolatedAsyncioTestCase):
    async def test_menu_without_args(self) -> None:
        import cmd_practice_io as cpio

        message = MagicMock()
        message.reply = AsyncMock()
        with patch("cmd_practice_io.format_shelf_menu", return_value="**Practice artifacts**"):
            await cpio.cmd_artifacts(message, [])
        self.assertIn("Practice artifacts", message.reply.await_args[0][0])


if __name__ == "__main__":
    unittest.main()
