import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.prepared_surface import (  # noqa: E402
    DISCORD_LIMIT,
    render_for_discord,
    render_surface_messages,
    split_into_blocks,
    strip_horizontal_rules,
)


class TestStripRules(unittest.TestCase):
    def test_drops_separator_lines_only(self):
        text = "# Title\n\n---\n\nBody with -- dashes\n***\nMore"
        out = strip_horizontal_rules(text)
        self.assertNotIn("---\n", out)
        self.assertNotIn("***", out)
        self.assertIn("Body with -- dashes", out)

    def test_keeps_frontmatter_content(self):
        self.assertIn("**Prepared by:**", strip_horizontal_rules("**Prepared by:** Spirit\n---\n"))


class TestBlocks(unittest.TestCase):
    def test_heading_starts_a_block_and_keeps_its_body(self):
        blocks = split_into_blocks("# T\n\nintro\n\n## One\n\na\n\n## Two\n\nb")
        self.assertEqual(len(blocks), 3)
        self.assertTrue(blocks[1].startswith("## One"))
        self.assertIn("a", blocks[1])

    def test_hash_inside_text_is_not_a_heading(self):
        blocks = split_into_blocks("## Real\n\nsee #4 and #tag here")
        self.assertEqual(len(blocks), 1)


class TestRender(unittest.TestCase):
    def test_every_chunk_under_the_limit(self):
        text = "\n\n".join(f"## Section {i}\n\n" + ("word " * 120) for i in range(12))
        for chunk in render_for_discord(text):
            self.assertLessEqual(len(chunk), 1900)

    def test_no_content_lost(self):
        text = "# T\n\nalpha\n\n## One\n\nbravo\n\n## Two\n\ncharlie"
        joined = " ".join(render_for_discord(text))
        for word in ("alpha", "bravo", "charlie"):
            self.assertIn(word, joined)

    def test_short_sections_pack_together(self):
        text = "## A\n\nshort\n\n## B\n\nalso short\n\n## C\n\ntiny"
        self.assertEqual(len(render_for_discord(text)), 1)

    def test_oversize_section_splits_without_breaking_words(self):
        text = "## Big\n\n" + ("supercalifragilistic " * 400)
        chunks = render_for_discord(text)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1900)
            self.assertNotIn("supercalifragilisticsuper", chunk)
            for word in chunk.split():
                self.assertTrue(
                    word.startswith("#") or word in ("Big", "supercalifragilistic"),
                    f"word fragment leaked: {word!r}",
                )

    def test_paragraph_boundaries_preferred_over_mid_sentence(self):
        para = "Sentence one is here. " * 40
        text = f"## S\n\n{para}\n\n{para}"
        for chunk in render_for_discord(text):
            self.assertLessEqual(len(chunk), 1900)


class TestFooters(unittest.TestCase):
    def test_sequence_and_final_marker(self):
        text = "\n\n".join(f"## S{i}\n\n" + ("word " * 200) for i in range(6))
        messages = render_surface_messages(text, "craft/surface-x.md")
        self.assertGreater(len(messages), 1)
        self.assertIn(f"1/{len(messages)}", messages[0])
        self.assertIn("file attached", messages[-1])
        self.assertNotIn("file attached", messages[0])
        self.assertIn("craft/surface-x.md", messages[-1])

    def test_footer_never_pushes_a_message_over_the_cap(self):
        text = "\n\n".join(f"## S{i}\n\n" + ("word " * 190) for i in range(20))
        for message in render_surface_messages(text, "craft/a-rather-long-surface-name.md"):
            self.assertLessEqual(len(message), DISCORD_LIMIT)


if __name__ == "__main__":
    unittest.main()
