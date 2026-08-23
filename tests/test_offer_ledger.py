"""Offer ledger — the write-path ratio that tells silence apart from absence."""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import offer_ledger as ol


class RootResolutionTests(unittest.TestCase):
    """The positive control that was never run, and the eight days it cost.

    On 2026-08-06 the resolver was made strict — channel to root, no fallback —
    because the unit suite had filed fixture channel 99 into the operator's
    ledger. That fix was verified by confirming the suite writes *nothing*: a
    negative control. Nobody checked that a real offer in a real eddy still
    lands a row, and it did not. Every contextual offer fires inside a thread,
    the registry holds only parent channels, so `root_for_channel` returned None
    for all 36 offers `river.log` recorded posting while the nightly report
    printed "instrumentation is live but nothing has been recorded yet".
    """

    def setUp(self) -> None:
        import mage

        self.mage = mage
        self._registry = mage._MAGE_REGISTRY
        self._thread_state = mage._parent_id_from_thread_state
        mage._MAGE_REGISTRY = {
            "channels": {"1000": {"mage": "kermit"}},
            "mages": {"kermit": {"practice_dir": "/tmp/kermit-practice-root"}},
        }
        # Stands in for the on-disk eddy thread-state the live path reads.
        mage._parent_id_from_thread_state = lambda tid: 1000 if int(tid) == 2000 else None

    def tearDown(self) -> None:
        self.mage._MAGE_REGISTRY = self._registry
        self.mage._parent_id_from_thread_state = self._thread_state

    def test_an_offer_in_an_eddy_resolves_to_the_parents_root(self) -> None:
        self.assertEqual(ol.root_for_channel(2000), "/tmp/kermit-practice-root")

    def test_a_registered_parent_channel_still_resolves(self) -> None:
        self.assertEqual(ol.root_for_channel(1000), "/tmp/kermit-practice-root")

    def test_an_unregistered_channel_still_resolves_to_nothing(self) -> None:
        """The negative control the strictness was bought with — still holds.

        Fixture channel 99 has no registry entry and no thread state, so the
        parent walk returns it unchanged and the lookup finds nobody. Widening
        the resolver must not re-open the door it closed.
        """
        self.assertIsNone(ol.root_for_channel(99))
        self.assertIsNone(ol.root_for_channel(None))
        self.assertIsNone(ol.root_for_channel("not-a-channel"))

    def test_a_posted_offer_in_an_eddy_writes_exactly_one_row(self) -> None:
        """End to end through the seneschal's own logger, not just the resolver.

        A resolver test alone would have passed on 08-06 too — the defect lived
        in what the call site handed it.
        """
        import river_eddy_seneschal as ses

        with tempfile.TemporaryDirectory() as tmp:
            self.mage._MAGE_REGISTRY["mages"]["kermit"]["practice_dir"] = tmp
            channel = MagicMock()
            channel.id = 2000
            channel.name = "difference between communal and covert narcissists"

            ses._log_contextual_posted(channel, "home_plan")
            ses._record_offer_suppressed(channel, "home_plan", "care_register")

            events = ol.read_events(tmp)
            self.assertEqual([e["event"] for e in events], ["offered", "suppressed"])
            self.assertEqual(events[0]["channel_id"], "2000")
            self.assertEqual(events[1]["detail"], "care_register")


