"""The rewrite: a row as an ideal state he can judge — and what it must not do.

The writer is the one place a model's words reach him unquoted. Each guard in
`backlog_feed_write.py` has a check, and each refusal has a positive control: the
same text passes once the offending word is gone.
"""

import asyncio
import unittest

import backlog_feed as feed
import backlog_feed_context as ctx
import backlog_feed_write as write

GOOD = """HEADLINE: Packets cross from craft to the workshop whole
WHEN THIS EXISTS: You finish a craft conversation and the workshop already has the whole packet. You open it and nothing needs retyping.
WHY IT WAS FILED: Hand-offs dropped half of what you had said.
NOT THIS: The row doesn't say.
HOW YOU WOULD KNOW: The next morning the packet is there with every point in it."""

ITEM = feed.FeedItem(
    id="2026-09-25-x-aaaaaa", title="Hand-off packet",
    body="Harvested 2026-09-25. Pickup: relay_hand_off.py drops context.", state="open",
)


def _context():
    return ctx.Context(
        said=ctx.Source("said", "your words when you filed it", "Please carry the packet."),
        origin=ctx.Source("eddy", "relay talk", "We said the packet is one page.", thread="1", shared=3),
        related=[ctx.Source("boom", "boom", "Packets over stories.")],
    )


class ParseTests(unittest.TestCase):
    def test_five_parts_parse(self):
        w = write.parse_written(GOOD)
        self.assertEqual(w.headline, "Packets cross from craft to the workshop whole")
        self.assertIn("nothing needs retyping", w.ideal)
        self.assertEqual(w.not_this, "The row doesn't say.")

    def test_markdown_labels_and_wrapped_lines_still_parse(self):
        raw = GOOD.replace("WHEN THIS EXISTS:", "**WHEN THIS EXISTS:**").replace(". You open", ".\nYou open")
        self.assertIsNotNone(write.parse_written(raw))

    def test_a_missing_part_refuses(self):
        self.assertIsNotNone(write.parse_written(GOOD))  # control
        self.assertIsNone(write.parse_written(GOOD.replace("NOT THIS:", "ALSO:")))

    def test_an_empty_part_refuses(self):
        self.assertIsNone(write.parse_written(GOOD.replace("The row doesn't say.", "")))

    def test_an_over_long_part_refuses(self):
        long = GOOD.replace("Hand-offs dropped half of what you had said.", "word " * 100)
        self.assertIsNone(write.parse_written(long))

    def test_code_words_refuse_and_are_the_only_difference(self):
        for dirty, clean in (
            ("a file named relay.py holds it", "a place holds it"),
            ("the relay_hand_off step", "the relay step"),
            ("the `packet` step", "the packet step"),
            ("see notes.md", "see the notes"),
        ):
            bad = GOOD.replace("nothing needs retyping", dirty)
            ok = GOOD.replace("nothing needs retyping", clean)
            self.assertIsNone(write.parse_written(bad), dirty)
            self.assertIsNotNone(write.parse_written(ok), clean)

    def test_his_name_is_refused_he_is_you(self):
        bad = GOOD.replace("You finish", "Kermit finishes")
        self.assertIsNone(write.parse_written(bad))
        self.assertIsNotNone(write.parse_written(GOOD))  # control

    def test_an_answer_with_the_absence_tacked_on_keeps_the_answer_and_drops_the_admission(self):
        mixed = GOOD.replace("nothing needs retyping.", "nothing needs retyping. The row doesn't say.")
        parsed = write.parse_written(mixed)
        self.assertTrue(parsed.ideal.endswith("nothing needs retyping."))
        self.assertNotIn("doesn't say", parsed.ideal)
        plain = GOOD.replace("WHY IT WAS FILED: Hand-offs dropped half of what you had said.", "WHY IT WAS FILED: The material does not say.")
        self.assertEqual(write.parse_written(plain).problem, "The row doesn't say.")
        other = GOOD.replace("Hand-offs dropped half of what you had said.", "The material cannot support further details.")
        self.assertEqual(write.parse_written(other).problem, "The row doesn't say.")
        real = GOOD.replace("Hand-offs dropped half of what you had said.", "The row says nothing is lost when it works.")
        self.assertNotEqual(write.parse_written(real).problem, "The row doesn't say.")  # an answer is not an absence

    def test_empty_and_none_refuse(self):
        self.assertIsNone(write.parse_written(""))
        self.assertIsNone(write.parse_written(None))


