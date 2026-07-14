"""Tests for the shared atomic-write primitive (issue 033, seed of 010)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import atomic_io


class TestAtomicWriteText(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            atomic_io.atomic_write_text(path, "hello wörld")
            self.assertEqual(path.read_text(encoding="utf-8"), "hello wörld")

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "note.md"
            atomic_io.atomic_write_text(path, "content")
            self.assertEqual(path.read_text(encoding="utf-8"), "content")

    def test_crash_between_write_and_replace_preserves_previous(self) -> None:
        """Simulated kill after the temp write but before replace: the
        previous valid file must remain intact."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.yaml"
            atomic_io.atomic_write_text(path, "previous: valid\n")

            with patch("atomic_io.os.replace", side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    atomic_io.atomic_write_text(path, "next: partial\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "previous: valid\n")

    def test_failed_write_cleans_up_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.yaml"
            atomic_io.atomic_write_text(path, "previous: valid\n")

            with patch("atomic_io.os.replace", side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    atomic_io.atomic_write_text(path, "next: partial\n")

            leftovers = [p for p in Path(tmp).iterdir() if p.name != "state.yaml"]
            self.assertEqual(leftovers, [])


class TestAtomicWriteJson(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            payload = [{"role": "user", "content": "héllo"}]
            atomic_io.atomic_write_json(path, payload, ensure_ascii=False, indent=0)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), payload)

    def test_crash_preserves_previous_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            atomic_io.atomic_write_json(path, {"v": 1})

            with patch("atomic_io.os.replace", side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    atomic_io.atomic_write_json(path, {"v": 2})

            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"v": 1})


class TestFileLock(unittest.TestCase):
    def test_concurrent_read_modify_write_with_lock_no_lost_update(self) -> None:
        """N writers doing read-modify-write under the flock: every
        increment lands (no lost update)."""
        writers = 16
        increments_each = 5
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "counter.json"
            atomic_io.atomic_write_json(path, {"count": 0})

            def bump() -> None:
                for _ in range(increments_each):
                    with atomic_io.file_lock(path):
                        with open(path, encoding="utf-8") as fh:
                            data = json.load(fh)
                        data["count"] += 1
                        atomic_io.atomic_write_json(path, data)

            threads = [threading.Thread(target=bump) for _ in range(writers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            with open(path, encoding="utf-8") as fh:
                final = json.load(fh)
            self.assertEqual(final["count"], writers * increments_each)

    def test_lock_parameter_serializes_writes(self) -> None:
        """lock=True writes from many threads never leave a corrupt file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shared.json"

            def write(i: int) -> None:
                atomic_io.atomic_write_json(path, {"writer": i, "payload": "x" * 512}, lock=True)

            threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIn("writer", data)
            self.assertEqual(len(data["payload"]), 512)


class TestRefactoredCallers(unittest.TestCase):
    """The two seed modules must route through the shared primitive."""

    def test_dialogue_store_write_survives_simulated_crash(self) -> None:
        import sys
        from unittest.mock import MagicMock

        sys.modules.setdefault("discord", MagicMock())
        import dialogue_store as ds

        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_runtime_dir", return_value=tmp):
                ds.write_shared(42, [{"role": "user", "content": "before"}])
                with patch("atomic_io.os.replace", side_effect=OSError("simulated crash")):
                    with self.assertRaises(OSError):
                        ds.write_shared(42, [{"role": "user", "content": "after"}])
                loaded = ds.read_shared(42)
            assert loaded is not None
            self.assertEqual(loaded[0]["content"], "before")

    def test_thread_registry_persist_survives_simulated_crash(self) -> None:
        import sys
        from unittest.mock import MagicMock

        sys.modules.setdefault("discord", MagicMock())
        import thread_registry as tr

        with tempfile.TemporaryDirectory() as tmp:
            # thread_registry binds get_runtime_dir at import time, so the
            # patch must target the thread_registry namespace.
            with patch("thread_registry.get_runtime_dir", return_value=tmp):
                tr._persist_registry({"threads": {"1": {"name": "before"}}})
                with patch("atomic_io.os.replace", side_effect=OSError("simulated crash")):
                    with self.assertRaises(OSError):
                        tr._persist_registry({"threads": {"1": {"name": "after"}}})
                import yaml

                reg_path = Path(tmp) / "thread-state" / "registry.yaml"
                with open(reg_path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            self.assertEqual(data["threads"]["1"]["name"], "before")


if __name__ == "__main__":
    unittest.main()
