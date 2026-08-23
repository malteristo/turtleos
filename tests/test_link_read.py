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


class LinkKindAndLabelTests(unittest.TestCase):
    """The offer must name what will actually arrive.

    Operator report, tested across 08-12 → 08-14: every bare YouTube link shape
    fetched its transcript, and a link with a sentence around it produced neither
    the fetch nor the right button — it offered "Read article" for a video.
    """

    LONG = (
        "I have been thinking about how our family uses the evenings and whether the "
        "current rhythm actually serves anyone, and this came up while I was reading "
        "about attention and shared rituals, which felt worth passing along to you. "
    )

    def test_youtube_offers_its_transcript_not_an_article(self) -> None:
        from runtime.link_offers import action_for_urls

        for url in (
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
            "https://m.youtube.com/watch?v=abc123&t=42s&feature=share",
        ):
            action = action_for_urls([url])
            self.assertEqual(action.label, "Fetch transcript", url)
            self.assertEqual(action.key, "read_youtube", url)

    def test_an_article_still_offers_to_be_read(self) -> None:
        from runtime.link_offers import action_for_urls

        self.assertEqual(
            action_for_urls(["https://example.com/essay"]).label, "Read article"
        )

    def test_a_mixed_set_does_not_claim_one_kind(self) -> None:
        from runtime.link_offers import action_for_urls

        action = action_for_urls(
            ["https://youtu.be/abc123", "https://example.com/essay"]
        )
        self.assertEqual(action.label, "Read links")

    def test_a_link_about_youtube_elsewhere_is_not_a_video(self) -> None:
        """The old substring match on the whole URL said otherwise."""
        from runtime.link_offers import classify_url

        self.assertEqual(
            classify_url("https://example.com/blog/youtube.com/why-video-is-hard"),
            "article",
        )
        self.assertEqual(classify_url("https://youtube.com.evil.test/x"), "article")

    def test_description_says_what_the_link_is_not_just_its_host(self) -> None:
        """`aihero.dev (+22 more)` was not enough to judge the button."""
        from runtime.link_offers import describe_urls

        out = describe_urls(
            ["https://www.youtube.com/watch?v=abc123", "https://aihero.dev/some/post"]
        )
        self.assertIn("YouTube video", out)
        self.assertIn("v=abc123", out)
        self.assertIn("aihero.dev/some/post", out)

    def test_many_links_report_the_remainder_by_count(self) -> None:
        from runtime.link_offers import describe_urls

        out = describe_urls([f"https://example.com/{i}" for i in range(9)])
        self.assertIn("and 6 more", out)

    def test_a_video_shared_with_a_paragraph_still_auto_fetches(self) -> None:
        url = "https://www.youtube.com/watch?v=abc123"
        text = self.LONG + url
        self.assertGreater(len(self.LONG.strip()), 120)
        self.assertTrue(should_auto_fetch_urls(text, [url]))

    def test_an_article_shared_with_the_same_paragraph_does_not(self) -> None:
        """Negative control — the widening is for media, not for everything."""
        url = "https://example.com/essay"
        self.assertFalse(should_auto_fetch_urls(self.LONG + url, [url]))

    def test_a_watch_cue_counts_as_engagement(self) -> None:
        url = "https://www.youtube.com/watch?v=abc123"
        text = self.LONG * 2 + f" watch this when you get a chance {url}"
        self.assertTrue(should_auto_fetch_urls(text, [url]))

    def test_detect_platform_and_the_offer_read_one_list(self) -> None:
        """Two copies of "what is this link" is how the button starts lying."""
        from content_fetch import detect_platform
        from runtime.link_offers import classify_url

        for url, expected in (
            ("https://youtu.be/abc", "youtube"),
            ("https://x.com/someone/status/1", "twitter"),
            ("https://old.reddit.com/r/x/comments/1/y", "reddit"),
        ):
            self.assertEqual(detect_platform(url), expected, url)
            self.assertEqual(classify_url(url), expected, url)
        self.assertIsNone(detect_platform("https://example.com/essay"))


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

    def test_native_eddy_auto_fetches_when_heuristics_match(self) -> None:
        url = "https://example.com/article"
        text = f"I just read this article {url}"
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=True)
        self.assertTrue(auto)
        self.assertEqual(urls, [url])
        self.assertEqual(pending, [])

    def test_native_eddy_incidental_offers_read_skip(self) -> None:
        url = "https://example.com/article"
        text = (
            "This is a long message about many things that are not primarily about the link. "
            "I wanted to mention my week, the workshop, intentions, and a few other threads "
            "before noting this article in passing without any particular ask attached. "
            + url
        )
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=True)
        self.assertFalse(auto)
        self.assertEqual(urls, [url])
        self.assertEqual(pending, [url])

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
