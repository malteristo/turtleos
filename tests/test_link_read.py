import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())

from link_read import (
    FetchResult,
    PROMPT_INLINE_MAX,
    X_READ_MAX,
    DIALOGUE_INJECT_MAX,
    inject_limit,
    stored_fetch,
    external_urls,
    format_fetch_results_for_dialogue,
    format_result_for_dialogue,
    should_auto_fetch_urls,
    should_rename_thread_from_fetch,
    plan_dialogue_urls,
    spill_fetch_artifact,
    url_display_host,
    _fetch_one_url,
    _open_signed_in_link,
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

    def test_a_link_with_a_paragraph_is_read_whatever_it_is(self) -> None:
        """His rule: he pastes the link, with or without words. Video or article."""
        for url in ("https://www.youtube.com/watch?v=abc123", "https://example.com/essay"):
            text = self.LONG * 2 + url
            self.assertGreater(len(self.LONG.strip()), 120)
            self.assertTrue(should_auto_fetch_urls(text, [url]), url)

    def test_no_link_is_nothing_to_read(self) -> None:
        """Positive control: the rule is not 'always True'."""
        self.assertFalse(should_auto_fetch_urls(self.LONG, []))

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

    def test_a_long_message_with_a_link_is_read(self) -> None:
        url = "https://example.com/article"
        text = ("A long message about my week, the workshop and a few other threads. " * 4) + url
        self.assertGreater(len(text.replace(url, "").strip()), 120)
        self.assertTrue(should_auto_fetch_urls(text, [url]))

    def test_native_eddy_auto_fetches_when_heuristics_match(self) -> None:
        url = "https://example.com/article"
        text = f"I just read this article {url}"
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=True)
        self.assertTrue(auto)
        self.assertEqual(urls, [url])
        self.assertEqual(pending, [])

    def test_a_long_message_with_a_link_reads_it_and_offers_nothing(self) -> None:
        url = "https://example.com/article"
        text = ("A long message about my week, the workshop and a few other threads. " * 4) + url
        auto, urls, pending = plan_dialogue_urls(text, [url], native_eddy=True)
        self.assertTrue(auto)
        self.assertEqual((urls, pending), ([url], []))

    def test_more_than_the_cap_reads_the_first_and_offers_the_rest(self) -> None:
        from link_read import MAX_URLS_PER_MESSAGE

        links = [f"https://example.com/{i}" for i in range(MAX_URLS_PER_MESSAGE + 2)]
        auto, urls, pending = plan_dialogue_urls("these " + " ".join(links), links)
        self.assertTrue(auto)
        self.assertEqual(urls, links[:MAX_URLS_PER_MESSAGE])
        self.assertEqual(pending, links[MAX_URLS_PER_MESSAGE:])

    def test_no_links_plans_nothing(self) -> None:
        self.assertEqual(plan_dialogue_urls("hello", []), (False, [], []))

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
        self.assertNotIn("!fetch", block)

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


class ACraftLinkUsesTheSignedInReadTests(unittest.IsolatedAsyncioTestCase):
    POST = "https://x.com/ada/status/1"

    async def test_craft_uses_the_signed_in_read_and_skips_the_old_preview(self) -> None:
        with (
            patch("link_read._open_signed_in_link", new=AsyncMock(return_value="[X — ada's]\nPLANTED_POST")),
            patch("link_read.fetch_twitter", new=AsyncMock()) as preview,
        ):
            result = await _fetch_one_url(self.POST)
        preview.assert_not_called()
        self.assertEqual(result.source, "X")
        self.assertIn("PLANTED_POST", result.content)

    async def test_outside_craft_the_old_preview_still_reads_the_link(self) -> None:
        with (
            patch("link_read._open_signed_in_link", new=AsyncMock(return_value=None)),
            patch("link_read.fetch_twitter", new=AsyncMock(return_value=("thin tweet", "twitter-cli"))),
        ):
            result = await _fetch_one_url(self.POST)
        self.assertEqual(result.source, "twitter-cli")
        self.assertEqual(result.content, "thin tweet")

    async def test_a_door_failure_leaves_the_old_preview(self) -> None:
        with (
            patch("mage.get_current_channel_id", return_value=1),
            patch("mage.uses_craft_surface", return_value=True),
            patch("outgoing_connections.live_call", return_value="X could not be read.") as door,
        ):
            text = await _open_signed_in_link(self.POST)
        door.assert_called_once()
        self.assertIsNone(text)

    async def test_another_room_does_not_open_the_connection(self) -> None:
        with (
            patch("mage.get_current_channel_id", return_value=1),
            patch("mage.uses_craft_surface", return_value=False),
            patch("outgoing_connections.live_call") as door,
        ):
            text = await _open_signed_in_link(self.POST)
        door.assert_not_called()
        self.assertIsNone(text)

    def test_a_long_signed_in_read_stays_in_the_turn_and_is_not_stored(self) -> None:
        body = ("word " * 2000) + "ENDMARK"
        result = FetchResult(
            url=self.POST,
            ok=True,
            content=body,
            source="X",
            char_count=len(body),
        )
        spilled = spill_fetch_artifact(result)
        self.assertIsNone(spilled.artifact_path)
        self.assertIn("ENDMARK", format_result_for_dialogue(spilled))

    def test_the_turn_keeps_a_signed_in_article_and_still_cuts_a_page(self) -> None:
        article = "[URL: https://x.com/ada/status/1 (via X)]\n" + ("word " * 3000)
        page = "[URL: https://example.com/a (via article)]\n" + ("word " * 3000)
        self.assertEqual(inject_limit(article), X_READ_MAX)
        self.assertGreater(len(article), DIALOGUE_INJECT_MAX)
        self.assertEqual(inject_limit(page), DIALOGUE_INJECT_MAX + 512)
        page_body = "[URL: https://example.com/a (via article)]\nPLANTED_PAGE"
        self.assertIn("PLANTED_PAGE", stored_fetch(page_body))
        kept = stored_fetch(article)
        self.assertNotIn("word", kept)
        self.assertIn("Not stored.", kept)
        source = Path(__file__).resolve().parents[1].joinpath("dialogue_turn.py").read_text()
        self.assertNotIn("url_content[:DIALOGUE_INJECT_MAX", source)
        self.assertEqual(source.count("inject_limit(url_content)"), 2)
        self.assertIn("stored_fetch(url_content)", source)


if __name__ == "__main__":
    unittest.main()
