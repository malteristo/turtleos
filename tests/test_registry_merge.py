"""Two bots, one registry file: a save keeps the other bot's change (issues/048)."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

import yaml

import mage
import river_keys
from registry_merge import merge


class MergeTests(unittest.TestCase):
    def test_both_sides_keep_their_changes(self):
        base = {"mages": {"a": {"name": "A"}}, "channels": {}}
        ours = {"mages": {"a": {"name": "A", "model": "sonnet"}}, "channels": {}}
        theirs = {"mages": {"a": {"name": "A"}, "b": {"name": "B"}}, "channels": {"1": {"type": "river"}}}
        self.assertEqual(
            merge(base, ours, theirs),
            {"mages": {"a": {"name": "A", "model": "sonnet"}, "b": {"name": "B"}}, "channels": {"1": {"type": "river"}}},
        )

    def test_a_deletion_on_either_side_survives(self):
        base = {"channels": {"1": {}, "2": {}}}
        self.assertEqual(merge(base, {"channels": {"2": {}}}, base), {"channels": {"2": {}}})
        self.assertEqual(merge(base, base, {"channels": {"1": {}}}), {"channels": {"1": {}}})

    def test_a_removal_beats_a_stale_edit(self):
        base = {"channels": {"1": {"type": "river"}}}
        edited = {"channels": {"1": {"type": "river", "orphaned": True}}}
        self.assertEqual(merge(base, edited, {"channels": {}}), {"channels": {}})
        self.assertEqual(merge(base, {"channels": {}}, edited), {"channels": {}})

    def test_the_same_value_changed_on_both_sides_takes_ours(self):
        self.assertEqual(merge({"x": 1}, {"x": 2}, {"x": 3}), {"x": 2})

    def test_member_lists_merge_additions_and_removals(self):
        base = {"members": ["a", "b"]}
        self.assertEqual(merge(base, {"members": ["a", "b", "c"]}, {"members": ["b", "d"]}), {"members": ["b", "d", "c"]})


class TwoProcessSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "mage_registry.yaml")
        self.orig_path = mage.REGISTRY_PATH
        mage.REGISTRY_PATH = self.path
        with open(self.path, "w") as fh:
            yaml.safe_dump({"mages": {"a": {"name": "A"}}, "channels": {}}, fh)
        mage.reload_mage_registry()

    def tearDown(self):
        mage.REGISTRY_PATH = self.orig_path
        mage.reload_mage_registry()
        self.tmp.cleanup()

    def _other_bot_writes(self, mutate):
        with open(self.path) as fh:
            data = yaml.safe_load(fh)
        mutate(data)
        time.sleep(0.01)
        with open(self.path, "w") as fh:
            yaml.safe_dump(data, fh)

    def test_a_stale_save_keeps_the_other_bots_change(self):
        ours = mage.get_registry()
        self._other_bot_writes(lambda d: d["channels"].update({"9": {"type": "river", "mage": "b"}}))
        ours["mages"]["a"]["model"] = "sonnet"
        river_keys.save_registry(ours)
        with open(self.path) as fh:
            on_disk = yaml.safe_load(fh)
        self.assertEqual(on_disk["channels"], {"9": {"type": "river", "mage": "b"}})
        self.assertEqual(on_disk["mages"]["a"]["model"], "sonnet")
        self.assertEqual(mage.get_registry()["channels"], {"9": {"type": "river", "mage": "b"}})

    def test_a_current_save_writes_as_given(self):
        ours = mage.get_registry()
        del ours["mages"]["a"]
        river_keys.save_registry(ours)
        with open(self.path) as fh:
            self.assertEqual(yaml.safe_load(fh)["mages"], {})


if __name__ == "__main__":
    unittest.main()
