"""Tests for admin host surface helpers (rivers list / sync / doctor / help)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

from admin_experience import (
    admin_help_default,
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
                "fares": {"discord_id": "1", "practice_dir": "~/workshops/fares"},
                "partner": {"discord_id": "2", "practice_dir": "~/workshops/partner"},
            },
            "channels": {
                "111": {
                    "mage": "fares",
                    "type": "hosted-river",
                    "name": "fares-dialogue",
                    "discord_name": "river-fares",
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
                    "name": "river-pending",
                    "discord_name": "river-pending",
                },
            },
        }
        rows = iter_river_rows(registry)
        self.assertEqual(len(rows), 3)
        by_key = {r.mage_key: r for r in rows}
        self.assertTrue(by_key["fares"].name_drift)  # registry name stale
        self.assertTrue(by_key["partner"].name_drift)
        self.assertFalse(by_key["pending"].name_drift)
        listing = format_rivers_list(rows)
        self.assertIn("fares", listing)
        self.assertIn("unclaimed", listing)

    def test_plan_sync_names_registry_only_when_discord_ok(self) -> None:
        registry = {
            "mages": {"fares": {"discord_id": "1"}},
            "channels": {
                "111": {
                    "mage": "fares",
                    "type": "hosted-river",
                    "name": "fares-dialogue",
                    "discord_name": "river-fares",
                },
            },
        }
        guild = MagicMock()
        ch = MagicMock()
        ch.name = "river-fares"
        guild.get_channel.return_value = ch
        actions = plan_sync_names(registry, guild)
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0].discord_rename)
        self.assertTrue(actions[0].registry_cleanup)
        preview = format_sync_preview(actions)
        self.assertIn("dry-run", preview)

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
        guild = MagicMock()
        guild.members = [MagicMock(bot=False), MagicMock(bot=True)]
        findings = collect_doctor_findings(registry, guild)
        joined = "\n".join(findings)
        self.assertIn("name drift", joined)


if __name__ == "__main__":
    unittest.main()
