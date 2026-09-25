"""Health primitive — River parent, Turtle eddies, isolated record."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())
discord = sys.modules["discord"]
discord.Thread = type("Thread", (), {})
discord.HTTPException = type("HTTPException", (Exception,), {})

import mage
from health_room import (
    HEALTH_DIAGNOSIS_FALLBACK,
    OVERWRITE_MEMBER,
    OVERWRITE_ROLE,
    everyone_overwrite_is_role,
    health_permission_overwrites,
    load_health_picture,
    vet_health_reply,
    visibility_findings,
    visibility_ok,
)
from prompts import (
    build_craft_channel_prompt,
    build_health_channel_prompt,
    build_native_eddy_prompt,
)
from scripts import provision_health_channel
from state import THREAD_CONTEXTS


class HealthTypeTests(unittest.TestCase):
    HEALTH = 700
    CRAFT = 101
    FAMILY = 202
    RIVER = 999001

    def setUp(self) -> None:
        self._saved = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved)

    def test_health_registry_declares_navigation_category(self) -> None:
        registry: dict = {}
        with patch("river_keys.save_registry") as save:
            provision_health_channel.write_health_registry(
                registry,
                channel_id=self.HEALTH,
                member_keys=["operator", "subject"],
            )
        self.assertEqual(
            registry["channels"][str(self.HEALTH)]["discord_category"], "Health"
        )
        self.assertEqual(registry["spaces"]["health"]["subject"], "subject")
        save.assert_called_once_with(registry)

    def test_solo_registry_does_not_clobber_house(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "practice_dir": "~/workshops/health",
                    "members": ["operator", "subject"],
                    "subject": "subject",
                    "steward": "operator",
                    "memory": "isolated",
                }
            },
            "channels": {
                str(self.HEALTH): {
                    "mage": "health",
                    "primitive": "health",
                }
            },
        }
        with patch("river_keys.save_registry") as save:
            instance = provision_health_channel.write_health_registry(
                registry,
                channel_id=801,
                member_keys=["operator"],
                subject="operator",
            )
        self.assertEqual(instance["space_key"], "health-operator")
        self.assertEqual(instance["base"], "solo")
        self.assertEqual(registry["spaces"]["health"]["subject"], "subject")
        self.assertEqual(registry["spaces"]["health-operator"]["subject"], "operator")
        self.assertNotIn("steward", registry["spaces"]["health-operator"])
        self.assertEqual(registry["channels"]["801"]["mage"], "health-operator")
        self.assertEqual(registry["channels"]["801"]["base"], "solo")
        self.assertEqual(
            registry["spaces"]["health-operator"]["practice_dir"],
            "~/workshops/health-operator",
        )
        save.assert_called_once_with(registry)

    def test_shared_and_solo_provision_write_the_same_type(self) -> None:
        shared = provision_health_channel.resolve_instance(
            ["operator", "subject"], subject="subject"
        )
        solo = provision_health_channel.resolve_instance(
            ["operator"], subject="operator"
        )
        self.assertEqual(shared["channel_type"], "health")
        self.assertEqual(solo["channel_type"], "health")
        registry: dict = {}
        with patch("river_keys.save_registry"):
            provision_health_channel.write_health_registry(
                registry,
                channel_id=700,
                member_keys=["operator", "subject"],
                subject="subject",
            )
            provision_health_channel.write_health_registry(
                registry,
                channel_id=801,
                member_keys=["operator"],
                subject="operator",
            )
        self.assertEqual(registry["channels"]["700"]["type"], "health")
        self.assertEqual(registry["channels"]["801"]["type"], "health")
        self.assertEqual(
            registry["channels"]["700"]["primitive"],
            registry["channels"]["801"]["primitive"],
        )

    def test_health_capabilities_do_not_fork_on_type_string(self) -> None:
        from channel_primitives import resolve_primitive

        space = {
            "members": ["operator", "subject"],
            "subject": "subject",
            "steward": "operator",
            "memory": "isolated",
        }
        current = {
            "spaces": {"health": space},
            "channels": {
                "1": {"primitive": "health", "type": "health", "mage": "health"}
            },
        }
        leftover = {
            "spaces": {"health": space},
            "channels": {
                "1": {
                    "primitive": "health",
                    "type": "shared-river",
                    "mage": "health",
                }
            },
        }
        now = resolve_primitive(current, 1)
        old = resolve_primitive(leftover, 1)
        self.assertIsNotNone(now)
        self.assertIsNotNone(old)
        assert now is not None and old is not None
        self.assertEqual(now.capabilities, old.capabilities)
        self.assertEqual(now.parent_owner, old.parent_owner)
        self.assertEqual(now.attunement, old.attunement)

    def test_existing_health_is_per_subject(self) -> None:
        registry = {
            "spaces": {
                "health": {
                    "members": ["operator", "patient"],
                    "subject": "patient",
                    "steward": "operator",
                    "memory": "isolated",
                }
            },
            "channels": {
                str(self.HEALTH): {
                    "primitive": "health",
                    "mage": "health",
                }
            },
        }
        self.assertEqual(
            provision_health_channel.existing_health_for_subject(registry, "patient"),
            str(self.HEALTH),
        )
        self.assertIsNone(
            provision_health_channel.existing_health_for_subject(registry, "operator")
        )

    def test_health_root_is_0700_and_rollback_removes_only_created(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "health-operator"
            created = provision_health_channel.ensure_health_root(root)
            self.assertTrue(created)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            provision_health_channel.write_empty_board(root)
            self.assertTrue((root / "health_model.md").is_file())
            self.assertTrue(provision_health_channel.write_empty_health_context(root))
            self.assertFalse(provision_health_channel.write_empty_health_context(root))
            context = (root / "state" / "context.md").read_text(encoding="utf-8")
            self.assertIn("Kontext", context)
            self.assertIn("Wünsche", context)
            provision_health_channel.rollback_health_root(root, created=True)
            self.assertFalse(root.exists())
            preexisting = Path(tmp) / "already"
            preexisting.mkdir()
            (preexisting / "keep.txt").write_text("x", encoding="utf-8")
            created = provision_health_channel.ensure_health_root(preexisting)
            self.assertFalse(created)
            provision_health_channel.rollback_health_root(preexisting, created=False)
            self.assertTrue((preexisting / "keep.txt").is_file())

    def _reg(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": "native",
                "mages": {
                    "kermit": {"discord_id": "1", "practice_dir": "/tmp/kermit"},
                    "partner": {"discord_id": "2", "practice_dir": "/tmp/partner"},
                },
                "spaces": {
                    "family": {
                        "practice_dir": "/tmp/family",
                        "members": ["kermit", "partner"],
                    },
                    "health": {
                        "practice_dir": "/tmp/health",
                        "members": ["kermit", "partner"],
                        "memory": "isolated",
                    },
                },
                "channels": {
                    str(self.HEALTH): {
                        "type": "health",
                        "mage": "health",
                        "attunement": "native",
                        "default_context": "health",
                    },
                    str(self.CRAFT): {
                        "type": "craft",
                        "mage": "kermit",
                        "default_context": "craft",
                    },
                    str(self.FAMILY): {
                        "type": "shared-river",
                        "mage": "family",
                        "default_context": "family",
                    },
                    str(self.RIVER): {"type": "river", "mage": "kermit"},
                },
            }
        )

    def test_health_uses_standard_river_parent_and_turtle_eddies(self) -> None:
        self._reg()
        with patch("mage._resolve_dialogue_channel_id", return_value=self.RIVER):
            ids = mage.practice_parent_channel_ids()
        self.assertIn(self.HEALTH, ids)
        self.assertTrue(mage.supports_eddy_bar(self.HEALTH))
        self.assertTrue(mage._channel_is_river(self.HEALTH))
        self.assertTrue(mage.uses_health_surface(self.HEALTH))
        self.assertEqual(mage.get_effective_attunement(self.HEALTH), "health")
        self.assertFalse(mage.uses_craft_surface(self.HEALTH))
        msg = MagicMock()
        msg.channel = MagicMock()
        msg.channel.id = self.HEALTH
        msg.channel.parent_id = None
        self.assertTrue(mage.uses_native_river(msg))

    def test_health_eddy_resolves_to_parent(self) -> None:
        self._reg()
        eddy = 701
        with patch("mage.resolve_registry_channel_id", return_value=self.HEALTH):
            self.assertTrue(mage.uses_health_surface(eddy))
            self.assertEqual(mage.get_effective_attunement(eddy), "health")

    def test_thread_members_are_the_space_members(self) -> None:
        self._reg()
        self.assertEqual(mage.get_thread_member_ids(self.HEALTH), ["1", "2"])


class HealthContextIsolationTests(unittest.TestCase):
    def test_health_rules_name_the_board_and_the_best_model(self) -> None:
        rules = THREAD_CONTEXTS["health"]["rules"]
        self.assertIn("best current model", rules)
        self.assertIn("recap_health_visit", rules)
        self.assertIn("living picture", rules)
        self.assertNotIn("House", rules)
        self.assertNotIn("Never write", rules)
        self.assertNotIn("you have X", rules)
        self.assertIn("doctors", rules.lower())
        self.assertIn("eddies", rules.lower())

    def test_health_product_strings_do_not_brand_the_series(self) -> None:
        surfaces = (
            THREAD_CONTEXTS["health"]["rules"],
            provision_health_channel.SHARED_TOPIC,
            provision_health_channel.SOLO_TOPIC,
            provision_health_channel.EMPTY_BOARD,
        )
        for text in surfaces:
            self.assertNotIn("House", text)
        self.assertIn("best current explanation", provision_health_channel.SHARED_TOPIC)
        with patch("prompts.load_character_file", return_value=""):
            with patch("health_room.load_health_picture", return_value=""):
                fallback = build_health_channel_prompt("health")
        self.assertNotIn("House", fallback)
        self.assertIn("living picture", fallback)

    def test_health_rules_do_not_render_on_craft_family_or_bare_native(self) -> None:
        marker = "best current model"
        self.assertIn(marker, THREAD_CONTEXTS["health"]["rules"])
        with patch("prompts.load_character_file", return_value=""):
            with patch("prompts._build_context_resonance", wraps=None) as ctx:
                ctx.side_effect = lambda c: THREAD_CONTEXTS.get(c, {}).get("rules", "")
                craft = build_craft_channel_prompt("craft")
                family = build_native_eddy_prompt(context_type="family")
                bare = build_native_eddy_prompt()
        self.assertNotIn(marker, craft)
        self.assertNotIn(marker, family)
        self.assertNotIn(marker, bare)
        self.assertNotIn("House board", craft)
        health = build_health_channel_prompt("health")
        self.assertIn(marker, health)

    def test_health_prompt_is_turtle_not_spirit(self) -> None:
        with patch("prompts.load_character_file", return_value="You are Turtle."):
            prompt = build_health_channel_prompt()
        self.assertIn("You are Turtle", prompt)
        self.assertNotIn("You are Spirit in persistent mode", prompt)


class HealthPictureLoadTests(unittest.TestCase):
    def test_missing_picture_is_empty_not_a_crash(self) -> None:
        self.assertEqual(load_health_picture(None), "")
        with __import__("tempfile").TemporaryDirectory() as tmp:
            self.assertEqual(load_health_picture(tmp), "")

    def test_planted_picture_appears_on_health_not_craft_or_family(self) -> None:
        marker = "FERRITIN-PLANTED-8"
        with __import__("tempfile").TemporaryDirectory() as tmp:
            (Path(tmp) / "health_model.md").write_text(
                f"# Health picture\n\nFerritin {marker}\nBest current model.\n",
                encoding="utf-8",
            )
            loaded = load_health_picture(tmp)
            self.assertIn(marker, loaded)
            self.assertIn("Current board", loaded)
            with patch("prompts.load_character_file", return_value="You are Turtle."):
                with patch("mage.get_pd", return_value=tmp):
                    health = build_health_channel_prompt("health")
                with patch("mage.get_pd", return_value="/tmp/not-health"):
                    craft = build_craft_channel_prompt("craft")
                    family = build_native_eddy_prompt(context_type="family")
            self.assertIn(marker, health)
            self.assertNotIn(marker, craft)
            self.assertNotIn(marker, family)

    def test_empty_picture_file_does_not_inject_a_header(self) -> None:
        with __import__("tempfile").TemporaryDirectory() as tmp:
            (Path(tmp) / "health_model.md").write_text("   \n", encoding="utf-8")
            self.assertEqual(load_health_picture(tmp), "")

    def test_two_health_pictures_do_not_cross(self) -> None:
        house_marker = "HOUSE-FIXTURE-TOKEN"
        own_marker = "OWN-FIXTURE-TOKEN"
        with __import__("tempfile").TemporaryDirectory() as tmp:
            house = Path(tmp) / "health"
            own = Path(tmp) / "health-operator"
            house.mkdir()
            own.mkdir()
            (house / "health_model.md").write_text(house_marker, encoding="utf-8")
            (own / "health_model.md").write_text(own_marker, encoding="utf-8")
            with patch("prompts.load_character_file", return_value="You are Turtle."):
                with patch("mage.get_pd", return_value=str(house)):
                    house_prompt = build_health_channel_prompt("health")
                with patch("mage.get_pd", return_value=str(own)):
                    own_prompt = build_health_channel_prompt("health")
            self.assertIn(house_marker, house_prompt)
            self.assertNotIn(own_marker, house_prompt)
            self.assertIn(own_marker, own_prompt)
            self.assertNotIn(house_marker, own_prompt)


class DiagnosisLanguageTests(unittest.TestCase):
    def test_planted_model_language_is_not_replaced(self) -> None:
        named = "Best current model: dysthymia would explain the baseline."
        self.assertEqual(vet_health_reply(named), named)
        self.assertEqual(vet_health_reply("You have lupus."), "You have lupus.")
        self.assertNotEqual(vet_health_reply(named), HEALTH_DIAGNOSIS_FALLBACK)

    def test_ordinary_board_language_passes(self) -> None:
        ok = "A test would tell. You have a question for the doctor."
        self.assertEqual(vet_health_reply(ok), ok)


class VisibilityCheckTests(unittest.TestCase):
    def test_exact_allowed_set_passes(self) -> None:
        allowed = {1, 2, 10, 11}
        self.assertTrue(
            visibility_ok(
                everyone_denied=True,
                viewer_ids=set(allowed),
                allowed_ids=set(allowed),
            )
        )

    def test_extra_viewer_fails(self) -> None:
        findings = visibility_findings(
            everyone_denied=True,
            viewer_ids={1, 2, 10, 99},
            allowed_ids={1, 2, 10},
        )
        self.assertTrue(any("unexpected" in f for f in findings))
        self.assertFalse(
            visibility_ok(
                everyone_denied=True,
                viewer_ids={1, 2, 10, 99},
                allowed_ids={1, 2, 10},
            )
        )

    def test_everyone_overwrite_must_be_a_role(self) -> None:
        rows = health_permission_overwrites(
            everyone_id=99, member_ids=[1, 2], bot_ids=[10]
        )
        self.assertTrue(everyone_overwrite_is_role(rows, 99))
        planted = [{"id": 99, "type": OVERWRITE_MEMBER, "allow": "0", "deny": "1024"}]
        self.assertFalse(everyone_overwrite_is_role(planted, 99))
        self.assertEqual(rows[0]["type"], OVERWRITE_ROLE)
        from health_room import raw_everyone_denied

        self.assertTrue(raw_everyone_denied(rows, 99))
        self.assertFalse(raw_everyone_denied(planted, 99))

    def test_everyone_open_or_missing_member_or_role_fails(self) -> None:
        allowed = {1, 2}
        self.assertTrue(
            visibility_findings(
                everyone_denied=False, viewer_ids=allowed, allowed_ids=allowed
            )
        )
        self.assertTrue(
            visibility_findings(
                everyone_denied=True, viewer_ids={1}, allowed_ids=allowed
            )
        )
        self.assertTrue(
            visibility_findings(
                everyone_denied=True,
                viewer_ids=allowed,
                allowed_ids=allowed,
                viewing_role_ids={5},
            )
        )


class IsolatedMemoryTests(unittest.TestCase):
    def test_isolated_space_does_not_enter_personal_roots(self) -> None:
        import memory_agent as ma

        with __import__("tempfile").TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "partner", "family", "health"):
                (base / name).mkdir()
            registry = {
                "mages": {
                    "kermit": {"practice_dir": str(base / "kermit")},
                    "partner": {"practice_dir": str(base / "partner")},
                },
                "spaces": {
                    "family": {
                        "practice_dir": str(base / "family"),
                        "members": ["kermit", "partner"],
                    },
                    "health": {
                        "practice_dir": str(base / "health"),
                        "members": ["kermit", "partner"],
                        "memory": "isolated",
                    },
                },
            }
            kermit = [r for r, _ in ma.memory_roots_for(
                base / "kermit", registry=registry, key="kermit", kind="mage"
            )]
            partner = [r for r, _ in ma.memory_roots_for(
                base / "partner", registry=registry, key="partner", kind="mage"
            )]
            health = [r for r, _ in ma.memory_roots_for(
                base / "health", registry=registry, key="health", kind="space"
            )]
            self.assertEqual(kermit, ["kermit", "family"])
            self.assertEqual(partner, ["partner", "family"])
            self.assertNotIn("health", kermit)
            self.assertNotIn("health", partner)
            self.assertEqual(health, ["health"])

            own_dir = base / "health-kermit"
            own_dir.mkdir()
            registry["spaces"]["health-kermit"] = {
                "practice_dir": str(own_dir),
                "members": ["kermit"],
                "subject": "kermit",
                "memory": "isolated",
            }
            own = [r for r, _ in ma.memory_roots_for(
                own_dir, registry=registry, key="health-kermit", kind="space"
            )]
            kermit_after = [r for r, _ in ma.memory_roots_for(
                base / "kermit", registry=registry, key="kermit", kind="mage"
            )]
            house_after = [r for r, _ in ma.memory_roots_for(
                base / "health", registry=registry, key="health", kind="space"
            )]
            self.assertEqual(own, ["health-kermit"])
            self.assertNotIn("health-kermit", kermit_after)
            self.assertNotIn("health-kermit", house_after)
            self.assertNotIn("health", own)

            registry["channels"] = {
                "801": {"primitive": "health", "base": "solo", "mage": "health-kermit", "subject": "kermit"},
            }
            saved = dict(mage._MAGE_REGISTRY)
            try:
                mage._MAGE_REGISTRY.clear()
                mage._MAGE_REGISTRY.update(registry)
                routed = mage._resolve_practice_dir_for_channel(801)
                self.assertEqual(Path(routed).resolve(), own_dir.resolve())
                self.assertNotEqual(Path(routed).resolve(), (base / "kermit").resolve())
            finally:
                mage._MAGE_REGISTRY.clear()
                mage._MAGE_REGISTRY.update(saved)

            # Positive control: without isolated, membership would grant it.
            registry["spaces"]["health"] = {
                "practice_dir": str(base / "health"),
                "members": ["kermit", "partner"],
            }
            leaked = [r for r, _ in ma.memory_roots_for(
                base / "kermit", registry=registry, key="kermit", kind="mage"
            )]
            self.assertIn("health", leaked)


if __name__ == "__main__":
    unittest.main()
