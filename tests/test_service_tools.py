"""The rooms' services: offered by room and asker, refused again at the call, never writing.

A room that must say yes sits beside every room that must say no.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import google_connection as gc
import outgoing_connections as door
import room_connections as rc
import service_tools as st
import tos_tools
import turn_trace
from tests.test_google_connection import ACCESS, CODE, FakeHttp, granted

REGISTRY = {
    "channels": {
        "1": {"type": "river", "name": "home", "mage": "ada"},
        "2": {"type": "craft", "name": "craft", "attunement": "craft", "mage": "ada"},
        "3": {"type": "health", "name": "my-health", "mage": "ada"},
        "4": {"type": "shared-river", "name": "family", "mage": "ada"},
    }
}
EVENT_BODY = "PLANTED_EVENT_TITLE"
WRITE_MARKERS = ("create", "update", "delete", "send", "reply", "forward", "respond", "insert", "patch", "trash")


def _names(tools) -> set[str]:
    return {(t.get("function") or {}).get("name") or t.get("name") or "" for t in tools}


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.house = base / "house"
        self.house.mkdir()
        self.root = base / "ada"
        self.root.mkdir()
        self.room = {"id": "1"}
        self.person = {"who": "ada"}
        self.seen: list[tuple[str, str]] = []
        env = patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "cs", "GOOGLE_REDIRECT_URI": "https://house.example/connect/google/callback"})
        env.start()
        self.addCleanup(env.stop)
        door.bind(
            door.Shell(
                lambda: REGISTRY,
                lambda: self.person["who"],
                lambda: str(self.root),
                lambda: [],
                lambda: self.room["id"],
            )
        )
        self.addCleanup(door.bind, None)

        def fetch(url, token, params):
            self.seen.append((url, token))
            if url.endswith("/calendarList"):
                return {"items": [{"summary": "Mine", "id": "primary"}]}
            return {"items": [{"id": "e1", "summary": EVENT_BODY, "start": {"dateTime": "2026-10-15T09:00:00+02:00"}, "end": {"dateTime": "2026-10-15T10:00:00+02:00"}}]}

        st.install_fetch(fetch)
        self.addCleanup(st.install_fetch, None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def sign_in(self, services=("calendar",)) -> None:
        import time

        now = time.time()  # real time: the token must still be fresh, so no call leaves the test
        gc.begin(person="ada", root=self.root, house=self.house, channel_id=1, services=list(services), now=now)
        state = list(json.loads(gc.pending_path(self.house).read_text()))[-1]
        gc.complete(self.house, state, CODE, FakeHttp([granted()]), now=now + 1)

    def offered(self) -> set[str]:
        return _names(tos_tools.tools_for_attunement("native"))


class OfferTests(Base):
    def test_home_is_offered_calendar_once_signed_in(self) -> None:
        self.assertNotIn("calendar_list_events", self.offered(), "no sign-in, no tool")
        self.sign_in()
        self.assertIn("calendar_list_events", self.offered())

    def test_every_other_room_says_no_until_it_is_allowed_and_switched_on(self) -> None:
        self.sign_in()
        self.room["id"] = "3"
        self.assertNotIn("calendar_list_events", self.offered(), "health")
        self.room["id"] = "4"
        self.assertNotIn("calendar_list_events", self.offered(), "shared")
        self.room["id"] = "2"
        self.assertNotIn("calendar_list_events", self.offered(), "craft: allowed, not on by default")
        rc.choose(self.root, "ada", "calendar", "2", "look", registry=REGISTRY)
        self.assertIn("calendar_list_events", self.offered(), "craft once he switches it on")
        self.room["id"] = "3"
        with self.assertRaises(rc.Forbidden):
            rc.choose(self.root, "ada", "calendar", "3", "look", registry=REGISTRY)

    def test_switched_off_in_home_it_is_gone(self) -> None:
        self.sign_in()
        self.assertIn("calendar_list_events", self.offered(), "positive control")
        rc.choose(self.root, "ada", "calendar", "1", "off", registry=REGISTRY)
        self.assertNotIn("calendar_list_events", self.offered())

    def test_a_sign_in_that_did_not_include_calendar_offers_nothing(self) -> None:
        self.sign_in()
        data = json.loads(gc.account_path(self.root).read_text())
        data["services"] = []
        gc.account_path(self.root).write_text(json.dumps(data))
        self.assertNotIn("calendar_list_events", self.offered())

    def test_another_person_asking_uses_nobody_elses_sign_in(self) -> None:
        self.sign_in()
        self.person["who"] = "bea"
        self.assertNotIn("calendar_list_events", self.offered())
        self.assertIn("Not in this room", tos_tools._execute_tos_tool_raw("calendar_list_events", {}))
        self.assertEqual(self.seen, [])

    def test_no_tool_here_writes_or_sends(self) -> None:
        for service, (tools, _needs) in st.SERVICE_TOOLS.items():
            for name in _names(tools):
                for marker in WRITE_MARKERS:
                    self.assertNotIn(marker, name, f"{service}: {name}")
        self.assertTrue(any(m in "calendar_create_event" for m in WRITE_MARKERS), "positive control: the markers do catch a write")
        self.assertTrue(any(m in "gmail_send_message" for m in WRITE_MARKERS))

    def test_the_two_lists_agree(self) -> None:
        self.assertLessEqual(set(st.SERVICE_TOOLS), set(rc.SERVICES))
        seen: set[str] = set()
        for tools, needs in st.SERVICE_TOOLS.values():
            self.assertIn(needs, gc.SERVICE_SCOPES)
            names = _names(tools)
            self.assertFalse(names & seen, "a tool name is offered by one service")
            seen |= names


class CallTests(Base):
    def test_a_call_in_the_right_room_reads_and_names_whose(self) -> None:
        self.sign_in()
        out = tos_tools._execute_tos_tool_raw("calendar_list_events", {"time_min": "2026-10-15T00:00:00+02:00"})
        self.assertIn("[Calendar — ada's]", out)
        self.assertIn(EVENT_BODY, out)
        self.assertNotIn(ACCESS, out)
        self.assertEqual(self.seen[0][1], ACCESS)

    def test_a_call_is_refused_again_in_a_room_that_says_no(self) -> None:
        self.sign_in()
        self.assertIn(EVENT_BODY, tos_tools._execute_tos_tool_raw("calendar_list_events", {}), "positive control")
        before = len(self.seen)
        for room in ("3", "4", "2"):
            self.room["id"] = room
            out = tos_tools._execute_tos_tool_raw("calendar_list_events", {})
            self.assertIn("Not in this room", out)
            self.assertNotIn(EVENT_BODY, out)
        self.assertEqual(len(self.seen), before, "Google was not called")

    def test_the_audit_names_the_act_and_not_the_content(self) -> None:
        self.sign_in()
        tos_tools._execute_tos_tool_raw("calendar_list_events", {})
        self.room["id"] = "3"
        tos_tools._execute_tos_tool_raw("calendar_list_events", {})
        text = (self.root / "state" / st.AUDIT_NAME).read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([r["decision"] for r in rows], ["called", "refused"])
        self.assertNotIn(EVENT_BODY, text)
        self.assertEqual(set(rows[0]), {"ts", "person", "service", "operation", "decision"})

    def test_a_revoked_sign_in_says_so_plainly(self) -> None:
        self.sign_in()
        out = st.call("calendar_list_events", {}, http=FakeHttp([{"error": "invalid_grant"}]))
        self.assertTrue(out)  # a fresh token is still good: no refresh is attempted
        gc.token_path(self.root).write_text(json.dumps({"person": "ada", "refresh_token": "r", "access_token": "a", "expires_at": 0}))
        out = st.call("calendar_list_events", {}, http=FakeHttp([{"error": "invalid_grant"}]))
        self.assertIn("sign in again", out)
        self.assertNotIn("invalid_grant", out)

    def test_a_failure_does_not_carry_googles_body(self) -> None:
        self.sign_in()

        def boom(url, token, params):
            raise RuntimeError("PLANTED_GOOGLE_FAILURE " + token)

        st.install_fetch(boom)
        out = tos_tools._execute_tos_tool_raw("calendar_list_events", {})
        self.assertIn("could not be read", out)
        self.assertNotIn("PLANTED_GOOGLE_FAILURE", out)
        self.assertNotIn(ACCESS, out)


class CallbackRouteTests(Base):
    def test_the_return_page_finishes_a_sign_in_and_shows_no_code(self) -> None:
        from aiohttp.test_utils import make_mocked_request

        import intake_server

        import time

        gc.begin(person="ada", root=self.root, house=self.house, channel_id=1, services=["calendar"], now=time.time())
        state = list(json.loads(gc.pending_path(self.house).read_text()))[-1]

        class Planted:
            def post_form(self, url, data):
                return granted()

        with patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": str(self.house)}), patch.object(gc, "UrlHttp", Planted):
            ok = asyncio.run(
                intake_server.handle_google_callback(make_mocked_request("GET", f"/connect/google/callback?state={state}&code={CODE}"))
            )
            bad = asyncio.run(
                intake_server.handle_google_callback(make_mocked_request("GET", f"/connect/google/callback?state=nope&code={CODE}"))
            )
            denied = asyncio.run(
                intake_server.handle_google_callback(make_mocked_request("GET", "/connect/google/callback?error=access_denied&state=x"))
            )
        self.assertEqual(ok.status, 200)
        self.assertIn("Connected", ok.text)
        self.assertEqual(gc.signed_in("ada", self.root)["services"], ["calendar"])
        for response in (ok, bad, denied):
            self.assertNotIn(CODE, response.text)
        self.assertEqual((bad.status, denied.status), (400, 400))

    def test_the_route_is_registered_before_the_catch_all(self) -> None:
        import intake_server

        app = intake_server.create_intake_app()
        from aiohttp.test_utils import make_mocked_request

        match = asyncio.run(app.router.resolve(make_mocked_request("GET", "/connect/google/callback?state=a&code=b")))
        self.assertIs(match.handler, intake_server.handle_google_callback)
        other = asyncio.run(app.router.resolve(make_mocked_request("GET", "/connect/other/page.md")))
        self.assertIsNot(other.handler, intake_server.handle_google_callback, "positive control")


class CalendarTrace(unittest.TestCase):
    """A connection is named before it is switched on. The card never carries the event."""

    def test_a_calendar_read_names_the_day_and_the_query_and_not_the_event(self) -> None:
        planted = "PLANTED_EVENT_TITLE at 11:00 with Claudia"
        step = turn_trace.describe_tool(
            "calendar_list_events",
            {"time_min": "2026-10-20T00:00:00+02:00", "time_max": "2026-10-21T00:00:00+02:00", "query": "Claudia"},
            planted,
        )
        self.assertEqual(step.text, 'read the calendar 20.10–21.10 for "Claudia"')
        self.assertNotIn(planted, step.text)
        self.assertNotIn("calendar_list_events", step.text)
        # The generic preview still shows a house tool's first line, so this check can fail.
        other = turn_trace.describe_tool("run_shell", {"command": "ls"}, planted)
        self.assertIn("PLANTED_EVENT_TITLE", other.text)

    def test_every_calendar_tool_has_a_line_and_a_planted_body_stays_off_it(self) -> None:
        planted = "PLANTED_EVENT_BODY"
        for spec in st.CALENDAR_TOOLS:
            name = spec["function"]["name"]
            step = turn_trace.describe_tool(
                name,
                {"query": "Kate", "time_min": "2026-10-15T00:00:00+02:00", "event_id": planted, "calendar_id": "primary"},
                planted,
            )
            self.assertNotIn(planted, step.text, name)
            self.assertNotIn(name, step.text, name)
            self.assertTrue(step.text.startswith("read "), name)
        listed = turn_trace.describe_tool("calendar_list_calendars", {}, planted)
        self.assertEqual(listed.text, "read the calendars")
        one = turn_trace.describe_tool("calendar_get_event", {"event_id": planted}, planted)
        self.assertEqual(one.text, "read one event")

    def test_a_blocked_calendar_call_says_why_and_not_the_wrapper(self) -> None:
        step = turn_trace.describe_tool(
            "calendar_list_events",
            {},
            "ToolResult[blocked] tool: Not in this room",
        )
        self.assertEqual(step.text, "read the calendar — blocked: Not in this room")
        self.assertNotIn("ToolResult", step.text)


if __name__ == "__main__":
    unittest.main()
