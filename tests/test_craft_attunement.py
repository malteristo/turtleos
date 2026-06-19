import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from state import THREAD_CONTEXTS
import mage
from prompts import (
    CRAFT_VOCATION_HEADER,
    build_craft_channel_prompt,
    get_thread_prompt,
    uses_native_turtle_prompt,
)


class CraftAttunementTests(unittest.TestCase):
    CRAFT_CHANNEL = 1504544358546931752
    RIVER_CHANNEL = 999001

    def setUp(self) -> None:
        self._saved_registry = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved_registry)

    def _set_registry(self, *, attunement="native", channels=None):
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": attunement,
                "channels": channels or {},
                "mages": {"default": {"discord_id": "1", "practice_dir": "/tmp/p"}},
                "default_mage": "default",
            }
        )

    def test_thread_contexts_includes_craft(self) -> None:
        self.assertIn("craft", THREAD_CONTEXTS)
        self.assertIn("Intake moves", THREAD_CONTEXTS["craft"]["rules"])

    def test_global_native_craft_channel_uses_craft_attunement(self) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "attunement": "craft",
                    "default_context": "craft",
                }
            },
        )
        self.assertEqual(mage.get_effective_attunement(self.CRAFT_CHANNEL), "craft")
        self.assertTrue(mage.uses_craft_surface(self.CRAFT_CHANNEL))
        self.assertFalse(mage.uses_native_eddy(self.CRAFT_CHANNEL))
        self.assertFalse(uses_native_turtle_prompt(self.CRAFT_CHANNEL))

    def test_craft_type_infers_craft_when_global_native(self) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "default_context": "craft",
                }
            },
        )
        self.assertEqual(mage.get_effective_attunement(self.CRAFT_CHANNEL), "craft")

    def test_river_stays_native_when_global_native(self) -> None:
        self._set_registry(
            attunement="native",
            channels={str(self.RIVER_CHANNEL): {"type": "river"}},
        )
        self.assertEqual(mage.get_effective_attunement(self.RIVER_CHANNEL), "native")
        self.assertTrue(uses_native_turtle_prompt(self.RIVER_CHANNEL))

    @patch("prompts.build_discord_prompt", return_value="practice block")
    @patch("prompts._build_context_resonance", return_value="craft context block")
    def test_build_craft_channel_prompt(self, _ctx, _practice) -> None:
        prompt = build_craft_channel_prompt("craft")
        self.assertIn(CRAFT_VOCATION_HEADER.split("\n")[0], prompt)
        self.assertIn("craft context block", prompt)
        self.assertIn("practice block", prompt)

    @patch("prompts.get_craft_channel_prompt", return_value="craft prompt")
    def test_get_thread_prompt_routes_craft_channel(self, mock_craft) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "attunement": "craft",
                }
            },
        )
        out = get_thread_prompt("semi", False, context_type="craft", channel_id=self.CRAFT_CHANNEL)
        self.assertEqual(out, "craft prompt")
        mock_craft.assert_called_once_with("craft")


if __name__ == "__main__":
    unittest.main()
