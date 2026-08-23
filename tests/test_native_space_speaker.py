"""INT-051: native multi-member eddies must name the speaking member.

Ordinary shared-river eddies (not share-origin) used to emit only
``Practitioner: <Space>``. The Discord handle prefix on the member turn is
not the registry address, so the model defaulted to the host name from
soul.md. Live finding 2026-08-02 — fixtures here are synthetic.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])


SPACE_PARENT_ID = 9001001
PARTNER_DISCORD_ID = "20002"
HOST_DISCORD_ID = "20001"

_REGISTRY = {
    "channels": {
        str(SPACE_PARENT_ID): {
            "mage": "household",
            "type": "shared-river",
        }
    },
    "mages": {
        "host": {
            "address": "Host",
            "discord_id": HOST_DISCORD_ID,
            "practice_dir": "~/workshops/host",
        },
        "partner": {
            "address": "Partner",
            "discord_id": PARTNER_DISCORD_ID,
            "practice_dir": "~/workshops/partner",
        },
    },
    "spaces": {
        "household": {
            "members": ["host", "partner"],
            "practice_dir": "~/workshops/household",
            "runtime_dir": "~/workshops/household",
        }
    },
}


class TestNativeSpaceSpeaker(unittest.TestCase):
    def setUp(self) -> None:
        import dialogue_runtime
        import mage

        self._orig_thread = dialogue_runtime.discord.Thread
        self.thread_type = type("Thread", (), {})
        dialogue_runtime.discord.Thread = self.thread_type

        self._saved_registry = dict(mage._MAGE_REGISTRY)
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(_REGISTRY)
        mage.set_practice_context_for_mage_key("household")

    def tearDown(self) -> None:
        import dialogue_runtime
        import mage

        dialogue_runtime.discord.Thread = self._orig_thread
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved_registry)

    def _message(self, *, discord_id: str, display_name: str):
        parent = MagicMock()
        parent.id = SPACE_PARENT_ID
        parent.name = "household"

        channel = MagicMock()
        channel.__class__ = self.thread_type
        channel.id = 9001002
        channel.name = "ordinary shared eddy"
        channel.parent = parent
        channel.parent_id = SPACE_PARENT_ID

        author = MagicMock()
        author.id = int(discord_id)
        author.display_name = display_name
        author.name = display_name

        message = MagicMock()
        message.channel = channel
        message.author = author
        return message

    def test_partner_speaker_named_by_registry_address(self) -> None:
        from dialogue_runtime import build_native_runtime_env

        # Handle ≠ address — the live failure shape.
        message = self._message(
            discord_id=PARTNER_DISCORD_ID, display_name="partner_nick"
        )
        with patch("share_eddy.resolve_eddy_thread_cfg", return_value={}), patch(
            "dialogue_runtime.read_thread_state", return_value=""
        ):
            env = build_native_runtime_env(message, {}, [])

        self.assertIn("**Space:** Household", env)
        self.assertIn("**Speaking now:** **Partner**", env)
        self.assertIn("partner_nick", env)
        self.assertNotIn("**Practitioner:**", env)
        # Host must not be presented as the addressee
        self.assertNotIn("**Practitioner:** Host", env)
        self.assertNotIn("**Speaking now:** **Host**", env)

    def test_host_speaker_still_named_when_he_speaks(self) -> None:
        from dialogue_runtime import build_native_runtime_env

        message = self._message(
            discord_id=HOST_DISCORD_ID, display_name="host_nick"
        )
        with patch("share_eddy.resolve_eddy_thread_cfg", return_value={}), patch(
            "dialogue_runtime.read_thread_state", return_value=""
        ):
            env = build_native_runtime_env(message, {}, [])

        self.assertIn("**Speaking now:** **Host**", env)
        self.assertNotIn("**Speaking now:** **Partner**", env)

    def test_solo_river_keeps_practitioner_line(self) -> None:
        from dialogue_runtime import build_native_runtime_env
        import mage

        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "channels": {"111": {"mage": "host", "type": "river"}},
                "mages": {
                    "host": {
                        "address": "Host",
                        "discord_id": HOST_DISCORD_ID,
                        "practice_dir": "~/workshops/host",
                    }
                },
                "spaces": {},
            }
        )
        mage.set_practice_context_for_mage_key("host")

        parent = MagicMock()
        parent.id = 111
        parent.name = "river"
        channel = MagicMock()
        channel.__class__ = self.thread_type
        channel.id = 222
        channel.name = "solo eddy"
        channel.parent = parent
        channel.parent_id = 111
        author = MagicMock()
        author.id = int(HOST_DISCORD_ID)
        author.display_name = "host_nick"
        message = MagicMock()
        message.channel = channel
        message.author = author

        with patch("share_eddy.resolve_eddy_thread_cfg", return_value={}), patch(
            "dialogue_runtime.read_thread_state", return_value=""
        ):
            env = build_native_runtime_env(message, {}, [])

        self.assertIn("**Practitioner:** Host", env)
        self.assertNotIn("**Speaking now:**", env)
        self.assertNotIn("**Space:**", env)


if __name__ == "__main__":
    unittest.main()
