import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.discord_stub import install_discord_stub

discord = install_discord_stub()

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
                "100": {"type": "shared-river", "mage": "guest_play"},
                "200": {"type": "shared-river", "mage": "kermit"},
            },
            mages={
                "guest_play": {"practice_dir": "/tmp/guest", "runtime_dir": self._runtime_root},
                "kermit": {"practice_dir": "/tmp/kermit", "runtime_dir": "/tmp/kermit_rt"},
            },
        )
        self.assertEqual(mage.resolve_registry_channel_id(100), 100)

    def test_resolve_registry_channel_id_from_awaiting_title(self) -> None:
        self._write_registry(
            {"302": {"type": "shared-river", "mage": "guest_play"}},
            mages={
                "guest_play": {
                    "practice_dir": "/tmp/guest",
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        thread_id = 303
        parent_id = 302
        awaiting_dir = Path(self._runtime_root) / "thread-state" / "awaiting-title"
        awaiting_dir.mkdir(parents=True, exist_ok=True)
        awaiting_dir.joinpath(f"{thread_id}.json").write_text(
            json.dumps({"thread_id": thread_id, "parent_channel_id": parent_id}),
            encoding="utf-8",
        )
        self.assertEqual(mage.resolve_registry_channel_id(thread_id), parent_id)

    def test_resolve_registry_channel_id_from_thread_registry_name(self) -> None:
        """After title assignment, awaiting-title JSON is gone — registry.yaml remains."""
        parent_id = 201
        thread_id = 304
        self._write_registry(
            {
                str(parent_id): {
                    "type": "hosted-river",
                    "mage": "partner",
                    "name": "partner-dialogue",
                }
            },
            mages={
                "partner": {
                    "practice_dir": os.path.join(self._tmpdir.name, "partner"),
                    "runtime_dir": self._runtime_root,
                },
            },
        )
        reg_dir = Path(self._runtime_root) / "thread-state"
        reg_dir.mkdir(parents=True, exist_ok=True)
        reg_dir.joinpath("registry.yaml").write_text(
            "\n".join(
                [
                    "threads:",
                    f"  '{thread_id}':",
                    "    name: Malte in Partner's river",
                    "    parent_channel: partner-dialogue",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(mage.resolve_registry_channel_id(thread_id), parent_id)

    def test_set_practice_context_for_thread_uses_parent_workshop(self) -> None:
        guest_pd = os.path.join(self._tmpdir.name, "guest")
        os.makedirs(guest_pd, exist_ok=True)
        parent_id = 302
        thread_id = 303
        self._write_registry(
            {str(parent_id): {"type": "shared-river", "mage": "guest_play"}},
            mages={
                "guest_play": {
                    "practice_dir": guest_pd,
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
        self.assertEqual(pd, guest_pd)

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


class EffectiveAttunementThroughThreadsTests(MageChannelResolutionTests):
    """An eddy inherits its parent's attunement.

    It did not. `get_effective_attunement` looked the id up literally in a
    registry that only holds parent channels, so every thread fell through to
    the *global* profile: a craft eddy answered `native` while its parent
    answered `craft`. Most callers were right only because they remembered to
    pass `parent_id` themselves. Measured 2026-08-14 against the live
    `#craft-turtle` — same shape as the offer ledger, which lost eight days of
    events to a literal lookup of a thread id that same morning.
    """

    def _craft_parent_with_eddy(self) -> tuple[int, int]:
        parent_id = 101
        thread_id = 305
        self._write_registry(
            {str(parent_id): {"type": "craft", "mage": "kermit", "attunement": "craft"}},
            mages={
                "kermit": {
                    "practice_dir": os.path.join(self._tmpdir.name, "kermit"),
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
        return parent_id, thread_id

    def test_a_craft_eddy_answers_craft(self) -> None:
        parent_id, thread_id = self._craft_parent_with_eddy()
        self.assertEqual(mage.get_effective_attunement(parent_id), "craft")
        self.assertEqual(mage.get_effective_attunement(thread_id), "craft")
        self.assertTrue(mage.uses_craft_surface(thread_id))

    def test_an_unrelated_channel_does_not_inherit_craft(self) -> None:
        """Negative control — resolution must not make everything craft."""
        self._craft_parent_with_eddy()
        self.assertNotEqual(mage.get_effective_attunement(999_000_111), "craft")
        self.assertFalse(mage.uses_craft_surface(999_000_111))

    def test_a_bad_channel_id_falls_back_to_the_global_profile(self) -> None:
        self._write_registry({}, mages={})
        self.assertEqual(
            mage.get_effective_attunement(None), mage.get_attunement_profile()
        )
        self.assertEqual(
            mage.get_effective_attunement("not-an-id"), mage.get_attunement_profile()
        )

    def test_craft_tools_reach_a_craft_eddy(self) -> None:
        """The consequence that matters: scoped tools follow the parent."""
        import tos_tools

        _, thread_id = self._craft_parent_with_eddy()
        names = {
            (t.get("function") or {}).get("name")
            for t in tos_tools.tools_for_channel(thread_id)
        }
        self.assertIn("exa_search", names)


if __name__ == "__main__":
    unittest.main()
