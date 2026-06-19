import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from readiness import assess_practitioner_substrate


class PractitionerReadinessTests(unittest.TestCase):
    def test_empty_substrate_is_fresh_not_scored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "boom.md"), "w").close()
            result = assess_practitioner_substrate(tmp)
            self.assertIn("fresh", result["summary"].lower())
            self.assertIsNone(result["highest_leverage"])
            self.assertEqual(len(result["dimensions"]), 1)


if __name__ == "__main__":
    unittest.main()
