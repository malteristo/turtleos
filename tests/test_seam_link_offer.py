"""The link offer, end to end through the transport seam.

Before 2026-08-14 `runtime/messages.py` had **zero production importers**: 184
lines of well-tested, carefully documented value objects that nothing in the
running system ever constructed. The design chapter said the seam had shipped. An
outside reviewer found the gap, and `tests/test_runtime_adoption.py` was written to
keep the number honest.

This file is the other half — not "the seam exists" but "a practitioner-visible
feature goes through it":

    discord.Message → IncomingMessage → runtime decides → OutgoingMessage
                    → discord_render posts it

The link offer was chosen because its decision (*what is this link, what should the
button be called*) was already transport-free and already living in `runtime/`,
while the posting was hand-rolled Discord. So this slice moved a boundary that was
half-drawn rather than inventing one.

Two things are protected here that a "does it work" test would miss:

* **The button `custom_id` did not change.** Discord matches persistent views by
  `custom_id`, so a new format leaves every already-posted offer with a dead
  button — a regression the practitioner meets before anyone else does.
* **A failed post records no offer.** The ledger's whole job is measuring take
  rate; counting an offer nobody could see poisons the denominator.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# A stub whose `discord.ui.View` is a real class. Without it `OutgoingView` is not a
# class at all but a mock, and constructing it fails inside `unittest.mock` with a
# StopIteration that names nothing. See `tests/discord_stub.py` — no view class in
# this codebase had ever had its constructor executed by a test.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from tests.discord_stub import install_discord_stub  # noqa: E402

discord = install_discord_stub(reload=("discord_render",))

from runtime.adapters.discord import incoming_from_discord  # noqa: E402
from runtime.link_offers import link_offer_for  # noqa: E402
from runtime.messages import IncomingMessage, OutgoingMessage  # noqa: E402


def _message(
    *,
    content: str = "some text",
    message_id: int = 555,
    channel_id: int = 42,
    parent_id: int | None = None,
    author_id: int = 7,
    is_bot: bool = False,
):
    msg = MagicMock()
    msg.content = content
    msg.id = message_id
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.channel.parent_id = parent_id
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = is_bot
    msg.attachments = []
    msg.reference = None
    return msg


class AdapterTests(unittest.TestCase):
    """Discord message in, transport-agnostic turn out."""

    def test_it_builds_an_incoming_message(self) -> None:
        incoming = incoming_from_discord(
            _message(content="look at this https://example.com/a"),
            urls=("https://example.com/a",),
        )
        self.assertIsInstance(incoming, IncomingMessage)
        self.assertEqual(incoming.practitioner_id, "7")
        self.assertEqual(incoming.message_id, "555")
        self.assertEqual(incoming.urls, ("https://example.com/a",))
        self.assertEqual(incoming.transport, "discord")
        self.assertFalse(incoming.is_from_bot)

    def test_a_thread_resolves_conversation_to_the_thread(self) -> None:
        """The eight-day ledger bug was a thread/parent confusion. Pin the shape."""
        incoming = incoming_from_discord(_message(channel_id=99, parent_id=42))
        self.assertEqual(incoming.thread_id, "99")
        self.assertEqual(incoming.channel_id, "42", "the channel that owns the thread")
        self.assertEqual(incoming.conversation_id, "99", "where the turn belongs")

    def test_a_plain_channel_has_no_thread(self) -> None:
        incoming = incoming_from_discord(_message(channel_id=42, parent_id=None))
        self.assertIsNone(incoming.thread_id)
        self.assertEqual(incoming.conversation_id, "42")

    def test_it_imports_no_discord_types(self) -> None:
        """Duck-typed on purpose: a plain object must be enough."""

        class Bare:
            content = "hi"
            id = 1

            class channel:  # noqa: N801
                id = 2
                parent_id = None

            class author:  # noqa: N801
                id = 3
                bot = False

            attachments = ()
            reference = None

        incoming = incoming_from_discord(Bare())
        self.assertEqual(incoming.practitioner_id, "3")

    def test_a_message_with_no_author_still_produces_a_turn(self) -> None:
        """`practitioner_id` is required by the value object; a crash here is worse."""
        msg = _message()
        msg.author = None
        incoming = incoming_from_discord(msg)
        self.assertEqual(incoming.practitioner_id, "unknown-author")

    def test_discord_declares_its_affordances(self) -> None:
        incoming = incoming_from_discord(_message())
        self.assertTrue(incoming.can("buttons"))
        self.assertTrue(incoming.can("threads"))
        self.assertFalse(incoming.can("voice_out"))


class RuntimeDecisionTests(unittest.TestCase):
    """The offer's words and label, with no Discord object in sight."""

    def _incoming(self, urls, text="a long message"):
        return IncomingMessage(
            text=text, practitioner_id="7", channel_id="42", urls=tuple(urls)
        )

    def test_a_video_offers_its_transcript(self) -> None:
        outgoing = link_offer_for(self._incoming(["https://youtu.be/abc123"]))
        self.assertIsInstance(outgoing, OutgoingMessage)
        self.assertEqual(outgoing.actions[0].label, "Fetch transcript")
        self.assertEqual(outgoing.actions[0].key, "read_youtube")

    def test_an_article_offers_its_text(self) -> None:
        outgoing = link_offer_for(self._incoming(["https://example.com/essay"]))
        self.assertEqual(outgoing.actions[0].label, "Read article")

    def test_the_action_carries_the_urls_for_the_handler(self) -> None:
        outgoing = link_offer_for(self._incoming(["https://youtu.be/abc"]))
        self.assertEqual(outgoing.actions[0].payload["urls"], ("https://youtu.be/abc",))

    def test_no_urls_means_no_offer(self) -> None:
        self.assertIsNone(link_offer_for(self._incoming([])))

    def test_a_discord_link_is_not_an_article_someone_shared(self) -> None:
        self.assertIsNone(
            link_offer_for(self._incoming(["https://discord.com/channels/1/2/3"]))
        )

    def test_the_offer_says_ignoring_is_fine(self) -> None:
        """There is no Skip button, so the text has to carry the permission."""
        outgoing = link_offer_for(self._incoming(["https://example.com/x"]))
        self.assertIn("Ignoring this is fine", outgoing.text)

    def test_a_surface_without_buttons_gets_no_actions(self) -> None:
        incoming = IncomingMessage(
            text="x",
            practitioner_id="7",
            channel_id="42",
            urls=("https://example.com/x",),
            affordances=frozenset({"voice_out"}),
        )
        outgoing = link_offer_for(incoming)
        self.assertEqual(outgoing.renderable_actions(incoming), ())
        self.assertTrue(outgoing.actions, "the offer still exists; only rendering differs")


