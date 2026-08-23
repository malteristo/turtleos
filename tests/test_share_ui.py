"""Tests for share_ui — picker and cmd_share (share_eddy decomposition Slice 6)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])


class ShareBotClientTests(unittest.TestCase):
    def test_get_share_bot_client_uses_guild_not_message_client(self) -> None:
        from share_ui import get_share_bot_client

        mock_client = object()
        message = MagicMock()
        message.channel.guild._state._get_client.return_value = mock_client
        del message.client

        with patch("mage.river_bot_enabled", return_value=False):
            self.assertIs(get_share_bot_client(message), mock_client)

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import SharePickerView, cmd_share, get_share_bot_client, register_persistent_share_views

        self.assertTrue(callable(cmd_share))
        self.assertTrue(callable(register_persistent_share_views))
        self.assertTrue(callable(get_share_bot_client))
        self.assertTrue(hasattr(SharePickerView, "__init__"))


if __name__ == "__main__":
    unittest.main()
