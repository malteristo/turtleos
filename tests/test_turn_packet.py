"""The packet a turn used is a file; !context renders only injection slots.

TURTLE_SPEC §3.2 line 1. current.yaml already existed (CE debounce). These tests
fail if persist writes that file, names the alive layer, or lists confirmed_by
as something that was "not loaded".
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub()

import continuity_engine as ce
import mage
import turn_packet as tp

FIREWALL_TERMS = ("bedrock", "sediment", "alive", "knot")
CARRY_TERMS = ("confirmed_by", "alive.yaml", "active_threads")
FIXED_NOW = datetime(2026, 8, 18, 12, 51, tzinfo=timezone.utc)


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "ana": {
                "practice_dir": f"{tmp}/ana",
                "address": "Ana",
                "discord_id": "111",
            },
            "ben": {
                "practice_dir": f"{tmp}/ben",
                "address": "Ben",
                "discord_id": "222",
            },
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["ana", "ben"],
            },
        },
        "channels": {},
    }


class InjectSlotCatalogTests(unittest.TestCase):
    def test_slots_never_name_the_alive_layer_or_confirmed_by(self) -> None:
        for key, label in tp.INJECT_SLOTS:
            blob = f"{key} {label}".lower()
            for term in FIREWALL_TERMS + CARRY_TERMS:
                self.assertNotIn(term, blob, f"slot {key!r} names {term!r}")


class PersistPacketTests(unittest.TestCase):
    def test_persist_is_a_noop_when_the_practice_root_is_missing(self) -> None:
        self.assertIsNone(
            tp.persist_turn_packet(
                "/nonexistent-practice-dir",
                1,
                injected={"practice_substrate": "x"},
            )
        )

    def test_unknown_keys_are_dropped_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = tp.persist_turn_packet(
                tmp,
                7,
                injected={
                    "practice_substrate": "the inject",
                    "alive_layer": "a distinctive label",
                    "confirmed_by": "Ben",
                },
                recorded_at=FIXED_NOW,
            )
            body = path.read_text(encoding="utf-8")
            self.assertIn("the inject", body)
            self.assertNotIn("a distinctive label", body)
            self.assertNotIn("Ben", body)
            self.assertNotIn("confirmed_by", body)
            self.assertNotIn("alive_layer", body)

    def test_empty_slots_are_named_under_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = tp.build_packet_markdown(
                3,
                injected={"practice_substrate": "here"},
                recorded_at=FIXED_NOW,
            )
            self.assertIn("### Practice substrate", body)
            self.assertIn("here", body)
            self.assertIn("## Not loaded this turn", body)
            self.assertIn("- Home working plan", body)
            self.assertIn("- Absorbed threads", body)
            self.assertNotIn("alive", body.lower())
            self.assertNotIn("confirmed_by", body)

    def test_tools_and_files_appear_when_a_read_ran(self) -> None:
        body = tp.build_packet_markdown(
            3,
            injected={"practice_substrate": "x"},
            tools_executed=[
                {
                    "name": "read_practice_file",
                    "args": {"filename": "desk/foo.md"},
                    "result": "ok",
                }
            ],
            recorded_at=FIXED_NOW,
        )
        self.assertIn("`read_practice_file`", body)
        self.assertIn("`desk/foo.md`", body)

    def test_search_is_a_tool_but_not_a_file_loaded(self) -> None:
        body = tp.build_packet_markdown(
            3,
            injected={},
            tools_executed=[
                {"name": "search_practice_files", "args": {"query": "x"}, "result": "hits"}
            ],
            recorded_at=FIXED_NOW,
        )
        self.assertIn("`search_practice_files`", body)
        self.assertIn("- none", body.split("## Files loaded")[1].split("##")[0])


class ContextCommandTests(unittest.IsolatedAsyncioTestCase):
    def test_missing_packet_is_honest_and_firewall_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = tp.render_context_command(tmp, 99)
            self.assertIn("No turn has been recorded", out)
            lowered = out.lower()
            for term in FIREWALL_TERMS:
                self.assertNotIn(term, lowered)
            self.assertNotIn("confirmed_by", out)

    def test_context_renders_the_persisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp.persist_turn_packet(
                tmp,
                42,
                injected={"practice_substrate": "UNIQUE_VIEW_MARKER"},
                recorded_at=FIXED_NOW,
            )
            out = tp.render_context_command(tmp, 42)
            self.assertIn("UNIQUE_VIEW_MARKER", out)
            self.assertIn("Practice substrate", out)

    async def test_cmd_context_posts_the_packet(self) -> None:
        from commands import cmd_context

        with tempfile.TemporaryDirectory() as tmp:
            tp.persist_turn_packet(
                tmp,
                8,
                injected={"runtime_environment": "ENV LINE"},
                recorded_at=FIXED_NOW,
            )
            message = MagicMock()
            message.channel.id = 8
            message.reply = AsyncMock()
            with patch("commands.set_practice_context"), patch(
                "commands.get_pd", return_value=tmp
            ):
                digest = await cmd_context(message, [])
            posted = "\n".join(call.args[0] for call in message.reply.await_args_list)
            self.assertIn("ENV LINE", posted)
            self.assertIn("Context this turn posted", digest)


class FirewallOverContextTests(unittest.TestCase):
    """Firewall and carry-guard extend over !context, with a shared-root control."""

    def test_shared_root_context_does_not_name_carry_or_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            family = f"{tmp}/family"
            ana = f"{tmp}/ana"
            Path(family).mkdir()
            Path(ana).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.add_active_thread(
                    family, "the birthday plan", confirmed_by="Ben"
                )
                ce.set_last_checkpoint(ana, "Ana's private plan about the dentist")
                # The inject a family turn actually uses — alive headers do not
                # reach it. Persist that inject, not the sibling root's yaml.
                inject = ce.render_substrate_packet(family)
                tp.persist_turn_packet(
                    family,
                    15,
                    injected={"practice_substrate": inject},
                    recorded_at=FIXED_NOW,
                )
                view = tp.render_context_command(family, 15).lower()
                stored = ce.list_active_threads(family)[0]
                self.assertEqual(stored["confirmed_by"], "Ben")
                self.assertIn("the birthday plan", stored["label"])
                for term in FIREWALL_TERMS + CARRY_TERMS:
                    self.assertNotIn(term, view, f"leaked {term!r}")
                self.assertNotIn("the birthday plan", view)
                self.assertNotIn("ana's private plan about the dentist", view)
                self.assertNotIn("ben", view)

    def test_dumping_alive_yaml_would_turn_the_firewall_red(self) -> None:
        """Positive control: if persist wrote the alive layer, this fails."""
        with tempfile.TemporaryDirectory() as tmp:
            family = f"{tmp}/family"
            Path(family).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.add_active_thread(
                    family, "the birthday plan", confirmed_by="Ben"
                )
                leaked = tp.build_packet_markdown(
                    1,
                    injected={
                        "practice_substrate": (
                            "In motion: the birthday plan — Ben\n"
                            "confirmed_by: Ben\n"
                            "alive.yaml active_threads"
                        )
                    },
                    recorded_at=FIXED_NOW,
                ).lower()
                with self.assertRaises(AssertionError):
                    for term in FIREWALL_TERMS + CARRY_TERMS:
                        self.assertNotIn(term, leaked)


class ConsideredSectionTests(unittest.TestCase):
    """What room memory had on offer, and what it carried."""

    def test_the_packet_names_the_notes_it_did_not_carry(self) -> None:
        body = tp.build_packet_markdown(
            1,
            injected={"practice_substrate": "block"},
            considered=[
                {"title": "the one it used", "when": "2026-08-18T10:00", "selected": True},
                {"title": "the one it skipped", "when": "2026-08-17T10:00", "selected": False},
            ],
            recorded_at=FIXED_NOW,
        )
        self.assertIn("Room memory considered", body)
        self.assertIn("1 of 2 notes", body)
        self.assertIn("[x] 2026-08-18 the one it used", body)
        self.assertIn("[ ] 2026-08-17 the one it skipped", body)

    def test_no_section_when_nothing_was_on_offer(self) -> None:
        """An empty room does not get a heading claiming a selection happened."""
        body = tp.build_packet_markdown(
            1, injected={"practice_substrate": "block"}, recorded_at=FIXED_NOW
        )
        self.assertNotIn("Room memory considered", body)


class PractitionerAllowlistTests(unittest.TestCase):
    def test_context_is_allowed_for_practitioners(self) -> None:
        from cmd_dispatch import _PRACTITIONER_COMMANDS

        self.assertIn("context", _PRACTITIONER_COMMANDS)


if __name__ == "__main__":
    unittest.main()
