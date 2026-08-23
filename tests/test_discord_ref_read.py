import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("discord", MagicMock())
discord = sys.modules["discord"]
discord.Thread = type("Thread", (), {})
discord.ChannelType = MagicMock(
    public_thread="public_thread",
    private_thread="private_thread",
    news_thread="news_thread",
)

from discord_ref_read import (
    DISCORD_REF_INJECT_LABEL,
    DISCORD_THREAD_REF_LABEL,
    DiscordRefResult,
    build_thread_result,
    extract_all_discord_refs,
    extract_discord_message_refs,
    extract_discord_thread_only_refs,
    format_dereferenced_message,
    format_discord_ref_for_dialogue,
    format_discord_refs_for_dialogue,
    format_thread_context_block,
    format_thread_summary_block,
    permalink_for,
)


class DiscordRefParseTests(unittest.TestCase):
    def test_extract_message_permalink(self) -> None:
        url = "https://discord.com/channels/111/222/333"
        text = f"what did we decide here? {url}"
        self.assertEqual(extract_discord_message_refs(text), [(111, 222, 333)])

    def test_extract_thread_only_permalink(self) -> None:
        url = "https://discord.com/channels/111/222"
        text = f"what happened in this eddy? {url}"
        self.assertEqual(extract_discord_thread_only_refs(text), [(111, 222)])

    def test_message_link_excludes_thread_only_duplicate(self) -> None:
        text = "https://discord.com/channels/1/2/3"
        self.assertEqual(extract_discord_thread_only_refs(text), [])
        self.assertEqual(extract_all_discord_refs(text), [(1, 2, 3)])

    def test_extract_all_includes_both_kinds(self) -> None:
        text = (
            "thread https://discord.com/channels/1/10 "
            "msg https://discord.com/channels/1/20/30"
        )
        self.assertEqual(
            extract_all_discord_refs(text),
            [(1, 20, 30), (1, 10, None)],
        )

    def test_dedupes_repeated_links(self) -> None:
        url = "https://discord.com/channels/1/2/3"
        text = f"{url} and again {url}"
        self.assertEqual(extract_discord_message_refs(text), [(1, 2, 3)])

    def test_permalink_for(self) -> None:
        self.assertEqual(
            permalink_for(1, 2, 3),
            "https://discord.com/channels/1/2/3",
        )
        self.assertEqual(
            permalink_for(1, 2),
            "https://discord.com/channels/1/2",
        )


class DiscordRefFormatTests(unittest.TestCase):
    def test_format_dereferenced_message_includes_author_and_content(self) -> None:
        msg = MagicMock()
        msg.channel.id = 99
        msg.id = 42
        msg.content = "We agreed to ship Navigator first."
        msg.author.display_name = "Kermit"
        msg.created_at = None
        msg.attachments = []
        block = format_dereferenced_message(msg, label="Read Discord message")
        self.assertIn("Kermit", block)
        self.assertIn("ship Navigator", block)

    def test_format_thread_context_block(self) -> None:
        block = format_thread_context_block(
            thread_name="planning",
            lines=["Kermit: first", "Turtle: second"],
            permalink="https://discord.com/channels/1/2/3",
            anchor_message_id=3,
        )
        self.assertIn(DISCORD_THREAD_REF_LABEL, block)
        self.assertIn("messages (2)", block)
        self.assertIn("Turtle: second", block)

    def test_format_thread_summary_block(self) -> None:
        block = format_thread_summary_block(
            thread_name="planning",
            lines=["Kermit: first", "Turtle: second"],
            permalink="https://discord.com/channels/1/2/3",
            summary="They agreed on bootstrap.",
            anchor_message_id=3,
        )
        self.assertIn("summary (2 messages on Discord)", block)
        self.assertIn("They agreed on bootstrap.", block)
        self.assertIn("ask to read more", block)

    def test_inject_label_constant(self) -> None:
        result = DiscordRefResult(
            guild_id=1,
            channel_id=2,
            message_id=3,
            ok=True,
            content="author: test\ncontent:\nhello",
            char_count=30,
            author="test",
            permalink="https://discord.com/channels/1/2/3",
        )
        block = format_discord_ref_for_dialogue(result)
        self.assertIn(f"[{DISCORD_REF_INJECT_LABEL}]", block)
        self.assertIn("hello", block)
        self.assertNotIn("[Dereferenced Discord context]", block)

    def test_thread_inject_label(self) -> None:
        result = DiscordRefResult(
            guild_id=1,
            channel_id=2,
            message_id=3,
            ok=True,
            content=f"[{DISCORD_THREAD_REF_LABEL}] x\nmessages (2):\na\nb",
            char_count=40,
            permalink="https://discord.com/channels/1/2/3",
            scope="thread",
            message_count=2,
            thread_name="planning",
        )
        block = format_discord_ref_for_dialogue(result)
        self.assertIn(f"[{DISCORD_THREAD_REF_LABEL}]", block)

    def test_failure_inject_is_honest(self) -> None:
        result = DiscordRefResult(
            guild_id=1,
            channel_id=2,
            message_id=3,
            ok=False,
            permalink="https://discord.com/channels/1/2/3",
            error="Forbidden: 403",
        )
        block = format_discord_ref_for_dialogue(result)
        self.assertIn("Could not read", block)
        self.assertIn("403", block)

    def test_multi_join(self) -> None:
        results = [
            DiscordRefResult(
                guild_id=1,
                channel_id=2,
                message_id=3,
                ok=True,
                content="one",
                char_count=3,
                permalink="https://discord.com/channels/1/2/3",
            ),
            DiscordRefResult(
                guild_id=1,
                channel_id=2,
                message_id=4,
                ok=True,
                content="two",
                char_count=3,
                permalink="https://discord.com/channels/1/2/4",
            ),
        ]
        block = format_discord_refs_for_dialogue(results)
        self.assertIn("one", block)
        self.assertIn("two", block)
        self.assertIn("---", block)


