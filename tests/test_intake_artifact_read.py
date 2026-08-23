"""Tests for allowlisted artifact read HTTP route.

The handler reads `state.ARTIFACT_READ_TOKEN` at call time. Mini's nightly
loads `.env` before unittest, and that file has the token set; Forge does not.
A test that never patches the token therefore passes where production config
is absent and 403s where it is present — which is how 2026-08-15's ops report
went FAIL while the same file was green on this machine. Patch `state`, not
`intake_server`: the handler does `from state import ARTIFACT_READ_TOKEN`
inside the call.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from aiohttp import web

import intake_server


def _read_request(path: str, token: str | None = None) -> MagicMock:
    request = MagicMock()
    request.match_info = {"mage_key": "kermit", "path": path}
    query = {} if token is None else {"t": token}
    request.rel_url.query.get = lambda key, default="": query.get(key, default)
    return request


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
            with open(os.path.join(sessions, "note.md"), "w") as fh:
                fh.write("# hi")
            request = _read_request("sessions/note.md")
            with patch("state.ARTIFACT_READ_TOKEN", ""), patch(
                "mage.set_practice_context_for_mage_key", return_value=True
            ), patch("mage.get_mage_type", return_value="practitioner"), patch(
                "artifact_viewer.get_pd", return_value=tmp
            ), patch("artifact_viewer.get_runtime_dir", return_value=tmp), patch(
                "artifact_viewer.get_mage_type", return_value="practitioner"
            ):
                resp = await intake_server.handle_artifact_read(request)
            self.assertEqual(resp.status, 200)
            body = resp.body if isinstance(resp.body, (bytes, bytearray)) else resp.text
            if isinstance(body, str):
                body = body.encode()
            self.assertIn(b"# hi", body)

    async def test_denies_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "proposals"))
            with open(os.path.join(tmp, "proposals", "secret.md"), "w") as fh:
                fh.write("nope")
            request = _read_request("proposals/secret.md")
            with patch("state.ARTIFACT_READ_TOKEN", ""), patch(
                "mage.set_practice_context_for_mage_key", return_value=True
            ), patch("mage.get_mage_type", return_value="practitioner"), patch(
                "artifact_viewer.get_pd", return_value=tmp
            ), patch("artifact_viewer.get_runtime_dir", return_value=tmp), patch(
                "artifact_viewer.get_mage_type", return_value="practitioner"
            ):
                with self.assertRaises(web.HTTPForbidden) as ctx:
                    await intake_server.handle_artifact_read(request)
            self.assertIn("not available", ctx.exception.text)

    async def test_configured_token_without_query_is_forbidden(self) -> None:
        """Positive control: this is the Mini nightly failure shape."""
        request = _read_request("sessions/note.md")
        with patch("state.ARTIFACT_READ_TOKEN", "secret-token"):
            with self.assertRaises(web.HTTPForbidden) as ctx:
                await intake_server.handle_artifact_read(request)
        self.assertEqual(ctx.exception.text, "Artifact read token required")

    async def test_configured_token_with_matching_query_allows_tier1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sessions = os.path.join(tmp, "sessions")
            os.makedirs(sessions)
            with open(os.path.join(sessions, "note.md"), "w") as fh:
                fh.write("# hi")
            request = _read_request("sessions/note.md", token="secret-token")
            with patch("state.ARTIFACT_READ_TOKEN", "secret-token"), patch(
                "mage.set_practice_context_for_mage_key", return_value=True
            ), patch("mage.get_mage_type", return_value="practitioner"), patch(
                "artifact_viewer.get_pd", return_value=tmp
            ), patch("artifact_viewer.get_runtime_dir", return_value=tmp), patch(
                "artifact_viewer.get_mage_type", return_value="practitioner"
            ):
                resp = await intake_server.handle_artifact_read(request)
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
