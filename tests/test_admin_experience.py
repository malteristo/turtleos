"""Tests for admin host surface helpers (rivers list / sync / doctor / help)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from admin_experience import (
    admin_help_default,
    apply_sync_names,
    collect_doctor_findings,
    format_rivers_list,
    format_sync_preview,
    iter_river_rows,
    plan_sync_names,
)


class AdminExperienceTests(unittest.TestCase):
    def test_help_teaches_invite_not_onboard(self) -> None:
        help_text = admin_help_default()
        self.assertIn("!admin invite", help_text)
        self.assertIn("!admin rivers", help_text)
        self.assertIn("rivers admit", help_text)
        self.assertIn("!admin doctor", help_text)
        self.assertNotIn("!admin onboard", help_text)

    def test_iter_river_rows_and_drift(self) -> None:
        registry = {
            "mages": {
                "robin": {"discord_id": "1", "practice_dir": "~/workshops/robin"},
                "partner": {"discord_id": "2", "practice_dir": "~/workshops/partner"},
            },
            "channels": {
                "111": {
                    "mage": "robin",
                    "type": "hosted-river",
                    "name": "robin-dialogue",
                    "discord_name": "home-robin",
                },
                "222": {
                    "mage": "partner",
                    "type": "hosted-river",
                    "name": "partner-dialogue",
                    "discord_name": "partner-dialogue",
                },
                "333": {
                    "mage": "pending",
                    "type": "unclaimed-river",
                    "river_key": "🌿",
                    "name": "home-pending",
                    "discord_name": "home-pending",
                },
            },
        }
        rows = iter_river_rows(registry)
        self.assertEqual(len(rows), 3)
        by_key = {r.mage_key: r for r in rows}
        self.assertTrue(by_key["robin"].name_drift)  # registry name stale
        self.assertTrue(by_key["partner"].name_drift)
        self.assertFalse(by_key["pending"].name_drift)
        listing = format_rivers_list(rows)
        self.assertIn("robin", listing)
        self.assertIn("unclaimed", listing)

    def test_plan_sync_names_registry_only_when_discord_ok(self) -> None:
        registry = {
            "mages": {"robin": {"discord_id": "1"}},
            "channels": {
                "111": {
                    "mage": "robin",
                    "type": "hosted-river",
                    "name": "robin-dialogue",
                    "discord_name": "home-robin",
                },
            },
        }
        guild = MagicMock()
        ch = MagicMock()
        ch.name = "home-robin"
        guild.get_channel.return_value = ch
        actions = plan_sync_names(registry, guild)
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0].discord_rename)
        self.assertTrue(actions[0].registry_cleanup)
        preview = format_sync_preview(actions)
        self.assertIn("dry-run", preview)

    def test_sync_names_renames_an_old_river_channel_to_home(self) -> None:
        # 2026-09-27: a member's own channel is their home channel; River is the agent.
        registry = {
            "mages": {"robin": {"discord_id": "1"}},
            "channels": {"111": {"mage": "robin", "type": "hosted-river",
                                 "name": "river-robin", "discord_name": "river-robin"}},
        }
        guild = MagicMock()
        ch = MagicMock()
        ch.name = "river-robin"
        guild.get_channel.return_value = ch
        (action,) = plan_sync_names(registry, guild)
        self.assertTrue(action.discord_rename)
        self.assertEqual(action.desired_name, "home-robin")
        self.assertIn("`#river-robin` → `#home-robin`", action.note)

    def test_an_operator_made_river_room_is_a_home_channel_too(self) -> None:
        # 2026-09-27: the operator's own `#river` and Spirit's room were type
        # `river`; the home-channel tools only knew `hosted-river`.
        registry = {
            "mages": {"kermit": {"discord_id": "1"}, "spirit": {"discord_id": "2"},
                      "alex": {"discord_id": "3"}},
            "channels": {
                "10": {"type": "river", "mage": "kermit", "name": "river", "discord_name": "home-kermit"},
                "20": {"type": "river", "mage": "spirit", "primitive": "private", "name": "spirit"},
                "30": {"type": "river", "mage": "alex", "name": "home-alex"},
                "31": {"type": "river", "mage": "alex", "name": "alex-notes"},
            },
        }
        by_key = {r.mage_key: r for r in iter_river_rows(registry)}
        self.assertEqual(set(by_key), {"kermit", "spirit"})
        guild = MagicMock()
        live = {10: "home-kermit", 20: "home-spirit"}

        def channel(cid):
            ch = MagicMock()
            ch.name = live[cid]
            return ch

        guild.get_channel.side_effect = channel
        actions = {a.mage_key: a for a in plan_sync_names(registry, guild)}
        self.assertFalse(actions["kermit"].discord_rename)
        self.assertTrue(actions["kermit"].registry_cleanup)
        self.assertEqual(actions["spirit"].desired_name, "home-spirit")

    def test_sync_names_records_the_home_category(self) -> None:
        # 2026-09-27: the operator renamed the category to "Home"; the registry
        # still expected "Rivers" / "Practice", so every edit would warn of drift.
        registry = {
            "mages": {"sam": {"discord_id": "1"}},
            "channels": {"11": {"type": "hosted-river", "mage": "sam", "name": "home-sam",
                                "discord_name": "home-sam", "discord_category": "Rivers"}},
        }
        guild = MagicMock()
        ch = MagicMock()
        ch.name = "home-sam"
        guild.get_channel.return_value = ch
        (action,) = plan_sync_names(registry, guild)
        self.assertFalse(action.discord_rename)
        self.assertTrue(action.registry_cleanup)
        import asyncio

        with patch("admin_experience.save_registry"):
            asyncio.run(apply_sync_names(registry, guild, [action]))
        self.assertEqual(registry["channels"]["11"]["discord_category"], "Home")

    def test_doctor_reports_invite_will_fail_without_admin_id(self) -> None:
        """Invite and doctor must agree. Empty admin set used to look healthy."""
        registry = {
            "mages": {
                "default": {
                    "discord_id": "YOUR_DISCORD_USER_ID",
                    "primary": True,
                    "admin": True,
                }
            },
            "channels": {},
        }
        findings = collect_doctor_findings(registry, None)
        joined = "\n".join(findings)
        self.assertIn("invite", joined)
        self.assertIn("primary operator", joined)
        self.assertNotIn("No admin issues", joined)

    def test_doctor_reports_name_drift(self) -> None:
        registry = {
            "mages": {"x": {"discord_id": "1"}},
            "channels": {
                "1": {
                    "mage": "x",
                    "type": "hosted-river",
                    "name": "x-dialogue",
                    "discord_name": "x-dialogue",
                },
            },
        }
        human = MagicMock(bot=False)
        human.id = 1
        guild = MagicMock()
        guild.members = [human, MagicMock(bot=True)]
        findings = collect_doctor_findings(registry, guild)
        joined = "\n".join(findings)
        self.assertIn("name drift", joined)

    def test_doctor_reports_roster_drift(self) -> None:
        """Bijection failure must not look healthy."""
        registry = {
            "mages": {"ghost": {"discord_id": "7"}},
            "channels": {},
        }
        human = MagicMock(bot=False)
        human.id = 9
        guild = MagicMock()
        guild.members = [human, MagicMock(bot=True)]
        findings = collect_doctor_findings(registry, guild)
        joined = "\n".join(findings)
        self.assertIn("on Discord not in turtleOS", joined)
        self.assertIn("in turtleOS not on Discord", joined)
        self.assertNotIn("No admin issues", joined)


if __name__ == "__main__":
    unittest.main()
