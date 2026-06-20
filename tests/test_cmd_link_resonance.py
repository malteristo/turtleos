"""Tests for link-resonance cache and fetch act digest."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

import cmd_link_resonance as clr


class TestLinkResonanceCache(unittest.TestCase):
    def test_roundtrip_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(clr, "get_runtime_dir", return_value=tmp):
                url = "https://example.com/article"
                clr.cache_resonance(url, "- Insight one\n- Insight two", title="Article")
                cached = clr.get_cached_resonance(url)
                self.assertIsNotNone(cached)
                self.assertIn("Insight one", cached)
                self.assertIn(url, cached)

    def test_miss_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(clr, "get_runtime_dir", return_value=tmp):
                self.assertIsNone(clr.get_cached_resonance("https://missing.example/x"))

    def test_fetch_act_digest_includes_excerpt(self) -> None:
        resonance = "# Title\n\n**URL:** x\n\n**Cached:** now\n\n---\n\n- Point one"
        digest = clr.fetch_act_digest("https://example.com/a", resonance)
        self.assertIn("Point one", digest)
        self.assertIn("example.com", digest)


if __name__ == "__main__":
    unittest.main()
