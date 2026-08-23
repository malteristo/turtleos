"""Unit tests for !admin member resolution (onboard / members cache gaps)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub()

from commands import _resolve_guild_member


class ResolveGuildMemberTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_by_username_case_insensitive(self) -> None:
        member = MagicMock(spec=discord.Member)
        member.id = 42
        member.name = "216.guest"
        member.display_name = "فارس"
        guild = MagicMock()
        guild.members = [member]
        guild.get_member = MagicMock(return_value=None)
        guild.fetch_member = AsyncMock()
        guild.query_members = AsyncMock(return_value=[])

        found = await _resolve_guild_member(guild, "216.Guest")
        self.assertIs(found, member)
        guild.fetch_member.assert_not_called()

    async def test_resolve_by_snowflake_fetch(self) -> None:
        member = MagicMock(spec=discord.Member)
        member.id = 401
        guild = MagicMock()
        guild.members = []
        guild.get_member = MagicMock(return_value=None)
        guild.fetch_member = AsyncMock(return_value=member)
        guild.query_members = AsyncMock(return_value=[])

        found = await _resolve_guild_member(guild, "401")
        self.assertIs(found, member)
        guild.fetch_member.assert_awaited_once_with(401)

    async def test_resolve_mention_token(self) -> None:
        member = MagicMock(spec=discord.Member)
        member.id = 99
        guild = MagicMock()
        guild.members = []
        guild.get_member = MagicMock(return_value=None)
        guild.fetch_member = AsyncMock(return_value=member)
        message = MagicMock()
        message.mentions = []

        found = await _resolve_guild_member(guild, "<@99>", message)
        self.assertIs(found, member)

    async def test_missing_returns_none(self) -> None:
        guild = MagicMock()
        guild.members = []
        guild.get_member = MagicMock(return_value=None)
        guild.fetch_member = AsyncMock(side_effect=discord.NotFound(MagicMock(), "missing"))
        guild.query_members = AsyncMock(return_value=[])

        found = await _resolve_guild_member(guild, "nobody")
        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
