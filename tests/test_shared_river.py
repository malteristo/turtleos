import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import mage
from prompts import build_native_eddy_prompt, get_native_eddy_prompt
from river_handler import _iter_river_channels
from state import THREAD_CONTEXTS


class SharedRiverHarnessTests(unittest.IsolatedAsyncioTestCase):
    FAMILY_CHANNEL = 1491163697278881836
    RIVER_CHANNEL = 999001

    def setUp(self) -> None:
        self._saved_registry = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved_registry)

    def _set_registry(self, *, attunement="magic", channels=None):
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": attunement,
                "channels": channels or {},
                "mages": {
                    "kermit": {"discord_id": "1", "practice_dir": "/tmp/kermit"},
                    "nesrine": {"discord_id": "2", "practice_dir": "/tmp/nesrine"},
                },
                "spaces": {
                    "family": {
                        "practice_dir": "/tmp/family",
                        "members": ["kermit", "nesrine"],
                    }
                },
            }
        )

    def _parent_message(self, channel_id: int):
        channel = MagicMock()
        channel.id = channel_id
        channel.parent_id = None
        message = MagicMock()
        message.channel = channel
        return message

    def test_channel_is_river_includes_shared_river(self) -> None:
        self._set_registry(
            channels={
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                    "default_context": "family",
                }
            }
        )
        self.assertTrue(mage._channel_is_river(self.FAMILY_CHANNEL))

    def test_shared_river_uses_harness_under_magic_attunement(self) -> None:
        self._set_registry(
            attunement="magic",
            channels={
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            },
        )
        msg = self._parent_message(self.FAMILY_CHANNEL)
        with patch.object(mage, "is_river_message", return_value=True):
            with patch.object(mage, "river_bot_enabled", return_value=False):
                self.assertTrue(mage.uses_native_river(msg))
                self.assertTrue(mage.turtle_handles_native_river(msg))

    def test_operator_river_still_dialogue_under_magic(self) -> None:
        self._set_registry(
            attunement="magic",
            channels={str(self.RIVER_CHANNEL): {"type": "river", "mage": "kermit"}},
        )
        msg = self._parent_message(self.RIVER_CHANNEL)
        with patch.object(mage, "is_river_message", return_value=True):
            self.assertFalse(mage.uses_native_river(msg))

    def test_iter_river_channels_includes_shared_river(self) -> None:
        self._set_registry(
            channels={
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            }
        )
        mock_ch = MagicMock()
        mock_ch.id = self.FAMILY_CHANNEL
        client = MagicMock()
        client.get_channel.return_value = mock_ch
        with patch("mage.get_channel", return_value=None):
            channels = _iter_river_channels(client)
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].id, self.FAMILY_CHANNEL)

    def test_get_thread_member_ids_expands_space(self) -> None:
        self._set_registry(
            channels={
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            }
        )
        ids = mage.get_thread_member_ids(self.FAMILY_CHANNEL)
        self.assertEqual(ids, ["1", "2"])

    async def test_ensure_space_channel_access_grants_missing_members(self) -> None:
        self._set_registry(
            channels={
                str(self.FAMILY_CHANNEL): {
                    "type": "shared-river",
                    "mage": "family",
                }
            }
        )
        member = MagicMock()
        member.id = 2
        guild = MagicMock()
        guild.get_member.return_value = member

        channel = MagicMock()
        channel.id = self.FAMILY_CHANNEL
        channel.guild = guild
        channel.overwrites = {}
        channel.edit = AsyncMock()

        ok = await mage.ensure_space_channel_access(channel)
        self.assertTrue(ok)
        channel.edit.assert_awaited_once()
        overwrites = channel.edit.await_args.kwargs["overwrites"]
        self.assertIn(member, overwrites)

    async def test_ensure_space_channel_access_skips_non_shared_river(self) -> None:
        channel = MagicMock()
        channel.id = self.RIVER_CHANNEL
        channel.edit = AsyncMock()
        self._set_registry(
            channels={str(self.RIVER_CHANNEL): {"type": "river", "mage": "kermit"}}
        )
        ok = await mage.ensure_space_channel_access(channel)
        self.assertFalse(ok)
        channel.edit.assert_not_awaited()


class SharedRiverNativePromptTests(unittest.TestCase):
    @patch("prompts.load_character_file", return_value="")
    @patch("prompts._build_context_resonance")
    def test_family_context_in_native_eddy(self, mock_ctx, _soul) -> None:
        mock_ctx.return_value = "Family rules block"
        prompt = build_native_eddy_prompt(context_type="family")
        mock_ctx.assert_called_once_with("family")
        self.assertIn("Family rules block", prompt)

    @patch("prompts.load_character_file", return_value="")
    @patch("prompts._build_context_resonance")
    def test_get_native_eddy_prompt_disambiguates_context(self, mock_ctx, _soul) -> None:
        mock_ctx.return_value = "Family rules block"
        prompt = get_native_eddy_prompt("family")
        mock_ctx.assert_called_once_with("family")
        self.assertIn("Family rules block", prompt)

    def test_family_context_rules_exist(self) -> None:
        self.assertIn("family", THREAD_CONTEXTS)
        self.assertIn("private", THREAD_CONTEXTS["family"]["rules"].lower())


if __name__ == "__main__":
    unittest.main()
