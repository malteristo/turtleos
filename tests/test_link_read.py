import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from link_read import (
    FetchResult,
    PROMPT_INLINE_MAX,
    external_urls,
    format_fetch_results_for_dialogue,
    format_result_for_dialogue,
    should_auto_fetch_urls,
    should_rename_thread_from_fetch,
    plan_dialogue_urls,
    spill_fetch_artifact,
    url_display_host,
    _partial_read_status_lines,
)


class LinkReadHeuristicTests(unittest.TestCase):
    def test_url_only_auto_fetches(self) -> None:
        url = "https://example.com/article"
        self.assertTrue(should_auto_fetch_urls(url, [url]))

    def test_short_commentary_auto_fetches(self) -> None:
        url = "https://example.com/article"
        text = f"what do you think? {url}"
        self.assertTrue(should_auto_fetch_urls(text, [url]))

    def test_long_incidental_skips_auto(self) -> None:
        url = "https://example.com/article"
        text = (
            "This is a long message about many things that are not primarily about the link. "
            "I wanted to mention my week, the workshop, intentions, and a few other threads "
            "before noting this article in passing without any particular ask attached. "
            + url
        )
        self.assertGreater(len(text.replace(url, "").strip()), 120)
        self.assertFalse(should_auto_fetch_urls(text, [url]))

    def test_read_cue_auto_fetches(self) -> None:
        url = "https://example.com/article"
        text = (
            "I've been thinking about practice design all week and also wanted you to "
            f"read this when you have a moment: {url}"
        )
        self.assertTrue(should_auto_fetch_urls(text, [url]))

    def test_native_eddy_never_auto_fetches(self) -> None:
        url = "https://example.com/article"
        text = f"I just read this article {url}"
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=True)
        self.assertFalse(auto)
        self.assertEqual(urls, [url])
        self.assertEqual(pending, [])

    def test_legacy_short_message_auto_fetches(self) -> None:
        url = "https://example.com/article"
        text = f"I just read this article {url}"
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=False)
        self.assertTrue(auto)
        self.assertEqual(urls, [url])
        self.assertEqual(pending, [])

    def test_external_urls_filters_discord(self) -> None:
        urls = [
            "https://discord.com/channels/1/2",
            "https://example.com/page",
        ]
        self.assertEqual(external_urls(urls), ["https://example.com/page"])


class LinkReadFormatTests(unittest.TestCase):
    def test_format_success_includes_source(self) -> None:
        result = FetchResult(
            url="https://example.com/a",
            ok=True,
            content="Article body text here.",
            source="trafilatura",
            char_count=23,
        )
        block = format_result_for_dialogue(result)
        self.assertIn("trafilatura", block)
        self.assertIn("Article body text here.", block)

    def test_format_failure_includes_attempts(self) -> None:
        result = FetchResult(
            url="https://example.com/missing",
            ok=False,
            attempts=["direct: HTTP 404"],
        )
        block = format_result_for_dialogue(result)
        self.assertIn("HTTP 404", block)
        self.assertIn("!fetch", block)

    def test_format_multiple_joins(self) -> None:
        results = [
            FetchResult(url="https://a.test", ok=True, content="A", source="direct", char_count=1),
            FetchResult(url="https://b.test", ok=True, content="B", source="jina", char_count=1),
        ]
        joined = format_fetch_results_for_dialogue(results)
        self.assertIn("---", joined)
        self.assertIn("https://a.test", joined)


class LinkReadHostTests(unittest.TestCase):
    def test_strips_www(self) -> None:
        self.assertEqual(url_display_host("https://www.example.com/path"), "example.com")


class LinkReadRenameTests(unittest.TestCase):
    def test_river_owns_titles(self) -> None:
        self.assertFalse(
            should_rename_thread_from_fetch(
                "new eddy",
                "https://example.com/a",
                river_enabled=True,
            )
        )
        self.assertFalse(
            should_rename_thread_from_fetch(
                "navigator",
                "https://example.com/a",
                river_enabled=True,
            )
        )

    def test_blank_eddy_only_when_single_bot(self) -> None:
        self.assertTrue(
            should_rename_thread_from_fetch(
                "new eddy",
                "https://example.com/a",
                river_enabled=False,
            )
        )
        self.assertFalse(
            should_rename_thread_from_fetch(
                "chiang machine consciousness",
                "https://example.com/a",
                river_enabled=False,
            )
        )
        self.assertFalse(
            should_rename_thread_from_fetch(
                "navigator",
                "https://example.com/a",
                river_enabled=False,
            )
        )

    def test_host_slug_eligible_single_bot(self) -> None:
        self.assertTrue(
            should_rename_thread_from_fetch(
                "example.com",
                "https://example.com/a",
                river_enabled=False,
            )
        )


class LinkReadPartialStatusTests(unittest.TestCase):
    def test_partial_shows_ratio_and_path(self) -> None:
        result = FetchResult(
            url="https://example.com/long",
            ok=True,
            content="x" * 10000,
            source="article",
            char_count=10000,
            artifact_path="box/intake/test.md",
            prompt_excerpt_chars=8000,
        )
        lines = _partial_read_status_lines(result)
        joined = "\n".join(lines)
        self.assertIn("8,000 / 10,000", joined)
        self.assertIn("box/intake/test.md", joined)

    def test_full_in_context_no_ratio(self) -> None:
        result = FetchResult(
            url="https://example.com/short",
            ok=True,
            content="short",
            source="direct",
            char_count=5,
        )
        lines = _partial_read_status_lines(result)
        self.assertIn("5** in context", "\n".join(lines))
        self.assertNotIn("/", "\n".join(lines))


class LinkReadSpillTests(unittest.TestCase):
    def test_spill_writes_file_when_long(self) -> None:
        long_body = "word " * 5000
        result = FetchResult(
            url="https://example.com/long",
            ok=True,
            content=long_body,
            source="article",
            char_count=len(long_body),
            title="Long Article",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("mage.get_pd", return_value=tmp):
                spilled = spill_fetch_artifact(result)
            self.assertIsNotNone(spilled.artifact_path)
            self.assertIn("box/intake/", spilled.artifact_path)
            path = Path(tmp) / "box" / "intake" / spilled.artifact_path.split("/")[-1]
            self.assertTrue(path.is_file())

    def test_format_includes_artifact_path(self) -> None:
        result = FetchResult(
            url="https://example.com/long",
            ok=True,
            content="x" * (PROMPT_INLINE_MAX + 100),
            source="article",
            char_count=PROMPT_INLINE_MAX + 100,
            artifact_path="box/intake/test.md",
            prompt_excerpt_chars=PROMPT_INLINE_MAX,
        )
        block = format_result_for_dialogue(result)
        self.assertIn("box/intake/test.md", block)
        self.assertIn("first", block.lower())


if __name__ == "__main__":
    unittest.main()
