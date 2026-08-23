"""Tests for claim-room invite auto-admit on member join."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub()

from river_keys import try_auto_admit_on_member_join


class AutoAdmitTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_admit_when_invite_uses_increase(self) -> None:
        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.name = "brother"
        member.display_name = "Brother"
        member.guild = MagicMock()

        invite = MagicMock()
        invite.code = "abc123"
        invite.uses = 1
        member.guild.invites = AsyncMock(return_value=[invite])

        channel = MagicMock(spec=discord.TextChannel)
        channel.name = "river-brother"
        member.guild.get_channel.return_value = channel
        member.guild.fetch_channel = AsyncMock(return_value=channel)

        registry = {
            "channels": {
                "555": {
                    "type": "unclaimed-river",
                    "mage": "brother",
                    "invite_code": "abc123",
                    "invite_uses": 0,
                }
            }
        }

        with patch("mage.get_registry", return_value=registry), patch(
            "river_keys.grant_claim_room_member_access", new_callable=AsyncMock
        ) as grant, patch("river_keys.save_registry") as save:
            summary = await try_auto_admit_on_member_join(member)

        self.assertIsNotNone(summary)
        self.assertIn("brother", summary.lower())
        grant.assert_awaited_once()
        save.assert_called_once()
        self.assertEqual(registry["channels"]["555"]["invite_uses"], 1)

    async def test_no_admit_when_uses_unchanged(self) -> None:
        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.guild = MagicMock()
        invite = MagicMock()
        invite.code = "abc123"
        invite.uses = 0
        member.guild.invites = AsyncMock(return_value=[invite])

        registry = {
            "channels": {
                "555": {
                    "type": "unclaimed-river",
                    "mage": "brother",
                    "invite_code": "abc123",
                    "invite_uses": 0,
                }
            }
        }
        with patch("mage.get_registry", return_value=registry), patch(
            "river_keys.grant_claim_room_member_access", new_callable=AsyncMock
        ) as grant:
            summary = await try_auto_admit_on_member_join(member)
        self.assertIsNone(summary)
        grant.assert_not_called()


if __name__ == "__main__":
    unittest.main()