class OfferLedgerTests(unittest.TestCase):
    def test_roundtrip_and_tally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ol.record(tmp, kind="date_keep", event="offered", channel_id=7)
            ol.record(tmp, kind="date_keep", event="offered", channel_id=7)
            ol.record(tmp, kind="date_keep", event="accepted", channel_id=7)
            ol.record(tmp, kind="home_plan", event="offered", channel_id=8)

            counts = ol.tally([tmp])
            self.assertEqual(counts["date_keep"]["offered"], 2)
            self.assertEqual(counts["date_keep"]["accepted"], 1)
            self.assertEqual(counts["date_keep"]["no_answer"], 1)
            self.assertEqual(counts["home_plan"]["no_answer"], 1)

    def test_tally_spans_roots(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ol.record(a, kind="save", event="offered")
            ol.record(b, kind="save", event="accepted")
            counts = ol.tally([a, b])
            self.assertEqual(counts["save"]["offered"], 1)
            self.assertEqual(counts["save"]["accepted"], 1)

    def test_unknown_event_is_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ol.record(tmp, kind="date_keep", event="pondered")
            self.assertEqual(ol.read_events(tmp), [])

    def test_corrupt_line_is_skipped_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ol.record(tmp, kind="save", event="offered")
            path = ol.ledger_path(tmp)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("{not json\n\n")
            self.assertEqual(len(ol.read_events(tmp)), 1)

    def test_window_filters_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = ol.ledger_path(tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            old = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            path.write_text(
                '{"ts": "%s", "kind": "save", "event": "offered"}\n' % old,
                encoding="utf-8",
            )
            ol.record(tmp, kind="save", event="offered")

            self.assertEqual(ol.tally([tmp])["save"]["offered"], 2)
            recent = ol.tally([tmp], since=ol.default_window_start(30))
            self.assertEqual(recent["save"]["offered"], 1)

    def test_never_raises_on_unwritable_root(self) -> None:
        # Instrumentation must not be the reason a member's turn fails.
        ol.record("/proc/nonexistent/nope", kind="save", event="offered")

    def test_zero_offers_is_rendered_as_a_defect_not_a_verdict(self) -> None:
        """The headline case: a feature that shipped and never fired.

        `dates` ran for two days across five rivers and produced zero keeps.
        Zero keeps is what a feature nobody wanted looks like *and* what a
        feature nobody was ever asked about looks like. The section has to say
        which, or it repeats the ambiguity it exists to remove.
        """
        section = ol.render_write_path_section(
            {"home_plan": {"offered": 17, "accepted": 1, "declined": 0, "no_answer": 16}},
            window_days=30,
            known_kinds=("date_keep", "home_plan"),
            opened=date.today() - timedelta(days=60),
        )
        self.assertIn("date_keep", section)
        self.assertIn("never fired", section)
        self.assertIn("Zero offers is", section)
        # The one that did fire reports its take rate rather than the flag.
        home_row = [ln for ln in section.splitlines() if ln.startswith("| home_plan")][0]
        self.assertIn("6%", home_row)
        self.assertNotIn("never fired", home_row)

    def test_a_cold_ledger_says_unmeasured_not_never_fired(self) -> None:
        """The first night must not accuse every feature of being broken."""
        def row_for(section: str, kind: str) -> str:
            # Assert on the table row, not the section — the explanatory prose
            # above it legitimately contains the phrase "never fired".
            return [ln for ln in section.splitlines() if ln.startswith(f"| {kind}")][0]

        young = ol.render_write_path_section(
            {}, window_days=30, known_kinds=("date_keep",), opened=date.today()
        )
        self.assertIn("no data yet", row_for(young, "date_keep"))
        self.assertNotIn("never fired", row_for(young, "date_keep"))
        self.assertIn("unmeasured", young)

        empty = ol.render_write_path_section({}, window_days=30, known_kinds=("date_keep",))
        self.assertIn("Ledger empty", empty)
        self.assertNotIn("never fired", row_for(empty, "date_keep"))

    def test_opened_on_reports_the_earliest_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ol.opened_on([tmp]))
            ol.record(tmp, kind="save", event="offered")
            self.assertEqual(ol.opened_on([tmp]), datetime.now(timezone.utc).date())

    def test_section_is_empty_when_nothing_is_known(self) -> None:
        self.assertEqual(ol.render_write_path_section({}, window_days=30), "")


class OfferWiringTests(unittest.TestCase):
    """Name the reader: every offer site must reach the ledger."""

    def test_contextual_offer_logger_records_against_the_owning_root(self) -> None:
        import river_eddy_seneschal as res

        with tempfile.TemporaryDirectory() as tmp:
            original = ol.root_for_channel
            ol.root_for_channel = lambda cid: tmp if str(cid) == "42" else None  # type: ignore[assignment]
            try:
                channel = MagicMock()
                channel.id = 42
                channel.name = "river"
                res._log_contextual_posted(channel, "home_plan")
            finally:
                ol.root_for_channel = original  # type: ignore[assignment]

            events = ol.read_events(tmp)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["kind"], "home_plan")
            self.assertEqual(events[0]["event"], "offered")

    def test_unregistered_channel_writes_no_ledger_anywhere(self) -> None:
        """The suite itself must not file offers against a real practitioner.

        It did, on the first live run: `channel_id: 99` — a fixture — landed in
        the operator's ledger because the logger resolved the root with
        get_pd() instead of from the channel.
        """
        import river_eddy_seneschal as res

        self.assertIsNone(ol.root_for_channel(99))
        self.assertIsNone(ol.root_for_channel(None))

        channel = MagicMock()
        channel.id = 99
        channel.name = "fixture"
        with tempfile.TemporaryDirectory() as tmp:
            before = sorted(Path(tmp).rglob("*"))
            res._log_contextual_posted(channel, "save")
            self.assertEqual(sorted(Path(tmp).rglob("*")), before)

    def test_date_keep_outcomes_reach_the_ledger(self) -> None:
        import dates as fd

        with tempfile.TemporaryDirectory() as tmp:
            fd._record_offer_accepted(tmp, 7)
            counts = ol.tally([tmp])
            self.assertEqual(counts["date_keep"]["accepted"], 1)
            # No decline path exists to exercise since 2026-08-14 — silence is
            # the decline, so non-acceptance is inferred rather than recorded.
            self.assertEqual(counts["date_keep"]["declined"], 0)


