"""Existing health files are registered/indexed in place."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.migrate_health_record import candidate_files, migrate


class HealthMigrationTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_excludes_managed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "labs").mkdir()
            source = root / "labs" / "lab.txt"
            source.write_text("Ferritin 21 ng/mL", encoding="utf-8")
            (root / "health_model.md").write_text("# Model", encoding="utf-8")
            (root / "documents" / "manifests").mkdir(parents=True)
            (root / "documents" / "manifests" / "old.json").write_text("{}")
            extracts = root / "documents" / "extracts"
            extracts.mkdir()
            (extracts / "lab.txt").write_text("derived text", encoding="utf-8")
            report = migrate(root, apply=False)
            self.assertEqual(report["candidates"], 1)
            self.assertFalse((root / "record").exists())

    def test_apply_keeps_original_and_maps_existing_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "labs").mkdir()
            source = root / "labs" / "lab.txt"
            original = "Ferritin measured at 21 ng/mL"
            source.write_text(original, encoding="utf-8")
            (root / "health_model.md").write_text(
                "# Model\n\n- Ferritin measured at 21 ng/mL\n", encoding="utf-8"
            )
            report = migrate(root, apply=True)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(report["saved"], 1)
            self.assertEqual(report["claim_map"]["mapped"], 1)

    def test_apply_prunes_mistaken_extract_manifest_without_touching_extract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extract = root / "documents" / "extracts" / "legacy.txt"
            extract.parent.mkdir(parents=True)
            extract.write_text("Existing derived extract remains.", encoding="utf-8")
            manifest = root / "documents" / "manifests" / "abc.json"
            manifest.parent.mkdir()
            manifest.write_text(
                json.dumps(
                    {
                        "source_id": "abcd1234",
                        "original_path": str(extract),
                    }
                ),
                encoding="utf-8",
            )
            (root / "health_model.md").write_text("# Model\n", encoding="utf-8")
            report = migrate(root, apply=True)
            self.assertEqual(report["pruned_derived_extracts"], 1)
            self.assertTrue(extract.is_file())
            self.assertFalse(manifest.exists())


if __name__ == "__main__":
    unittest.main()
