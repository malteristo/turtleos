"""`!mcp` in the turtleOS design language: who can read your context, what your house uses for you.

docs/design/mcp-list-v2.md, criteria 1-5 and 7. Each guard has a positive control; the
owner guards and the "ended is ended" check carry the mutation the same test must catch.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import discord
except ImportError:  # system Python without discord.py: skip, never pass by omission
    raise unittest.SkipTest("needs discord.py")
from aiohttp.test_utils import TestClient, TestServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import outgoing_connections as door  # noqa: E402
import ui_kit  # noqa: E402
from mcp_access.audit import AUDIT_REL  # noqa: E402
from mcp_access.reveal import RevealError, end, friendly_program, listed_grants, set_open  # noqa: E402
from mcp_access.server import build_app  # noqa: E402
from mcp_list_ui import render  # noqa: E402
from tests.test_mcp_workshop import ROOM_CANARY, Shop  # noqa: E402


def _interaction(user_id: int, *, message_id: int = 900):
    response = SimpleNamespace(send_message=mock.AsyncMock(), edit_message=mock.AsyncMock())
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=response,
        client=mock.Mock(),
        message=SimpleNamespace(id=message_id),
        data={},
    )


def buttons(view) -> list[discord.ui.Button]:
    return [c for c in view.walk_children() if isinstance(c, discord.ui.Button)]


def button(view, label: str) -> discord.ui.Button:
    return next(b for b in buttons(view) if b.label == label)


def sections(view) -> list[dict]:
    return [n for n in ui_kit._walk(view.to_components()) if n.get("type") == 9]


def row_for(view, name: str) -> dict:
    """The Section whose text names this row."""
    return next(s for s in sections(view) if f"**{name}**" in s["components"][0]["content"])


def alltext(view) -> str:
    return "\n".join(ui_kit.texts(view))


class ListFixture(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.shop = Shop()
        self.bob_root = self.shop.base / "bob"
        self.bob_root.mkdir()
        self.shop.registry["mages"]["alice"]["runtime_dir"] = str(self.shop.root)
        self.shop.registry["mages"]["bob"] = {
            "practice_dir": str(self.bob_root),
            "discord_id": "222",
            "runtime_dir": str(self.bob_root),
        }
        health = self.shop.base / "health"
        health.mkdir()
        self.shop.registry["spaces"] = {"health-alice": {"subject": "alice", "practice_dir": str(health)}}
        self.grant, self.token = self.shop.store.create(principal="laptop cursor", owner="alice", sources=[], profile="house")
        self.bobs, _ = self.shop.store.create(principal="bobs phone", owner="bob", sources=[], profile="house")
        self.env = mock.patch.dict(os.environ, {"TURTLE_MCP_STATE": str(self.shop.state)})
        self.env.start()
        door.bind(door.Shell(lambda: self.shop.registry, lambda: "alice", lambda: str(self.shop.root), lambda: []))

    def tearDown(self):
        door.bind(None)
        door._told_unbound = False
        self.env.stop()
        self.shop.close()

    def view(self, **kw):
        return render("alice", self.shop.root, self.shop.registry, **kw)

    def audit_lines(self, root: Path) -> list[dict]:
        path = root / AUDIT_REL
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class RowsTests(ListFixture):
    async def test_each_thing_has_its_state_and_its_own_button_on_one_row(self):
        view = self.view()
        notes = row_for(view, "Notes")
        self.assertIn("closed", notes["components"][0]["content"])
        self.assertEqual(notes["accessory"]["label"], "Open")
        self.assertEqual(row_for(view, "Health picture")["accessory"]["label"], "Open")
        self.assertEqual(row_for(view, "Practice")["accessory"]["label"], "Open")
        set_open(self.shop.store, self.grant.id, "alice", opened=True, registry=self.shop.registry)
        notes = row_for(self.view(), "Notes")
        self.assertIn("open", notes["components"][0]["content"])
        self.assertEqual(notes["accessory"]["label"], "Close", "positive control: the row follows the grant")

    async def test_the_consequence_is_said_in_words_and_names_the_program_as_he_does(self):
        self.shop.store.remember_mcp_client(self.grant.id, "s1", "cursor-vscode", "1.0")
        set_open(self.shop.store, self.grant.id, "alice", opened=True, registry=self.shop.registry)
        view = self.view()
        text = alltext(view)
        self.assertIn("laptop cursor · Cursor", text)
        self.assertNotIn("cursor-vscode", text)
        self.assertIn("Cursor can read them", row_for(view, "Notes")["components"][0]["content"])
        self.assertIn("Hidden from Cursor", row_for(view, "Practice")["components"][0]["content"])
        self.assertEqual(friendly_program("cursor-vscode"), "Cursor")
        self.assertEqual(friendly_program("some-new-client"), "some-new-client", "an unknown name is shown, not hidden")

    async def test_time_is_a_live_relative_token_and_a_missing_one_does_not_claim_a_time(self):
        self.assertIn("Has not asked yet", alltext(self.view()))
        self.shop.store.update(self.grant.id, calls=3)
        self.assertIn("the time was not kept", alltext(self.view()))
        self.shop.store.count(self.grant.id, refused=False)
        text = alltext(self.view())
        self.assertRegex(text, r"Last asked <t:\d+:R>")
        self.assertNotIn("ago", text, "a frozen string would go stale")

    async def test_german_has_the_same_surface(self):
        self.shop.registry["mages"]["alice"]["locale"] = "de"
        view = self.view()
        text = alltext(view)
        self.assertIn("Wer deinen Kontext lesen kann", text)
        self.assertIn("Notizen", text)
        self.assertEqual(row_for(view, "Notizen")["accessory"]["label"], "Öffnen")
        self.assertEqual(ui_kit.violations(view), [])

    async def test_only_the_owners_connections_are_listed(self):
        mine = [g.id for g in listed_grants(self.shop.store, "alice", self.shop.registry)]
        self.assertEqual(mine, [self.grant.id], "positive control: the owner's own is listed")
        self.assertNotIn("bobs phone", alltext(self.view()))
        theirs = [g.id for g in listed_grants(self.shop.store, "bob", self.shop.registry)]
        self.assertEqual(theirs, [self.bobs.id])

    async def test_an_ended_or_expired_connection_is_not_listed_and_the_empty_state_says_how_it_fills(self):
        end(self.shop.store, self.grant.id, owner="alice", registry=self.shop.registry)
        self.shop.store.create(principal="old", owner="alice", sources=[], profile="house", ttl_days=-1)
        text = alltext(self.view())
        self.assertNotIn("laptop cursor", text)
        self.assertNotIn("old", text.replace("hold", ""))
        self.assertIn("Nothing is connected. To connect a program, ask your Spirit", text)
        self.assertFalse(any(b.label in ("Open", "Close", "End connection") for b in buttons(self.view())))

    async def test_each_connection_is_its_own_card_and_overflow_is_counted_not_dropped(self):
        for n in range(5):
            self.shop.store.create(principal=f"extra {n}", owner="alice", sources=[], profile="house")
        view = self.view()
        text = alltext(view)
        self.assertEqual(sum(1 for b in buttons(view) if b.label == "End connection"), 2, "two cards fit the budget")
        self.assertIn("4 more connection(s) are not shown", text)
        self.assertEqual(ui_kit.violations(view), [])
        self.assertLessEqual(ui_kit.count_parts(view), ui_kit.PART_BUDGET)

    async def test_a_workshop_only_connection_lists_only_its_kind(self):
        self.shop.store.create(principal="shop", owner="alice", sources=[], profile="workshop-reader")
        view = self.view()
        shop_cards = [c for c in ui_kit._walk(view.to_components()) if c.get("type") == 17]
        shop = next(c for c in shop_cards if "shop" in c["components"][0].get("content", "").split("\n")[0])
        names = [n["components"][0]["content"] for n in shop["components"] if n.get("type") == 9]
        self.assertEqual(len(names), 1)
        self.assertIn("Practice", names[0])


class ServicesTests(ListFixture):
    async def test_a_checked_time_is_set_off_from_the_state_and_there_is_no_second_only_you_line(self):
        door.write_account(self.shop.root, "alice", "ada_name")
        door._write_health(self.shop.root, "alice", status="ready", tries=0, raised=False, now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        text = alltext(self.view())
        self.assertRegex(text, r"ready · checked <t:\d+:R>")
        self.assertNotIn("Only you see this", text, "Discord says it already")

    async def test_x_says_its_state_and_its_room_and_is_not_a_table(self):
        view = self.view()
        text = alltext(view)
        self.assertIn("not signed in", text)
        self.assertIn(f"In {door.ANSWERS_IN} only", text)
        self.assertNotIn("```", text, "criterion 4: no code-block table on a phone")
        self.assertFalse(any(b.label in ("Pause X", "Remove X") for b in buttons(view)), "nothing to pause yet")
        door.write_account(self.shop.root, "alice", "ada_name")
        view = self.view()
        self.assertIn("not checked yet", alltext(view))
        self.assertEqual(row_for(view, "X")["accessory"]["label"], "Pause X")
        self.assertIn("Remove X", [b.label for b in buttons(view)])
        self.assertNotIn("ada_name", alltext(view))

    async def test_the_room_x_answers_in_is_the_one_the_door_enforces(self):
        self.assertTrue(door.connection_offered(door.ANSWERS_IN))
        self.assertFalse(door.connection_offered("family"), "positive control")

    async def test_pausing_changes_the_row_in_place_and_resuming_puts_it_back(self):
        door.write_account(self.shop.root, "alice", "ada_name")
        pause = button(self.view(), "Pause X")
        press = _interaction(111)
        await pause.callback(press)
        press.response.send_message.assert_not_awaited()
        edited = press.response.edit_message.await_args.kwargs["view"]
        self.assertIn("paused", alltext(edited))
        self.assertEqual(row_for(edited, "X")["accessory"]["label"], "Resume X")
        self.assertTrue(door.paused_for("alice", self.shop.root))
        await button(edited, "Resume X").callback(_interaction(111))
        self.assertFalse(door.paused_for("alice", self.shop.root))

    async def test_removing_x_asks_once_then_removes(self):
        import mcp_list_ui as ui

        door.write_account(self.shop.root, "alice", "ada_name")
        ask = _interaction(111)
        await button(self.view(), "Remove X").callback(ask)
        self.assertTrue(door.account_for("alice", self.shop.root), "asking removes nothing")
        asked = ask.response.edit_message.await_args.kwargs["view"]
        self.assertIn("Remove X?", alltext(asked))
        self.assertEqual([b.label for b in buttons(asked)], ["Keep", "Remove it"])
        kept = _interaction(111)
        await button(asked, "Keep").callback(kept)
        self.assertTrue(door.account_for("alice", self.shop.root))
        done = _interaction(111)
        with mock.patch("outgoing_x.clear_login", return_value=True):
            await button(asked, "Remove it").callback(done)
        self.assertIsNone(door.account_for("alice", self.shop.root))
        self.assertIn("X is removed.", alltext(done.response.edit_message.await_args.kwargs["view"]))
        _ = ui


class OwnerActsTests(ListFixture):
    async def test_the_last_used_time_is_written_by_a_call_and_carries_no_content(self):
        self.assertNotIn("last_used", self.shop.store.get(self.grant.id).extra)
        self.shop.store.count(self.grant.id, refused=False)
        stamped = self.shop.store.get(self.grant.id)
        self.assertIn("last_used", stamped.extra)
        self.assertNotIn(ROOM_CANARY, json.dumps(stamped.public()))

    async def test_ending_stops_the_connection_and_only_the_owner_can_end_it(self):
        with self.assertRaises(RevealError):
            end(self.shop.store, self.grant.id, owner="bob", registry=self.shop.registry)
        self.assertEqual(self.shop.store.get(self.grant.id).status, "active", "mutation: dropping the owner check ends it")
        ended = end(self.shop.store, self.grant.id, owner="alice", registry=self.shop.registry)
        self.assertEqual(ended.status, "revoked")
        with self.assertRaises(RevealError):
            end(self.shop.store, self.grant.id, owner="alice", registry=self.shop.registry)

    async def test_opening_and_closing_is_refused_for_someone_elses_connection(self):
        with self.assertRaises(RevealError) as caught:
            set_open(self.shop.store, self.grant.id, "alice", opened=True, registry=self.shop.registry, owner="bob")
        self.assertEqual(caught.exception.code, "inactive")
        self.assertEqual(self.shop.store.get(self.grant.id).sources, [])
        set_open(self.shop.store, self.grant.id, "alice", opened=True, registry=self.shop.registry, owner="alice")
        self.assertEqual(self.shop.store.get(self.grant.id).sources, ["alice"], "positive control")

    async def test_each_act_is_one_line_in_the_owners_audit_and_names_no_source(self):
        set_open(self.shop.store, self.grant.id, "alice", opened=True, registry=self.shop.registry)
        set_open(self.shop.store, self.grant.id, "alice", opened=False, registry=self.shop.registry)
        end(self.shop.store, self.grant.id, owner="alice", registry=self.shop.registry)
        lines = self.audit_lines(self.shop.root)
        self.assertEqual([line["operation"] for line in lines], ["owner_open", "owner_close", "owner_end"])
        self.assertTrue(all(line["grant"] == self.grant.id and line["decision"] == "done" for line in lines))
        raw = (self.shop.root / AUDIT_REL).read_text(encoding="utf-8")
        for hidden in ("health-alice", "alice-workshop"):
            self.assertNotIn(hidden, raw)
        self.assertEqual(self.audit_lines(self.bob_root), [], "another member's audit is untouched")


class EndedIsEndedOverHttpTests(ListFixture):
    async def test_the_next_request_after_ending_is_refused(self):
        client = TestClient(TestServer(build_app(self.shop.store, lambda: self.shop.registry)))
        await client.start_server()
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Tailscale-User-Login": "alice@example.com",
                "X-Forwarded-For": "203.0.113.7",
            }
            body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            self.assertEqual((await client.post("/mcp", json=body, headers=headers)).status, 200)
            end(self.shop.store, self.grant.id, owner="alice", registry=self.shop.registry)
            self.assertEqual((await client.post("/mcp", json=body, headers=headers)).status, 401)
        finally:
            await client.close()


class PressTests(ListFixture):
    async def test_pressing_open_changes_the_row_in_place_and_the_next_request_and_the_card(self):
        import mcp_list_ui as ui

        view = self.view()
        interaction = _interaction(111)
        with mock.patch.object(ui, "refresh_card", mock.AsyncMock()) as card:
            await row_for_button(view, "Notes").callback(interaction)
        self.assertEqual(self.shop.store.get(self.grant.id).sources, ["alice"])
        interaction.response.send_message.assert_not_awaited()  # criterion 5: nothing else posts
        self.assertEqual(set(interaction.response.edit_message.await_args.kwargs), {"view"})
        edited = interaction.response.edit_message.await_args.kwargs["view"]
        self.assertEqual(row_for(edited, "Notes")["accessory"]["label"], "Close")
        card.assert_awaited_once()
        with mock.patch.object(ui, "refresh_card", mock.AsyncMock()):
            await row_for_button(edited, "Notes").callback(_interaction(111))
        self.assertEqual(self.shop.store.get(self.grant.id).sources, [])

    async def test_someone_elses_press_changes_nothing(self):
        import mcp_list_ui as ui

        view = self.view()
        other = _interaction(222)  # bob: a member of the house, not the owner of this connection
        with mock.patch.object(ui, "refresh_card", mock.AsyncMock()) as card:
            await row_for_button(view, "Notes").callback(other)
        self.assertEqual(self.shop.store.get(self.grant.id).sources, [], "mutation: dropping the owner check opens it")
        other.response.edit_message.assert_not_awaited()
        self.assertTrue(other.response.send_message.await_args.kwargs["ephemeral"])
        card.assert_not_awaited()
        stranger = _interaction(999)
        await row_for_button(view, "Notes").callback(stranger)
        self.assertEqual(self.shop.store.get(self.grant.id).sources, [])
        self.assertIn("member of the house", stranger.response.send_message.await_args.args[0])

    async def test_ending_asks_once_with_the_consequence_then_ends_and_the_card_says_so(self):
        import mcp_list_ui as ui

        view = self.view()
        ask = _interaction(111)
        await button(view, "End connection").callback(ask)
        self.assertEqual(self.shop.store.get(self.grant.id).status, "active", "asking does not end")
        confirm = ask.response.edit_message.await_args.kwargs["view"]
        text = alltext(confirm)
        self.assertIn("End laptop cursor?", text)
        self.assertIn("It stops reading at once and has to be connected again.", text)
        self.assertEqual([b.label for b in buttons(confirm)], ["Keep", "End it"], "red is last")
        self.assertEqual(ui_kit.violations(confirm), [])

        keep = _interaction(111)
        await button(confirm, "Keep").callback(keep)
        self.assertEqual(self.shop.store.get(self.grant.id).status, "active")
        self.assertIn("laptop cursor", alltext(keep.response.edit_message.await_args.kwargs["view"]))

        done = _interaction(111)
        with mock.patch.object(ui, "refresh_card", mock.AsyncMock()) as card:
            await button(confirm, "End it").callback(done)
        self.assertEqual(self.shop.store.get(self.grant.id).status, "revoked")
        self.assertIn("laptop cursor is ended.", alltext(done.response.edit_message.await_args.kwargs["view"]))
        self.assertEqual(card.await_args.kwargs["ended_text"], "laptop cursor is ended.")

    async def test_someone_else_cannot_end_it_even_with_the_buttons_in_hand(self):
        import mcp_list_ui as ui

        asked = _interaction(222)
        await button(self.view(), "End connection").callback(asked)
        asked.response.edit_message.assert_not_awaited()
        direct = _interaction(222)
        await ui._end(direct, self.grant.id)
        self.assertEqual(self.shop.store.get(self.grant.id).status, "active")
        self.assertEqual(self.shop.store.get(self.bobs.id).status, "active")

    async def test_the_public_button_posts_one_private_layout_reply(self):
        from outgoing_connect_ui import OutgoingConnectionsView

        interaction = _interaction(111)
        await OutgoingConnectionsView()._on_list(interaction)
        interaction.response.send_message.assert_awaited_once()
        sent = interaction.response.send_message.await_args
        self.assertTrue(sent.kwargs["ephemeral"])
        self.assertIsInstance(sent.kwargs["view"], discord.ui.LayoutView)
        self.assertEqual(sent.args, (), "a layout message carries no plain content")
        self.assertIn("Who can read your context", alltext(sent.kwargs["view"]))
        self.assertIn("What your house uses for you", alltext(sent.kwargs["view"]))


def row_for_button(view, name: str) -> discord.ui.Button:
    """The button on the row that names this thing, found by its custom id, not its label."""
    node = row_for(view, name)
    return next(b for b in buttons(view) if b.custom_id == node["accessory"]["custom_id"])


class CardFixture(ListFixture):
    """A connection that was picked up, and a fake Discord that remembers what was sent and edited."""

    def accepted(self, *, card: int | None = None):
        from mcp_access import offers

        made = offers.create(
            self.shop.root, owner="alice", principal="laptop cursor", sources=[], profile="house", url="https://h:8443/mcp"
        )
        offers.mark_ready(self.shop.root, made.id)
        offer, grant, _token = offers.pickup(self.shop.root, self.shop.store)
        offers.mark_posted(self.shop.root, offer.id, channel_id=66, message_id=55)
        if card:
            offers.mark_card(self.shop.root, offer.id, card)
        return next(o for o in offers.accepted(self.shop.root) if o.id == offer.id), grant

    def discord(self):
        self.old = SimpleNamespace(edit=mock.AsyncMock())
        self.card = SimpleNamespace(edit=mock.AsyncMock())
        messages = {55: self.old, 77: self.card}
        self.channel = SimpleNamespace(
            send=mock.AsyncMock(return_value=SimpleNamespace(id=77)),
            fetch_message=mock.AsyncMock(side_effect=lambda mid: messages[mid]),
        )
        return SimpleNamespace(get_channel=lambda _id: self.channel, add_view=mock.Mock())

    def stored_card(self):
        from mcp_access import offers

        return offers.accepted(self.shop.root)[0].card_message_id


class HomeCardTests(CardFixture):
    async def test_the_card_names_the_kinds_not_the_identifiers_in_both_languages(self):
        from mcp_reveal_ui import card_view

        _offer, grant = self.accepted()
        for locale, title, practice in (("en", "laptop cursor is connected", "Practice"), ("de", "laptop cursor ist verbunden", "Praxis")):
            view = card_view(grant, self.shop.registry, locale)
            text = alltext(view)
            self.assertIn(title, text)
            self.assertIn(practice, text)
            for secret in ("alice-workshop", "health-alice", grant.id):
                self.assertNotIn(secret, text)
            self.assertEqual(ui_kit.violations(view, forbidden=("alice-workshop", "health-alice", grant.id, "house")), [], locale)
        view = card_view(grant, self.shop.registry, "en")
        self.assertEqual([b.label for b in buttons(view)], ["Open", "Open", "Open"])
        self.assertRegex(alltext(view), r"Until <t:\d+:D>")

    async def test_the_card_still_answers_after_a_restart(self):
        from mcp_reveal_ui import CUSTOM_ID_PREFIX, card_view

        _offer, grant = self.accepted()
        view = card_view(grant, self.shop.registry, "en")
        self.assertTrue(view.is_persistent(), "discord refuses add_view for a card that cannot outlive the process")
        self.assertTrue(all(b.custom_id.startswith(CUSTOM_ID_PREFIX) for b in buttons(view)))

    async def test_the_owner_presses_and_the_card_changes_in_place(self):
        from mcp_reveal_ui import card_view

        _offer, grant = self.accepted()
        view = card_view(grant, self.shop.registry, "en")
        press = _interaction(111, message_id=77)
        await row_for_button(view, "Notes").callback(press)
        self.assertIn("alice", self.shop.store.get(grant.id).sources)
        edited = press.response.edit_message.await_args.kwargs["view"]
        self.assertEqual(row_for(edited, "Notes")["accessory"]["label"], "Close")
        self.assertIn("open", row_for(edited, "Notes")["components"][0]["content"])
        press.client.add_view.assert_called_once()
        self.assertEqual(press.client.add_view.call_args.kwargs, {"message_id": 77})

    async def test_nobody_else_presses_it(self):
        from mcp_reveal_ui import card_view

        _offer, grant = self.accepted()
        view = card_view(grant, self.shop.registry, "en")
        for stranger in (222, 999):
            press = _interaction(stranger, message_id=77)
            await row_for_button(view, "Notes").callback(press)
            press.response.edit_message.assert_not_awaited()
            self.assertTrue(press.response.send_message.await_args.kwargs["ephemeral"])
        self.assertNotIn("alice", self.shop.store.get(grant.id).sources)

    async def test_the_first_card_goes_under_the_message_and_the_message_keeps_the_receipt(self):
        from mcp_reveal_ui import show_card

        offer, grant = self.accepted()
        client = self.discord()
        await show_card(client, self.shop.registry, offer, grant, said="**Connected**")
        self.channel.send.assert_awaited_once()
        self.assertIn("laptop cursor is connected", alltext(self.channel.send.await_args.kwargs["view"]))
        self.assertEqual(self.stored_card(), 77)
        self.assertEqual(self.old.edit.await_args.kwargs, {"content": "**Connected**", "view": None})
        client.add_view.assert_called_once()
        await show_card(client, self.shop.registry, offer, grant, said="**Connected**")
        self.channel.send.assert_awaited_once()  # a card that exists is never posted twice

    async def test_a_change_from_the_list_edits_the_card_not_the_message(self):
        from mcp_reveal_ui import refresh_card

        self.accepted(card=77)
        grant = self.shop.store.get(self.accepted_grant())
        client = self.discord()
        set_open(self.shop.store, grant.id, "alice", opened=True, registry=self.shop.registry)
        grant = self.shop.store.get(grant.id)
        self.assertTrue(await refresh_card(client, self.shop.registry, grant))
        text = alltext(self.card.edit.await_args.kwargs["view"])
        self.assertIn("Notes", text)
        self.assertNotIn(grant.id, text)
        self.old.edit.assert_not_awaited()
        self.channel.send.assert_not_awaited()
        self.assertFalse(await refresh_card(client, self.shop.registry, self.shop.store.get(self.bobs.id)))

    async def test_an_ended_connection_says_so_on_its_card(self):
        from mcp_reveal_ui import refresh_card

        self.accepted(card=77)
        grant = self.shop.store.get(self.accepted_grant())
        client = self.discord()
        await refresh_card(client, self.shop.registry, grant, ended_text="laptop cursor is ended.")
        view = self.card.edit.await_args.kwargs["view"]
        self.assertEqual(buttons(view), [], "an ended card has nothing left to press")
        self.assertIn("laptop cursor is ended.", alltext(view))

    async def test_a_card_from_before_is_moved_once_not_edited_into_a_shape_it_cannot_take(self):
        from mcp_reveal_ui import refresh_card, restore_reveal_cards

        offer, grant = self.accepted()  # no card yet: the old kind of message
        client = self.discord()
        self.assertEqual(await restore_reveal_cards(client, lambda: self.shop.registry), 1)
        self.assertEqual(self.stored_card(), 77)
        self.assertIn("card below", self.old.edit.await_args.kwargs["content"])
        self.assertIsNone(self.old.edit.await_args.kwargs["view"])
        self.assertEqual(await restore_reveal_cards(client, lambda: self.shop.registry), 1)
        self.channel.send.assert_awaited_once()
        self.assertEqual(client.add_view.call_args.kwargs, {"message_id": 77}, "second start re-arms the card, it does not repost")
        # a change before the move is also a move, never an edit of the old message into layout
        other = self.discord()
        self.assertTrue(await refresh_card(other, self.shop.registry, grant))
        self.card.edit.assert_awaited()

    async def test_announcing_a_pickup_posts_the_card_and_marks_the_message_connected(self):
        from mcp_access import offers
        import mcp_connect_ui

        offer, grant = self.accepted()
        client = self.discord()
        with mock.patch("offer_ledger.record_for_channel"):
            done = await mcp_connect_ui.announce_pickups(client, lambda: self.shop.registry)
        self.assertEqual(done, 1)
        self.assertIn("**Connected**", self.old.edit.await_args.kwargs["content"])
        self.assertEqual(self.stored_card(), 77)
        self.assertTrue(offers.accepted(self.shop.root)[0].announced)

    def accepted_grant(self) -> str:
        from mcp_access import offers

        return offers.accepted(self.shop.root)[0].grant


if __name__ == "__main__":
    unittest.main()