REPO = Path(__file__).resolve().parents[1]

# A kind arrives at the ledger through one of these call shapes. `kind=` covers
# ContextualOffer(...) and offer_ledger.record(...); the positional pair covers
# the two seneschal helpers that take the kind as their second argument.
# `record_for_channel` (2026-08-14) is the resolve-then-record helper; it must be
# scanned like `record`, or wiring an offer through it would read as no wiring.
_KIND_KEYWORD_CALLS = {"ContextualOffer", "record", "record_for_channel", "_offer"}
_KIND_SECOND_ARG_CALLS = {"_log_contextual_posted", "_record_offer_suppressed"}

# Asking the runtime registry for a label is *not* a ledger write, and conflating
# the two would make every uncounted offer look like an unwatched one. Scanned
# separately, against the registry rather than against KINDS.
_REGISTRY_LOOKUP_CALLS = {"accept_action", "label_for", "description_for"}

# Other per-root JSONL ledgers share the ``record(kind=...)`` call shape and
# have their own kind list. `record_gaps` (2026-08-07) counts holes in the
# practice record, not offers; its coverage guard lives in
# `test_record_gaps.py`. Matching on the bare name `record` cannot tell them
# apart, so the receiver decides.
_OTHER_LEDGER_RECEIVERS = {"record_gaps"}


def _literal_kinds(source: str) -> set[str]:
    """Every offer kind written as a literal on its way to the ledger."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and getattr(node.func.value, "id", "") in _OTHER_LEDGER_RECEIVERS
        ):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name in _KIND_KEYWORD_CALLS:
            for kw in node.keywords:
                if kw.arg == "kind" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    found.add(kw.value.value)
        if name in _KIND_SECOND_ARG_CALLS and len(node.args) >= 2:
            arg = node.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.add(arg.value)
    return found


def _registry_lookup_kinds(source: str) -> set[str]:
    """Every offer kind a module asks the runtime registry about."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", "")
        )
        if name in _REGISTRY_LOOKUP_CALLS and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.add(arg.value)
    return found


