"""The X bridge behind the door. Planted replies only. No live network call."""

from __future__ import annotations

import ast
import inspect
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from outgoing_connections import (
    Door,
    account_for,
    install_catalog,
    live_call,
    write_account,
    _render_open,
)
from outgoing_x import (
    ProcessTransport,
    ScriptedTransport,
    XServer,
    choose_tools,
    command_for,
    fetch_views,
    resolve_xurl,
    views_in,
)

REPO = Path(__file__).resolve().parents[1]
POST = "https://x.com/ada/status/1"
ARTICLE = "https://x.com/ada/article/2"
OUTER = "https://example.com/outer"
INNER = "https://example.com/inner"
SECRET = "planted-secret-value"

TOOLS = [
    {"name": "create_post", "inputSchema": {"type": "object", "properties": {"text": {}}}},
    {"name": "search_posts_all", "inputSchema": {"type": "object", "properties": {"query": {}}}},
    {
        "name": "search_posts_recent",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {}, "max_results": {"type": "integer"}},
        },
    },
    {
        "name": "get_posts",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ids": {"type": "string"},
                "expansions": {},
                "tweet.fields": {},
                "media.fields": {},
            },
        },
    },
    {
        "name": "get_bookmarks",
        "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
    },
    {"name": "get_users_me", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_article", "inputSchema": {"type": "object", "properties": {"id": {}}}},
]

TWEET = {
    "data": {
        "id": "1",
        "text": f"PLANTED_POST {SECRET}",
        "entities": {"urls": [{"expanded_url": OUTER, "url": "https://t.co/abc"}]},
        "referenced_tweets": [{"type": "quoted", "id": "2"}],
    },
    "includes": {
        "tweets": [
            {
                "id": "2",
                "text": "PLANTED_NESTED",
                "entities": {"urls": [{"expanded_url": INNER}]},
            }
        ]
    },
}


def _bounded_calls_missing_timeout(tree: ast.AST) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        rendered = ast.unparse(node.func)
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if rendered == "select.select":
            has_timeout = len(node.args) >= 4 or any(kw.arg == "timeout" for kw in node.keywords)
        elif name in {"wait", "communicate", "urlopen"}:
            has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
        else:
            continue
        if not has_timeout:
            bad.append(f"line {node.lineno}: {rendered}()")
    return bad


def _bridge(reply) -> ScriptedTransport:
    return ScriptedTransport(
        {
            "initialize": {},
            "tools/list": {"tools": TOOLS},
            "tools/call": reply,
        }
    )