class DesignNoteTests(unittest.TestCase):
    NOTE = """# Hosted tester program

## Open slices

| Slice | What |
|-------|------|
| **Feedback intake persist** | `write_flow_intake` on Feedback close, today a thread and a checkpoint tail |
| **Operator digest** | Weekly list of new feedback files across hosted guests |

## Short

Too short to quote.
"""

    def corpus(self):
        import tempfile

        root = tempfile.mkdtemp()
        return ctx.load_corpus(root, "500", design_notes={"hosted.md": self.NOTE})

    def test_a_design_note_is_cut_at_its_headings_and_short_sections_are_dropped(self):
        labels = [d.source.label for d in self.corpus().refs]
        self.assertEqual(labels, ["turtleOS design · Hosted tester program › Open slices"])

    def test_a_row_about_the_same_subject_finds_the_note_and_quotes_it_flat(self):
        short = ctx.shortlist(self.corpus(), "x", "Operator digest across hosted guests", "weekly feedback files digest")
        quotes = [c.source.quote for c in short.candidates if c.source.kind == "doc"]
        self.assertEqual(len(quotes), 1)
        self.assertNotIn("|", quotes[0])
        self.assertNotIn("`", quotes[0])

    def test_an_unrelated_row_finds_nothing_in_the_notes(self):
        short = ctx.shortlist(self.corpus(), "x", "Pin shelf lifecycle", "artifacts expire after seven days")
        self.assertEqual([c for c in short.candidates if c.source.kind == "doc"], [])

    def test_the_notes_do_not_change_what_is_rare_among_his_own_writing(self):
        import tempfile

        root = tempfile.mkdtemp()
        with_notes = ctx.load_corpus(root, "500", design_notes={"hosted.md": self.NOTE})
        without = ctx.load_corpus(root, "500")
        self.assertEqual(with_notes.df, without.df)

    def test_a_missing_folder_gives_no_notes(self):
        self.assertEqual(ctx.read_design_notes("/nonexistent-checkout"), {})

    def test_this_checkout_has_notes_to_read(self):
        """Positive control: the loader finds the real design notes."""
        from pathlib import Path

        notes = ctx.read_design_notes(Path(__file__).resolve().parents[1])
        self.assertIn("hosted-tester-program.md", notes)


class PromptTests(unittest.TestCase):
    def test_the_prompt_carries_the_row_his_words_and_what_was_kept(self):
        prompt = write.build_prompt(ITEM, _context())
        for text in ("Hand-off packet", "Please carry the packet.", "We said the packet is one page.", "Packets over stories."):
            self.assertIn(text, prompt)

    def test_a_row_with_no_context_still_gets_a_prompt_that_says_use_only_this(self):
        prompt = write.build_prompt(ITEM, ctx.Context())
        self.assertNotIn("HIS OWN WORDS", prompt)
        self.assertNotIn("CONVERSATION IT CAME FROM", prompt)
        self.assertIn("Never invent", prompt)
        self.assertIn("The row doesn't say.", prompt)  # the way out the model is given

    def test_a_long_row_is_cut(self):
        item = feed.FeedItem(id="x", title="t", body="word " * 2000, state="open")
        self.assertLess(len(write.build_prompt(item, ctx.Context())), 4000)


class WriteTests(unittest.TestCase):
    def run_write(self, answers):
        calls = []

        async def ask(prompt):
            calls.append(prompt)
            answer = answers[min(len(calls) - 1, len(answers) - 1)]
            if isinstance(answer, Exception):
                raise answer
            return answer

        return asyncio.run(write.write_for_item(ITEM, _context(), ask_fn=ask)), calls

    def test_a_good_answer_is_used_with_one_call(self):
        written, calls = self.run_write([GOOD])
        self.assertIsNotNone(written)
        self.assertEqual(len(calls), 1)

    def test_a_bad_answer_is_asked_again_once_and_the_retry_can_succeed(self):
        written, calls = self.run_write(["nonsense", GOOD])
        self.assertIsNotNone(written)
        self.assertEqual(len(calls), 2)
        self.assertIn("Plain words only", calls[1])

    def test_two_bad_answers_give_none_and_stop(self):
        written, calls = self.run_write(["nonsense"])
        self.assertIsNone(written)
        self.assertEqual(len(calls), 2)

    def test_a_model_that_raises_gives_none_and_never_raises(self):
        written, calls = self.run_write([RuntimeError("model down")])
        self.assertIsNone(written)
        self.assertEqual(len(calls), 1)


class ComposeTests(unittest.TestCase):
    def test_the_message_is_short_enough_for_discord_at_every_limit(self):
        full = write.Written(*(("x" * limit) for limit in write.LIMITS.values()))
        text = feed.compose_pitch(ITEM, position=37, total=37, commit="abc1234", written=full)
        self.assertLess(len(text), 2000)

    def test_the_footer_still_names_the_row(self):
        text = feed.compose_pitch(ITEM, position=1, total=2, commit="abc", written=write.parse_written(GOOD))
        self.assertEqual(feed.item_id_from_message(text), ITEM.id)
        self.assertEqual(feed.numbering_from_message(text), (1, 2))

    def test_numbering_is_none_when_there_is_none(self):
        self.assertIsNone(feed.numbering_from_message("**A headline**\n\nbody"))

    def test_the_embed_says_so_when_nothing_is_known_and_always_shows_the_row_as_filed(self):
        empty = ctx.compose_embed(ctx.Context(), 42, ITEM.body)
        self.assertIn(ctx.NOTHING_YET, empty)
        self.assertIn("The row as filed", empty)
        known = ctx.compose_embed(_context(), 42, ITEM.body)
        self.assertNotIn(ctx.NOTHING_YET, known)
        self.assertIn("Please carry the packet.", known)

    def test_a_pitch_in_the_old_format_is_stale_until_it_is_rewritten(self):
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        now = datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed.record_pitched(root, ITEM, channel_id=1, message_id=2, now=now, format=1)
            self.assertEqual([i.id for i in feed.stale([ITEM], root)], [ITEM.id])
            later = datetime(2026, 10, 10, 18, 5, tzinfo=timezone.utc)
            feed.record_pitched(root, ITEM, channel_id=1, message_id=2, now=later)
            self.assertEqual(feed.stale([ITEM], root), [])


if __name__ == "__main__":
    unittest.main()
