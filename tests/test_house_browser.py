"""The house spirit's browser: one page of text, and not for a forge turn.

A local server holds the page. The test can read it. The tool cannot, when the
address is the machine itself, and a redirect onto that address is refused
even when the first hop was fetched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import house_browser as hb
import outgoing_connections as door
import tos_tools
import turn_trace
import workshop_tools as wt


def git(cwd: Path, *argv: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "nobody",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "nobody",
    }
    subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True, text=True, env=env)


class _Page(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.hits += 1
        if self.path.startswith("/go"):
            port = self.server.server_address[1]
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/secret")
            self.end_headers()
            return
        if self.path.startswith("/page"):
            body = b"<html><script>SECRET_SCRIPT</script><p>Visible sentence</p></html>"
            self._body(body, "text/html; charset=utf-8")
            return
        if self.path.startswith("/secret"):
            self._body(b"SECRET_BODY", "text/plain")
            return
        self.send_error(404)

    def _body(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


class Browser(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.shop = base / "workshop"
        self.shop.mkdir()
        git(self.shop, "init", "-q", "-b", "main")
        (self.shop / "readme.md").write_text("here\n")
        git(self.shop, "add", "-A")
        git(self.shop, "commit", "-q", "-m", "first")
        self.runtime = base / "runtime"
        self.runtime.mkdir()
        self.registry = {
            "mages": {"ada": {"workshop": {"checkout": str(self.shop)}}},
            "channels": {"1": {"type": "magic", "name": "magic", "mage": "ada"}},
        }
        self.room = {"id": "1"}
        door.bind(
            door.Shell(
                lambda: self.registry,
                lambda: "ada",
                lambda: str(self.runtime),
                lambda: [],
                lambda: self.room["id"],
            )
        )
        self.addCleanup(door.bind, None)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Page)
        self.server.hits = 0
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}{path}"

    def test_the_page_is_readable_here_and_not_opened_on_this_machine(self) -> None:
        with urllib.request.urlopen(self.url("/secret"), timeout=5) as response:
            self.assertIn(b"SECRET_BODY", response.read())
        self.server.hits = 0
        result = hb.call("house_browser", {"url": self.url("/page")})
        self.assertEqual(result, "That page is not one to open.")
        self.assertEqual(self.server.hits, 0)
        self.assertNotIn("SECRET_SCRIPT", result)
        self.assertNotIn("Visible sentence", result)

    def test_a_redirect_onto_this_machine_does_not_return_the_secret(self) -> None:
        with urllib.request.urlopen(self.url("/secret"), timeout=5) as response:
            self.assertIn(b"SECRET_BODY", response.read())
        with self.assertRaises(wt.Refused) as caught:
            hb._retrieve(self.url("/go"))
        self.assertIn("not one to open", str(caught.exception))
        self.assertNotIn("SECRET_BODY", str(caught.exception))

    def test_the_reader_returns_the_words_and_drops_the_script(self) -> None:
        with self.assertRaises(wt.Refused):
            hb._retrieve(self.url("/page"))
        real = hb.validate_fetch_url

        def allow_the_test_page(url: str):
            if url.startswith(self.url("")):
                return None
            return real(url)

        with patch.object(hb, "validate_fetch_url", allow_the_test_page):
            result = hb._retrieve(self.url("/page"))
        self.assertIn("Visible sentence", result)
        self.assertNotIn("SECRET_SCRIPT", result)
        self.assertIn(self.url("/page"), result)

    def test_a_forge_turn_does_not_open_it(self) -> None:
        self.server.hits = 0
        token = wt.set_forge_turn(True)
        try:
            result = hb.call("house_browser", {"url": "https://example.com/page"})
            self.assertEqual(result, hb.FORGE_HELD)
        finally:
            wt.reset_forge_turn(token)
        self.assertEqual(self.server.hits, 0)

    def test_the_channel_names_the_page_and_not_the_query(self) -> None:
        step = turn_trace.describe_tool(
            "house_browser",
            {"url": "https://example.com/notes?token=SECRET_QUERY"},
            "SECRET_PAGE",
        )
        self.assertEqual(step.text, "opened `example.com/notes`")
        self.assertNotIn("SECRET_QUERY", step.text)
        self.assertNotIn("SECRET_PAGE", step.text)

    def test_not_in_another_room(self) -> None:
        self.room["id"] = "9"
        self.assertEqual(hb.tools_offered(), [])
        self.assertEqual(hb.call("house_browser", {"url": "https://example.com"}), "Not in this room.")
        self.room["id"] = "1"
        self.assertIn("house_browser", {t["function"]["name"] for t in hb.tools_offered()})
        self.assertIn("not one to open", tos_tools._execute_tos_tool_raw("house_browser", {"url": self.url("/page")}))

    def test_the_prompt_gives_the_house_spirit_the_page_and_not_the_forge_spirit(self) -> None:
        import magic_prompt

        self.assertIn("house_browser", magic_prompt.SUBSTRATE)
        self.assertIn("does not click", magic_prompt.SUBSTRATE)
        self.assertIn("That message has no terminal and no browser.", magic_prompt.SUBSTRATE)
