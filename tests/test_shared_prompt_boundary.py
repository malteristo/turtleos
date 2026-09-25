"""Shared runtime prompts never pull a member's private practice state."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub()

from channel_primitives import resolve_primitive
from dialogue_runtime import build_runtime_env


class SharedPromptBoundaryTests(unittest.TestCase):
    def test_shared_runtime_names_the_boundary_without_private_workspace(self) -> None:
        registry = {
            "spaces": {
                "family": {
                    "members": ["one", "two"],
                    "memory": "own_root",
                }
            },
            "channels": {
                "42": {
                    "primitive": "partnership",
                    "mage": "family",
                }
            },
        }
        primitive = resolve_primitive(registry, 42)
        message = MagicMock()
        message.channel.name = "family"
        message.author.display_name = "One"

        with patch(
            "dialogue_runtime.get_current_channel_primitive",
            return_value=primitive,
        ), patch(
            "dialogue_runtime.get_mage_key", return_value="family"
        ), patch(
            "dialogue_runtime.get_mage_name", return_value="Partnership"
        ), patch(
            "dialogue_runtime.get_registry", return_value=registry
        ):
            rendered = build_runtime_env(message, None)

        self.assertIn("may read only its own practice root", rendered)
        self.assertNotIn("Speaking mage workspace", rendered)
        self.assertNotIn("personal compass", rendered)


if __name__ == "__main__":
    unittest.main()
