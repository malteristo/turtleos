"""Pins for delegate_edit — empty-content failure mode found 2026-08-11.

qwen3.5 with thinking left on can return empty ``content`` and put the rewrite
in ``thinking``. Craft Turtle then pasted the intended Live-state write into
chat and said nothing was lost. Chat paste is not a write.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError


class DelegateNumCtxTests(unittest.TestCase):
    def test_small_files_get_at_least_8k(self) -> None:
        from tos_tools import _delegate_num_ctx

        self.assertEqual(_delegate_num_ctx(100), 8192)

    def test_mid_surface_gets_room_for_rewrite(self) -> None:
        from tos_tools import _delegate_num_ctx

        # ~10k-char prepared surface — the morning's failure case.
        ctx = _delegate_num_ctx(10_202)
        self.assertGreaterEqual(ctx, 8192)
        self.assertGreater(ctx, 8192)  # must grow past the old hard-code
        self.assertLessEqual(ctx, 32768)

    def test_huge_files_cap(self) -> None:
        from tos_tools import _delegate_num_ctx

        self.assertEqual(_delegate_num_ctx(500_000), 32768)


class DelegateEditThinkFalseTests(unittest.TestCase):
    """The payload must disable thinking — otherwise content can be empty."""

    def test_payload_sets_think_false(self) -> None:
        from tos_tools import _delegate_edit_sync

        captured: dict = {}

        class _Resp:
            def read(self) -> bytes:
                return json.dumps(
                    {"message": {"content": "# edited\n\nbody that is long enough", "thinking": ""}}
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(req, timeout=None):
            body = req.data
            if isinstance(body, bytes):
                captured.update(json.loads(body.decode()))
            return _Resp()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surface.md"
            path.write_text("# title\n\n**Settled so far:** nothing yet.\n", encoding="utf-8")
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = _delegate_edit_sync(
                    str(path), "surface.md", path.read_text(encoding="utf-8"),
                    "Update Live state",
                )

        self.assertTrue(result.startswith("Done."), result)
        self.assertIs(captured.get("think"), False)
        self.assertIn("options", captured)
        self.assertGreaterEqual(captured["options"]["num_ctx"], 8192)

    def test_empty_content_with_thinking_names_the_fallback(self) -> None:
        from tos_tools import _delegate_edit_sync

        class _Resp:
            def read(self) -> bytes:
                return json.dumps(
                    {"message": {"content": "", "thinking": "I would rewrite the file…"}}
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surface.md"
            path.write_text("# title\n\nold\n", encoding="utf-8")
            with mock.patch("urllib.request.urlopen", return_value=_Resp()):
                result = _delegate_edit_sync(
                    str(path), "surface.md", path.read_text(encoding="utf-8"),
                    "Update Live state",
                )
            unchanged = path.read_text(encoding="utf-8")

        self.assertIn("empty content", result)
        self.assertIn("thinking consumed", result)
        self.assertIn("patch_practice_file", result)
        self.assertIn("do not paste", result)
        self.assertEqual(unchanged, "# title\n\nold\n")

    def test_transport_error_also_names_the_fallback(self) -> None:
        from tos_tools import _delegate_edit_sync

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surface.md"
            path.write_text("# title\n", encoding="utf-8")
            with mock.patch(
                "urllib.request.urlopen",
                side_effect=URLError("connection refused"),
            ):
                result = _delegate_edit_sync(
                    str(path), "surface.md", path.read_text(encoding="utf-8"),
                    "Update Live state",
                )

        self.assertIn("Delegate edit failed", result)
        self.assertIn("patch_practice_file", result)
        self.assertIn("do not paste", result)


if __name__ == "__main__":
    unittest.main()
