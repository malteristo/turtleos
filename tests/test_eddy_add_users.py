"""Tests for eddy member auto-add (INT-034)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
discord = sys.modules["discord"]
discord.Object = lambda id: {"id": id}
discord.HTTPException = type("HTTPException", (Exception,), {})


class EddyAddUsersTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_users_uses_object_not_fetch_user(self) -> None:
        from eddy_spawn import add_users_to_thread

        thread = MagicMock()
        thread.add_user = AsyncMock()

        await add_users_to_thread(thread, ["111", "222"])

        self.assertEqual(thread.add_user.await_count, 2)
        calls = [c.args[0]["id"] for c in thread.add_user.await_args_list]
        self.assertEqual(calls, [111, 222])

    async def test_add_users_ignores_already_member(self) -> None:
        from eddy_spawn import add_users_to_thread

        thread = MagicMock()
        exc = discord.HTTPException()
        exc.code = 30083
        thread.add_user = AsyncMock(side_effect=exc)

        await add_users_to_thread(thread, ["111"])

        thread.add_user.assert_awaited_once()

    def test_turtle_bot_cache_uses_primary_runtime(self) -> None:
        from eddy_spawn import _turtle_bot_id_cache_path

        with patch("mage._resolve_primary_runtime_dir", return_value="/tmp/operator"):
            path = _turtle_bot_id_cache_path()

        self.assertEqual(
            str(path), "/tmp/operator/thread-state/river/turtle_bot_user_id"
        )


if __name__ == "__main__":
    unittest.main()