class ProductionPathTests(unittest.IsolatedAsyncioTestCase):
    """`post_link_offer` must actually construct the value objects.

    A seam nothing crosses is the thing this slice existed to fix, so this asserts
    the objects are built — not merely that a message got posted.
    """

    async def _post(self, *, send_result=None, send_raises=False, urls=None):
        import link_read

        channel = MagicMock()
        channel.id = 42
        if send_raises:
            channel.send = AsyncMock(side_effect=discord.HTTPException("boom"))
        else:
            channel.send = AsyncMock(return_value=send_result or MagicMock())
        bot = MagicMock()
        bot.add_view = MagicMock()

        recorded: list[dict] = []
        seen: dict[str, object] = {}

        real_incoming = incoming_from_discord

        def spy_incoming(message, **kwargs):
            built = real_incoming(message, **kwargs)
            seen["incoming"] = built
            return built

        real_offer = link_offer_for

        def spy_offer(incoming):
            built = real_offer(incoming)
            seen["outgoing"] = built
            return built

        with patch("runtime.adapters.discord.incoming_from_discord", spy_incoming), patch(
            "runtime.link_offers.link_offer_for", spy_offer
        ), patch(
            "offer_ledger.record_for_channel",
            lambda channel_id, **kw: recorded.append({"channel_id": channel_id, **kw}) or True,
        ), patch(
            "bar_anchor.ensure_channel_bars", new=AsyncMock()
        ):
            await link_read.post_link_offer(
                channel,
                _message(),
                urls if urls is not None else ["https://youtu.be/abc123"],
                bot,
            )
        return channel, bot, recorded, seen

    async def test_the_offer_is_built_from_the_value_objects(self) -> None:
        _channel, _bot, _recorded, seen = await self._post()
        self.assertIsInstance(seen.get("incoming"), IncomingMessage)
        self.assertIsInstance(seen.get("outgoing"), OutgoingMessage)

    async def test_it_posts_and_records_the_offer(self) -> None:
        channel, _bot, recorded, _seen = await self._post()
        channel.send.assert_awaited_once()
        self.assertEqual([r["kind"] for r in recorded], ["link_read"])
        self.assertEqual(recorded[0]["event"], "offered")
        self.assertEqual(recorded[0]["detail"], "read_youtube")

    async def test_a_failed_post_records_nothing(self) -> None:
        """An offer nobody saw is not an offer, and must not enter the denominator."""
        _channel, _bot, recorded, _seen = await self._post(send_raises=True)
        self.assertEqual(recorded, [], "a failed send recorded an offer anyway")

    async def test_no_urls_posts_nothing(self) -> None:
        channel, _bot, recorded, _seen = await self._post(urls=[])
        channel.send.assert_not_awaited()
        self.assertEqual(recorded, [])

    async def test_the_view_is_registered_for_persistence(self) -> None:
        """Offer buttons must survive a restart."""
        _channel, bot, _recorded, _seen = await self._post()
        bot.add_view.assert_called_once()

    async def test_the_custom_id_format_is_unchanged(self) -> None:
        """A new format leaves every already-posted offer with a dead button.

        Discord matches persistent views by `custom_id`, so this string is a
        compatibility surface, not an implementation detail.
        """
        _channel, bot, _recorded, _seen = await self._post()
        view = bot.add_view.call_args.args[0]
        self.assertEqual(
            [child.custom_id for child in view.children],
            ["turtle:link:read:42:555"],
        )

    async def test_the_button_is_labelled_for_what_the_link_is(self) -> None:
        """The 08-12 defect: a YouTube link offering to read an article."""
        _channel, bot, _recorded, _seen = await self._post()
        view = bot.add_view.call_args.args[0]
        self.assertEqual([child.label for child in view.children], ["Fetch transcript"])

    async def test_the_button_has_exactly_one_action_and_no_decline(self) -> None:
        _channel, bot, _recorded, _seen = await self._post()
        view = bot.add_view.call_args.args[0]
        self.assertEqual(len(view.children), 1, "one button: reading it. Silence declines.")

    async def test_the_button_callback_is_wired(self) -> None:
        """An offer whose button does nothing is worse than no offer."""
        _channel, bot, _recorded, _seen = await self._post()
        view = bot.add_view.call_args.args[0]
        self.assertIsNotNone(view.children[0].callback)


if __name__ == "__main__":
    unittest.main()
