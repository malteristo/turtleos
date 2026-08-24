"""Install writes the file the bot reads — one path, not two."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import mage
import river_keys


class RegistryPathTests(unittest.TestCase):
    def test_default_path_is_the_checkout(self) -> None:
        env = os.environ.pop("MAGE_REGISTRY", None)
        try:
            expected = str(Path(mage.__file__).resolve().parent / "mage_registry.yaml")
            self.assertEqual(mage.default_registry_path(), expected)
        finally:
            if env is not None:
                os.environ["MAGE_REGISTRY"] = env

    def test_env_overrides_checkout(self) -> None:
        with patch.dict(os.environ, {"MAGE_REGISTRY": "~/somewhere/mage_registry.yaml"}):
            self.assertEqual(
                mage.default_registry_path(),
                os.path.expanduser("~/somewhere/mage_registry.yaml"),
            )

    def test_save_writes_the_path_mage_reads(self) -> None:
        """Positive control: a second constant in river_keys would miss this file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mage_registry.yaml")
            orig = mage.REGISTRY_PATH
            saved = dict(mage._MAGE_REGISTRY)
            mage.REGISTRY_PATH = path
            try:
                river_keys.save_registry({"mages": {}, "channels": {}, "spaces": {}})
                self.assertTrue(os.path.isfile(path))
            finally:
                mage.REGISTRY_PATH = orig
                mage._MAGE_REGISTRY.clear()
                mage._MAGE_REGISTRY.update(saved)

    def test_example_has_no_family_space_stub(self) -> None:
        import yaml

        example = Path(mage.__file__).resolve().parent / "mage_registry.example.yaml"
        data = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
        spaces = data.get("spaces") or {}
        self.assertNotIn("family", spaces)
        self.assertNotIn("shared", spaces)


if __name__ == "__main__":
    unittest.main()
