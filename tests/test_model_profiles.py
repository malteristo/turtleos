"""Every model the house can route to has a profile; prices compute; unknown stays unknown."""

from __future__ import annotations

import unittest

from core import models
from core.model_profiles import PROFILES, awareness_block, cost_usd, is_cloud, profile_for


def _routed_models() -> set[str]:
    named = {
        models.TURTLE_MODEL,
        models.LIGHTER_TURTLE_MODEL,
        models.DIALOGUE_MODEL,
        models.CRAFT_MODEL,
        models.RIVER_MODEL,
        models.TRIAGE_MODEL,
        models.REFLECTION_MODEL,
        models.EDIT_DELEGATE_MODEL,
    }
    named |= {m for m in models.KNOWN_MODELS.values() if m}
    return named


class ProfileCoverageTests(unittest.TestCase):
    def test_every_routed_model_has_a_profile(self) -> None:
        missing = sorted(m for m in _routed_models() if m not in PROFILES)
        self.assertEqual(missing, [], f"models routed without a profile: {missing}")

    def test_the_coverage_check_can_fail(self) -> None:
        planted = _routed_models() | {"claude-imaginary-9"}
        self.assertIn("claude-imaginary-9", [m for m in planted if m not in PROFILES])

    def test_every_cloud_claude_profile_has_a_price(self) -> None:
        for model, profile in PROFILES.items():
            if model.startswith("claude-"):
                self.assertIsNotNone(profile.input_per_mtok, model)
                self.assertIsNotNone(profile.output_per_mtok, model)


class CostTests(unittest.TestCase):
    def test_opus_turn_prices_every_token_kind(self) -> None:
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_creation_input_tokens": 1_000_000,
            "cache_read_input_tokens": 1_000_000,
        }
        self.assertAlmostEqual(cost_usd("claude-opus-5-5", usage), 4 + 20 + 5 + 0.20)

    def test_unknown_model_has_no_cost_rather_than_zero(self) -> None:
        self.assertIsNone(cost_usd("claude-imaginary-9", {"input_tokens": 10}))

    def test_local_model_has_no_cost(self) -> None:
        self.assertIsNone(cost_usd("gemma4:31b", {"input_tokens": 10}))


class AwarenessTests(unittest.TestCase):
    def test_local_block_names_the_local_model_and_its_limits(self) -> None:
        block = awareness_block("gemma4:31b")
        self.assertIn("Gemma 4 31B", block)
        self.assertIn("own hardware", block)
        self.assertIn("park", block)

    def test_fallback_block_forbids_speaking_as_the_cloud_model(self) -> None:
        block = awareness_block("gemma4:31b", fallback_from="claude-opus-5-5")
        self.assertIn("Claude Opus 5.5", block)
        self.assertIn("Never speak as that model", block)
        self.assertNotIn("Never speak as", awareness_block("gemma4:31b"))

    def test_unknown_model_is_told_not_to_claim(self) -> None:
        self.assertIn("No profile", awareness_block("mystery:1b"))

    def test_cloud_detection(self) -> None:
        self.assertTrue(is_cloud("claude-opus-5-5"))
        self.assertTrue(is_cloud("claude-new-thing"))
        self.assertFalse(is_cloud("gemma4:31b"))
        self.assertIsNone(profile_for(None))


if __name__ == "__main__":
    unittest.main()
