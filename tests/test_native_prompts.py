import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from prompts import build_native_eddy_prompt, load_character_file


class NativePromptTests(unittest.TestCase):
    def test_load_character_from_template(self) -> None:
        soul = load_character_file("soul.md")
        self.assertIn("thinking partner", soul.lower())
        conduct = load_character_file("conduct.md")
        self.assertIn("think-aloud", conduct.lower())

    def test_build_native_prompt_includes_soul_and_conduct(self) -> None:
        prompt = build_native_eddy_prompt()
        self.assertIn("What You Are", prompt)
        self.assertIn("Eddy Entry", prompt)
        self.assertIn("Discord Eddy", prompt)

    @patch("prompts.get_pd")
    def test_build_native_prompt_with_flow(self, mock_pd) -> None:
        mock_pd.return_value = "/nonexistent/practice"
        prompt = build_native_eddy_prompt("shelter")
        self.assertIn("Shelter", prompt)


if __name__ == "__main__":
    unittest.main()
