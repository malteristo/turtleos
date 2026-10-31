"""The design language has a mechanism. docs/ux/design-language.md §5.

Every rule the doc states is checked here, and every check has a positive control: a
surface that breaks the rule, which the check must catch. A check that has only ever
seen good input is a check nobody has seen fail.
"""

from __future__ import annotations

import re
import sys
import unittest
import unittest.mock
from pathlib import Path

try:
    import discord
    from discord import ui
except ImportError:  # system Python without discord.py: skip, never pass by omission
    raise unittest.SkipTest("needs discord.py")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import ui_kit  # noqa: E402
from tests.test_mcp_list import ListFixture, buttons  # noqa: E402

_SKIP = {"venv", ".git", "tests", "node_modules", ".publish-worktree", "__pycache__", "logs", "state"}


def _source_files() -> list[Path]:
    found = []
    for path in REPO.rglob("*.py"):
        parts = set(path.relative_to(REPO).parts)
        if parts & _SKIP:
            continue
        found.append(path)
    return found


def _noop():
    async def press(_interaction):
        return None

    return press


class KitRefusesTests(unittest.IsolatedAsyncioTestCase):
    def act(self, **kw):
        base = dict(label="Close", custom_id="x:1", callback=_noop())
        base.update(kw)
        return ui_kit.Act(**base)

    async def test_red_must_ask_first(self):
        with self.assertRaises(ui_kit.LanguageError):
            self.act(style="danger")
        self.act(style="danger", asks=True)  # positive control
        self.act(style="danger", confirms=True)
        with self.assertRaises(ui_kit.LanguageError):
            self.act(style="safe", asks=True)  # only red asks

    async def test_a_label_is_a_few_words(self):
        with self.assertRaises(ui_kit.LanguageError):
            self.act(label="x" * (ui_kit.LABEL_MAX + 1))
        with self.assertRaises(ui_kit.LanguageError):
            self.act(label="  ")
        self.act(label="x" * ui_kit.LABEL_MAX)

    async def test_a_state_glyph_never_stands_without_its_word_or_outside_the_vocabulary(self):
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Row(name="A", state="on", word=" ")
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Row(name="A", state="sparkles", word="ok")
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Row(name="A", state="on", word="ok", kind="rocket")
        ui_kit.Row(name="A", state="on", word="ok", kind="notes")

    async def test_red_sits_last_and_alone_never_on_a_row(self):
        red = self.act(style="danger", asks=True)
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Row(name="A", state="on", word="ok", act=red)
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Card(acts=(red,))
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Card(danger=self.act())  # the last act of a card is red, or there is none
        ui_kit.Card(acts=(self.act(),), danger=red)

    async def test_a_card_is_a_glance(self):
        rows = tuple(ui_kit.Row(name=str(i), state="on", word="ok") for i in range(ui_kit.ROWS_MAX + 1))
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Card(rows=rows)
        ui_kit.Card(rows=rows[:-1])

    async def test_accent_is_from_the_vocabulary_and_the_budget_is_enforced(self):
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Card(accent="hotpink")
        rows = tuple(ui_kit.Row(name=str(i), state="on", word="ok", act=self.act(custom_id=f"x:{i}")) for i in range(7))
        cards = [ui_kit.Card(title="c", rows=rows) for _ in range(3)]
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.build(cards)
        shown, hidden = ui_kit.fit(cards, ui_kit.PART_BUDGET)
        self.assertEqual((len(shown), hidden), (1, 2), "fit() counts what it leaves out")
        ui_kit.build(shown)  # positive control


class CognitiveErgonomicsTests(unittest.IsolatedAsyncioTestCase):
    """docs/ux/design-language.md §8, the rules that have a mechanism. Each has the case it must catch."""

    async def test_a_surface_says_what_it_is_before_its_first_card(self):
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.build([ui_kit.Card(rows=(ui_kit.Row("r", "ok", "on"),))])
        ui_kit.build([ui_kit.Header("Who answers here"), ui_kit.Card(rows=(ui_kit.Row("r", "ok", "on"),))])  # positive control
        ui_kit.build([ui_kit.Note("Done."), ui_kit.Header("h"), ui_kit.Card()])  # a receipt line may come first
        ui_kit.build([ui_kit.Card(title="Named", rows=(ui_kit.Row("r", "ok", "on"),))])

    async def test_what_a_thing_is_for_is_one_short_line(self):
        ui_kit.Item("!status", "How the house is doing")  # positive control
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Item("!status", "x" * (ui_kit.ITEM_LINE_MAX + 1))
        with self.assertRaises(ui_kit.LanguageError):
            ui_kit.Item("!status", " ")

    async def test_a_raw_clock_reading_is_caught_and_relative_time_is_not(self):
        raw = ui_kit.build([ui_kit.Header("h"), ui_kit.Note("Last used 2026-10-14 09:28")])
        self.assertTrue(any("raw timestamp" in v for v in ui_kit.violations(raw)))
        iso = ui_kit.build([ui_kit.Header("h"), ui_kit.Note("Checked 2026-10-14T09:28:00Z")])
        self.assertTrue(any("raw timestamp" in v for v in ui_kit.violations(iso)))
        relative = ui_kit.build([ui_kit.Header("h"), ui_kit.Note("Last used <t:1760000000:R>")])
        self.assertEqual(ui_kit.violations(relative), [], "positive control")

    async def test_an_item_renders_beside_no_state_glyph(self):
        view = ui_kit.build([ui_kit.Header("h"), ui_kit.Card(rows=(ui_kit.Item("!status", "How the house is doing"),))])
        self.assertIn("**!status**  How the house is doing", ui_kit.texts(view))


