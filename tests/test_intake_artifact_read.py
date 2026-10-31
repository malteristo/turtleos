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

    async def test_unset_token_refuses_tier1(self) -> None:
        """Positive control: an empty token used to return 200. That was the open door."""
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
                with self.assertRaises(web.HTTPForbidden) as ctx:
                    await intake_server.handle_artifact_read(request)
            self.assertEqual(ctx.exception.text, "Artifact read token required")

    async def test_wrong_token_is_forbidden(self) -> None:
        request = _read_request("sessions/note.md", token="secret-tokex")
        with patch("state.ARTIFACT_READ_TOKEN", "secret-token"):
            with self.assertRaises(web.HTTPForbidden) as ctx:
                await intake_server.handle_artifact_read(request)
        self.assertEqual(ctx.exception.text, "Artifact read token required")

    async def test_denies_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "proposals"))
            with open(os.path.join(tmp, "proposals", "secret.md"), "w") as fh:
                fh.write("nope")
            request = _read_request("proposals/secret.md", token="secret-token")
            with patch("state.ARTIFACT_READ_TOKEN", "secret-token"), patch(
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


class TestArtifactPage(unittest.IsolatedAsyncioTestCase):
    def test_todays_shell_is_not_the_note(self) -> None:
        """Positive control: the shell contains words, and the check still fails."""
        shell_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "practice_viewer",
            "index.html",
        )
        with open(shell_path, encoding="utf-8") as fh:
            shell = fh.read()
        from artifact_viewer import note_is_readable_without_script

        self.assertIn("Loading", shell)
        self.assertIn("cdn.jsdelivr.net", shell)
        self.assertFalse(note_is_readable_without_script(shell, "Loading"))

    async def test_the_first_response_is_the_note(self) -> None:
        from artifact_viewer import note_is_readable_without_script

        phrase = "the sparks eddy kept its title"
        with tempfile.TemporaryDirectory() as tmp:
            eddies = os.path.join(tmp, "story", "eddies")
            os.makedirs(eddies)
            with open(os.path.join(eddies, "7-sparks-as-intentions.md"), "w", encoding="utf-8") as fh:
                fh.write(f"title: sparks as intentions\n\n{phrase}\n")
            request = _read_request("story/eddies/7-new-eddy.md", token="secret-token")
            with patch("state.ARTIFACT_READ_TOKEN", "secret-token"), patch(
                "mage.set_practice_context_for_mage_key", return_value=True
            ), patch("mage.get_mage_type", return_value="practitioner"), patch(
                "artifact_viewer.get_pd", return_value=tmp
            ), patch("artifact_viewer.get_runtime_dir", return_value=tmp), patch(
                "artifact_viewer.get_mage_type", return_value="practitioner"
            ):
                resp = await intake_server.handle_artifact_page(request)
        page = resp.text
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.content_type, "text/html")
        self.assertTrue(note_is_readable_without_script(page, phrase))
        self.assertIn("sparks as intentions", page)
        self.assertNotIn("<script", page.lower())

    async def test_the_page_refuses_without_a_token(self) -> None:
        request = _read_request("story/eddies/7-new-eddy.md")
        with patch("state.ARTIFACT_READ_TOKEN", "secret-token"):
            with self.assertRaises(web.HTTPForbidden):
                await intake_server.handle_artifact_page(request)

    async def test_a_script_in_the_note_is_not_a_script_in_the_page(self) -> None:
        from artifact_viewer import render_note_page

        page = render_note_page("Title", "hello <script>alert(1)</script>")
        self.assertNotIn("<script", page.lower())
        self.assertIn("hello", page)


class TestArtifactTokenCompare(unittest.TestCase):
    def test_missing_secret_refuses_even_a_blank_query(self) -> None:
        self.assertFalse(intake_server.artifact_read_authorized("", ""))

    def test_match_and_mismatch(self) -> None:
        self.assertTrue(intake_server.artifact_read_authorized("secret-token", "secret-token"))
        self.assertFalse(intake_server.artifact_read_authorized("secret-tokex", "secret-token"))
        self.assertFalse(intake_server.artifact_read_authorized("", "secret-token"))

    def test_handler_cannot_skip_the_check(self) -> None:
        import inspect

        src = inspect.getsource(intake_server.handle_artifact_read)
        self.assertIn("artifact_read_authorized", src)
        self.assertNotIn("if ARTIFACT_READ_TOKEN", src)
        compare = inspect.getsource(intake_server.artifact_read_authorized)
        self.assertIn("compare_digest", compare)


if __name__ == "__main__":
    unittest.main()
