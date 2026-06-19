import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from hosted_river_onboarding import (
    _parse_onboarding_markdown,
    is_onboarding_posted,
    load_onboarding_markdown,
    mark_onboarding_posted,
)


class HostedRiverOnboardingTests(unittest.TestCase):
    def test_parse_onboarding_markdown(self) -> None:
        body = "# Hello\n\nSome text."
        title, description = _parse_onboarding_markdown(body)
        self.assertEqual(title, "Hello")
        self.assertIn("Some text", description)

    def test_onboarding_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("hosted_river_onboarding._onboarding_state_path") as mock_path:
                state_file = os.path.join(tmp, "onboarding.json")
                mock_path.return_value = state_file
                self.assertFalse(is_onboarding_posted(123))
                mark_onboarding_posted(123, 456)
                self.assertTrue(is_onboarding_posted(123))

    @patch("mage.get_pd")
    @patch("mage.set_practice_context_for_channel")
    @patch("hosted_river_onboarding._practitioner_locale")
    def test_load_template_when_no_custom(
        self, mock_locale, _mock_ctx, mock_pd
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mock_pd.return_value = tmp
            mock_locale.return_value = "en"
            text = load_onboarding_markdown(999)
            self.assertIn("your river", text.lower())


if __name__ == "__main__":
    unittest.main()
