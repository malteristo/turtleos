import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import discord

import mage


class MageChannelResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = os.path.join(self._tmpdir.name, "mage_registry.yaml")
        self._orig_path = mage.REGISTRY_PATH
        mage.REGISTRY_PATH = self._path
        self._runtime_root = os.path.join(self._tmpdir.name, "runtime")
        os.makedirs(self._runtime_root, exist_ok=True)

    def tearDown(self) -> None:
        mage.REGISTRY_PATH = self._orig_path
        mage.reload_mage_registry()
        self._tmpdir.cleanup()

    def _write_registry(self, channels: dict, mages: dict | None = None) -> None:
        if channels:
            lines = ["channels:"]
            for ch_id, entry in channels.items():
                lines.append(f"  '{ch_id}':")
                for key, val in entry.items():
                    lines.append(f"    {key}: {val}")
        else:
            lines = ["channels: {}"]
        if mages:
            lines.append("mages:")
            for key, entry in mages.items():
                lines.append(f"  {key}:")
                for k, v in entry.items():
                    lines.append(f"    {k}: {v}")
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        time.sleep(0.01)
        mage.reload_mage_registry()

    def test_resolve_registry_channel_id_parent_channel(self) -> None:
        self._write_registry(
            {
                "100": {"type": "shared-river", "mage": "lukas_play"},
                "200": {"type": "shared-river", "mage": "kermit"},
            },
            mages={
                "lukas_play": {"practice_dir": "/tmp/lukas", "runtime_dir": self._runtime_root},
                "kermit": {"practice_dir": "/tmp/kermit", "runtime_dir": "/tmp/kermit_rt"},
            },
        )
        self.assertEqual(mage.resolve_registry_channel_id(100), 100)

    def test_resolve_registry_channel_id_from_awaiting_title(self) -> None:
        self._write_registry(
            {"1522210357622341766": {"type": "shared-river", "mage": "lukas_play"}},
            mages={
                "lukas_play": {
                    "practice_dir": "/tmp/lukas",
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        thread_id = 1522648705360990469
        parent_id = 1522210357622341766
        awaiting_dir = Path(self._runtime_root) / "thread-state" / "awaiting-title"
        awaiting_dir.mkdir(parents=True, exist_ok=True)
        awaiting_dir.joinpath(f"{thread_id}.json").write_text(
            json.dumps({"thread_id": thread_id, "parent_channel_id": parent_id}),
            encoding="utf-8",
        )
        self.assertEqual(mage.resolve_registry_channel_id(thread_id), parent_id)

    def test_set_practice_context_for_thread_uses_parent_workshop(self) -> None:
        lukas_pd = os.path.join(self._tmpdir.name, "lukas")
        os.makedirs(lukas_pd, exist_ok=True)
        parent_id = 1522210357622341766
        thread_id = 1522648705360990469
        self._write_registry(
            {str(parent_id): {"type": "shared-river", "mage": "lukas_play"}},
            mages={
                "lukas_play": {
                    "practice_dir": lukas_pd,
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        awaiting_dir = Path(self._runtime_root) / "thread-state" / "awaiting-title"
        awaiting_dir.mkdir(parents=True, exist_ok=True)
        awaiting_dir.joinpath(f"{thread_id}.json").write_text(
            json.dumps({"thread_id": thread_id, "parent_channel_id": parent_id}),
            encoding="utf-8",
        )
        pd = mage.set_practice_context_for_channel(thread_id)
        self.assertEqual(pd, lukas_pd)

    def test_infer_primary_workshop_prefers_dialogue_bar_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workshops = Path(tmp) / "workshops"
            kermit = workshops / "kermit"
            default = workshops / "default"
            for path in (kermit, default):
                (path / "state").mkdir(parents=True)
            dialogue_id = 1479428854513664030
            kermit_bar = kermit / "thread-state" / "river" / "eddy_bar.json"
            kermit_bar.parent.mkdir(parents=True)
            kermit_bar.write_text(json.dumps({str(dialogue_id): 1}), encoding="utf-8")
            for i in range(5):
                (kermit / "thread-state" / "awaiting-title").mkdir(parents=True, exist_ok=True)
                (kermit / "thread-state" / "awaiting-title" / f"{i}.json").write_text("{}", encoding="utf-8")
            default_bar = default / "thread-state" / "river" / "eddy_bar.json"
            default_bar.parent.mkdir(parents=True)
            default_bar.write_text(json.dumps({str(dialogue_id): 2}), encoding="utf-8")

            orig_home = Path.home
            try:
                Path.home = lambda: Path(tmp)  # type: ignore[method-assign]
                mage.reload_mage_registry()
                from state import CHANNELS

                old_dialogue = CHANNELS.get("dialogue")
                CHANNELS["dialogue"] = str(dialogue_id)
                inferred = mage._infer_primary_workshop_dir()
                self.assertEqual(inferred, str(kermit))
                runtime = mage._resolve_primary_runtime_dir()
                self.assertEqual(runtime, str(kermit))
            finally:
                Path.home = orig_home  # type: ignore[method-assign]
                if old_dialogue is None:
                    CHANNELS.pop("dialogue", None)
                else:
                    CHANNELS["dialogue"] = old_dialogue
                mage.reload_mage_registry()

    def test_get_thread_member_ids_env_fallback_for_dialogue_river(self) -> None:
        self._write_registry({}, mages={})
        from state import CHANNELS

        old_dialogue = CHANNELS.get("dialogue")
        CHANNELS["dialogue"] = "999"
        old_env = os.environ.get("DISCORD_USER_ID")
        os.environ["DISCORD_USER_ID"] = "123456789"
        try:
            ids = mage.get_thread_member_ids(999)
            self.assertEqual(ids, ["123456789"])
        finally:
            if old_env is None:
                os.environ.pop("DISCORD_USER_ID", None)
            else:
                os.environ["DISCORD_USER_ID"] = old_env
            if old_dialogue is None:
                CHANNELS.pop("dialogue", None)
            else:
                CHANNELS["dialogue"] = old_dialogue

    def test_is_practice_channel_uses_env_dialogue_without_client(self) -> None:
        self._write_registry({}, mages={})
        from state import CHANNELS, client

        old_dialogue = CHANNELS.get("dialogue")
        CHANNELS["dialogue"] = "888"
        thread = MagicMock(spec=discord.Thread)
        thread.id = 777
        thread.parent_id = 888
        with patch.object(client, "get_channel", return_value=None):
            self.assertTrue(mage.is_practice_channel(MagicMock(channel=thread)))
            parent = MagicMock()
            parent.id = 888
            parent.parent_id = None
            self.assertTrue(mage.is_practice_channel(MagicMock(channel=parent)))
        if old_dialogue is None:
            CHANNELS.pop("dialogue", None)
        else:
            CHANNELS["dialogue"] = old_dialogue


if __name__ == "__main__":
    unittest.main()
