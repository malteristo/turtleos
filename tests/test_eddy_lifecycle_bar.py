"""Tests for in-thread lifecycle bar eligibility and state."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import eddy_lifecycle_bar as bar


class TestLifecycleBarEligibility(unittest.TestCase):
    def _runtime(self):
        return patch(
            "primitive_runtime.runtime_for",
            return_value=SimpleNamespace(lifecycle_bar=True),
        )

    def test_bootstrap_allows_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with self._runtime():
                    self.assertTrue(bar.bootstrap_bar_eligible(11, 22))

    def test_live_blocks_awaiting_title(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                with self._runtime():
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))

    def test_blocks_awaiting_intake(self) -> None:
        with patch("eddy_spawn.is_awaiting_title", return_value=False):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=True):
                with self._runtime():
                    self.assertFalse(bar.lifecycle_bar_eligible(11, 22))
                    self.assertFalse(bar.bootstrap_bar_eligible(11, 22))

    def test_allows_live_eddy(self) -> None:
        with patch.object(bar, "standing_lifecycle_bar_enabled", return_value=True):
            with patch("eddy_spawn.is_awaiting_title", return_value=False):
                with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                    with self._runtime():
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
        self.assertIn("lifecycle_act_labels", block)


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

        class _View:
            children = [object()]

            def __init__(self, *args, **kwargs):
                pass

        with patch.object(bar, "_load_state", return_value={"101": 9001, "102": 9002}):
            with patch.object(bar, "get_bar_phase", return_value="live"):
                with patch.object(bar, "EddyLifecycleBarView", _View):
                    count = bar.rehydrate_lifecycle_bar_views(_Client())

        self.assertEqual(count, 2)
        self.assertEqual(len(registered), 2)

    def test_rehydrate_skips_a_bar_with_no_children(self) -> None:
        """An empty view cannot be registered persistently — skip, do not raise."""

        class _Client:
            def add_view(self, view):
                raise AssertionError("must not register an empty view")

        class _Empty:
            children = []

            def __init__(self, *args, **kwargs):
                pass

        with patch.object(bar, "_load_state", return_value={"101": 9001}):
            with patch.object(bar, "get_bar_phase", return_value="bootstrap"):
                with patch.object(bar, "EddyLifecycleBarView", _Empty):
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

        class _View:
            children = [object()]

            def __init__(self, *args, **kwargs):
                pass

        with patch.object(bar, "_load_state", return_value={"101": 1, "102": 2}):
            with patch.object(bar, "get_bar_phase", side_effect=_phase):
                with patch.object(bar, "EddyLifecycleBarView", _View):
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
        self.assertIn("withdraw_operator_lifecycle_bars(river_client)", setup)
        self.assertLess(
            setup.index("await withdraw_operator_lifecycle_bars"),
            setup.index("rehydrate_lifecycle_bar_views(river_client)"),
        )

    def test_bar_declaration_matches_what_the_view_renders(self) -> None:
        """prompts.py told Turtle the bar carried release and dissolve. It never did."""
        prompts_src = Path("prompts.py").read_text(encoding="utf-8")
        lines = [
            ln
            for ln in prompts_src.splitlines()
            if "Lifecycle bar" in ln and "flow pick" in ln
        ]
        self.assertEqual(len(lines), 2)
        view_src = Path("eddy_lifecycle_bar.py").read_text(encoding="utf-8")
        block = view_src.split("class EddyLifecycleBarView", 1)[1].split(
            "class EddyDissolveConfirmView", 1
        )[0]
        for claim in lines:
            self.assertIn("operator's own eddies", claim)
            self.assertNotIn("always visible", claim)
            for label in ("checkpoint", "share"):
                self.assertIn(label, claim)
            for absent in ("release", "dissolve"):
                self.assertNotIn(f"· {absent}", claim)
        for label in ("checkpoint", "share"):
            self.assertIn(f'label="{label}"', block)
        for absent in ("release", "dissolve"):
            self.assertNotIn(f'label="{absent}"', block)


class TestLifecycleBarHiddenForTheOperator(unittest.TestCase):
    """The bar is off in the operator's own eddies until it is redesigned."""

    def test_his_eddy_withholds_the_bar(self) -> None:
        primitive = SimpleNamespace(practice_key="operator", base="solo")
        registry = {"spaces": {}, "mages": {"operator": {"type": "mage"}}}
        with patch("mage.get_channel_primitive", return_value=primitive), patch(
            "mage.get_registry", return_value=registry
        ):
            self.assertTrue(bar.lifecycle_bar_withheld(10))

    def test_another_persons_eddy_keeps_the_bar(self) -> None:
        primitive = SimpleNamespace(practice_key="guest", base="solo")
        registry = {"spaces": {}, "mages": {"guest": {"type": "practitioner"}}}
        with patch("mage.get_channel_primitive", return_value=primitive), patch(
            "mage.get_registry", return_value=registry
        ):
            self.assertFalse(bar.lifecycle_bar_withheld(10))

    def test_a_shared_room_keeps_the_bar(self) -> None:
        primitive = SimpleNamespace(practice_key="house", base="shared")
        registry = {"spaces": {"house": {}}, "mages": {}}
        with patch("mage.get_channel_primitive", return_value=primitive), patch(
            "mage.get_registry", return_value=registry
        ):
            self.assertFalse(bar.lifecycle_bar_withheld(10))

    def test_a_withheld_room_does_not_qualify_for_a_new_bar(self) -> None:
        with patch.object(bar, "lifecycle_bar_withheld", return_value=True):
            self.assertFalse(bar.bootstrap_bar_eligible(11, 22))
            self.assertFalse(bar.lifecycle_bar_eligible(11, 22))

    def test_the_operator_file_is_his_even_when_context_is_another_room(self) -> None:
        registry = {
            "spaces": {},
            "mages": {
                "guest": {"type": "practitioner", "runtime_dir": "/tmp/guest"},
                "operator": {"type": "mage", "primary": True, "runtime_dir": "/tmp/operator"},
            },
        }
        with patch("mage.get_registry", return_value=registry), patch.object(
            bar, "_state_path", return_value="/tmp/ambient/lifecycle_bar.json"
        ):
            self.assertEqual(
                bar._operator_eddy_dir(),
                "/tmp/operator/thread-state/eddy",
            )

    def test_startup_removes_his_bar_and_leaves_the_other(self) -> None:
        import asyncio
        import json
        import tempfile

        class Message:
            def __init__(self):
                self.deleted = False

            async def delete(self):
                self.deleted = True

        class Thread:
            def __init__(self, thread_id: int, parent_id: int):
                self.id = thread_id
                self.parent_id = parent_id
                self.message = Message()

            async def fetch_message(self, _message_id: int):
                return self.message

        his = Thread(7, 10)
        theirs = Thread(8, 99)

        class Client:
            def get_channel(self, channel_id: int):
                return {7: his, 8: theirs}[channel_id]

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "lifecycle_bar.json").write_text(
                json.dumps({"7": 100, "8": 200}), encoding="utf-8"
            )
            (directory / "bar_phase.json").write_text(
                json.dumps({"7": "live", "8": "live"}), encoding="utf-8"
            )
            with patch.object(bar, "_operator_eddy_dir", return_value=str(directory)), patch.object(
                bar, "_load_state", return_value={"9": 300}
            ), patch.object(
                bar, "clear_lifecycle_bar_state", side_effect=AssertionError("ambient file")
            ), patch.object(
                bar, "lifecycle_bar_withheld", side_effect=lambda parent_id: parent_id == 10
            ):
                hidden = asyncio.run(bar.withdraw_operator_lifecycle_bars(Client()))
            left = json.loads((directory / "lifecycle_bar.json").read_text(encoding="utf-8"))
            phases = json.loads((directory / "bar_phase.json").read_text(encoding="utf-8"))

        self.assertEqual(hidden, 1)
        self.assertTrue(his.message.deleted)
        self.assertFalse(theirs.message.deleted)
        self.assertEqual(left, {"8": 200})
        self.assertEqual(phases, {"8": "live"})

    def test_a_failed_delete_keeps_the_row_so_the_next_start_tries_again(self) -> None:
        import asyncio
        import json
        import tempfile

        import discord

        failed = discord.HTTPException.__new__(discord.HTTPException)
        Exception.__init__(failed, "discord said no")

        class Thread:
            id = 7
            parent_id = 10

            async def fetch_message(self, _message_id: int):
                class Message:
                    async def delete(self):
                        raise failed

                return Message()

        class Client:
            def get_channel(self, _channel_id: int):
                return Thread()

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "lifecycle_bar.json").write_text(
                json.dumps({"7": 100}), encoding="utf-8"
            )
            with patch.object(bar, "_operator_eddy_dir", return_value=str(directory)), patch.object(
                bar, "lifecycle_bar_withheld", return_value=True
            ):
                hidden = asyncio.run(bar.withdraw_operator_lifecycle_bars(Client()))
            left = json.loads((directory / "lifecycle_bar.json").read_text(encoding="utf-8"))

        self.assertEqual(hidden, 0)
        self.assertEqual(left, {"7": 100})

    def test_a_closed_eddy_is_opened_only_long_enough_to_take_the_bar_down(self) -> None:
        import asyncio
        import json
        import tempfile

        class Message:
            def __init__(self):
                self.deleted = False

            async def delete(self):
                self.deleted = True

        class Thread:
            id = 7
            parent_id = 10
            archived = True
            edits: list[bool] = []

            def __init__(self):
                self.message = Message()
                self.edits = []

            async def edit(self, *, archived: bool):
                self.edits.append(archived)
                self.archived = archived

            async def fetch_message(self, _message_id: int):
                return self.message

        thread = Thread()

        class Client:
            def get_channel(self, _channel_id: int):
                return thread

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "lifecycle_bar.json").write_text(
                json.dumps({"7": 100}), encoding="utf-8"
            )
            with patch.object(bar, "_operator_eddy_dir", return_value=str(directory)), patch.object(
                bar, "lifecycle_bar_withheld", return_value=True
            ):
                hidden = asyncio.run(bar.withdraw_operator_lifecycle_bars(Client()))
            left = json.loads((directory / "lifecycle_bar.json").read_text(encoding="utf-8"))

        self.assertEqual(hidden, 1)
        self.assertTrue(thread.message.deleted)
        self.assertEqual(thread.edits, [False, True])
        self.assertTrue(thread.archived)
        self.assertEqual(left, {})
