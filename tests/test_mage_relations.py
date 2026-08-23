"""Tests for the relation layer — docs/design/relations-and-membership.md.

Relations are circles, not a ladder: household and kin reach each other,
guests reach their host only, and admin is an orthogonal capability that
reaches (and is reached by) everyone.
"""

from __future__ import annotations

import unittest

import mage


REGISTRY = {
    "default_mage": "operator",
    "mages": {
        "operator": {"discord_id": "1", "admin": True, "relation": "household"},
        "partner": {"discord_id": "2", "relation": "household"},
        "sibling": {"discord_id": "3", "relation": "kin"},
        "friend": {"discord_id": "4", "relation": "guest"},
        "unclassified": {"discord_id": "5"},
        "typo": {"discord_id": "6", "relation": "familly"},
    },
}


class RelationResolutionTests(unittest.TestCase):
    def test_declared_relations_resolve(self) -> None:
        self.assertEqual(mage.relation_for_mage("partner", REGISTRY), "household")
        self.assertEqual(mage.relation_for_mage("sibling", REGISTRY), "kin")
        self.assertEqual(mage.relation_for_mage("friend", REGISTRY), "guest")

    def test_absent_relation_defaults_to_guest(self) -> None:
        self.assertEqual(mage.relation_for_mage("unclassified", REGISTRY), "guest")

    def test_unknown_relation_falls_back_to_guest(self) -> None:
        """A typo must never widen reach."""
        self.assertEqual(mage.relation_for_mage("typo", REGISTRY), "guest")

    def test_case_and_whitespace_tolerated(self) -> None:
        registry = {"mages": {"a": {"relation": "  Household "}}}
        self.assertEqual(mage.relation_for_mage("a", registry), "household")

    def test_unknown_key_is_a_guest(self) -> None:
        self.assertEqual(mage.relation_for_mage("nobody", REGISTRY), "guest")


class AdminCapabilityTests(unittest.TestCase):
    def test_admin_flag_grants(self) -> None:
        self.assertTrue(mage.is_admin_mage("operator", REGISTRY))

    def test_members_are_not_admins(self) -> None:
        for key in ("partner", "sibling", "friend", "unclassified"):
            self.assertFalse(mage.is_admin_mage(key, REGISTRY), key)

    def test_legacy_primary_still_grants(self) -> None:
        registry = {"mages": {"old": {"discord_id": "9", "primary": True}}}
        self.assertTrue(mage.is_admin_mage("old", registry))

    def test_default_mage_still_grants(self) -> None:
        registry = {"default_mage": "old", "mages": {"old": {"discord_id": "9"}}}
        self.assertTrue(mage.is_admin_mage("old", registry))

    def test_second_admin_needs_no_second_primary(self) -> None:
        registry = {
            "default_mage": "one",
            "mages": {
                "one": {"discord_id": "1", "primary": True},
                "two": {"discord_id": "2", "admin": True},
                "three": {"discord_id": "3"},
            },
        }
        self.assertEqual(mage.admin_discord_ids(registry), {1, 2})

    def test_unparseable_discord_id_is_skipped(self) -> None:
        registry = {"mages": {"broken": {"discord_id": "not-a-number", "admin": True}}}
        self.assertEqual(mage.admin_discord_ids(registry), set())


class ReachTests(unittest.TestCase):
    def _reach(self, sender: str, target: str) -> bool:
        return mage.may_reach(sender, target, REGISTRY)

    def test_household_and_kin_reach_each_other(self) -> None:
        self.assertTrue(self._reach("partner", "sibling"))
        self.assertTrue(self._reach("sibling", "partner"))

    def test_household_does_not_reach_guests(self) -> None:
        self.assertFalse(self._reach("partner", "friend"))

    def test_kin_does_not_reach_guests(self) -> None:
        self.assertFalse(self._reach("sibling", "friend"))

    def test_guest_reaches_admin_only(self) -> None:
        self.assertTrue(self._reach("friend", "operator"))
        self.assertFalse(self._reach("friend", "partner"))
        self.assertFalse(self._reach("friend", "sibling"))

    def test_admin_reaches_everyone(self) -> None:
        for key in ("partner", "sibling", "friend", "unclassified", "typo"):
            self.assertTrue(self._reach("operator", key), key)

    def test_nobody_reaches_themselves(self) -> None:
        self.assertFalse(self._reach("partner", "partner"))

    def test_missing_keys_deny(self) -> None:
        self.assertFalse(mage.may_reach(None, "partner", REGISTRY))
        self.assertFalse(mage.may_reach("partner", None, REGISTRY))

    def test_empty_registry_denies_everything(self) -> None:
        self.assertFalse(mage.may_reach("a", "b", {"mages": {}}))


class RelationIssueReportingTests(unittest.TestCase):
    def test_missing_and_unknown_relations_are_reported(self) -> None:
        issues = mage.registry_relation_issues(REGISTRY)
        joined = " ".join(issues)
        self.assertEqual(len(issues), 2)
        self.assertIn("unclassified", joined)
        self.assertIn("typo", joined)

    def test_fully_classified_registry_is_quiet(self) -> None:
        registry = {
            "mages": {
                "a": {"relation": "household"},
                "b": {"relation": "kin"},
                "c": {"relation": "guest"},
            }
        }
        self.assertEqual(mage.registry_relation_issues(registry), [])


if __name__ == "__main__":
    unittest.main()
