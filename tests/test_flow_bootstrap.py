"""Tests for flow bootstrap seed (Slice 2)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("discord", __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())

from flow_bootstrap import build_bootstrap_user_seed, _intake_fields_complete
from flow_runner import load_flow_spec, write_flow_intake


class FlowBootstrapSeedTests(unittest.TestCase):
    def test_navigator_fresh_asks_intention(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        seed = build_bootstrap_user_seed(spec, "/nonexistent/practice")
        self.assertIn("ONE question", seed)
        self.assertIn("working toward", seed.lower())

    def test_navigator_with_intake_skips_reask(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            write_flow_intake(
                spec,
                {"intention": "Ship turtleOS", "territory": "Install friction"},
                tmp,
            )
            with patch("flow_bootstrap.get_pd", return_value=tmp):
                seed = build_bootstrap_user_seed(spec, tmp)
            self.assertIn("do NOT re-ask", seed)
            self.assertIn("Territory", seed)

    def test_intake_fields_complete(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        self.assertFalse(_intake_fields_complete(spec, {"intention": "", "territory": ""}))
        self.assertFalse(_intake_fields_complete(spec, {}))
        self.assertTrue(_intake_fields_complete(spec, {"intention": "x", "territory": ""}))
        self.assertTrue(
            _intake_fields_complete(spec, {"intention": "x", "territory": "y"})
        )


if __name__ == "__main__":
    unittest.main()