def _content(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class BridgeChoiceTests(unittest.TestCase):
    def test_a_write_is_not_a_way_to_read(self) -> None:
        self.assertEqual(choose_tools([{"name": "create_post"}]), {})
        chosen = choose_tools(TOOLS)
        self.assertEqual(chosen["search"]["name"], "search_posts_recent")
        self.assertEqual(chosen["open"]["name"], "get_posts")
        both = TOOLS + [
            {
                "name": "get_posts_by_ids",
                "inputSchema": {"type": "object", "properties": {"ids": {}, "post.fields": {}}},
            },
            {
                "name": "get_posts_by_id",
                "inputSchema": {"type": "object", "properties": {"id": {}, "post.fields": {}, "expansions": {}}},
            },
        ]
        self.assertEqual(choose_tools(both)["open"]["name"], "get_posts_by_id")
        self.assertNotIn("create_post", {tool["name"] for tool in chosen.values()})

    def test_the_command_carries_the_account_and_not_a_secret(self) -> None:
        command = command_for("ada_name")
        self.assertTrue(command[0] == "xurl" or command[0].endswith("/xurl"))
        self.assertEqual(
            command[1:],
            ["--app", "tos-mcp", "-u", "ada_name", "mcp", "https://api.x.com/mcp"],
        )
        self.assertNotIn(SECRET, command)

    def test_a_service_path_finds_the_home_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "xurl"
            local.write_text("", encoding="utf-8")
            local.chmod(0o755)
            self.assertEqual(resolve_xurl(None, local), str(local))
            self.assertEqual(resolve_xurl("/usr/bin/xurl", local), "/usr/bin/xurl")
            missing = Path(tmp) / "absent"
            self.assertEqual(resolve_xurl(None, missing), "xurl")

    def test_stderr_is_not_kept(self) -> None:
        source = inspect.getsource(ProcessTransport._read_err)
        self.assertNotIn("append", source)
        self.assertNotIn("SECRET", source)

    def test_the_bridge_read_has_a_timeout(self) -> None:
        tree = ast.parse((REPO / "outgoing_x.py").read_text(encoding="utf-8"))
        self.assertEqual(_bounded_calls_missing_timeout(tree), [])

    def test_a_planted_unbounded_read_fails(self) -> None:
        planted = ast.parse("select.select([stdout], [], [])\nproc.wait()\nurlopen(req)\n")
        self.assertEqual(len(_bounded_calls_missing_timeout(planted)), 3)


class PlantedBridgeTests(unittest.TestCase):
    def _server(self, reply) -> tuple[XServer, ScriptedTransport]:
        transport = _bridge(reply)
        return XServer("ada_name", opener=lambda: transport), transport

    def test_initialize_keeps_the_manual(self) -> None:
        transport = ScriptedTransport(
            {
                "initialize": {"instructions": "PLANTED_MANUAL"},
                "tools/list": {"tools": TOOLS},
                "tools/call": lambda message: _content(TWEET),
            }
        )
        server = XServer("ada_name", opener=lambda: transport)
        server.open_link(POST)
        self.assertEqual(server.last_catalog["instructions"], "PLANTED_MANUAL")

    def test_a_named_read_returns_the_object_and_a_write_is_not_sent(self) -> None:
        transport = _bridge(lambda message: _content(TWEET))
        server = XServer("ada_name", opener=lambda: transport)
        payload = server.call_named("get_posts", {"ids": "1"})
        self.assertIn("PLANTED_POST", payload["data"]["text"])
        self.assertEqual(payload["includes"]["tweets"][0]["text"], "PLANTED_NESTED")
        arguments = next(
            message["params"]["arguments"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        )
        self.assertEqual(arguments["ids"], "1")
        self.assertIn("article", arguments["tweet.fields"])
        sent = len(transport.sent)
        with self.assertRaises(RuntimeError):
            server.call_named("create_post", {"text": "no"})
        self.assertEqual(len(transport.sent), sent)

    def test_an_account_call_is_not_given_the_post_fields(self) -> None:
        account = {
            "name": "get_users_me",
            "inputSchema": {
                "type": "object",
                "properties": {"expansions": {}, "post.fields": {}, "user.fields": {}},
            },
        }
        tools = [account if tool["name"] == "get_users_me" else tool for tool in TOOLS]
        tools.append(
            {
                "name": "get_users_bookmarks",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {}, "expansions": {}, "post.fields": {}},
                },
            }
        )
        calls: list[dict] = []

        def reply(message):
            if message.get("method") == "tools/call":
                calls.append(message["params"])
            return _content({"data": {"id": "99"}})

        transport = ScriptedTransport(
            {"initialize": {}, "tools/list": {"tools": tools}, "tools/call": reply}
        )
        server = XServer("ada_name", opener=lambda: transport)
        server.call_named("get_users_me", {})
        server.call_named("get_users_bookmarks", {"id": "99"})
        self.assertEqual(calls[0]["arguments"], {})
        self.assertEqual(calls[1]["arguments"], {"id": "99"})
        self.assertNotIn("expansions", calls[0]["arguments"])
        self.assertNotIn("referenced_tweets.id", json.dumps(calls))

    def test_a_post_includes_the_nested_post_and_offers_the_links_that_leave(self) -> None:
        server, transport = self._server(lambda message: _content(TWEET))
        opened = server.open_link(POST)
        self.assertIn("PLANTED_POST", opened["text"])
        self.assertEqual(opened["nested"]["text"], "PLANTED_NESTED")
        self.assertEqual(opened["nested"]["relation"], "quoted")
        self.assertEqual(opened["offers"], [OUTER])
        self.assertEqual(opened["nested"]["offers"], [INNER])
        names = [
            message["params"]["name"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        ]
        self.assertEqual(names, ["get_posts"])
        arguments = next(
            message["params"]["arguments"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        )
        self.assertEqual(arguments["ids"], "1")
        self.assertIn("referenced_tweets.id", arguments["expansions"])
        self.assertIn("attachments.media_keys", arguments["expansions"])
        self.assertIn("article.cover_media", arguments["expansions"])
        self.assertIn("url", arguments["media.fields"])
        self.assertIn("preview_image_url", arguments["media.fields"])
        self.assertIn("article", arguments["tweet.fields"])

    def test_a_status_that_holds_an_article_returns_the_body_and_offers_what_leaves(self) -> None:
        body = "PLANTED_ARTICLE_BODY " + ("word " * 30)
        payload = {
            "data": {
                "id": "1",
                "text": "announcement https://t.co/abc",
                "entities": {
                    "urls": [
                        {
                            "url": "https://t.co/abc",
                            "expanded_url": "https://x.com/i/article/99",
                        }
                    ]
                },
                "article": {
                    "title": "Part one",
                    "plain_text": body,
                    "entities": {"urls": [{"expanded_url": OUTER}]},
                },
            }
        }
        tools = [
            tool if tool["name"] != "get_posts" else {
                "name": "get_posts_by_id",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {}, "post.fields": {}, "expansions": {}},
                },
            }
            for tool in TOOLS
        ]
        transport = ScriptedTransport(
            {"initialize": {}, "tools/list": {"tools": tools}, "tools/call": lambda message: _content(payload)}
        )
        server = XServer("ada_name", opener=lambda: transport)
        opened = server.open_link(POST)
        self.assertEqual(opened["kind"], "article")
        self.assertIn("Part one", opened["text"])
        self.assertIn(body, opened["text"])
        self.assertEqual(opened["offers"], [OUTER])
        arguments = next(
            message["params"]["arguments"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        )
        self.assertEqual(arguments["id"], "1")
        self.assertIn("article", arguments["post.fields"])
        self.assertIn("article", arguments["tweet.fields"])
        self.assertIn("attachments.media_keys", arguments["expansions"])
        self.assertEqual(
            [message["params"]["name"] for message in transport.sent if message.get("method") == "tools/call"],
            ["get_posts_by_id"],
        )

    def test_an_article_is_the_whole_text(self) -> None:
        body = "PLANTED_ARTICLE_FULL " + ("word " * 40)
        server, transport = self._server(
            lambda message: _content({"data": {"id": "2", "text": "stub", "article": {"plain_text": body}}})
        )
        opened = server.open_link(ARTICLE)
        self.assertEqual(opened["kind"], "article")
        self.assertIn(body, opened["text"])
        names = [
            message["params"]["name"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        ]
        self.assertEqual(names, ["get_article"])

    def test_search_uses_the_recent_tool_and_names_the_posts(self) -> None:
        server, transport = self._server(
            lambda message: _content(
                {"data": [{"id": "s1", "text": "PLANTED_TITLE_ONE"}, {"id": "s2", "text": "PLANTED_TITLE_TWO"}]}
            )
        )
        posts = server.search("agents")
        self.assertEqual([post["title"] for post in posts], ["PLANTED_TITLE_ONE", "PLANTED_TITLE_TWO"])
        call = next(message for message in transport.sent if message.get("method") == "tools/call")
        self.assertEqual(call["params"]["name"], "search_posts_recent")
        self.assertEqual(call["params"]["arguments"]["query"], "agents")
        self.assertEqual(call["params"]["arguments"]["max_results"], 10)

    def test_bookmarks_are_his_and_the_user_id_comes_from_the_me_tool(self) -> None:
        def reply(message):
            name = message["params"]["name"]
            if name == "get_users_me":
                return _content({"data": {"id": "99", "username": "ada_name"}})
            return _content({"data": [{"id": "b1", "text": "PLANTED_BODY_AGENTS"}]})

        server, transport = self._server(reply)
        rows = server.bookmarks("ada")
        self.assertEqual(rows[0]["person"], "ada")
        self.assertEqual(rows[0]["id"], "b1")
        names = [
            message["params"]["name"]
            for message in transport.sent
            if message.get("method") == "tools/call"
        ]
        self.assertEqual(names, ["get_users_me", "get_bookmarks"])
        bookmark_call = [
            message for message in transport.sent if message.get("method") == "tools/call"
        ][1]
        self.assertEqual(bookmark_call["params"]["arguments"]["id"], "99")

    def test_a_link_that_is_not_http_is_not_fetched(self) -> None:
        fetched: list[str] = []
        server = XServer("ada_name", fetch=lambda url: fetched.append(url) or "body")
        self.assertEqual(server.fetch_url("file:///tmp/secret"), "That link cannot be read.")
        self.assertEqual(fetched, [])
        self.assertEqual(server.fetch_url(OUTER), "body")
        self.assertEqual(fetched, [OUTER])


class SignInFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_file_is_the_account_and_nothing_else(self) -> None:
        write_account(self.root, "ada", "@ada_name")
        path = self.root / "state" / "x-account.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"person": "ada", "account": "ada_name"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(account_for("ada", self.root), "ada_name")
        self.assertIsNone(account_for("bea", self.root))
        path.write_text(
            json.dumps({"person": "ada", "account": "ada_name", "client_secret": SECRET}),
            encoding="utf-8",
        )
        self.assertIsNone(account_for("ada", self.root))
        with self.assertRaises(ValueError):
            write_account(self.root, "ada", SECRET)

    def test_another_person_does_not_call_and_a_failure_drops_its_text(self) -> None:
        write_account(self.root, "ada", "ada_name")
        calls: list[str] = []

        class Recording:
            def open_link(self, link: str) -> dict:
                calls.append(link)
                return {
                    "kind": "post",
                    "text": "PLANTED_POST",
                    "offers": [OUTER],
                    "nested": {"text": "PLANTED_NESTED", "offers": [INNER], "relation": "quoted"},
                }

            def search(self, query: str) -> list[dict]:
                return []

            def bookmarks(self, person: str) -> list[dict]:
                return []

            def fetch_url(self, url: str) -> str:
                calls.append(url)
                return "fetched"

        text = live_call(
            {"operation": "open", "link": POST},
            person="ada",
            root=self.root,
            server=Recording(),
        )
        self.assertIn("Post:\nPLANTED_POST", text)
        self.assertIn("Quoted post:\nPLANTED_NESTED", text)
        replied = _render_open(
            {"text": "OUTER", "nested": {"text": "INNER", "relation": "replied_to", "offers": []}}
        )
        self.assertIn("The post it replies to:\nINNER", replied)
        self.assertIn(f"Offer: {OUTER}", text)
        self.assertEqual(calls, [POST])
        other = live_call(
            {"operation": "open", "link": POST},
            person="bea",
            root=self.root,
            server=Recording(),
        )
        self.assertIn("You have not signed in to X.", other)
        self.assertEqual(calls, [POST])

    def test_the_signed_in_read_is_the_server_object(self) -> None:
        write_account(self.root, "ada", "ada_name")
        transport = _bridge(lambda message: _content(TWEET))
        server = XServer("ada_name", opener=lambda: transport)
        try:
            text = live_call(
                {"operation": "open", "link": POST},
                person="ada",
                root=self.root,
                server=server,
            )
            self.assertIn("PLANTED_POST", text)
            self.assertIn("PLANTED_NESTED", text)
            self.assertIn(OUTER, text)
            self.assertIn(INNER, text)
            self.assertNotIn("Quoted post:", text)
            self.assertIn("[X — ada's]", text)
            audit = (self.root / "state" / "outgoing_audit.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("PLANTED_POST", audit)
            self.assertNotIn(SECRET, audit)

            class Spy:
                def __init__(self) -> None:
                    self.calls: list[str] = []

                def call_named(self, name: str, arguments: dict) -> dict:
                    self.calls.append(name)
                    return {}

            spy = Spy()
            refused = live_call({}, tool="create_post", person="ada", root=self.root, server=spy)
            self.assertIn("Refused.", refused)
            self.assertEqual(spy.calls, [])
            audit = (self.root / "state" / "outgoing_audit.jsonl").read_text(encoding="utf-8")
            self.assertIn('"decision": "refused"', audit)
        finally:
            install_catalog(None)

        class Boom:
            def open_payload(self, link: str) -> dict:
                raise RuntimeError(SECRET)

        failed = live_call(
            {"operation": "open", "link": POST},
            person="ada",
            root=self.root,
            server=Boom(),
        )
        self.assertIn("X could not be read.", failed)
        self.assertNotIn(SECRET, failed)
        audit = (self.root / "state" / "outgoing_audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(SECRET, audit)
        self.assertNotIn("PLANTED_POST", audit)

    def test_a_topic_matches_the_bookmark_text(self) -> None:
        class Books:
            def bookmarks(self, person: str) -> list[dict]:
                return [
                    {"person": person, "id": "b1", "title": "note", "text": "a note about agents"},
                    {"person": person, "id": "b2", "title": "loaf", "text": "bread"},
                ]

            def open_link(self, link: str) -> dict:
                return {}

            def search(self, query: str) -> list[dict]:
                return []

            def fetch_url(self, url: str) -> str:
                return ""

        door = Door(self.root, Books())
        door.sign_in("ada", "marker-not-a-token")
        text = door.call(
            person="ada",
            room="craft",
            operation="bookmarks",
            arguments={"which": "topic", "topic": "agents"},
        )
        self.assertIn("a note about agents", text)
        self.assertNotIn("bread", text)


class PictureTests(unittest.TestCase):
    def test_a_picture_is_shown_and_another_host_is_not_fetched(self) -> None:
        from llm import messages_seeing

        photo = "https://pbs.twimg.com/media/a.jpg"
        preview = "https://pbs.twimg.com/media/b.jpg"
        views = views_in({
            "includes": {
                "media": [
                    {"type": "photo", "url": photo},
                    {"type": "video", "preview_image_url": preview},
                    {"type": "photo", "url": OUTER},
                ]
            }
        })
        self.assertEqual([(view["kind"], view["url"]) for view in views], [("photo", photo), ("video", preview)])

        opened: list[str] = []

        class Response:
            def __init__(self, url: str) -> None:
                self.url = url
                self.headers = {"Content-Type": "image/jpeg"}

            def geturl(self) -> str:
                return self.url

            def read(self, _limit: int) -> bytes:
                return b"\xff\xd8" + b"x" * 8

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

        def urlopen(request, timeout=0):
            opened.append(request.full_url)
            return Response(request.full_url)

        with unittest.mock.patch("outgoing_x.urllib.request.urlopen", urlopen):
            loaded = fetch_views(views + [{"url": OUTER, "kind": "photo"}])
        self.assertEqual(opened, [photo, preview])
        self.assertEqual([item["kind"] for item in loaded], ["photo", "video"])
        self.assertTrue(loaded[0]["data"])
        self.assertNotIn(OUTER, opened)

        stored = [{"role": "user", "content": "PLANTED_TEXT"}]
        seen = messages_seeing(stored, loaded[:1])
        plain = messages_seeing(stored, [])
        self.assertEqual(stored[0]["content"], "PLANTED_TEXT")
        self.assertEqual(plain[0]["content"], "PLANTED_TEXT")
        self.assertEqual(seen[0]["content"][0], {"type": "text", "text": "PLANTED_TEXT"})
        self.assertEqual(seen[0]["content"][1]["type"], "image")
        self.assertEqual(seen[0]["content"][1]["source"]["media_type"], "image/jpeg")
