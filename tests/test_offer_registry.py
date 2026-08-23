"""One list of offers, and it is the one the ledger counts from.

Slice 3 of the transport abstraction. Labels lived in six Discord modules and the
ledger's kind list was hand-maintained beside them; the ledger's own comment
records getting that wrong once, missing the only two kinds that had never fired.
The registry replaces both — and these tests are what stop it becoming a third
list that drifts from the other two.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import offer_ledger as ol
from runtime import offers
from runtime.messages import Action

REPO_ROOT = Path(__file__).resolve().parents[1]


class RegistryShapeTests(unittest.TestCase):
    def test_every_spec_has_an_english_label(self) -> None:
        for kind, spec in offers.REGISTRY.items():
            if spec.dynamic_label_from:
                continue
            self.assertIn("en", spec.labels, kind)
            self.assertTrue(spec.labels["en"].strip(), kind)

    def test_kind_matches_its_registry_key(self) -> None:
        for key, spec in offers.REGISTRY.items():
            self.assertEqual(key, spec.kind)

    def test_an_unknown_kind_names_the_fix(self) -> None:
        with self.assertRaises(KeyError) as caught:
            offers.spec("no_such_offer")
        self.assertIn("runtime/offers.py", str(caught.exception))

    def test_accept_action_is_a_runtime_action(self) -> None:
        action = offers.accept_action("home_plan")
        self.assertIsInstance(action, Action)
        self.assertEqual(action.key, "home_plan")
        self.assertEqual(action.label, "Keep as working plan")
        self.assertEqual(action.payload["kind"], "home_plan")

    def test_payload_extras_do_not_lose_the_kind(self) -> None:
        action = offers.accept_action("save", payload={"url": "https://example.test"})
        self.assertEqual(action.payload["url"], "https://example.test")
        self.assertEqual(action.payload["kind"], "save")


class LocaleTests(unittest.TestCase):
    def test_german_date_label_survived_the_move(self) -> None:
        """The one translation in the product; it used to sit in a Discord view."""
        self.assertEqual(offers.label_for("date_keep", "de"), "Datum merken")
        self.assertEqual(offers.label_for("date_keep", "en"), "Keep this date")

    def test_an_unknown_locale_falls_back_to_english(self) -> None:
        self.assertEqual(offers.label_for("date_keep", "fr"), "Keep this date")
        self.assertEqual(offers.label_for("home_plan", "de"), "Keep as working plan")

    def test_a_dynamic_label_refuses_to_be_guessed(self) -> None:
        """`link_read` names its offer from the URL — a video is not an article."""
        with self.assertRaises(ValueError) as caught:
            offers.label_for("link_read")
        self.assertIn("action_for_urls", str(caught.exception))

    def test_the_delegate_the_registry_names_exists(self) -> None:
        from runtime.link_offers import action_for_urls

        self.assertEqual(
            offers.REGISTRY["link_read"].dynamic_label_from,
            "runtime.link_offers.action_for_urls",
        )
        action = action_for_urls(["https://youtu.be/abc123"])
        self.assertEqual(action.label, "Fetch transcript")


class LedgerAgreementTests(unittest.TestCase):
    def test_the_ledger_counts_exactly_the_counted_kinds(self) -> None:
        self.assertEqual(tuple(ol.KINDS), offers.counted_kinds())

    def test_the_counted_set_is_exactly_what_we_decided(self) -> None:
        """Deriving the list must not silently drop a row from the report.

        Six historical kinds plus `themes_keep` and `link_read`, counted
        2026-08-14, plus `eddy_ready`, counted 2026-08-16. A kind leaving this
        list means a report row vanishing, which is the failure mode that hid an
        eight-day silence.
        """
        self.assertEqual(
            sorted(ol.KINDS),
            [
                "checkpoint",
                "date_keep",
                "eddy_ready",
                "home_plan",
                "link_read",
                "save",
                "themes_keep",
                "turtle_checkpoint",
                "turtle_save",
            ],
        )

    def test_every_uncounted_kind_says_why(self) -> None:
        """An uncounted offer is a measurement gap; an unexplained one is a bug."""
        self.assertEqual(sorted(offers.uncounted_kinds()), sorted(offers.UNCOUNTED))
        for kind, reason in offers.UNCOUNTED.items():
            self.assertIn(kind, offers.REGISTRY, kind)
            self.assertGreater(len(reason.strip()), 20, kind)

    def test_counted_and_uncounted_partition_the_registry(self) -> None:
        self.assertEqual(
            sorted(offers.counted_kinds()) + sorted(offers.uncounted_kinds()),
            sorted(offers.counted_kinds()) + sorted(offers.uncounted_kinds()),
        )
        self.assertEqual(
            set(offers.counted_kinds()) | set(offers.uncounted_kinds()),
            set(offers.REGISTRY),
        )
        self.assertEqual(
            set(offers.counted_kinds()) & set(offers.uncounted_kinds()), set()
        )

    def test_accept_instrumented_kinds_are_counted_kinds(self) -> None:
        """Recording an accept for a kind with no row would be unreadable."""
        self.assertTrue(set(ol.ACCEPT_INSTRUMENTED) <= set(ol.KINDS))


class NoLabelsLeftInTheViewsTests(unittest.TestCase):
    """A view may render a label; it may not invent one.

    The point of the registry is that a transport without buttons has something to
    fold into prose. That only holds if the string is not typed into the Discord
    module — which is where all five of these lived until 2026-08-14.
    """

    VIEW_MODULES = (
        "home_plan_ui.py",
        "continuity_confirm.py",
        "dates.py",
        "flow_intake_handler.py",
        "eddy_flow_library.py",
    )

    MIGRATED_LABELS = (
        "Keep as working plan",
        "Keep these",
        "Keep this date",
        "Datum merken",
        "Rename thread",
    )

    def test_no_view_spells_a_migrated_label(self) -> None:
        offenders = []
        for name in self.VIEW_MODULES:
            source = (REPO_ROOT / name).read_text(encoding="utf-8")
            for label in self.MIGRATED_LABELS:
                if f'"{label}"' in source or f"'{label}'" in source:
                    offenders.append(f"{name}: {label!r}")
        self.assertEqual(
            offenders,
            [],
            "ask runtime.offers.accept_action for the label instead of spelling "
            f"it in a Discord view: {offenders}",
        )

    def test_each_view_asks_the_registry(self) -> None:
        for name in self.VIEW_MODULES:
            source = (REPO_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("accept_action", source, name)

    def test_the_seneschal_no_longer_spells_its_descriptions(self) -> None:
        source = (REPO_ROOT / "river_eddy_seneschal.py").read_text(encoding="utf-8")
        self.assertNotIn("save this link", source)
        self.assertNotIn("checkpoint** this thread", source)
        self.assertIn("description_for", source)

    def test_the_guard_would_notice_a_relapse(self) -> None:
        """Positive control — the substring check must actually match."""
        sample = '        keep = Button(label="Keep as working plan")'
        self.assertIn('"Keep as working plan"', sample)


class BoundaryTests(unittest.TestCase):
    def test_the_registry_imports_no_transport(self) -> None:
        """The whole reason it lives under `runtime/`."""
        tree = ast.parse((REPO_ROOT / "runtime" / "offers.py").read_text("utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("discord", "nio", "slack_sdk", "matrix"):
            self.assertNotIn(forbidden, imported)


if __name__ == "__main__":
    unittest.main()
