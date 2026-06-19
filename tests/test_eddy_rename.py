import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from eddy_spawn import normalize_eddy_title, parse_rename_command, rename_eddy_thread


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
