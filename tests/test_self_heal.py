import asyncio
import unittest

from self_heal import HEAL_REGISTRY, check_and_heal, registry_summary


class TestSelfHealRegistry(unittest.TestCase):
    def test_registry_matches_spec_checks(self):
        expected = {"ollama", "loops", "practice_freshness", "file_io", "discord"}
        self.assertEqual(set(HEAL_REGISTRY.keys()), expected)

    def test_only_ollama_is_healable(self):
        healable = [name for name, entry in HEAL_REGISTRY.items() if entry.healable]
        self.assertEqual(healable, ["ollama"])

    def test_registry_summary_covers_all_entries(self):
        summary = registry_summary()
        self.assertEqual(len(summary), len(HEAL_REGISTRY))

    def test_check_and_heal_returns_none_for_non_healable(self):
        for name, entry in HEAL_REGISTRY.items():
            if entry.healable:
                continue
            result = asyncio.run(check_and_heal(name))
            self.assertIsNone(result)

    def test_check_and_heal_returns_none_for_unknown(self):
        self.assertIsNone(asyncio.run(check_and_heal("unknown_check")))


if __name__ == "__main__":
    unittest.main()