class MenuTests(unittest.IsolatedAsyncioTestCase):
    def pick(self, **kw):
        base = dict(
            placeholder="Change it",
            custom_id="m:1",
            choices=(ui_kit.Choice("A", "a", "first", current=True), ui_kit.Choice("B", "b")),
            callback=_noop(),
        )
        base.update(kw)
        return ui_kit.Pick(**base)

    async def test_a_menu_says_what_it_changes_and_offers_a_few_distinct_choices(self):
        self.pick()  # positive control
        for bad in (
            dict(placeholder=" "),
            dict(placeholder="x" * 151),
            dict(choices=()),
            dict(choices=tuple(ui_kit.Choice(str(i), str(i)) for i in range(ui_kit.PICK_MAX + 1))),
            dict(choices=(ui_kit.Choice("A", "a"), ui_kit.Choice("B", "a"))),
            dict(choices=(ui_kit.Choice("A", "a", current=True), ui_kit.Choice("B", "b", current=True))),
            dict(choices=(ui_kit.Choice("A" * 101, "a"),)),
        ):
            with self.assertRaises(ui_kit.LanguageError, msg=str(bad)[:60]):
                self.pick(**bad)

    async def test_the_part_count_includes_the_menu_and_is_the_librarys(self):
        card = ui_kit.Card(title="c", rows=(ui_kit.Row("r", "ok", "on"),), pick=self.pick())
        view = ui_kit.build([card])
        self.assertEqual(ui_kit.count_parts(view), view._total_children)
        self.assertEqual(card.parts(), ui_kit.count_parts(view), "the card counts its container, text, row, action row and menu")

    async def test_what_a_menu_says_is_read_by_the_checks_too(self):
        # A menu is text a person reads. If the checker could not see into it, an id or an
        # emoji outside the vocabulary would walk through it.
        leak = ui_kit.build([ui_kit.Card(title="c", pick=self.pick(choices=(ui_kit.Choice("g_f10adceb390c", "a", current=True),)))])
        self.assertTrue(any("id-shaped" in v for v in ui_kit.violations(leak)))
        fire = ui_kit.build([ui_kit.Card(title="c", pick=self.pick(choices=(ui_kit.Choice("A", "a", "\U0001f525 hot"),)))])
        self.assertTrue(any("vocabulary" in v for v in ui_kit.violations(fire)))
        self.assertEqual(ui_kit.violations(ui_kit.build([ui_kit.Card(title="c", pick=self.pick())])), [], "positive control")


