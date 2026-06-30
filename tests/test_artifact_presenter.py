"""Tests for generative UI E1 artifact presenter."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_browse_shelf_includes_export_row_paths(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        pd = tmp.name
        os.makedirs(os.path.join(pd, "sessions"), exist_ok=True)
        runtime = os.path.join(pd, "runtime")
        os.makedirs(runtime, exist_ok=True)
        for name in ("a.md", "b.md", "c.md"):
            with open(os.path.join(pd, "sessions", name), "w") as fh:
                fh.write("# x")
        try:
            class CapturingEmbed:
                def __init__(self, **kwargs):
                    self.title = kwargs.get("title")
                    self.description = kwargs.get("description")

                def set_footer(self, **kwargs):
                    pass

            with patch("artifact_viewer.get_pd", return_value=pd), patch(
                "artifact_viewer.get_runtime_dir", return_value=runtime
            ), patch("artifact_viewer.get_mage_type", return_value="practitioner"), patch(
                "artifact_presenter.discord.Embed", CapturingEmbed
            ):
                surface = ap.compose_artifact_surface(
                    ap.ArtifactIntent.BROWSE_SHELF,
                    mage_type="practitioner",
                    shelf_key="sessions",
                )
            self.assertEqual(surface.template_id, "shelf_listing")
            self.assertEqual(len(surface.export_paths), 3)
            self.assertTrue(all(p.startswith("sessions/") for p in surface.export_paths))
        finally:
            tmp.cleanup()

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

    def test_artifact_read_url_uses_mage_key_not_default(self) -> None:
        with patch("practice_io.is_readable", return_value=True), patch(
            "practice_io.PRACTICE_WEB_BASE", "http://100.110.46.104:8080"
        ), patch("practice_io.ARTIFACT_READ_TOKEN", ""), patch(
            "practice_io.get_mage_key", return_value="kermit"
        ):
            url = ap._artifact_read_url("sessions/2026-06-30-3.md")
        self.assertEqual(
            url, "http://100.110.46.104:8080/kermit/sessions/2026-06-30-3.md"
        )

    def test_artifact_read_url_appends_token_when_configured(self) -> None:
        with patch("practice_io.is_readable", return_value=True), patch(
            "practice_io.PRACTICE_WEB_BASE", "https://practice.example.com"
        ), patch("practice_io.ARTIFACT_READ_TOKEN", "secret-token"), patch(
            "practice_io.get_mage_key", return_value="kermit"
        ):
            url = ap._artifact_read_url("sessions/a.md")
        self.assertEqual(
            url, "https://practice.example.com/kermit/sessions/a.md?t=secret-token"
        )

    def test_compose_export_handoff_is_compact(self) -> None:
        text = ap.compose_export_handoff("chronicle/surface.md")
        self.assertIn("surface.md", text)
        self.assertIn("⋯", text)
        self.assertIn("Download", text)
        self.assertLess(len(text), 120)

    def test_compose_artifact_preview_content_truncates_long_files(self) -> None:
        content = "line\n" * 500
        text = ap.compose_artifact_preview_content(content)
        assert text is not None
        self.assertIn("```md", text)
        self.assertIn("lines total", text)
        self.assertNotIn("**", text)


class TestPresentArtifactPreview(unittest.IsolatedAsyncioTestCase):
    @patch("artifact_presenter._apply_practice_context")
    @patch("artifact_presenter._load_artifact_content", return_value=("chronicle/surface.md", "# Surface\n"))
    @patch("artifact_presenter.build_artifact_open_view", return_value=MagicMock())
    @patch("bar_anchor.ensure_channel_bars", new_callable=AsyncMock)
    async def test_present_artifact_preview_replaces_embed(
        self, _ensure, _view, _load, _ctx
    ) -> None:
        interaction = MagicMock()
        interaction.channel = MagicMock()
        interaction.channel.id = 1
        interaction.response.edit_message = AsyncMock()
        interaction.client = MagicMock()

        await ap.present_artifact_preview_in_place(interaction, "chronicle/surface.md")

        interaction.response.edit_message.assert_awaited()
        kwargs = interaction.response.edit_message.await_args.kwargs
        self.assertIsNone(kwargs.get("embed"))
        self.assertEqual(kwargs["content"], "\u200b")
        self.assertIn("attachments", kwargs)
        _ensure.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
