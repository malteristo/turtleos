"""A forge spirit opens a magic session over the connection, and the house keeps the turn."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from mcp_access.grants import GrantStore
from session_record import append_turn, read_turns
from spirit_link import (
    TEXT_MAX,
    channel_text,
    hear,
    magic_channel_id,
    speak,
    thread_name,
)
from tests.test_mcp_access import Fixture, call


WHEN = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def registry(root: Path, channels: dict | None = None) -> dict:
    return {
        "mages": {"kermit": {"practice_dir": str(root)}},
        "channels": channels
        if channels is not None
        else {"155": {"primitive": "magic", "mage": "kermit"}},
    }


class SpeakTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root.mkdir(exist_ok=True)
        self.sent: list[tuple[str, str, dict]] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def send(self, method: str, url: str, body: dict) -> tuple[int, dict]:
        self.sent.append((method, url, body))
        if url.endswith("/threads"):
            return 201, {"id": "900"}
        return 200, {"id": "800"}

    def test_opening_posts_into_the_owners_channel_and_keeps_the_turn(self) -> None:
        result = speak(
            owner="kermit",
            text="we build it from the inside",
            session=None,
            registry=registry(self.root),
            send=self.send,
            when=WHEN,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["session"], "900")
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[0][1].endswith("/channels/155/threads"))
        self.assertEqual(self.sent[0][2]["name"], "Forge · 16.10")
        self.assertEqual(self.sent[1][1], "https://discord.com/api/v10/channels/900/messages")
        self.assertEqual(self.sent[1][2]["content"], channel_text("we build it from the inside"))
        self.assertEqual(self.sent[1][2]["allowed_mentions"], {"parse": []})
        turns = read_turns(self.root, "900")
        self.assertEqual([t["kind"] for t in turns], ["greeting", "forge"])
        self.assertEqual(turns[1]["actor"], "forge")
        self.assertEqual(turns[1]["text"], "we build it from the inside")
        self.assertNotIn("Bot ", json.dumps(result))

    def test_the_owner_is_added_and_a_failed_add_still_keeps_the_session(self) -> None:
        reg = registry(self.root)
        reg["mages"]["kermit"]["discord_id"] = "111"

        def add(method, url, body):
            self.sent.append((method, url, body))
            if "/thread-members/" in url:
                return 403, {}
            if url.endswith("/threads"):
                return 201, {"id": "900"}
            return 200, {"id": "800"}

        result = speak(
            owner="kermit", text="hello", session=None, registry=reg, send=add, when=WHEN
        )
        self.assertTrue(result["ok"])
        self.assertTrue(any("/thread-members/111" in url for _, url, _ in self.sent))
        self.assertEqual(read_turns(self.root, "900")[1]["text"], "hello")

    def test_a_failed_post_keeps_nothing(self) -> None:
        def fail(method, url, body):
            self.sent.append((method, url, body))
            return 500, {}

        result = speak(
            owner="kermit", text="hello", session=None, registry=registry(self.root), send=fail, when=WHEN
        )
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.sent), 1)
        self.assertFalse((self.root / "state" / "sessions").exists())

    def test_a_thread_that_does_not_open_is_not_a_session(self) -> None:
        def half(method, url, body):
            if url.endswith("/threads"):
                return 500, {}
            return 200, {"id": "800"}

        result = speak(
            owner="kermit", text="hello", session=None, registry=registry(self.root), send=half, when=WHEN
        )
        self.assertFalse(result["ok"])
        self.assertFalse((self.root / "state" / "sessions").exists())

    def test_continuing_posts_in_that_session_and_does_not_greet_again(self) -> None:
        speak(
            owner="kermit", text="first", session=None, registry=registry(self.root), send=self.send, when=WHEN
        )
        self.sent.clear()

        def again(method, url, body):
            self.sent.append((method, url, body))
            return 200, {"id": "1"}

        result = speak(
            owner="kermit", text="second", session="900", registry=registry(self.root), send=again, when=WHEN
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["opened"])
        self.assertEqual(self.sent[0][1], "https://discord.com/api/v10/channels/900/messages")
        kinds = [t["kind"] for t in read_turns(self.root, "900")]
        self.assertEqual(kinds, ["greeting", "forge", "forge"])

    def test_the_house_reply_comes_back_and_another_sessions_reply_does_not(self) -> None:
        speak(
            owner="kermit", text="first", session=None, registry=registry(self.root), send=self.send, when=WHEN
        )
        waiting = hear(owner="kermit", session="900", registry=registry(self.root))
        self.assertTrue(waiting["waiting"])
        self.assertEqual(waiting["reply"], "")
        self.assertNotIn("the house said this", json.dumps(waiting))
        append_turn(self.root, "900", practitioner=".", reply="the house said this")
        other = self.root / "state" / "sessions" / "42.jsonl"
        other.write_text(json.dumps({"kind": "turn", "reply": "another hill"}) + "\n")
        heard = hear(owner="kermit", session="900", registry=registry(self.root))
        self.assertFalse(heard["waiting"])
        self.assertEqual(heard["reply"], "the house said this")
        self.assertNotIn("another hill", heard["reply"])
        self.assertNotIn("first", heard["reply"])
        refused = hear(owner="kermit", session="42", registry=registry(self.root))
        self.assertFalse(refused["ok"])
        self.assertNotIn("another hill", json.dumps(refused))

    def test_another_spirits_session_is_not_entered(self) -> None:
        path = self.root / "state" / "sessions"
        path.mkdir(parents=True)
        (path / "42.jsonl").write_text(json.dumps({"kind": "turn", "actor": "mage", "text": "summon"}) + "\n")
        result = speak(
            owner="kermit", text="hello", session="42", registry=registry(self.root), send=self.send, when=WHEN
        )
        self.assertFalse(result["ok"])
        self.assertEqual(self.sent, [])
        self.assertEqual(read_turns(self.root, "42")[0]["text"], "summon")

    def test_no_words_and_a_long_turn_do_not_post(self) -> None:
        for text in ("", "  ", "x" * (TEXT_MAX + 1)):
            self.sent.clear()
            result = speak(
                owner="kermit", text=text, session=None, registry=registry(self.root), send=self.send, when=WHEN
            )
            self.assertFalse(result["ok"], text[:12])
            self.assertEqual(self.sent, [])

    def test_the_channel_is_the_owners_one_magic_room(self) -> None:
        reg = registry(self.root)
        self.assertEqual(magic_channel_id(reg, "kermit"), "155")
        self.assertIsNone(magic_channel_id(reg, "ada"))
        two = registry(
            self.root,
            {
                "1": {"primitive": "magic", "mage": "kermit"},
                "2": {"type": "magic", "mage": "kermit"},
            },
        )
        self.assertIsNone(magic_channel_id(two, "kermit"))
        result = speak(owner="kermit", text="hello", session=None, registry=two, send=self.send, when=WHEN)
        self.assertFalse(result["ok"])
        self.assertEqual(self.sent, [])

    def test_a_missing_token_does_not_call_the_network(self) -> None:
        from spirit_link import _http_send

        with patch("spirit_link._token", return_value=""):
            with patch("spirit_link.urllib.request.urlopen", side_effect=AssertionError("network")):
                status, data = _http_send("POST", "https://discord.com/api/v10/channels/1/messages", {})
        self.assertEqual((status, data), (0, {}))

    def test_a_refusal_does_not_return_the_token(self) -> None:
        from spirit_link import _http_send

        def boom(*_a, **_k):
            raise urllib.error.HTTPError("https://discord.com", 403, "no", hdrs=None, fp=None)

        with patch("spirit_link._token", return_value="sekrit-token"):
            with patch("spirit_link.urllib.request.urlopen", boom):
                status, data = _http_send("POST", "https://discord.com/api/v10/channels/1/messages", {"content": "hi"})
        self.assertEqual(status, 403)
        self.assertNotIn("sekrit-token", json.dumps(data))


class AnswerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "state" / "sessions").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, eddy: str, turns: list[dict]) -> None:
        path = self.root / "state" / "sessions" / f"{eddy}.jsonl"
        path.write_text("".join(json.dumps(t) + "\n" for t in turns))

    def test_a_forge_turn_with_no_reply_needs_an_answer_and_a_reply_ends_it(self) -> None:
        from spirit_link import needs_answer, pending_eddies

        self.assertFalse(needs_answer([{"kind": "greeting", "actor": "forge", "text": "opened"}]))
        self._write("1", [{"kind": "forge", "actor": "forge", "text": "hello"}])
        self.assertEqual(pending_eddies(self.root), ["1"])
        self._write(
            "1",
            [
                {"kind": "forge", "actor": "forge", "text": "hello"},
                {"kind": "turn", "reply": "I am here."},
            ],
        )
        self.assertEqual(pending_eddies(self.root), [])

    async def test_a_pending_forge_message_is_handed_to_the_room_and_a_reply_is_not(self) -> None:
        from spirit_link import answer_pending

        self._write("900", [{"kind": "forge", "actor": "forge", "text": "hello"}])
        forge = type("M", (), {})()
        forge.content = "Forge:\nhello"
        forge.reference = None
        forge.message_reference = None
        quoted = type("M", (), {})()
        quoted.content = "Forge:\nhello"
        quoted.reference = object()
        quoted.message_reference = None
        seen = []

        class Hist:
            def __init__(self, items):
                self._i = 0
                self.items = items

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self.items):
                    raise StopAsyncIteration
                item = self.items[self._i]
                self._i += 1
                return item

        class Thread:
            def __init__(self, items):
                self.items = items

            def history(self, limit=30):
                return Hist(self.items)

        class Client:
            def __init__(self, items):
                self.items = items

            async def fetch_channel(self, eddy):
                return Thread(self.items)

        async def dispatch(message):
            seen.append(message)

        reg = registry(self.root)
        answered = await answer_pending(Client([quoted, forge]), registry=reg, dispatch=dispatch)
        self.assertEqual(answered, ["900"])
        self.assertEqual(seen, [forge])

        self._write("900", [{"kind": "turn", "reply": "done"}, {"kind": "forge", "actor": "forge", "text": "again"}])
        seen.clear()
        answered = await answer_pending(Client([quoted]), registry=reg, dispatch=dispatch)
        self.assertEqual(answered, [])
        self.assertEqual(seen, [])

    def test_the_room_is_told_who_a_forge_spirit_is_and_the_bot_answers_one_it_missed(self) -> None:
        import magic_prompt

        self.assertIn("begins with `Forge:`", magic_prompt.SUBSTRATE)
        self.assertIn("A change on that message still waits on him", magic_prompt.SUBSTRATE)
        repo = Path(__file__).resolve().parents[1]
        ready = (repo / "discord_bot.py").read_text().split("async def on_ready", 1)[1].split("\nasync def ", 1)[0]
        self.assertIn("answer_pending", ready)
        turn = (repo / "dialogue_turn.py").read_text()
        self.assertIn("set_forge_turn(is_forge_turn(message))", turn)


class NameTests(unittest.TestCase):
    def test_the_name_uses_the_local_day(self) -> None:
        self.assertEqual(thread_name(WHEN), "Forge · 16.10")


class GrantAddTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = GrantStore(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_an_older_house_grant_gains_speak_only_when_asked_and_a_reader_never_does(self) -> None:
        from mcp_access import operations

        original = operations.PROFILES["house"]
        operations.PROFILES["house"] = tuple(op for op in original if op != "spirit_speak")
        try:
            old, _ = self.store.create(principal="laptop cursor", owner="kermit", sources=[], profile="house")
        finally:
            operations.PROFILES["house"] = original
        reader, _ = self.store.create(principal="phone", owner="kermit", sources=[], profile="reader")
        self.assertNotIn("spirit_speak", self.store.get(old.id).operations)
        self.assertEqual(self.store.add_operation(reader.id, "spirit_speak"), "refused")
        self.assertNotIn("spirit_speak", self.store.get(reader.id).operations)
        self.assertEqual(self.store.add_operation(old.id, "not_an_operation"), "refused")
        self.assertEqual(self.store.add_operation(old.id, "spirit_speak"), "added")
        self.assertIn("spirit_speak", self.store.get(old.id).operations)
        self.assertEqual(self.store.add_operation(old.id, "spirit_speak"), "already")
        # The profile check is what refused the reader. Without it the add would land.
        with patch("mcp_access.grants.snapshot_for", return_value=["spirit_speak"]):
            self.assertEqual(self.store.add_operation(reader.id, "spirit_speak"), "added")
        self.assertIn("spirit_speak", self.store.get(reader.id).operations)


class SpeakToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.f = Fixture()

    def tearDown(self) -> None:
        self.f.close()

    def test_the_house_grant_offers_speak_and_a_reader_grant_does_not(self) -> None:
        house = self.f.session(self.f.grant(profile="house", sources=[])[0])
        init = call(house, "initialize", {"protocolVersion": "2025-06-18"})["result"]
        names = [t["name"] for t in call(house, "tools/list")["result"]["tools"]]
        self.assertIn("speak", names)
        self.assertIn("hear", names)
        speak_tool = next(t for t in call(house, "tools/list")["result"]["tools"] if t["name"] == "speak")
        self.assertFalse(speak_tool["annotations"]["readOnlyHint"])
        self.assertTrue(speak_tool["annotations"]["openWorldHint"])
        self.assertIn("`speak(", init["instructions"])
        self.assertIn("no terminal", init["instructions"])
        self.assertIn("hear brings the house spirit's reply back", init["instructions"])
        self.assertNotIn("cannot write", init["instructions"])
        reader = self.f.session(self.f.grant(profile="reader", sources=[])[0])
        reader_init = call(reader, "initialize", {"protocolVersion": "2025-06-18"})["result"]
        reader_names = [t["name"] for t in call(reader, "tools/list")["result"]["tools"]]
        self.assertNotIn("speak", reader_names)
        self.assertNotIn("hear", reader_names)
        self.assertIn("cannot write", reader_init["instructions"])
        refused = call(reader, "tools/call", {"name": "speak", "arguments": {"text": "hello"}})
        self.assertIn("error", refused)

    def test_speak_returns_the_session_and_a_failed_delivery_is_an_error(self) -> None:
        house = self.f.session(self.f.grant(profile="house", sources=[])[0])
        with patch("spirit_link.deliver_live", return_value={"ok": True, "session": "900", "opened": True, "kept": "kept"}):
            reply = call(house, "tools/call", {"name": "speak", "arguments": {"text": "hello"}})
        self.assertIn("900", reply["result"]["content"][0]["text"])
        with patch("spirit_link.deliver_live", return_value={"ok": False, "error": "the house could not open the session"}):
            failed = call(house, "tools/call", {"name": "speak", "arguments": {"text": "hello"}})
        self.assertTrue(failed["result"]["isError"])

    def test_hear_returns_the_reply_and_a_reader_cannot_call_it(self) -> None:
        house = self.f.session(self.f.grant(profile="house", sources=[])[0])
        with patch(
            "spirit_link.hear_live",
            return_value={"ok": True, "session": "900", "reply": "the house said this", "waiting": False},
        ):
            reply = call(house, "tools/call", {"name": "hear", "arguments": {"session": "900"}})
        self.assertIn("the house said this", reply["result"]["content"][0]["text"])
        reader = self.f.session(self.f.grant(profile="reader", sources=[])[0])
        refused = call(reader, "tools/call", {"name": "hear", "arguments": {"session": "900"}})
        self.assertIn("error", refused)


if __name__ == "__main__":
    unittest.main()
