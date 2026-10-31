"""Channel practice is specified with the channel, not in the platform spec.

The identity question of the home channel is the positive control. It lives in
docs/channels/home.md. Pasting it back into TURTLE_SPEC.md fails this test.
Removing the platform's refusal to supply a key question fails it too.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = ROOT / "TURTLE_SPEC.md"
HOME = ROOT / "docs" / "channels" / "home.md"

IDENTITY = "What has this room been, and what is it for now?"
STANDING = "What is on your mind?"


class ChannelSpecBoundaryTests(unittest.TestCase):
    def test_platform_does_not_describe_the_home_practice(self) -> None:
        platform = PLATFORM.read_text(encoding="utf-8")
        home = HOME.read_text(encoding="utf-8")
        self.assertIn(IDENTITY, home)
        self.assertNotIn(IDENTITY, platform)
        self.assertIn(STANDING, home)
        self.assertIn("Channel specs are not this document.", platform)
        self.assertIn("may differ from one channel to the next", platform)
        self.assertIn("docs/channels/home.md", platform)

    def test_home_spec_names_its_own_key_question(self) -> None:
        home = HOME.read_text(encoding="utf-8")
        self.assertIn("A channel key is part of the channel's architecture.", home)
        self.assertIn("starts in the craft channel", home)
        self.assertIn("When a session in this channel closes", home)
        self.assertIn("Not what the running house does.", home)


if __name__ == "__main__":
    unittest.main()
