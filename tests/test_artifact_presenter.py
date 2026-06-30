"""Tests for generative UI E1 artifact presenter."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import artifact_presenter as ap
import artifact_viewer as av


class TestCheckpointOpenPath(unittest.TestCase):
    def test_session_note(self) -> None:
        self.assertEqual(
            ap.checkpoint_open_path(session_note="2026-06-29.md", flow_write=None),
            "sessions/2026-06-29.md",
        )

    def test_flow_write(self) -> None:
        self.assertEqual(
            ap.checkpoint_open_path(session_note=None, flow_write="state/notes/nav.md"),
            "state/notes/nav.md",
        )


class TestListRecentArtifacts(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pd = self.tmp.name
        os.makedirs(os.path.join(self.pd, "sessions"), exist_ok=True)
        os.makedirs(os.path.join(self.pd, "state", "notes"), exist_ok=True)
        self.runtime = os.path.join(self.pd, "runtime")
        os.makedirs(self.runtime, exist_ok=True)
        old = os.path.join(self.pd, "sessions", "old.md")
        new = os.path.join(self.pd, "sessions", "new.md")
        note = os.path.join(self.pd, "state", "notes", "flow.md")
        for path in (old, new, note):
            with open(path, "w") as fh:
                fh.write("# x")
        now = time.time()
        os.utime(old, (now - 86400, now - 86400))
        os.utime(new, (now, now))
        os.utime(note, (now - 3600, now - 3600))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_recent_sorted_by_mtime(self) -> None:
        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
            recent = av.list_recent_artifacts(limit=3, mage_type="practitioner")
        self.assertEqual([r.path for r in recent], [
            "sessions/new.md",
            "state/notes/flow.md",
            "sessions/old.md",
        ])


class TestComposeArtifactSurface(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pd = self.tmp.name
        os.makedirs(os.path.join(self.pd, "sessions"), exist_ok=True)
        with open(os.path.join(self.pd, "sessions", "2026-06-29.md"), "w") as fh:
            fh.write("# hi")
        self.runtime = os.path.join(self.pd, "runtime")
        os.makedirs(self.runtime, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_browse_default_recent(self) -> None:
        class CapturingEmbed:
            def __init__(self, **kwargs):
                self.title = kwargs.get("title")
                self.description = kwargs.get("description")

            def set_footer(self, **kwargs):
                pass

        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="practitioner"), patch(
            "artifact_presenter.discord.Embed", CapturingEmbed
        ):
            surface = ap.compose_artifact_surface(
                ap.ArtifactIntent.BROWSE_DEFAULT, mage_type="practitioner"
            )
        self.assertEqual(surface.template_id, "recent_cross_shelf")
        assert surface.embed is not None
        self.assertEqual(surface.embed.title, "Recent")
        self.assertTrue(surface.open_actions)

    def test_browse_all_operator_menu(self) -> None:
        class CapturingEmbed:
            def __init__(self, **kwargs):
                self.title = kwargs.get("title")
                self.description = kwargs.get("description")

        with patch("artifact_viewer.get_pd", return_value=self.pd), patch(
            "artifact_viewer.get_runtime_dir", return_value=self.runtime
        ), patch("artifact_viewer.get_mage_type", return_value="mage"), patch(
            "artifact_presenter.discord.Embed", CapturingEmbed
        ):
            surface = ap.compose_artifact_surface(
                ap.ArtifactIntent.BROWSE_ALL, mage_type="mage"
            )
        self.assertEqual(surface.template_id, "operator_catalog")
        assert surface.embed is not None
        self.assertIn("!artifacts sessions", surface.embed.description or "")


if __name__ == "__main__":
    unittest.main()
