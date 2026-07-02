"""Tests for flow bootstrap seed (Slice 2)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("discord", __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())

from flow_bootstrap import (
    build_bootstrap_user_seed,
    _intake_fields_complete,
    list_flow_bootstrap_requests,
)
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

    def test_lens_seed_includes_history(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        excerpt = "Practitioner: I've been circling the installer issue.\nTurtle: What's blocking?"
        seed = build_bootstrap_user_seed(
            spec, "/nonexistent/practice", lens=True, history_excerpt=excerpt
        )
        self.assertIn("Lens load", seed)
        self.assertIn("circling the installer", seed)

    def test_intake_fields_complete(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        self.assertFalse(_intake_fields_complete(spec, {"intention": "", "territory": ""}))
        self.assertFalse(_intake_fields_complete(spec, {}))
        self.assertTrue(_intake_fields_complete(spec, {"intention": "x", "territory": ""}))
        self.assertTrue(
            _intake_fields_complete(spec, {"intention": "x", "territory": "y"})
        )


class FlowBootstrapPollingTests(unittest.TestCase):
    def test_list_requests_scans_all_registered_runtime_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as primary, tempfile.TemporaryDirectory() as space:
            for runtime_dir, thread_id in ((primary, 111), (space, 333)):
                bdir = Path(runtime_dir) / "thread-state" / "flow-bootstrap"
                bdir.mkdir(parents=True)
                (bdir / f"{thread_id}.json").write_text(
                    json.dumps(
                        {
                            "thread_id": thread_id,
                            "parent_id": 222,
                            "flow_id": "navigator",
                        }
                    ),
                    encoding="utf-8",
                )
            reg = {
                "mages": {"kermit": {"runtime_dir": primary}},
                "spaces": {"lukas_sandbox": {"runtime_dir": space}},
            }
            with patch("mage._MAGE_REGISTRY", reg), patch(
                "mage._resolve_primary_runtime_dir", return_value=primary
            ):
                found = list_flow_bootstrap_requests()
            thread_ids = {int(p["thread_id"]) for p in found}
            self.assertEqual(thread_ids, {111, 333})


if __name__ == "__main__":
    unittest.main()
