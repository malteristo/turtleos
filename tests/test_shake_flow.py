import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from flow_runner import load_flow_spec, write_flow_checkpoint
from state import MIN_EXCHANGES_FOR_CHECKPOINT

REPO = Path(__file__).resolve().parents[1]


def _load_shake_flow():
    path = REPO / "scripts" / "shake_flow.py"
    spec = importlib.util.spec_from_file_location("shake_flow", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SessionsFlowCheckpointTests(unittest.TestCase):
    def test_min_exchanges_for_checkpoint_is_low(self) -> None:
        self.assertLessEqual(MIN_EXCHANGES_FOR_CHECKPOINT, 4)

    def test_checkpoint_writes_with_two_exchanges(self) -> None:
        spec = load_flow_spec("shelter")
        self.assertIsNotNone(spec)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            history = [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]
            written = write_flow_checkpoint(spec, history, "Spirit", tmp)
            self.assertEqual(written, ["state/notes/shelter-last.md"])


class ShakeFlowOfflineTests(unittest.TestCase):
    def test_offline_shelter_passes(self) -> None:
        shake_flow = _load_shake_flow()
        errors = shake_flow.check_offline("shelter")
        self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