class ViolationsCatchTests(unittest.IsolatedAsyncioTestCase):
    """Each rule, broken on purpose, in a surface built by hand around the kit."""

    def raw(self, *texts: str, danger_first=False, accessory_red=False) -> ui.LayoutView:
        view = ui.LayoutView(timeout=None)
        box = ui.Container()
        for text in texts:
            box.add_item(ui.TextDisplay(text))
        if accessory_red:
            box.add_item(ui.Section(ui.TextDisplay("row"), accessory=ui.Button(label="Delete", style=discord.ButtonStyle.danger, custom_id="r")))
        line = ui.ActionRow()
        line.add_item(ui.Button(label="End", style=discord.ButtonStyle.danger, custom_id="d"))
        line.add_item(ui.Button(label="Keep", style=discord.ButtonStyle.secondary, custom_id="k"))
        box.add_item(line)
        if danger_first:
            box.add_item(ui.TextDisplay("after the red row"))
        view.add_item(box)
        return view

    def good(self) -> ui.LayoutView:
        view = ui.LayoutView(timeout=None)
        box = ui.Container()
        box.add_item(ui.TextDisplay("\U0001f7e2 **Notes**  \U0001f7e2 open"))
        line = ui.ActionRow()
        line.add_item(ui.Button(label="Keep", style=discord.ButtonStyle.secondary, custom_id="k"))
        line.add_item(ui.Button(label="End", style=discord.ButtonStyle.danger, custom_id="d"))
        box.add_item(line)
        view.add_item(box)
        return view

    async def test_the_good_surface_passes(self):
        self.assertEqual(ui_kit.violations(self.good()), [], "positive control: the checker is not just saying no")

    async def test_a_code_block_is_caught(self):
        self.assertTrue(any("code block" in v for v in ui_kit.violations(self.raw("```\na  b\n```"))))

    async def test_an_id_or_a_named_thing_is_caught(self):
        self.assertTrue(any("id-shaped" in v for v in ui_kit.violations(self.raw("grant g_f10adceb390c is open"))))
        self.assertTrue(any("names" in v for v in ui_kit.violations(self.raw("the house profile"), forbidden=("house",))))

    async def test_an_emoji_outside_the_vocabulary_is_caught(self):
        self.assertTrue(any("vocabulary" in v for v in ui_kit.violations(self.raw("\U0001f525 hot"))))
        self.assertEqual([v for v in ui_kit.violations(self.raw("\u23f8 Pause")) if "vocabulary" in v], [])

    async def test_a_glyph_with_no_word_beside_it_is_caught(self):
        self.assertTrue(any("without a word" in v for v in ui_kit.violations(self.raw("\U0001f7e2"))))
        self.assertTrue(any("without a word" in v for v in ui_kit.violations(self.raw("**\U0001f7e2**  ."))))
        self.assertEqual([v for v in ui_kit.violations(self.raw("\U0001f7e2 open")) if "without" in v], [])

    async def test_red_not_last_or_red_on_a_row_is_caught(self):
        self.assertTrue(any("red" in v for v in ui_kit.violations(self.raw("x"))), "End before Keep: red is not last")
        self.assertTrue(any("red" in v for v in ui_kit.violations(self.raw("x", accessory_red=True))))
        mismatch = self.raw("x", danger_first=True)
        self.assertTrue(any("last thing in its card" in v for v in ui_kit.violations(mismatch)))

    async def test_too_many_parts_is_caught(self):
        # The library refuses to build 41, so hand the checker the payload a hand-rolled client could send.
        payload = [{"type": 17, "components": [{"type": 10, "content": f"line {n}"} for n in range(ui_kit.PART_BUDGET + 1)]}]
        self.assertTrue(any("budget" in v for v in ui_kit.violations(payload)))

    async def test_our_count_is_the_librarys_count(self):
        from mcp_access.reveal import set_open  # noqa: F401  (import keeps the fixture honest)

        rows = tuple(ui_kit.Row(name=str(i), state="on", word="ok", act=ui_kit.Act("Close", f"x:{i}", _noop())) for i in range(5))
        view = ui_kit.build([ui_kit.Header("t", "q"), ui_kit.Card(title="c", rows=rows, danger=ui_kit.Act("End", "e", _noop(), style="danger", asks=True))], footer="f")
        self.assertEqual(ui_kit.count_parts(view), view._total_children, "if Discord counts differently, the budget lies")


class RealSurfacesTests(ListFixture):
    """The `!mcp` list in every state it can be in, in both languages, keeps the grammar."""

    def check(self, label: str):
        for locale in ("en", "de"):
            self.shop.registry["mages"]["alice"]["locale"] = locale
            view = self.view()
            self.assertEqual(
                ui_kit.violations(view, forbidden=("alice-workshop", "health-alice", self.grant.id)),
                [],
                f"{label} / {locale}",
            )

    async def test_the_list_in_every_state(self):
        from mcp_access.reveal import set_open

        self.check("closed, X not signed in")
        for source in ("alice", "health-alice", "alice-workshop"):
            set_open(self.shop.store, self.grant.id, source, opened=True, registry=self.shop.registry)
        self.shop.store.remember_mcp_client(self.grant.id, "s", "cursor-vscode", "1")
        self.shop.store.count(self.grant.id, refused=False)
        self.check("all open, used")
        import outgoing_connections as door

        door.write_account(self.shop.root, "alice", "ada_name")
        self.check("X signed in, unchecked")
        door.set_paused(self.shop.root, "alice", True)
        self.check("X paused")
        for n in range(5):
            self.shop.store.create(principal=f"extra {n}", owner="alice", sources=[], profile="house")
        self.check("overflow")

    async def test_the_confirmations_keep_it_too(self):
        confirm = ui_kit.build(
            [
                ui_kit.Card(
                    title="End it?",
                    quiet="It stops.",
                    acts=(ui_kit.Act("Keep", "k", _noop()),),
                    danger=ui_kit.Act("End it", "e", _noop(), style="danger", confirms=True),
                    accent="attention",
                )
            ]
        )
        self.assertEqual(ui_kit.violations(confirm), [])
        self.assertEqual([b.label for b in buttons(confirm)], ["Keep", "End it"])


