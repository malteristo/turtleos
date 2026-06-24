import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("discord", MagicMock())

from discord_ref_read import (
    DISCORD_REF_INJECT_LABEL,
    DiscordRefResult,
    extract_discord_message_refs,
    format_dereferenced_message,
    format_discord_ref_for_dialogue,
    format_discord_refs_for_dialogue,
    permalink_for,
)


class DiscordRefParseTests(unittest.TestCase):
    def test_extract_message_permalink(self) -> None:
        url = "https://discord.com/channels/111/222/333"
        text = f"what did we decide here? {url}"
        self.assertEqual(extract_discord_message_refs(text), [(111, 222, 333)])

    def test_dedupes_repeated_links(self) -> None:
        url = "https://discord.com/channels/1/2/3"
        text = f"{url} and again {url}"
        self.assertEqual(extract_discord_message_refs(text), [(1, 2, 3)])

    def test_permalink_for(self) -> None:
        self.assertEqual(
            permalink_for(1, 2, 3),
            "https://discord.com/channels/1/2/3",
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

        source = MagicMock()
        source.channel.id = 2
        source.id = 3
        source.content = "decision: use bootstrap not modal"
        source.author.display_name = "Spirit"
        source.created_at = None
        source.attachments = []

        ch = MagicMock()
        ch.fetch_message = AsyncMock(return_value=source)
        client = MagicMock()
        client.fetch_channel = AsyncMock(return_value=ch)

        results, block = await fetch_discord_refs_with_status(
            channel, client, [(1, 2, 3)]
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertIn("bootstrap", block)
        channel.send.assert_awaited_once()
        status_msg.edit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
