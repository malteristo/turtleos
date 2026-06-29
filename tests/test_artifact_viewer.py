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
