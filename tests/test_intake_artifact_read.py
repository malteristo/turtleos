"""Tests for allowlisted artifact read HTTP route."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from aiohttp import web

import intake_server


class TestArtifactReadRoute(unittest.IsolatedAsyncioTestCase):
    async def test_route_registered(self) -> None:
        app = intake_server.create_intake_app()
        paths = []
        for route in app.router.routes():
            info = route.get_info()
            if "path" in info:
                paths.append(info["path"])
            elif "formatter" in info:
                paths.append(str(info["formatter"]))
        joined = " ".join(paths)
        self.assertIn("read", joined)

    async def test_allows_tier1_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = os.path.join(tmp, "sessions")
            os.makedirs(sessions)
            open(os.path.join(sessions, "note.md"), "w").write("# hi")
            request = MagicMock()
            request.match_info = {"mage_key": "kermit", "path": "sessions/note.md"}
            with patch("mage.set_practice_context_for_mage_key", return_value=True), patch(
                "mage.get_mage_type", return_value="practitioner"
            ), patch("artifact_viewer.get_pd", return_value=tmp), patch(
                "artifact_viewer.get_runtime_dir", return_value=tmp
            ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
                resp = await intake_server.handle_artifact_read(request)
            self.assertEqual(resp.status, 200)
            body = resp.body if isinstance(resp.body, (bytes, bytearray)) else resp.text
            if isinstance(body, str):
                body = body.encode()
            self.assertIn(b"# hi", body)

    async def test_denies_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "proposals"))
            open(os.path.join(tmp, "proposals", "secret.md"), "w").write("nope")
            request = MagicMock()
            request.match_info = {"mage_key": "kermit", "path": "proposals/secret.md"}
            with patch("mage.set_practice_context_for_mage_key", return_value=True), patch(
                "mage.get_mage_type", return_value="practitioner"
            ), patch("artifact_viewer.get_pd", return_value=tmp), patch(
                "artifact_viewer.get_runtime_dir", return_value=tmp
            ), patch("artifact_viewer.get_mage_type", return_value="practitioner"):
                with self.assertRaises(web.HTTPForbidden):
                    await intake_server.handle_artifact_read(request)


if __name__ == "__main__":
    unittest.main()
