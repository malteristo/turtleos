"""Flow context_type must survive restarts (Galactic Adventure / dnd_dm remount)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from eddy_spawn import hydrate_native_eddy_context, read_pending_native_eddy


class ContextTypePersistenceTests(unittest.TestCase):
    def test_load_flow_persists_registry_context_type(self) -> None:
        src = Path(__file__).resolve().parents[1] / "eddy_flow_library.py"
        text = src.read_text(encoding="utf-8")
        block = text.split("async def load_flow_in_eddy")[1].split(
            "async def dismiss_eddy_flow_library"
        )[0]
        self.assertIn("update_thread_context_type", block)

    def test_deliver_bootstrap_persists_registry_context_type(self) -> None:
        src = Path(__file__).resolve().parents[1] / "flow_bootstrap.py"
        text = src.read_text(encoding="utf-8")
        block = text.split("async def deliver_flow_bootstrap")[1].split(
            "async def process_flow_bootstrap"
        )[0]
        self.assertIn("update_thread_context_type", block)

    def test_dialogue_turn_hydrates_native_context(self) -> None:
        src = Path(__file__).resolve().parents[1] / "dialogue_turn.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn("hydrate_native_eddy_context", text)

    def test_hydrate_from_registry(self) -> None:
        configs: dict = {}
        registry = {
            "threads": {
                "99": {"name": "Galactic Adventure", "context_type": "dnd_dm"},
            }
        }
        with (
            patch("state.thread_configs", configs),
            patch("thread_registry.load_registry", return_value=registry),
            patch("thread_registry.update_thread_context_type") as persist,
        ):
            ctx = hydrate_native_eddy_context(99, 111)
        self.assertEqual(ctx, "dnd_dm")
        self.assertEqual(configs[99]["context_type"], "dnd_dm")
        persist.assert_called_once_with(99, "dnd_dm")

    def test_hydrate_from_pending_when_registry_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            pending_dir = runtime / "thread-state" / "pending"
            pending_dir.mkdir(parents=True)
            (pending_dir / "77.json").write_text(
                json.dumps({"context_type": "dnd_dm", "blank_eddy": False}),
                encoding="utf-8",
            )
            configs: dict = {}
            registry = {"threads": {"77": {"name": "x", "context_type": None}}}
            with (
                patch("state.thread_configs", configs),
                patch("thread_registry.load_registry", return_value=registry),
                patch("thread_registry.update_thread_context_type") as persist,
                patch("mage.set_practice_context_for_channel"),
                patch("mage.get_runtime_dir", return_value=str(runtime)),
            ):
                ctx = hydrate_native_eddy_context(77, 222)
            self.assertEqual(ctx, "dnd_dm")
            self.assertEqual(configs[77]["context_type"], "dnd_dm")
            persist.assert_called_once_with(77, "dnd_dm")

    def test_read_pending_does_not_consume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            pending_dir = runtime / "thread-state" / "pending"
            pending_dir.mkdir(parents=True)
            path = pending_dir / "55.json"
            path.write_text(json.dumps({"context_type": "navigator"}), encoding="utf-8")
            with (
                patch("mage.set_practice_context_for_channel"),
                patch("mage.get_runtime_dir", return_value=str(runtime)),
            ):
                first = read_pending_native_eddy(55, 1)
                second = read_pending_native_eddy(55, 1)
            self.assertEqual(first["context_type"], "navigator")
            self.assertEqual(second["context_type"], "navigator")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