def _mock_message(content: str, *, author: str = "Kermit", bot: bool = False, msg_id: int = 1):
    msg = MagicMock()
    msg.id = msg_id
    msg.content = content
    msg.author.bot = bot
    msg.author.display_name = author
    msg.author.name = author
    msg.attachments = []
    return msg


async def _async_history(messages):
    for msg in messages:
        yield msg


class DiscordRefFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_with_status_posts_and_edits_embed(self) -> None:
        from discord_ref_read import fetch_discord_refs_with_status

        channel = MagicMock()
        channel.typing = MagicMock()
        channel.typing.return_value.__aenter__ = AsyncMock(return_value=None)
        channel.typing.return_value.__aexit__ = AsyncMock(return_value=None)
        status_msg = MagicMock()
        status_msg.edit = AsyncMock()
        channel.send = AsyncMock(return_value=status_msg)

        source = _mock_message("decision: use bootstrap not modal", author="Spirit", msg_id=3)
        source.channel = MagicMock()
        source.channel.id = 2

        ch = MagicMock()
        ch.fetch_message = AsyncMock(return_value=source)
        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=ch)

        results, block = await fetch_discord_refs_with_status(
            channel, client, [(1, 2, 3)]
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].scope, "message")
        self.assertIn("bootstrap", block)
        channel.send.assert_awaited_once()
        status_msg.edit.assert_awaited_once()

    async def test_message_in_thread_fetches_thread_history(self) -> None:
        from discord_ref_read import fetch_one_discord_ref

        thread = MagicMock(spec=discord.Thread)
        thread.name = "planning-eddy"
        thread.id = 99
        msgs = [
            _mock_message("we should ship bootstrap", msg_id=10),
            _mock_message("agreed — one step at a time", author="Turtle", bot=True, msg_id=11),
            _mock_message("decision: bootstrap wins", msg_id=12),
        ]
        thread.history = lambda limit=40, oldest_first=True: _async_history(msgs)

        anchor = _mock_message("decision: bootstrap wins", msg_id=12)
        anchor.channel = thread
        thread.fetch_message = AsyncMock(return_value=anchor)

        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=thread)

        result = await fetch_one_discord_ref(client, 1, 99, 12)
        self.assertTrue(result.ok)
        self.assertEqual(result.scope, "thread")
        self.assertEqual(result.message_count, 3)
        self.assertIn("ship bootstrap", result.content)
        self.assertIn("bootstrap wins", result.content)

    async def test_thread_only_link_fetches_history(self) -> None:
        from discord_ref_read import fetch_one_discord_thread

        thread = MagicMock(spec=discord.Thread)
        thread.name = "long-eddy"
        thread.id = 55
        msgs = [
            _mock_message("alpha", msg_id=1),
            _mock_message("beta", msg_id=2),
        ]
        thread.history = lambda limit=40, oldest_first=True: _async_history(msgs)

        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=thread)

        result = await fetch_one_discord_thread(client, 1, 55)
        self.assertTrue(result.ok)
        self.assertEqual(result.scope, "thread")
        self.assertEqual(result.message_count, 2)
        self.assertIn("alpha", result.content)
        self.assertIn("beta", result.content)

    async def test_long_thread_is_summarized(self) -> None:
        from unittest.mock import patch

        from discord_ref_read import fetch_one_discord_thread

        thread = MagicMock(spec=discord.Thread)
        thread.name = "long-eddy"
        thread.id = 55
        long_line = "Kermit: " + ("x" * 200)
        msgs = [_mock_message(long_line, msg_id=i) for i in range(1, 41)]
        thread.history = lambda limit=40, oldest_first=True: _async_history(msgs)

        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=thread)

        with patch("discord_ref_read.THREAD_INLINE_MAX", 500), patch(
            "discord_ref_read.summarize_thread_lines",
            new=AsyncMock(return_value="They debated bootstrap vs modal; bootstrap won."),
        ):
            result = await fetch_one_discord_thread(client, 1, 55)

        self.assertTrue(result.ok)
        self.assertTrue(result.summarized)
        self.assertGreater(result.raw_char_count, 500)
        self.assertIn("bootstrap won", result.content)
        self.assertIn("summary (40 messages on Discord)", result.content)

    async def test_summary_failure_falls_back_to_full_transcript(self) -> None:
        from unittest.mock import patch

        lines = ["Kermit: " + ("y" * 300)] * 5
        with patch("discord_ref_read.THREAD_INLINE_MAX", 100), patch(
            "discord_ref_read.summarize_thread_lines",
            new=AsyncMock(side_effect=RuntimeError("ollama down")),
        ):
            result = await build_thread_result(
                guild_id=1,
                channel_id=2,
                message_id=3,
                thread_name="planning",
                lines=lines,
                permalink="https://discord.com/channels/1/2/3",
            )

        self.assertTrue(result.ok)
        self.assertFalse(result.summarized)
        self.assertIn("messages (5)", result.content)


if __name__ == "__main__":
    unittest.main()
