"""Tests for in-thread lifecycle bar eligibility and state."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import eddy_lifecycle_bar as bar


class TestLifecycleBarEligibility(unittest.TestCase):
    def test_bootstrap_allows_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertTrue(bar.bootstrap_bar_eligible(11, 22))

    def test_live_blocks_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))

    def test_blocks_awaiting_intake(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=False):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=True):
                with patch("prompts.uses_native_turtle_prompt", return_value=True):
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))
                    self.assertFalse(bar.bootstrap_bar_eligible(11, 22))

    def test_allows_live_eddy(self) -> None:
        with patch.object(bar, "standing_lifecycle_bar_enabled", return_value=True):
            with patch("eddy_spawn.is_awaiting_title", return_value=False):
                with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                    with patch("prompts.uses_native_turtle_prompt", return_value=True):
                        self.assertTrue(bar.lifecycle_bar_eligible(11, 22))

    def test_native_enables_standing_bar(self) -> None:
        self.assertTrue(bar.standing_lifecycle_bar_enabled())


class TestLifecycleBarState(unittest.TestCase):
    def test_mark_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lifecycle_bar.json"
            with patch.object(bar, "_state_path", return_value=str(path)):
                self.assertFalse(bar.is_lifecycle_bar_active(99))
                bar._mark_bar_message(99, 12345)
                self.assertTrue(bar.is_lifecycle_bar_active(99))
                self.assertEqual(bar._load_state()["99"], 12345)
                bar.clear_lifecycle_bar_state(99)
                self.assertFalse(bar.is_lifecycle_bar_active(99))


class TestLifecycleBarArtifactsButton(unittest.TestCase):
    def test_eddy_bar_phased_flow_pick_and_live_actions(self) -> None:
        src = (Path(__file__).resolve().parents[1] / "eddy_lifecycle_bar.py").read_text(
            encoding="utf-8"
        )
        block = src.split("class EddyLifecycleBarView")[1].split("class EddyDissolveConfirmView")[0]
        self.assertIn("eddy:lifecycle:flowpick:", block)
        self.assertIn('label="checkpoint"', block)
        self.assertIn('label="share"', block)
        self.assertIn('phase == "live"', block)


class TestBarPhaseState(unittest.TestCase):
    def test_phase_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            phase_path = Path(tmp) / "bar_phase.json"
            with patch.object(bar, "_phase_state_path", return_value=str(phase_path)):
                self.assertIsNone(bar.get_bar_phase(42))
                bar.set_bar_phase(42, "bootstrap")
                self.assertEqual(bar.get_bar_phase(42), "bootstrap")
                bar.set_bar_phase(42, "live")
                self.assertEqual(bar.get_bar_phase(42), "live")
                bar.clear_bar_phase(42)
                self.assertIsNone(bar.get_bar_phase(42))


class TestPractitionerAuthor(unittest.TestCase):
    def test_spirit_counts_as_practitioner(self) -> None:
        class Author:
            bot = True
            id = 499

        class Msg:
            author = Author()

        with patch("state.SPIRIT_BOT_ID", 499):
            self.assertTrue(bar._is_practitioner_author(Msg()))


class TestRiverActCustomIds(unittest.TestCase):
    def test_roundtrip_simple_command(self) -> None:
        cid = bar._encode_act_custom_id(1234567890, "!checkpoint")
        self.assertIsNotNone(cid)
        channel_id, command = bar._decode_act_custom_id(cid)
        self.assertEqual(channel_id, 1234567890)
        self.assertEqual(command, "checkpoint")

    def test_roundtrip_thread_command(self) -> None:
        cmd = '!thread "my topic" --model local'
        cid = bar._encode_act_custom_id(99, cmd)
        self.assertIsNotNone(cid)
        _, decoded = bar._decode_act_custom_id(cid)
        self.assertEqual(decoded, cmd.lstrip("!"))

    def test_long_fetch_uses_hash_fallback(self) -> None:
        cmd = "!fetch https://example.com/" + ("a" * 120)
        cid = bar._encode_act_custom_id(42, cmd)
        self.assertIsNotNone(cid)
        self.assertIn(":h:", cid)
        _, decoded = bar._decode_act_custom_id(cid)
        self.assertEqual(decoded, cmd.lstrip("!"))


if __name__ == "__main__":
    unittest.main()


class TestLifecycleBarRehydration(unittest.TestCase):
    """A restart must not leave live bars with dead buttons.

    Reported 2026-08-20: checkpoint pressed, nothing happened, and nothing was
    logged — Discord routes a component interaction to the owning client, and an
    unregistered persistent view means our code never runs.
    """

    def test_rehydrate_registers_a_view_per_live_bar(self) -> None:
        registered: list[object] = []

        class _Client:
            def add_view(self, view):
                registered.append(view)

        with patch.object(bar, "_load_state", return_value={"101": 9001, "102": 9002}):
            with patch.object(bar, "get_bar_phase", return_value="live"):
                with patch("flow_runner.list_flow_ids_for_bar_phase", return_value=["f1"]):
                    count = bar.rehydrate_lifecycle_bar_views(_Client())

        self.assertEqual(count, 2)
        self.assertEqual(len(registered), 2)

    def test_rehydrate_skips_a_bar_with_no_children(self) -> None:
        """An empty view cannot be registered persistently — skip, do not raise."""

        class _Client:
            def add_view(self, view):
                raise AssertionError("must not register an empty view")

        with patch.object(bar, "_load_state", return_value={"101": 9001}):
            with patch.object(bar, "get_bar_phase", return_value="bootstrap"):
                with patch("flow_runner.list_flow_ids_for_bar_phase", return_value=[]):
                    self.assertEqual(bar.rehydrate_lifecycle_bar_views(_Client()), 0)

    def test_one_bad_row_does_not_cost_the_rest(self) -> None:
        seen: list[object] = []

        class _Client:
            def add_view(self, view):
                seen.append(view)

        phases = {"101": "live", "102": "live"}

        def _phase(thread_id):
            if thread_id == 101:
                raise RuntimeError("phase state unreadable")
            return phases[str(thread_id)]

        with patch.object(bar, "_load_state", return_value={"101": 1, "102": 2}):
            with patch.object(bar, "get_bar_phase", side_effect=_phase):
                with patch("flow_runner.list_flow_ids_for_bar_phase", return_value=["f1"]):
                    self.assertEqual(bar.rehydrate_lifecycle_bar_views(_Client()), 1)
        self.assertEqual(len(seen), 1)

    def test_river_startup_calls_the_rehydrate(self) -> None:
        """The guard that actually protects the practitioner.

        The function existing is not the fix; River calling it at startup is.
        Asserted by shape against the source so a refactor that drops the call
        fails here rather than in an eddy.
        """
        src = Path("river_bot.py").read_text(encoding="utf-8")
        self.assertIn("rehydrate_lifecycle_bar_views", src)
        setup = src.split("async def _setup_native_river()", 1)[1].split("asyncio.create_task", 1)[0]
        self.assertIn("rehydrate_lifecycle_bar_views(river_client)", setup)

    def test_bar_declaration_matches_what_the_view_renders(self) -> None:
        """prompts.py told Turtle the bar carried release and dissolve. It never did."""
        prompts_src = Path("prompts.py").read_text(encoding="utf-8")
        line = next(
            ln for ln in prompts_src.splitlines() if "Lifecycle bar (always visible" in ln
        )
        view_src = Path("eddy_lifecycle_bar.py").read_text(encoding="utf-8")
        block = view_src.split("class EddyLifecycleBarView", 1)[1].split(
            "class EddyDissolveConfirmView", 1
        )[0]
        for label in ("checkpoint", "share"):
            self.assertIn(f'label="{label}"', block)
            self.assertIn(label, line)
        for absent in ("release", "dissolve"):
            self.assertNotIn(f'label="{absent}"', block)
            self.assertNotIn(f"· {absent}", line)
