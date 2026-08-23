"""No offer carries a button whose only job is to decline it.

The operator's principle, given 2026-08-11 for the link offer and applied to
every surface on 2026-08-14: *"Ignoring the offer should just be enough. No
action needed to decline."*

The reason it generalises is a measurement argument, not a taste one. A decline
button manufactures the very event the offer ledger exists to infer, so
``declined`` counted how often someone bothered to dismiss a thing rather than
how often they wanted it. Silence was always the real signal.

This is a class guard, not five deletions: the next offer view will be written by
someone who has read four existing views, all of which had a Skip.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Labels that mean "no thanks" and nothing else. Matched case-insensitively
# against button label literals.
DECLINE_LABELS = re.compile(
    r"^\s*(skip\b|not now|no thanks|nicht jetzt|dismiss|cancel offer|nein danke)",
    re.IGNORECASE,
)

# custom_id fragments that identify a decline handler.
DECLINE_IDS = re.compile(r"(:|^)(skip|decline|dismiss)(:|$)", re.IGNORECASE)

# A `Cancel` inside a modal or a destructive confirmation is not an offer being
# declined — it is backing out of an action already begun. Named, with reasons.
EXEMPT_FILES: dict[str, str] = {}


def _string_kwarg(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg != name:
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
        if isinstance(kw.value, ast.JoinedStr):
            parts = []
            for value in kw.value.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                else:
                    parts.append("{}")
            return "".join(parts)
        if isinstance(kw.value, ast.IfExp):
            # `label="Not now" if locale != "de" else "Nicht jetzt"` — both arms
            # are the button's text, so either matching is a hit.
            for branch in (kw.value.body, kw.value.orelse):
                if isinstance(branch, ast.Constant) and isinstance(branch.value, str):
                    if DECLINE_LABELS.match(branch.value):
                        return branch.value
            return None
    return None


# `Button` is where labels used to be written. Since 2026-08-14 an offer's label
# can also be written as a runtime `Action`, which `discord_render` turns into a
# button — so a scanner that only knew `Button` would have gone quietly blind the
# moment the seam was wired, and reported a clean tree while the label it was
# looking for moved one file over. `Action` carries `key`, not `custom_id`.
LABEL_CALLS = {"Button", "Action"}


def _button_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = ""
        if isinstance(target, ast.Attribute):
            name = target.attr
        elif isinstance(target, ast.Name):
            name = target.id
        if name in LABEL_CALLS:
            yield node


def _offenders(paths) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if path.name in EXEMPT_FILES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for call in _button_calls(tree):
            label = _string_kwarg(call, "label") or ""
            identifier = (
                _string_kwarg(call, "custom_id") or _string_kwarg(call, "key") or ""
            )
            if DECLINE_LABELS.match(label) or DECLINE_IDS.search(identifier):
                hits.append(f"{path.name}:{call.lineno} label={label!r}")
    return sorted(hits)


class NoDeclineButtonTests(unittest.TestCase):
    def test_no_module_builds_a_decline_button(self) -> None:
        offenders = _offenders(sorted(REPO_ROOT.glob("*.py")))
        self.assertEqual(
            offenders,
            [],
            "ignoring an offer is how it is declined — drop the button and let "
            "silence carry it:\n  " + "\n  ".join(offenders),
        )

    def test_the_guard_catches_each_shape_it_claims_to(self) -> None:
        """Positive control — one case per shape that was actually removed."""
        cases = {
            "plain": 'discord.ui.Button(label="Skip", custom_id="x")',
            "not_now": 'discord.ui.Button(label="Not now", custom_id="x")',
            "suffixed": 'discord.ui.Button(label="Skip — I\'ll talk", custom_id="x")',
            "localised": (
                'discord.ui.Button(label="Not now" if l != "de" else "Nicht jetzt",'
                ' custom_id="x")'
            ),
            "by_id": 'discord.ui.Button(label="Later", custom_id=f"dates:skip:{c}")',
        }
        for name, src in cases.items():
            with self.subTest(shape=name):
                tree = ast.parse(src)
                calls = list(_button_calls(tree))
                self.assertEqual(len(calls), 1, name)
                label = _string_kwarg(calls[0], "label") or ""
                custom_id = _string_kwarg(calls[0], "custom_id") or ""
                self.assertTrue(
                    DECLINE_LABELS.match(label) or DECLINE_IDS.search(custom_id), name
                )

    def test_the_runtime_offers_no_decline_action(self) -> None:
        """Offer labels moved into `runtime/`; the guard has to follow them there.

        Without this, wiring the transport seam would have silently narrowed the
        guard to the modules that still write `Button(label=...)` literals.
        """
        offenders = _offenders(sorted((REPO_ROOT / "runtime").rglob("*.py")))
        self.assertEqual(
            offenders,
            [],
            "a runtime Action whose label means 'no thanks' is a decline button "
            "with extra steps:\n  " + "\n  ".join(offenders),
        )

    def test_the_guard_sees_a_decline_action(self) -> None:
        """Positive control for the new shape, in both spellings."""
        for src in (
            'Action(key="skip", label="Skip")',
            'Action(key="link_skip", label="Not now", payload={})',
            'messages.Action(key="dismiss", label="Later")',
        ):
            with self.subTest(src=src):
                tree = ast.parse(src)
                calls = list(_button_calls(tree))
                self.assertEqual(len(calls), 1, src)
                label = _string_kwarg(calls[0], "label") or ""
                identifier = (
                    _string_kwarg(calls[0], "custom_id")
                    or _string_kwarg(calls[0], "key")
                    or ""
                )
                self.assertTrue(
                    DECLINE_LABELS.match(label) or DECLINE_IDS.search(identifier), src
                )

    def test_the_guard_does_not_flag_a_real_runtime_action(self) -> None:
        """Negative control — the labels actually shipped must pass."""
        for src in (
            'Action(key="read_youtube", label="Fetch transcript")',
            'Action(key="read_aloud", label="Read aloud")',
            'Action(key="read_links", label="Read links", payload={"kind": "mixed"})',
        ):
            tree = ast.parse(src)
            call = next(_button_calls(tree))
            label = _string_kwarg(call, "label") or ""
            identifier = _string_kwarg(call, "key") or ""
            self.assertFalse(DECLINE_LABELS.match(label), src)
            self.assertFalse(DECLINE_IDS.search(identifier), src)

    def test_the_guard_does_not_flag_an_accept_button(self) -> None:
        """Negative control — it must not simply reject every button."""
        for src in (
            'discord.ui.Button(label="Keep this date", custom_id="dates:keep:1")',
            'discord.ui.Button(label="Prepare", custom_id="river:flow:intake:prepare:1")',
            'discord.ui.Button(label="Fetch transcript", custom_id="link:read:1")',
        ):
            tree = ast.parse(src)
            call = next(_button_calls(tree))
            label = _string_kwarg(call, "label") or ""
            custom_id = _string_kwarg(call, "custom_id") or ""
            self.assertFalse(DECLINE_LABELS.match(label), src)
            self.assertFalse(DECLINE_IDS.search(custom_id), src)

    def test_no_module_records_a_decline(self) -> None:
        """`declined` is historical. Nothing may write it while no button exists.

        Matched on the offer ledger's own keyword, not the word "declined":
        `record_gaps` and `consent` both use that word for unrelated states, and a
        text search reports them as defects forever, which is how a guard teaches
        its reader to ignore it.
        """
        offenders = []
        for path in sorted(REPO_ROOT.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg != "event":
                        continue
                    if (
                        isinstance(kw.value, ast.Constant)
                        and kw.value.value == "declined"
                    ):
                        offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "a decline was recorded but no surface can produce one — either the "
            f"button came back or the write is dead: {offenders}",
        )

    def test_the_decline_guard_catches_a_ledger_write(self) -> None:
        """Positive control for the event-keyword match."""
        tree = ast.parse('record(pd, kind="date_keep", event="declined", channel_id=1)')
        found = [
            kw
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "event"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value == "declined"
        ]
        self.assertEqual(len(found), 1)

    def test_the_decline_guard_ignores_unrelated_uses_of_the_word(self) -> None:
        """Negative control — `record_gaps` and `consent` legitimately say it."""
        for src in (
            '_record_gap(cid, kind="eddy_note", reason="declined", detail=str(e))',
            'reason = "no answer recorded" if not answered(k, n) else "declined"',
            'REASONS = ("failed", "declined", "exhausted")',
        ):
            tree = ast.parse(src)
            found = [
                kw
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                for kw in node.keywords
                if kw.arg == "event"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "declined"
            ]
            self.assertEqual(found, [], src)

    def test_exemptions_name_a_file_that_exists(self) -> None:
        for name in EXEMPT_FILES:
            self.assertTrue((REPO_ROOT / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
