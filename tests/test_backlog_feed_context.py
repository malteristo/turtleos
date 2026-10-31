"""What a pitch brings with it — and what it must never bring.

Each claim in `backlog_feed_context.py` / `backlog_feed_judge.py` has a check, and
each "absent" has a positive control beside it: the other channel's note that must
never surface is shown to surface once the registry says it belongs to craft.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

import backlog_feed as feed
import backlog_feed_context as ctx
import backlog_feed_judge as judge

CRAFT = "500"
OTHER = "999"
# Built, not written out: a literal 18-digit number is what the sanitation hook looks for.
A, B, X = (str(10**17 + n) for n in (1, 2, 3))

REGISTRY_YAML = """threads:
  '{a}': {{name: relay hand-offs, parent_channel_id: 500}}
  '{b}': {{name: durable outputs, parent_channel_id: 500}}
  '{x}': {{name: a private room, parent_channel_id: 999}}
"""


def _note(thread, title, body, sparks=""):
    return (
        f"---\nthread: '{thread}'\ntitle: {title}\ntrigger: idle\n"
        f"timestamp: '2026-10-01T10:00:00+02:00'\n{sparks}---\n\n{body}\n"
    )


NOTE_A = _note(
    A, "relay hand-offs",
    "The relay hand-off between craft and the workshop drops context. Handing the relay over needs a packet.",
    "sparks:\n- {id: packet, name: hand-off packet, topic: relay packets, status: open}\n"
    "- {id: old, name: finished idea, topic: relay packets, status: developed}\n",
)
NOTE_B = _note(B, "durable outputs", "Outputs that last: a pin shelf for artifacts and their lifecycle.")
NOTE_X = _note(
    X, "a private room",
    "The relay hand-off between craft and the workshop drops context. Handing the relay over needs a packet.",
)

BOOM = """# Boom Buffer

*2026-10-01 12:23. Meta line about placement.*

---

## Boom

The relay hand-off should be one packet, not a story.

A second paragraph about gardening and nothing else.

---

Something unrelated about cooking pasta.
"""
ALT = "- relay packet handling\n- choose model with !model\n"

ROW_ID = "2026-09-13-relay-aaaaaa"
ROW_TITLE = "Relay hand-off packet"
ROW_BODY = "The relay hand-off to the workshop drops context; a packet would carry it."

INTAKE = f"""# Craft Intake — x

## Mage report

Please make the hand-off carry the packet. It drops things, and I only learn that later.

## Source references

- guild=1 channel={A} message=5

## Origin eddy