class LanguageTablesTests(unittest.TestCase):
    def test_every_string_exists_in_english_and_german(self):
        import help_card
        import mcp_connect_ui
        import mcp_list_ui
        import mcp_reveal_ui
        import room_models
        from mcp_access import reveal

        for name, table in (
            ("mcp_list_ui", mcp_list_ui._TEXT),
            ("reveal", reveal.LABELS),
            ("mcp_reveal_ui", mcp_reveal_ui._TEXT),
            ("mcp_connect_ui", mcp_connect_ui._TEXT),
            ("room_models", room_models._TEXT),
            ("help_card", help_card._TEXT),
        ):
            self.assertEqual(ui_kit.parity(table), [], name)

    def test_the_parity_check_can_fail(self):
        self.assertEqual(ui_kit.parity({"en": {"a": 1, "b": 2}, "de": {"a": 1}}), ["de lacks 'b'"])


class OnePlaceBuildsSurfacesTests(unittest.TestCase):
    PARTS = re.compile(r"\b(LayoutView|TextDisplay)\b|\bui\.(Container|Section|Separator)\b")
    EMBED = re.compile(r"\bEmbed\(")

    def test_only_the_kit_touches_the_layout_parts(self):
        offenders = [p.name for p in _source_files() if p.name != "ui_kit.py" and self.PARTS.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [], "build surfaces with ui_kit blocks, not raw layout parts")
        self.assertTrue(self.PARTS.search((REPO / "ui_kit.py").read_text(encoding="utf-8")), "positive control: the scan can see the parts")

    def test_a_new_embed_surface_is_a_decision_not_an_accident(self):
        using = {p.name for p in _source_files() if p.name != "ui_kit.py" and self.EMBED.search(p.read_text(encoding="utf-8"))}
        self.assertIn("commands.py", using, "positive control: the scan finds a known legacy surface")
        new = sorted(using - ui_kit.LEGACY_EMBED_SURFACES)
        self.assertEqual(new, [], "a new embed surface: build it with ui_kit, or add it to LEGACY_EMBED_SURFACES with a reason")
        gone = sorted(ui_kit.LEGACY_EMBED_SURFACES - using)
        self.assertEqual(gone, [], "no longer builds an embed: remove it from LEGACY_EMBED_SURFACES")


class EveryModalityHasItsSectionTests(unittest.TestCase):
    """§8: a modality cannot ship, or be dropped, without the design language knowing."""

    HEADING = re.compile(r"^### Modality: ([a-z ]+?)( \(planned\))?$", re.MULTILINE)

    def doc_modalities(self):
        doc = (REPO / "docs" / "ux" / "design-language.md").read_text(encoding="utf-8")
        found = self.HEADING.findall(doc)
        return {name: bool(planned) for name, planned in found}

    def test_the_code_and_the_doc_agree_both_ways(self):
        in_doc = self.doc_modalities()
        shipped = {name for name, planned in in_doc.items() if not planned}
        planned = {name for name, is_planned in in_doc.items() if is_planned}
        self.assertEqual(shipped, set(ui_kit.MODALITIES), "a modality in code with no section, or a section for one that is not in code")
        self.assertEqual(planned, set(ui_kit.PLANNED_MODALITIES), "a planned modality is named in both, with its reason in code")
        self.assertTrue(all(ui_kit.PLANNED_MODALITIES.values()), "a planned modality names why it has no code yet")

    def test_the_check_can_fail(self):
        with unittest.mock.patch.object(ui_kit, "MODALITIES", ("text", "card", "gesture")):
            self.assertNotEqual({n for n, p in self.doc_modalities().items() if not p}, set(ui_kit.MODALITIES))


class DocNamesTheVocabularyTests(unittest.TestCase):
    def test_every_glyph_in_code_is_in_the_doc_and_back(self):
        doc = (REPO / "docs" / "ux" / "design-language.md").read_text(encoding="utf-8")
        for glyph in ui_kit.GLYPHS:
            self.assertIn(glyph, doc, f"{glyph!r} is in the kit's vocabulary but not in the doc")
        vocabulary = doc[doc.index("| Glyph | Means"): doc.index("`system-state.md` rejects")]
        in_doc = {c for c in vocabulary if re.match("[\U0001f000-\U0001faff\u2300-\u23ff\u25a0-\u25ff\u2600-\u27bf\u2b00-\u2bff]", c)}
        self.assertEqual(in_doc - ui_kit.GLYPHS, set(), "the doc promises a glyph the kit does not allow")


if __name__ == "__main__":
    unittest.main()
