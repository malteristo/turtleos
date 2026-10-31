"""The outgoing door, proven on a fixture. No live network call."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import tos_tools
import turn_trace
from outgoing_connections import (
    AUDIT_NAME,
    EXEMPT_OFFER_SITES,
    GUEST_AUDIT_NAME,
    TOOL_NAME,
    Door,
    channel_line,
    connection_list,
    connection_preamble,
    connection_tools,
    files_containing,
    health_for,
    health_step,
    install_catalog,
    is_summary,
    live_call,
    offer_sites,
    paused_for,
    private_action,
    set_paused,
    summarize,
    tend_outgoing,
    tool_log_line,
    write_account,
)
from outgoing_connect_ui import ACT, CHANNEL_LINE
from outgoing_x import clear_command
from turn_packet import tools_called

REPO = Path(__file__).resolve().parents[1]
POST = "https://x.com/ada/status/1"
ARTICLE = "https://x.com/ada/article/2"
SECRET = "planted-secret-value"
POST_BODY = "PLANTED_POST"
NESTED_BODY = "PLANTED_NESTED"
ARTICLE_BODY = "PLANTED_ARTICLE_FULL " + ("word " * 40)
OUTER = "https://example.com/outer"
INNER = "https://example.com/inner"
TITLE = "PLANTED_TITLE_ONE"
ADA_BOOK = "PLANTED_BODY_AGENTS"
BEA_BOOK = "PLANTED_BODY_BEA"


def _names(tools) -> set[str]:
    out = set()
    for tool in tools:
        name = (tool.get("function") or {}).get("name") or tool.get("name") or ""
        if name:
            out.add(name)
    return out


class FixtureX:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fetched: list[str] = []

    def open_link(self, link: str) -> dict:
        self.calls.append(("open_link", link))
        if link == ARTICLE:
            return {"kind": "article", "text": ARTICLE_BODY}
        if link == POST:
            return {
                "kind": "post",
                "text": f"{POST_BODY} {SECRET}",
                "offers": [OUTER],
                "nested": {
                    "text": NESTED_BODY,
                    "offers": [INNER],
                },
            }
        return {"kind": "post", "text": "unknown"}

    def fetch_url(self, url: str) -> str:
        self.calls.append(("fetch_url", url))
        self.fetched.append(url)
        return f"fetched {url}"

    def search(self, query: str) -> list[dict]:
        self.calls.append(("search", query))
        return [{"id": "s1", "title": TITLE}, {"id": "s2", "title": "PLANTED_TITLE_TWO"}]

    def bookmarks(self, person: str) -> list[dict]:
        self.calls.append(("bookmarks", person))
        rows = [
            {"person": "ada", "id": "b1", "topic": "agents", "title": "Agents", "text": ADA_BOOK},
            {"person": "ada", "id": "b2", "topic": "bread", "title": "Bread", "text": "PLANTED_BODY_BREAD"},
            {"person": "bea", "id": "b9", "topic": "agents", "title": "Bea", "text": BEA_BOOK},
        ]
        return rows


class OfferSiteTests(unittest.TestCase):
    def test_exempt_list_is_empty(self) -> None:
        self.assertEqual(EXEMPT_OFFER_SITES, frozenset())

    def test_the_tree_before_the_door_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(offer_sites(Path(tmp)), ["MISSING_DOOR"])

    def test_a_planted_offer_fails_and_the_plant_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "outgoing_connections.py").write_text("# door\n", encoding="utf-8")
            plant = root / "second_offer.py"
            plant.write_text(f'name = "{TOOL_NAME}"\n', encoding="utf-8")
            self.assertEqual(offer_sites(root), ["second_offer.py"])
            plant.unlink()
            self.assertEqual(offer_sites(root), [])

    def test_this_tree_has_one_offer_site(self) -> None:
        self.assertEqual(offer_sites(REPO), [])


class DoorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fixture = FixtureX()
        self.door = Door(self.root, self.fixture)
        self.door.sign_in("ada", SECRET)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _audit(self) -> list[dict]:
        path = self.root / "state" / AUDIT_NAME
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_craft_is_offered_the_servers_reads(self) -> None:
        install_catalog(
            {
                "instructions": "PLANTED_MANUAL",
                "tools": [
                    {
                        "name": "get_posts",
                        "description": "PLANTED_SERVER_DESCRIPTION",
                        "inputSchema": {"type": "object", "properties": {"id": {}}},
                    },
                    {"name": "create_post", "description": "writes a post", "inputSchema": {}},
                    {"name": "search_posts_recent", "description": "search", "inputSchema": {}},
                ],
            }
        )
        try:
            craft = tos_tools.tools_for_attunement("craft")
            names = _names(craft)
            self.assertIn("get_posts", names)
            self.assertIn("search_posts_recent", names)
            self.assertNotIn("create_post", names)
            self.assertNotIn(TOOL_NAME, names)
            spec = next(tool for tool in craft if tool["function"]["name"] == "get_posts")
            self.assertEqual(spec["function"]["description"], "PLANTED_SERVER_DESCRIPTION")
            for attunement in ("native", "magic", "", "semi"):
                self.assertNotIn("get_posts", _names(tos_tools.tools_for_attunement(attunement)))
            self.assertNotIn("get_posts", tos_tools._TOOL_SCOPES)
            self.assertNotIn(TOOL_NAME, tos_tools._TOOL_SCOPES)
            self.assertEqual(connection_preamble("craft"), "PLANTED_MANUAL")
            self.assertEqual(connection_preamble("native"), "")
            self.assertIn("connection_preamble", (REPO / "prompts.py").read_text(encoding="utf-8"))
        finally:
            install_catalog(None)

    def test_an_empty_catalog_does_not_offer_the_old_tool(self) -> None:
        install_catalog(None)
        self.assertNotIn(TOOL_NAME, _names(tos_tools.tools_for_attunement("craft")))

    def test_the_channel_names_the_act_and_not_the_object(self) -> None:
        install_catalog(
            {
                "instructions": "",
                "tools": [
                    {"name": "get_posts", "inputSchema": {}},
                    {"name": "search_posts_recent", "inputSchema": {}},
                    {"name": "create_post", "inputSchema": {}},
                ],
            }
        )
        try:
            body = '{"data": {"text": "PLANTED_OBJECT_BODY"}}'
            step = turn_trace.describe_tool("get_posts", {"id": "1"}, body)
            self.assertEqual(step.text, "read X")
            self.assertNotIn("PLANTED_OBJECT_BODY", step.text)
            self.assertNotIn("get_posts", step.text)
            other = turn_trace.describe_tool("run_shell", {"command": "ls"}, "first line\nsecond")
            self.assertEqual(other.text, "run_shell → first line")
            self.assertEqual(channel_line("search_posts_recent"), "searched X")
            self.assertEqual(tool_log_line("read_practice_file", "PLANTED_NOTE"), "read_practice_file -> PLANTED_NOTE")
            self.assertNotIn("PLANTED_OBJECT_BODY", tool_log_line("get_posts", body))
            self.assertIn("chars", tool_log_line("get_posts", body))
            trace = turn_trace.render_trace(
                turn_trace.AttunementSteps(),
                1,
                "model",
                ["get_posts", "get_posts", "search_practice_files"],
            )
            self.assertIn("looked up: X, search_practice_files", trace)
            self.assertNotIn("get_posts", trace)
            steps: list[turn_trace.Step] = []
            turn_trace.remember_step(steps, turn_trace.Step("📖", "read `a.md`"))
            turn_trace.remember_step(steps, turn_trace.Step("📖", "read `a.md`"))
            turn_trace.remember_step(steps, turn_trace.Step("📖", "read X"))
            turn_trace.remember_step(steps, turn_trace.Step("📖", "read X"))
            turn_trace.remember_step(steps, turn_trace.Step("🔎", "searched X"))
            self.assertEqual([step.text for step in steps], ["read `a.md`", "read `a.md`", "read X", "searched X"])
            self.assertEqual(
                tools_called(
                    [
                        {"name": "get_posts"},
                        {"name": "search_posts_recent"},
                        {"name": "read_practice_file"},
                    ]
                ),
                ["X", "read_practice_file"],
            )
        finally:
            install_catalog(None)

    def test_two_rooms_are_one_secret_and_it_stays_out_of_the_channel(self) -> None:
        first = self.door.call(person="ada", room="room-1", operation="open", arguments={"link": POST})
        second = self.door.call(person="ada", room="room-2", operation="open", arguments={"link": POST})
        self.assertEqual(len(self.door._secrets), 1)
        self.assertIn(POST_BODY, first)
        self.assertIn(NESTED_BODY, first)
        self.assertIn(f"Offer: {OUTER}", first)
        self.assertIn(f"Offer: {INNER}", first)
        self.assertNotIn(SECRET, first)
        self.assertNotIn(SECRET, second)
        self.assertEqual(self.fixture.fetched, [])
        self.assertIn("[X — ada's]", first)

    def test_no_sign_in_does_not_call(self) -> None:
        text = self.door.call(person="bea", room="room-9", operation="open", arguments={"link": POST})
        self.assertIn("You have not signed in to X.", text)
        self.assertNotIn(POST_BODY, text)
        self.assertNotIn(ADA_BOOK, text)
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(self._audit()[-1]["decision"], "unsigned")

    def test_another_persons_bookmarks_are_not_in_his_set(self) -> None:
        text = self.door.call(person="ada", room="room-1", operation="bookmarks", arguments={"which": "all"})
        self.assertIn(ADA_BOOK, text)
        self.assertNotIn(BEA_BOOK, text)
        self.assertEqual(self.fixture.calls, [("bookmarks", "ada")])

    def test_article_is_whole_and_accept_is_a_second_call(self) -> None:
        opened = self.door.call(person="ada", room="room-1", operation="open", arguments={"link": ARTICLE})
        self.assertIn(ARTICLE_BODY, opened)
        self.assertNotIn(ARTICLE_BODY[:20] + "…", opened)
        self.assertEqual(self.fixture.fetched, [])
        accepted = self.door.call(
            person="ada", room="room-1", operation="accept_offer", arguments={"url": OUTER}
        )
        self.assertEqual(self.fixture.fetched, [OUTER])
        self.assertIn("fetched", accepted)

    def test_search_names_titles_and_an_unasked_search_does_not_run(self) -> None:
        found = self.door.call(person="ada", room="room-1", operation="search", arguments={"query": "agents"})
        self.assertTrue(is_summary(found.split("\n", 1)[1], [TITLE, "PLANTED_TITLE_TWO"]))
        self.assertFalse(is_summary("s1\ns2", [TITLE]))
        self.assertEqual(summarize([{"id": "s1"}]), "")
        quiet = self.door.call(person="ada", room="room-1", operation="search", arguments={})
        self.assertIn("A search needs an ask.", quiet)
        self.assertEqual([call for call in self.fixture.calls if call[0] == "search"], [("search", "agents")])
        self.assertEqual(self._audit()[-1]["decision"], "refused")

    def test_bookmarks_all_topic_one_and_none(self) -> None:
        everyone = self.door.call(person="ada", room="room-1", operation="bookmarks", arguments={"which": "all"})
        topic = self.door.call(
            person="ada", room="room-1", operation="bookmarks", arguments={"which": "topic", "topic": "agents"}
        )
        one = self.door.call(
            person="ada", room="room-1", operation="bookmarks", arguments={"which": "one", "bookmark_id": "b2"}
        )
        none = self.door.call(
            person="ada", room="room-1", operation="bookmarks", arguments={"which": "topic", "topic": "nope"}
        )
        self.assertIn(ADA_BOOK, everyone)
        self.assertIn("PLANTED_BODY_BREAD", everyone)
        self.assertIn(ADA_BOOK, topic)
        self.assertNotIn("PLANTED_BODY_BREAD", topic)
        self.assertIn("PLANTED_BODY_BREAD", one)
        self.assertNotIn(ADA_BOOK, one)
        self.assertIn("none", none)

    def test_write_and_calendar_are_refused_without_a_body(self) -> None:
        write = self.door.call(person="ada", room="room-1", operation="post", arguments={"link": POST})
        calendar = self.door.call(person="ada", room="room-1", operation="calendar", arguments={})
        self.assertIn("Refused.", write)
        self.assertIn("Refused.", calendar)
        self.assertEqual(self.fixture.calls, [])
        for row in self._audit():
            self.assertEqual(set(row), {"ts", "person", "service", "operation", "decision"})
            self.assertEqual(row["decision"], "refused")
            self.assertNotIn(POST_BODY, json.dumps(row))

    def test_the_body_is_not_stored_and_a_planted_file_is_seen(self) -> None:
        self.door.call(person="ada", room="room-1", operation="open", arguments={"link": POST})
        self.assertEqual(files_containing(self.root, POST_BODY), [])
        self.assertEqual(files_containing(self.root, NESTED_BODY), [])
        self.assertFalse((self.root / "state" / GUEST_AUDIT_NAME).exists())
        planted = self.root / "state" / "store.md"
        planted.write_text(POST_BODY, encoding="utf-8")
        self.assertEqual(files_containing(self.root, POST_BODY), ["state/store.md"])
        planted.unlink()
        self.assertEqual(files_containing(self.root, POST_BODY), [])
        raw = (self.root / "state" / AUDIT_NAME).read_text(encoding="utf-8")
        self.assertNotIn(POST_BODY, raw)
        self.assertNotIn(SECRET, raw)

    def test_the_live_tool_path_does_not_call_a_server(self) -> None:
        install_catalog({"instructions": "", "tools": [{"name": "get_posts", "inputSchema": {}}]})
        try:
            text = tos_tools._execute_tos_tool_raw("get_posts", {"id": "1"})
            self.assertIn("You have not signed in to X.", text)
            self.assertNotIn(POST_BODY, text)
            self.assertEqual(self.fixture.calls, [])
            unknown = tos_tools._execute_tos_tool_raw(TOOL_NAME, {"operation": "open", "link": POST})
            self.assertIn("Unknown tool", unknown)
        finally:
            install_catalog(None)

    def test_the_list_is_private_and_a_pause_does_not_call(self) -> None:
        write_account(self.root, "ada", "ada_name")
        shown = connection_list("ada", self.root)
        self.assertIn("not checked yet", shown)
        self.assertIn("Posts, bookmarks, and search", shown)
        self.assertIn("```", shown)
        self.assertNotIn("ada_name", shown)
        self.assertNotIn(SECRET, shown)
        self.assertEqual(CHANNEL_LINE, "Your connections. Only you see the list.")
        self.assertNotIn("ready", CHANNEL_LINE)
        self.assertNotIn("ada_name", ACT)
        ui = (REPO / "outgoing_connect_ui.py").read_text(encoding="utf-8")
        command = (REPO / "commands.py").read_text(encoding="utf-8")
        card = (REPO / "mcp_list_ui.py").read_text(encoding="utf-8")
        self.assertIn("ephemeral=True", ui)
        self.assertIn('private_action(person, root, "pause")', card)  # pause and remove live on the card
        self.assertIn('"remove-yes"', card)
        self.assertNotIn('"test"', card)  # he does not press Test
        self.assertNotIn("connection_list", command)
        self.assertIn("CHANNEL_LINE", command)

        asked = private_action("ada", self.root, "remove")
        self.assertIn("Remove X?", asked)
        self.assertTrue((self.root / "state" / "x-account.json").is_file())

        set_paused(self.root, "ada", True)
        self.assertEqual(oct((self.root / "state" / "x-paused.json").stat().st_mode & 0o777), "0o600")
        self.assertIn("paused", connection_list("ada", self.root))
        self.assertNotIn("not checked yet", connection_list("ada", self.root))
        self.assertFalse(paused_for("bea", self.root))
        install_catalog(
            {"instructions": "PLANTED_MANUAL", "tools": [{"name": "get_posts", "inputSchema": {}}]}
        )
        try:
            with unittest.mock.patch("outgoing_connections._asker", return_value="ada"), unittest.mock.patch(
                "outgoing_connections._runtime_root", return_value=self.root
            ):
                self.assertEqual(connection_tools("craft"), [])
                self.assertEqual(connection_preamble("craft"), "X is paused.")
        finally:
            install_catalog(None)

        server = unittest.mock.Mock()
        text = live_call({"link": POST}, person="ada", root=self.root, server=server)
        self.assertIn("X is paused.", text)
        self.assertNotIn(POST_BODY, text)
        server.open_payload.assert_not_called()
        server.call_named.assert_not_called()
        audit = self._audit()
        self.assertEqual(audit[-1]["decision"], "paused")
        self.assertNotIn(POST_BODY, json.dumps(audit))

        resumed = private_action("ada", self.root, "pause")
        self.assertIn("not checked yet", resumed)
        self.assertNotIn("paused", resumed)
        self.assertFalse((self.root / "state" / "x-paused.json").exists())

        def _probe(account: str) -> str:
            return SECRET

        answered = private_action("ada", self.root, "test", probe=_probe)
        self.assertEqual(answered, "X responded.")
        self.assertNotIn(SECRET, answered)
        self.assertNotIn(SECRET, (self.root / "state" / AUDIT_NAME).read_text(encoding="utf-8"))

        junk = self.root / "state" / "x-paused.json"
        junk.write_text(json.dumps({"person": "ada", "secret": SECRET}), encoding="utf-8")
        self.assertFalse(paused_for("ada", self.root))
        self.assertNotIn(SECRET, connection_list("ada", self.root))
        junk.unlink()

        removed = private_action("ada", self.root, "remove-yes", clear=lambda account: account == "ada_name")
        self.assertEqual(removed, "X is removed.")
        self.assertNotIn("ada_name", removed)
        self.assertFalse((self.root / "state" / "x-account.json").exists())
        self.assertIn("not signed in", connection_list("ada", self.root))

        command_line = clear_command("ada_name")
        self.assertNotIn("--all", command_line)
        self.assertIn("--oauth2-username", command_line)
        self.assertIn("ada_name", command_line)
        with self.assertRaises(ValueError):
            clear_command("ada --all")

    def test_river_checks_the_login_and_retries_once_it_is_quiet(self) -> None:
        from datetime import datetime, timedelta, timezone

        write_account(self.root, "ada", "ada_name")
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        calls: list[str] = []

        def boom(account: str) -> str:
            calls.append(account)
            raise RuntimeError(SECRET)

        self.assertIsNone(health_step("ada", self.root, quiet=False, probe=boom, now=now))
        self.assertEqual(calls, ["ada_name"])
        health = health_for("ada", self.root)
        self.assertEqual(health["status"], "down")
        self.assertEqual(health["tries"], 1)
        self.assertFalse(health["raised"])
        self.assertNotIn(SECRET, json.dumps(health))
        self.assertIn("not answering", connection_list("ada", self.root, now=now))
        self.assertEqual(self._audit()[-1]["decision"], "refused")

        self.assertIsNone(
            health_step("ada", self.root, quiet=False, probe=boom, now=now + timedelta(minutes=5))
        )
        self.assertEqual(len(calls), 1)

        note = health_step("ada", self.root, quiet=True, probe=boom, now=now + timedelta(minutes=6))
        self.assertEqual(
            note,
            "X is not answering. I tried again once the room was quiet, and it still did not.",
        )
        self.assertNotIn(SECRET, note)
        self.assertEqual(len(calls), 2)
        self.assertTrue(health_for("ada", self.root)["raised"])

        def ok(account: str) -> str:
            calls.append("ok")
            return SECRET

        back = health_step(
            "ada", self.root, quiet=True, probe=ok, now=now + timedelta(minutes=40)
        )
        self.assertEqual(back, "X is answering again.")
        self.assertNotIn(SECRET, (self.root / "state" / "x-health.json").read_text(encoding="utf-8"))
        shown = connection_list("ada", self.root, now=now + timedelta(minutes=40))
        self.assertIn("ready, just now", shown)
        self.assertNotIn(SECRET, shown)
        self.assertIsNone(
            health_step("ada", self.root, quiet=True, probe=boom, now=now + timedelta(minutes=50))
        )
        self.assertEqual(calls[-1], "ok")

        set_paused(self.root, "ada", True)
        before = len(calls)
        self.assertIsNone(
            health_step("ada", self.root, quiet=True, probe=boom, now=now + timedelta(hours=3))
        )
        self.assertEqual(len(calls), before)

        junk = {"person": "ada", "status": "ready", "checked": now.isoformat(), "tries": 0, "raised": False, "secret": SECRET}
        (self.root / "state" / "x-health.json").write_text(json.dumps(junk), encoding="utf-8")
        self.assertIsNone(health_for("ada", self.root))
        self.assertNotIn(SECRET, connection_list("ada", self.root, now=now))

        (self.root / "state" / "x-health.json").unlink()
        set_paused(self.root, "ada", False)
        heard = tend_outgoing(roots=[self.root], quiet=True, probe=boom, now=now + timedelta(hours=4))
        self.assertIsNone(heard)
        heard = tend_outgoing(
            roots=[self.root], quiet=True, probe=boom, now=now + timedelta(hours=4, minutes=1)
        )
        self.assertIn("tried again", heard)


class DoorIsBoundByTheShellTests(unittest.TestCase):
    """The door does not import `mage` (issue 053); the shell hands it in. Unbound,
    it must not pass for a fact, and both bots must bind it."""

    def tearDown(self) -> None:
        import outgoing_connections as door

        door.bind(None)
        door._told_unbound = False

    def test_a_bound_shell_answers_who_is_asking_and_where(self) -> None:
        import outgoing_connections as door

        door.bind(door.Shell(lambda: {"mages": {}}, lambda: "ada", lambda: "/tmp/ada-root", lambda: ["/tmp/a", "/tmp/b"]))
        self.assertEqual(door._asker(), "ada")
        self.assertEqual(door._runtime_root(), Path("/tmp/ada-root"))

    def test_an_unbound_door_sees_nobody_and_says_so_once(self) -> None:
        import contextlib
        import io

        import outgoing_connections as door

        door.bind(None)
        door._told_unbound = False
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(door._asker(), "")
            self.assertIsNone(door._runtime_root())
        self.assertEqual(out.getvalue().count("before a shell was bound"), 1)

    def test_a_shell_that_raises_is_nobody_not_a_crash(self) -> None:
        import outgoing_connections as door

        def boom():
            raise RuntimeError("no context")

        door.bind(door.Shell(lambda: {}, boom, boom, lambda: []))
        self.assertEqual(door._asker(), "")
        self.assertIsNone(door._runtime_root())

    def test_arming_the_views_binds_the_door(self) -> None:
        import outgoing_connect_ui as ui
        import outgoing_connections as door

        shell = door.Shell(lambda: {}, lambda: "x", lambda: None, lambda: [])
        ui.register_outgoing_views(unittest.mock.MagicMock(), shell)
        self.assertIs(door.shell(), shell)

    def test_a_member_is_found_through_the_shells_registry(self) -> None:
        import outgoing_connect_ui as ui
        import outgoing_connections as door

        registry = {"mages": {"ada": {"discord_id": "42", "runtime_dir": "/tmp/ada"}}}
        door.bind(door.Shell(lambda: registry, lambda: None, lambda: None, lambda: []))
        self.assertEqual(ui.member_for(42), ("ada", Path("/tmp/ada")))
        self.assertIsNone(ui.member_for(43))  # control: it is the registry that answers
        door.bind(None)
        self.assertIsNone(ui.member_for(42))

    def test_both_bots_arm_the_views_with_a_shell(self) -> None:
        import ast

        repo = Path(__file__).resolve().parents[1]
        for name in ("discord_bot.py", "river_bot.py"):
            tree = ast.parse((repo / name).read_text(encoding="utf-8"))
            calls = [
                n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "register_outgoing_views"
            ]
            self.assertEqual(len(calls), 1, name)
            self.assertEqual(len(calls[0].args), 2, f"{name} must hand the door its shell")
