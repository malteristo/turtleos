"""Channel primitives bind Channel + Turtle + River + Practice."""

from __future__ import annotations

import unittest

from channel_primitives import (
    assign_health_support,
    primitive_definition,
    resolve_primitive,
)
from scripts.migrate_channel_architecture import migrated as migrated_channels
from scripts.migrate_health_primitive import migrated


class ChannelPrimitiveTests(unittest.TestCase):
    def test_explicit_health_primitive_resolves_complete_contract(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "subject": "partner",
                    "steward": "default",
                    "memory": "isolated",
                }
            },
            "channels": {
                "42": {
                    "primitive": "health",
                    "type": "shared-river",
                    "mage": "health",
                }
            },
        }
        primitive = resolve_primitive(registry, 42)
        self.assertIsNotNone(primitive)
        assert primitive is not None
        self.assertEqual(primitive.base, "shared")
        self.assertEqual(primitive.attunement, "health")
        self.assertEqual(primitive.parent_owner, "river")
        self.assertEqual(primitive.data_policy, "sensitive_local")
        self.assertTrue(primitive.has("source_intake"))
        self.assertEqual(primitive.role_for("partner"), "subject")
        self.assertEqual(primitive.role_for("default"), "steward")

    def test_legacy_health_row_has_deterministic_role_adapter(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "memory": "isolated",
                }
            },
            "channels": {"42": {"type": "health", "mage": "health"}},
        }
        primitive = resolve_primitive(registry, "42")
        self.assertIsNotNone(primitive)
        assert primitive is not None
        self.assertEqual(primitive.subject, "partner")
        self.assertEqual(primitive.steward, "default")

    def test_health_fails_closed_without_isolated_memory(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "subject": "partner",
                    "steward": "default",
                    "memory": "own_root",
                }
            },
            "channels": {"42": {"primitive": "health", "mage": "health"}},
        }
        self.assertIsNone(resolve_primitive(registry, 42))

        # Positive control: restoring the required boundary makes it resolvable.
        registry["spaces"]["health"]["memory"] = "isolated"
        self.assertIsNotNone(resolve_primitive(registry, 42))

    def test_solo_health_requires_subject_but_not_fictional_steward(self) -> None:
        registry = {
            "mages": {
                "owner": {
                    "practice_dir": "/tmp/owner-health",
                }
            },
            "channels": {
                "42": {
                    "primitive": "health",
                    "base": "solo",
                    "mage": "owner",
                    "subject": "owner",
                }
            },
        }
        primitive = resolve_primitive(registry, 42)
        self.assertIsNotNone(primitive)
        assert primitive is not None
        self.assertEqual(primitive.base, "solo")
        self.assertTrue(primitive.has_role("owner", "subject"))
        self.assertFalse(primitive.has_role("owner", "steward"))

        registry["channels"]["42"]["subject"] = "someone-else"
        self.assertIsNone(resolve_primitive(registry, 42))

    def test_space_owned_solo_health_does_not_use_personal_mage_dir(self) -> None:
        registry = {
            "mages": {
                "operator": {"practice_dir": "/tmp/operator"},
            },
            "spaces": {
                "health": {
                    "practice_dir": "/tmp/health",
                    "members": ["operator", "patient"],
                    "subject": "patient",
                    "steward": "operator",
                    "memory": "isolated",
                },
                "health-operator": {
                    "practice_dir": "/tmp/health-operator",
                    "members": ["operator"],
                    "subject": "operator",
                    "memory": "isolated",
                },
            },
            "channels": {
                "7": {
                    "primitive": "health",
                    "mage": "health",
                },
                "42": {
                    "primitive": "health",
                    "base": "solo",
                    "mage": "health-operator",
                    "subject": "operator",
                },
            },
        }
        house = resolve_primitive(registry, 7)
        own = resolve_primitive(registry, 42)
        self.assertIsNotNone(house)
        self.assertIsNotNone(own)
        assert house is not None and own is not None
        self.assertEqual(house.subject, "patient")
        self.assertEqual(house.steward, "operator")
        self.assertEqual(house.base, "shared")
        self.assertEqual(own.base, "solo")
        self.assertEqual(own.subject, "operator")
        self.assertEqual(own.members, ("operator",))
        self.assertIsNone(own.steward)
        self.assertEqual(own.practice_key, "health-operator")
        self.assertEqual(own.memory_boundary, "isolated")

        registry["spaces"]["health-operator"]["subject"] = "someone-else"
        self.assertIsNone(resolve_primitive(registry, 42))

    def test_presets_reject_unsupported_topology(self) -> None:
        registry = {
            "spaces": {
                "room": {
                    "members": ["one", "two"],
                    "coordinator": "one",
                }
            },
            "channels": {
                "42": {
                    "primitive": "craft",
                    "base": "shared",
                    "mage": "room",
                }
            },
        }
        self.assertIsNone(resolve_primitive(registry, 42))
        registry["channels"]["42"]["primitive"] = "team"
        self.assertIsNotNone(resolve_primitive(registry, 42))

    def test_partnership_is_two_person_shared_practice(self) -> None:
        registry = {
            "spaces": {
                "room": {
                    "members": ["one", "two"],
                    "memory": "own_root",
                }
            },
            "channels": {"42": {"primitive": "partnership", "mage": "room"}},
        }
        self.assertEqual(resolve_primitive(registry, 42).name, "partnership")
        registry["spaces"]["room"]["members"].append("three")
        self.assertIsNone(resolve_primitive(registry, 42))

    def test_unknown_primitive_gets_no_capabilities(self) -> None:
        registry = {"channels": {"42": {"primitive": "mystery"}}}
        self.assertIsNone(resolve_primitive(registry, 42))
        self.assertIsNone(primitive_definition("mystery"))

    def test_legacy_types_resolve_without_migration(self) -> None:
        registry = {
            "channels": {
                "1": {"type": "river"},
                "2": {"type": "shared-river"},
                "3": {"type": "craft"},
            }
        }
        self.assertEqual(resolve_primitive(registry, 1).name, "private")
        self.assertEqual(resolve_primitive(registry, 2).name, "shared")
        self.assertEqual(resolve_primitive(registry, 3).name, "craft")

    def test_health_registry_migration_names_roles_and_standard_parent(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "memory": "isolated",
                }
            },
            "channels": {"42": {"type": "health", "mage": "health"}},
        }
        result, channel_id = migrated(
            registry, subject="partner", steward="default"
        )
        self.assertEqual(result["channels"]["42"]["type"], "health")
        self.assertEqual(result["channels"]["42"]["primitive"], "health")
        primitive = resolve_primitive(result, channel_id)
        self.assertEqual(primitive.parent_owner, "river")
        self.assertEqual(primitive.role_for("partner"), "subject")

    def test_established_channel_migration_preserves_ids_and_roots(self) -> None:
        registry = {
            "mages": {"default": {"practice_dir": "/tmp/default"}},
            "spaces": {
                "family": {
                    "practice_dir": "/tmp/family",
                    "members": ["default", "partner"],
                }
            },
            "channels": {
                "10": {"type": "craft", "mage": "default"},
                "20": {"type": "shared-river", "mage": "family"},
            },
        }
        result, channels = migrated_channels(
            registry, craft_key="default", partnership_key="family"
        )
        self.assertEqual(channels, {"craft": "10", "partnership": "20"})
        self.assertEqual(result["channels"]["10"]["primitive"], "craft")
        self.assertEqual(result["channels"]["20"]["primitive"], "partnership")
        self.assertEqual(
            result["channels"]["20"]["default_context"], "partnership-room"
        )
        self.assertEqual(
            result["spaces"]["family"]["practice_dir"], "/tmp/family"
        )


class HealthSupportAssignmentTests(unittest.TestCase):
    def test_only_owner_can_assign_support(self) -> None:
        space = {
            "members": ["default", "partner"],
            "subject": "partner",
            "steward": None,
            "memory": "isolated",
        }
        updated = assign_health_support(space, actor="partner", support="default")
        self.assertEqual(updated["steward"], "default")
        with self.assertRaisesRegex(PermissionError, "only the health owner"):
            assign_health_support(space, actor="default", support="default")

    def test_owner_aliases_subject_and_support_aliases_steward(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "subject": "partner",
                    "steward": "default",
                    "memory": "isolated",
                }
            },
            "channels": {
                "42": {
                    "primitive": "health",
                    "type": "shared-river",
                    "mage": "health",
                }
            },
        }
        primitive = resolve_primitive(registry, 42)
        assert primitive is not None
        self.assertTrue(primitive.has_role("partner", "owner"))
        self.assertTrue(primitive.has_role("default", "support"))
        self.assertFalse(primitive.has_role("default", "owner"))


if __name__ == "__main__":
    unittest.main()
