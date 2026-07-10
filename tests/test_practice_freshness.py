import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())

from practice_freshness import (
    CANARY_MAX_AGE_HOURS,
    detect_topology,
    evaluate_freshness,
    readiness_freshness_issues,
)


class PracticeFreshnessTests(unittest.TestCase):
    def test_detect_native_from_state_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = os.path.join(tmp, "state")
            os.makedirs(state_dir)
            open(os.path.join(state_dir, "current.yaml"), "w").close()
            self.assertEqual(detect_topology(tmp), "native")

    def test_native_fresh_when_current_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = os.path.join(tmp, "state")
            os.makedirs(state_dir)
            path = os.path.join(state_dir, "current.yaml")
            with open(path, "w") as f:
                f.write("updated_at: '2026-07-09T12:00:00+02:00'\n")
            result = evaluate_freshness(tmp, max_age_hours=CANARY_MAX_AGE_HOURS)
            self.assertTrue(result.passed)
            self.assertEqual(result.topology, "native")
            self.assertIn("current", result.signals)

    def test_native_passes_without_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = os.path.join(tmp, "state")
            os.makedirs(state_dir)
            with open(os.path.join(state_dir, "current.yaml"), "w") as f:
                f.write("version: 1\n")
            result = evaluate_freshness(tmp)
            self.assertTrue(result.passed)
            self.assertEqual(result.topology, "native")

    def test_empty_practice_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_freshness(tmp)
            self.assertTrue(result.passed)
            self.assertEqual(result.topology, "empty")

    def test_stale_native_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = os.path.join(tmp, "state")
            os.makedirs(state_dir)
            path = os.path.join(state_dir, "current.yaml")
            with open(path, "w") as f:
                f.write("version: 1\n")
            old = time.time() - (200 * 3600)
            os.utime(path, (old, old))
            result = evaluate_freshness(tmp, max_age_hours=CANARY_MAX_AGE_HOURS)
            self.assertFalse(result.passed)

    def test_readiness_issues_empty_when_native_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = os.path.join(tmp, "state")
            os.makedirs(state_dir)
            with open(os.path.join(state_dir, "current.yaml"), "w") as f:
                f.write("version: 1\n")
            self.assertEqual(readiness_freshness_issues(tmp), [])


if __name__ == "__main__":
    unittest.main()
