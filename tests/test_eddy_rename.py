import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

from eddy_spawn import (
    fallback_topic,
    generate_topic,
    normalize_eddy_title,
    parse_rename_command,
    rename_eddy_thread,
    title_is_grounded,
)


class TitleGroundingTests(unittest.TestCase):
    def test_invented_place_is_not_grounded(self) -> None:
        source = "what's waiting in my practice?"
        self.assertFalse(title_is_grounded("waiting in dental practice", source))

    def test_words_from_the_opening_are_grounded(self) -> None:
        source = "what's waiting in my practice?"
        self.assertTrue(title_is_grounded("waiting in my practice", source))

    def test_fallback_is_the_first_line(self) -> None:
        self.assertEqual(
            fallback_topic("what's waiting in my practice?\nmore"),
            "what's waiting in my practice?",
        )

    def test_ungrounded_model_falls_back_to_first_line(self) -> None:
        async def run() -> None:
            with patch(
                "eddy_spawn.chat_ollama",
                AsyncMock(return_value="waiting in dental practice"),
            ):
                title = await generate_topic("what's waiting in my practice?")
            self.assertEqual(title, "what's waiting in my practice?")

        asyncio.run(run())


class NormalizeEddyTitleTests(unittest.TestCase):
    def test_plain_title(self) -> None:
        self.assertEqual(normalize_eddy_title("checking turtle readiness"), "checking turtle readiness")

    def test_quoted_title(self) -> None:
        self.assertEqual(normalize_eddy_title('"the untrodden world"'), "the untrodden world")

    def test_truncates_to_discord_limit(self) -> None:
        self.assertEqual(len(normalize_eddy_title("x" * 200)), 100)


class ParseRenameCommandTests(unittest.TestCase):
    def test_parses_multi_word_title(self) -> None:
        self.assertEqual(parse_rename_command("!rename my exact title"), "my exact title")

    def test_parses_quoted_title(self) -> None:
        self.assertEqual(parse_rename_command('!rename "my exact title"'), "my exact title")

    def test_missing_title(self) -> None:
        self.assertIsNone(parse_rename_command("!rename"))


class RenameEddyThreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_renames_thread_and_registry(self) -> None:
        thread = MagicMock()
        thread.id = 123
        thread.parent_id = 456
        thread.name = "new eddy"

        with patch("eddy_spawn._edit_eddy_thread_name", new=AsyncMock()) as mock_edit, patch(
            "eddy_spawn.is_awaiting_title", return_value=False
        ), patch("thread_registry.update_thread_name") as mock_registry:
            new_name, err = await rename_eddy_thread(thread, "Navigator")

        self.assertIsNone(err)
        self.assertEqual(new_name, "Navigator")
        mock_edit.assert_awaited_once_with(thread, "Navigator")
        mock_registry.assert_called_once_with(123, "Navigator")

    async def test_blank_eddy_rename_adds_turtle_when_split_bot(self) -> None:
        thread = MagicMock()
        thread.id = 123
        thread.parent_id = 456
        thread.name = "new eddy"

        with patch("eddy_spawn._edit_eddy_thread_name", new=AsyncMock()), patch(
            "eddy_spawn.is_awaiting_title", return_value=True
        ), patch("eddy_spawn.pop_awaiting_title", return_value={}), patch(
            "eddy_spawn.river_add_turtle_to_eddy", new=AsyncMock()
        ) as mock_add, patch("mage.river_bot_enabled", return_value=True), patch(
            "thread_registry.update_thread_name"
        ):
            new_name, err = await rename_eddy_thread(thread, "My Topic")

        self.assertIsNone(err)
        self.assertEqual(new_name, "My Topic")
        mock_add.assert_awaited_once_with(thread)


if __name__ == "__main__":
    unittest.main()
