"""Reply path must not emit LaTeX arrows (intake 66443a)."""
from __future__ import annotations

import unittest

from discord_plain import for_discord
from helpers import split_message


CHAIN = (
    "you can't relax because there is chaos $\\rightarrow$ you try to fix "
    "the chaos while sick $\\rightarrow$ you become more exhausted"
)


class DiscordPlainTests(unittest.TestCase):
    def test_generated_arrow_chain_has_no_latex(self) -> None:
        out = for_discord(CHAIN)
        self.assertNotIn("$", out)
        self.assertNotIn(r"\rightarrow", out)
        self.assertIn("→", out)
        self.assertEqual(out.count("→"), 2)

    def test_split_message_is_the_reply_path_guard(self) -> None:
        chunks = split_message(CHAIN)
        joined = "".join(chunks)
        self.assertNotIn("$", joined)
        self.assertNotIn(r"\rightarrow", joined)
        self.assertIn("→", joined)

    def test_plain_to_and_unicode_dollar_forms(self) -> None:
        self.assertEqual(for_discord(r"a $\to$ b"), "a → b")
        self.assertEqual(for_discord("a $→$ b"), "a → b")