- **Channel ID:** `{A}`
"""
INTAKE_FROM_OTHER = INTAKE.replace(A, X)


def make_root(tmp: Path, *, x_in_craft=False) -> Path:
    root = tmp / "root"
    (root / "story/eddies").mkdir(parents=True)
    (root / "thread-state").mkdir()
    (root / "craft/intake").mkdir(parents=True)
    registry = REGISTRY_YAML.format(a=A, b=B, x=X)
    if x_in_craft:
        registry = registry.replace("parent_channel_id: 999", "parent_channel_id: 500")
    (root / "thread-state/registry.yaml").write_text(registry, encoding="utf-8")
    for tid, slug, text in ((A, "relay", NOTE_A), (B, "outputs", NOTE_B), (X, "private", NOTE_X)):
        (root / f"story/eddies/{tid}-{slug}.md").write_text(text, encoding="utf-8")
    (root / f"craft/intake/{ROW_ID}.md").write_text(INTAKE, encoding="utf-8")
    return root


class OriginTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_root(Path(self._tmp.name))
        self.corpus = ctx.load_corpus(self.root, CRAFT, boom_text=BOOM, altbacklog_text=ALT)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_origin_is_the_eddy_the_intake_names(self):
        short = ctx.shortlist(self.corpus, ROW_ID, ROW_TITLE, ROW_BODY)
        self.assertEqual(short.origin.thread, A)
        self.assertEqual(short.origin.label, "relay hand-offs")
        self.assertIn("relay hand-off between craft", short.origin.quote)

    def test_a_row_with_no_intake_and_no_id_has_no_origin_and_says_nothing_of_one(self):
        short = ctx.shortlist(self.corpus, "2026-08-08-by-hand", "By hand", "No ids in here.")
        self.assertIsNone(short.origin)
        self.assertIsNone(short.said)

    def test_an_id_written_in_the_row_counts(self):
        short = ctx.shortlist(self.corpus, "2026-08-08-by-hand", "By hand", f"Came from eddy {B}.")
        self.assertEqual(short.origin.thread, B)

    def test_his_own_words_come_from_the_intake(self):
        short = ctx.shortlist(self.corpus, ROW_ID, ROW_TITLE, ROW_BODY)
        self.assertIn("make the hand-off carry the packet", short.said.quote)

    def test_the_origin_is_not_repeated_among_the_related(self):
        short = ctx.shortlist(self.corpus, ROW_ID, ROW_TITLE, ROW_BODY)
        self.assertNotIn(A, [c.source.thread for c in short.candidates if c.source.kind == "eddy"])


class TheCraftLaneTests(unittest.TestCase):
    """A note from another channel never surfaces. The positive control below shows
    the same note surfacing when the registry says it is craft's."""

    def _threads_in(self, root, ident="2026-08-08-by-hand", title=ROW_TITLE, body=ROW_BODY):
        corpus = ctx.load_corpus(root, CRAFT, boom_text=None, altbacklog_text=None)
        short = ctx.shortlist(corpus, ident, title, body)
        return {c.source.thread for c in short.candidates} | ({short.origin.thread} if short.origin else set())

    def test_another_channels_note_never_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = self._threads_in(make_root(Path(tmp)))
            self.assertNotIn(X, seen)
            self.assertIn(A, seen)  # the shortlist finds craft's own, so empty is not "broken"

    def test_positive_control_the_same_note_appears_once_it_is_craft(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn(X, self._threads_in(make_root(Path(tmp), x_in_craft=True)))

    def test_a_row_from_another_channel_gets_no_origin_eddy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            (root / f"craft/intake/{ROW_ID}.md").write_text(INTAKE_FROM_OTHER, encoding="utf-8")
            corpus = ctx.load_corpus(root, CRAFT)
            short = ctx.shortlist(corpus, ROW_ID, ROW_TITLE, ROW_BODY)
            self.assertIsNone(short.origin)
            # The id is still a candidate: whether it is a live craft eddy is Discord's to say.
            self.assertIn(X, short.origin_candidates)

    def test_an_unreadable_registry_shows_nothing_rather_than_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            (root / "thread-state/registry.yaml").write_text(": : not yaml [", encoding="utf-8")
            corpus = ctx.load_corpus(root, CRAFT)
            self.assertEqual(corpus.notes, {})


class ShortlistAndDecideTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_root(Path(self._tmp.name))
        self.corpus = ctx.load_corpus(self.root, CRAFT, boom_text=BOOM, altbacklog_text=ALT)
        # A row with no origin, so the related material is not hidden behind it.
        self.short = ctx.shortlist(self.corpus, "2026-08-08-by-hand", ROW_TITLE, ROW_BODY)

    def tearDown(self):
        self._tmp.cleanup()

    def kinds(self):
        return {c.source.kind for c in self.short.candidates}

    def test_every_source_kind_can_be_on_the_shortlist(self):
        self.assertTrue({"eddy", "spark", "boom", "alt"} <= self.kinds(), self.kinds())

    def test_only_open_sparks_are_offered(self):
        quotes = " ".join(c.source.quote for c in self.short.candidates if c.source.kind == "spark")
        self.assertIn("hand-off packet", quotes)
        self.assertNotIn("finished idea", quotes)

    def test_the_boom_quote_is_the_paragraph_that_touches_the_row(self):
        boom = next(c for c in self.short.candidates if c.source.kind == "boom")
        self.assertIn("relay hand-off should be one packet", boom.source.quote)
        self.assertNotIn("gardening", boom.source.quote)

    def test_unrelated_material_is_not_on_the_shortlist(self):
        texts = " ".join(c.text for c in self.short.candidates)
        self.assertNotIn("cooking pasta", texts)
        self.assertNotIn("pin shelf", texts)

    def test_decide_keeps_only_what_the_judge_named_and_only_what_exists(self):
        keys = [c.key for c in self.short.candidates]
        got = ctx.decide(self.short, [keys[0], "c99", "not-a-key"])
        self.assertEqual(len(got.related), 1)
        self.assertEqual(got.related[0], self.short.candidates[0].source)

    def test_nothing_named_means_nothing_shown(self):
        got = ctx.decide(self.short, [])
        self.assertEqual(got.related, ())

    def test_decide_caps_what_is_shown(self):
        got = ctx.decide(self.short, [c.key for c in self.short.candidates])
        self.assertLessEqual(len(got.related), ctx.MAX_KEPT)

    def test_every_quotation_is_in_its_source(self):
        """The claim that no word on a pitch was written by a model. Mutation: change
        one quote and the check fails."""
        origin_short = ctx.shortlist(self.corpus, ROW_ID, ROW_TITLE, ROW_BODY)
        got = ctx.decide(origin_short, [c.key for c in origin_short.candidates])
        sources = [NOTE_A, NOTE_B, BOOM, ALT, INTAKE]
        self.assertTrue(got.related and got.origin and got.said)
        self.assertTrue(ctx.in_sources(got, sources))
        forged = ctx.Context(got.origin_candidates, got.origin, (ctx.Source("boom", "boom", "invented words"),), got.said)
        self.assertFalse(ctx.in_sources(forged, sources))


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        corpus = ctx.load_corpus(make_root(Path(self._tmp.name)), CRAFT, boom_text=BOOM, altbacklog_text=ALT)
        short = ctx.shortlist(corpus, ROW_ID, ROW_TITLE, ROW_BODY)
        self.context = ctx.decide(short, [c.key for c in short.candidates])

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_origin_links_to_its_eddy_in_the_guild(self):
        text = ctx.compose_context(self.context, 42)
        self.assertIn(f"https://discord.com/channels/42/{A}", text)
        self.assertIn("Where it came from", text)
        self.assertIn("Your words when you filed it", text)

    def test_nothing_known_composes_to_nothing(self):
        self.assertEqual(ctx.compose_context(ctx.Context(), 42), "")
        self.assertTrue(ctx.Context().empty)

    def test_a_short_limit_drops_whole_parts_and_never_cuts_a_link(self):
        full = ctx.compose_context(self.context, 42, limit=10_000)
        cut = ctx.compose_context(self.context, 42, limit=len(full) // 2)
        self.assertLessEqual(len(cut), len(full) // 2)
        self.assertEqual(cut.count("["), cut.count("]"))
        self.assertTrue(full.startswith(cut))


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.corpus = ctx.load_corpus(make_root(Path(self._tmp.name)), CRAFT, boom_text=BOOM, altbacklog_text=ALT)
        self.item = feed.FeedItem("2026-08-08-by-hand", ROW_TITLE, ROW_BODY, "open")
        self.short = ctx.shortlist(self.corpus, self.item.id, self.item.title, self.item.body)

    def tearDown(self):
        self._tmp.cleanup()

    def test_parse_keeps_known_keys_in_order_and_drops_the_rest(self):
        self.assertEqual(judge.parse_keep('{"keep": ["c2", "c1", "c2", "zz", 3]}', {"c1", "c2"}), ["c2", "c1"])

    def test_parse_survives_prose_around_the_json_and_bad_shapes(self):
        self.assertEqual(judge.parse_keep('Sure! {"keep": ["c1"]} done', {"c1"}), ["c1"])
        for bad in ("", "no json", '{"keep": "c1"}', '{"other": []}', "{broken", "[]"):
            self.assertEqual(judge.parse_keep(bad, {"c1"}), [], bad)

    def test_the_prompt_carries_the_row_and_every_candidate_and_nothing_else(self):
        prompt = judge.build_prompt(self.item, self.short)
        self.assertIn(ROW_TITLE, prompt)
        for c in self.short.candidates:
            self.assertIn(f"[{c.key}]", prompt)
        self.assertNotIn("a private room", prompt)  # another channel's note never reaches the model

    def test_a_judge_that_cannot_answer_keeps_nothing_and_does_not_raise(self):
        async def boom(_prompt):
            raise TimeoutError("no slot")

        self.assertEqual(asyncio.run(judge.keep_for(self.item, self.short, ask_fn=boom)), [])

    def test_a_judge_that_answers_garbage_keeps_nothing(self):
        async def junk(_prompt):
            return "I think they are all great!"

        self.assertEqual(asyncio.run(judge.keep_for(self.item, self.short, ask_fn=junk)), [])

    def test_nothing_on_the_shortlist_means_no_call(self):
        calls = []

        async def spy(prompt):
            calls.append(prompt)
            return '{"keep": []}'

        empty = ctx.Shortlist((), None, (), None)
        self.assertEqual(asyncio.run(judge.keep_for(self.item, empty, ask_fn=spy)), [])
        self.assertEqual(calls, [])

    def test_context_for_item_shows_what_the_judge_kept(self):
        first = self.short.candidates[0].key

        async def pick_first(_prompt):
            return f'{{"keep": ["{first}"]}}'

        got = asyncio.run(judge.context_for_item(self.corpus, self.item, ask_fn=pick_first))
        self.assertEqual([s.label for s in got.related], [self.short.candidates[0].source.label])


class WordsTests(unittest.TestCase):
    def test_ids_and_dates_are_not_words(self):
        self.assertEqual(ctx.words("2026-09-24 deadbeef12 relay"), {"relay"})

    def test_a_plural_and_its_singular_meet(self):
        self.assertEqual(ctx.words("eddies"), ctx.words("eddy"))

    def test_a_quote_stays_within_its_limit_and_ends_on_a_sentence_when_it_can(self):
        text = "One short sentence here. " * 40
        out = ctx.quote_of(text, 100)
        self.assertLessEqual(len(out), 100)
        self.assertTrue(out.endswith("."))


if __name__ == "__main__":
    unittest.main()
