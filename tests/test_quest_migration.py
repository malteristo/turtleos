"""Quest migration preserves the established shared space and campaign lineage."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from channel_primitives import resolve_primitive


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_quest_team.py"
SPEC = importlib.util.spec_from_file_location("migrate_quest_team", SCRIPT)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MIGRATION
SPEC.loader.exec_module(MIGRATION)


def config(coordinator: str = "member-a"):
    return MIGRATION.MigrationConfig(
        channel_id="700",
        prologue_thread_id="701",
        space_key="team_sandbox",
        activity_id="shared-adventure",
        channel_name="quest",
        coordinator=coordinator,
        topic="Asynchronous shared work",
        world="A shared world",
        current_scene="Two paths begin",
        lanes=(
            MIGRATION.Lane("member-a", "Adventure — A", "Character A", "ready"),
            MIGRATION.Lane("member-b", "Adventure — B", "Character B", "ready"),
        ),
    )


def registry() -> dict:
    return {
        "mages": {
            "member-a": {"discord_id": "1"},
            "member-b": {"discord_id": "2"},
        },
        "spaces": {
            "team_sandbox": {
                "practice_dir": "~/workshops/team_sandbox",
                "runtime_dir": "~/workshops/team_sandbox",
                "members": ["member-a", "member-b"],
                "share_policy": "members_only",
            }
        },
        "channels": {
            "700": {
                "mage": "team_sandbox",
                "type": "shared-river",
                "name": "team-sandbox",
            }
        },
    }


class QuestMigrationTests(unittest.TestCase):
    def test_registry_migrates_in_place_to_valid_team_contract(self) -> None:
        before = registry()
        after = MIGRATION.migrated_registry(before, config())
        self.assertEqual(
            after["spaces"]["team_sandbox"]["practice_dir"],
            before["spaces"]["team_sandbox"]["practice_dir"],
        )
        self.assertEqual(set(after["channels"]), set(before["channels"]))
        row = after["channels"]["700"]
        self.assertEqual(row["primitive"], "team")
        self.assertEqual(row["default_context"], "team")
        self.assertEqual(row["discord_category"], "Quest")
        self.assertEqual(row["name"], "quest")
        primitive = resolve_primitive(after, "700")
        self.assertEqual(primitive.coordinator, "member-a")
        self.assertEqual(primitive.members, ("member-a", "member-b"))

    def test_dry_run_names_both_member_lanes_and_prologue(self) -> None:
        before = registry()
        migration = config()
        after = MIGRATION.migrated_registry(before, migration)
        report = MIGRATION.dry_run(after, migration)
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(
            report["prologue_thread_id"], "701"
        )
        self.assertEqual(set(report["lanes"]), {"member-a", "member-b"})

    def test_team_without_member_coordinator_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            MIGRATION.migrated_registry(registry(), config("outsider"))

    def test_retry_reads_immutable_prologue_not_rebuilt_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "campaign" / "checkpoints" / "latest.md"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_text("original table", encoding="utf-8")
            migration = config()
            migrated = MIGRATION.migrated_registry(registry(), migration)
            primitive = resolve_primitive(migrated, migration.channel_id)
            first = MIGRATION.seed_live_campaign(root, primitive, migration)
            self.assertNotEqual(
                checkpoint.read_text(encoding="utf-8"), "original table"
            )
            second = MIGRATION.seed_live_campaign(root, primitive, migration)
            self.assertEqual(
                first["event"]["event_id"], second["event"]["event_id"]
            )


if __name__ == "__main__":
    unittest.main()