class OfferKindCoverageTests(unittest.TestCase):
    """The list of watched kinds must come from the code, not from memory.

    `KNOWN_OFFER_KINDS` was hand-maintained and named four of six. The two it
    missed — `turtle_save` / `turtle_checkpoint` — sit *ahead* of `save` /
    `checkpoint` in the turn handler and have never fired once, so the only
    genuinely dead offer path was the one path the "never fired" flag could
    not reach. A missing row and a zero row mean opposite things; a kind that
    is absent from the list renders as no row at all.
    """

    def test_every_emitted_kind_is_a_watched_kind(self) -> None:
        emitted: dict[str, set[str]] = {}
        for path in sorted(REPO.glob("*.py")):
            kinds = _literal_kinds(path.read_text(encoding="utf-8"))
            if kinds:
                emitted[path.name] = kinds

        self.assertIn("river_eddy_seneschal.py", emitted, "offer sites moved — retarget this scan")

        unwatched = {
            module: sorted(kinds - set(ol.KINDS))
            for module, kinds in emitted.items()
            if kinds - set(ol.KINDS)
        }
        self.assertEqual(
            unwatched,
            {},
            "offer kinds reaching the ledger but absent from offer_ledger.KINDS "
            f"(add them, or they render as no row at all): {unwatched}",
        )

    def test_scan_catches_an_unwatched_kind(self) -> None:
        """Positive control — an empty result must mean absence, not a blind scan."""
        for snippet, expected in (
            ('ContextualOffer(kind="brand_new", description="x")', "brand_new"),
            ('_log_contextual_posted(channel, "brand_new")', "brand_new"),
            ('_record_offer_suppressed(channel, "brand_new", "why")', "brand_new"),
            ('record(root, kind="brand_new", event="offered")', "brand_new"),
            ('_offer(kind="brand_new", command="!x")', "brand_new"),
            ('record_for_channel(ch, kind="brand_new", event="offered")', "brand_new"),
        ):
            with self.subTest(snippet=snippet):
                found = _literal_kinds(snippet)
                self.assertIn(expected, found)
                self.assertTrue(found - set(ol.KINDS), "control kind should read as unwatched")

    def test_every_label_lookup_names_a_declared_offer(self) -> None:
        """A view asking for a kind the registry never declared raises at runtime.

        Counted or not is a separate question — `flow_intake` and `flow_rename`
        are real offers with no ledger row, and `runtime.offers.UNCOUNTED` is
        where that is admitted, with the reason.
        """
        from runtime import offers as offer_registry

        undeclared = {}
        for path in sorted(REPO.glob("*.py")):
            kinds = _registry_lookup_kinds(path.read_text(encoding="utf-8"))
            missing = sorted(kinds - set(offer_registry.REGISTRY))
            if missing:
                undeclared[path.name] = missing
        self.assertEqual(
            undeclared,
            {},
            f"declare these in runtime/offers.py: {undeclared}",
        )

    def test_registry_scan_catches_an_undeclared_lookup(self) -> None:
        """Positive control for the second scan."""
        found = _registry_lookup_kinds('accept_action("brand_new").label')
        self.assertIn("brand_new", found)

    def test_every_instrumented_accept_is_actually_recorded(self) -> None:
        """ACCEPT_INSTRUMENTED prints a take rate — it must not print a fiction.

        The column reads "not recorded" for kinds outside this set. A kind listed
        here with no `event="accepted"` write anywhere would print `0%` instead,
        which reads as *nobody took it* rather than *nobody counted*. Those two
        are the exact confusion this ledger was built to end.
        """
        recorded: set[str] = set()
        for path in REPO.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", "")
                )
                if name not in _KIND_KEYWORD_CALLS:
                    continue
                kw = {
                    k.arg: k.value.value
                    for k in node.keywords
                    if isinstance(k.value, ast.Constant)
                }
                if kw.get("event") == "accepted" and isinstance(kw.get("kind"), str):
                    recorded.add(kw["kind"])
        self.assertEqual(
            sorted(set(ol.ACCEPT_INSTRUMENTED) - recorded),
            [],
            "these claim a take rate but no code records their acceptance",
        )

    def test_watched_kinds_are_all_actually_emitted(self) -> None:
        """The other direction: a watched kind no code emits is a stale row."""
        emitted: set[str] = set()
        for path in REPO.glob("*.py"):
            emitted |= _literal_kinds(path.read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(set(ol.KINDS) - emitted),
            [],
            "offer_ledger.KINDS names a kind nothing emits — it would render as "
            "a permanent 'never fired' row for a path that does not exist",
        )


if __name__ == "__main__":
    unittest.main()
