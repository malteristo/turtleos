#!/usr/bin/env python3
"""Shakedown for family dates — a member journey, not a feature poke.

The journey this walks is the one the family thesis is measured on: a member
names a date the way people actually name dates, and a reminder arrives,
without anyone having learned a command.

  1. notice    — the river sees a commitment in ordinary speech
  2. restraint — and stays quiet when there was no commitment (the control)
  3. confirm   — the offer is a question with a readable echo
  4. keep      — accepting writes the owning root's registry
  5. surface   — reminders come due at the lead times, once each
  6. read back — `!dates` answers in the member's language
  7. typed     — the `!date` path accepts the same forms the river does

Offline only. Live verification is the operator dogfood after restart:
say a date in the river, take the Keep, wait for the lead day.
"""
from __future__ import annotations

# Declared for scripts/shake_report.py: this script mutates nothing a
# practitioner can see, so the nightly gate may run it unattended.
OFFLINE_SAFE = True

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

TEST_RUNS = REPO / "test-runs"

# A Thursday, so weekday arithmetic in the fixtures is checkable by hand.
TODAY = date(2026, 8, 6)


def check_notice() -> list[str]:
    """Stage 1 — the forms a family actually uses all reach the parser."""
    errors: list[str] = []
    import dates as fd

    # (text, locale, expected date) — none of these contain a digit-form date
    # except where a member deliberately wrote one.
    journeys = [
        ("Maëls Geburtstagsfeier ist am 24. Dezember", "de", date(2026, 12, 24)),
        ("Wir fahren am 24. Dezember nach Hamburg", "de", date(2026, 12, 24)),
        ("Der Elternabend ist am Samstag", "de", date(2026, 8, 8)),
        ("Zahnarzttermin morgen — bitte erinnern", "de", date(2026, 8, 7)),
        ("Am 24.12. ist Kita Fest", "de", date(2026, 12, 24)),
        ("the parent evening is on December 24", "en", date(2026, 12, 24)),
        ("remind me about the appointment on Saturday", "en", date(2026, 8, 8)),
    ]
    for text, locale, expected in journeys:
        parsed = fd.parse_date_commitment(text, locale=locale, today=TODAY)
        if parsed is None:
            errors.append(f"missed commitment: {text!r}")
            continue
        if parsed.when != expected:
            errors.append(f"{text!r} → {parsed.when}, expected {expected}")
        if not parsed.title.strip():
            errors.append(f"{text!r} produced an empty title")
    return errors


def check_restraint() -> list[str]:
    """Stage 2 — the negative control. A river is not a calendar."""
    errors: list[str] = []
    import dates as fd

    quiet = [
        ("Ich gehe morgen noch schnell einkaufen", "de"),
        ("Am Samstag war es richtig heiß hier", "de"),
        ("Er hat heute den ganzen Tag geschlafen", "de"),
        ("we talked about it yesterday and today it still hurts", "en"),
        ("das dauert bestimmt noch drei Wochen", "de"),
    ]
    for text, locale in quiet:
        parsed = fd.parse_date_commitment(text, locale=locale, today=TODAY)
        if parsed is not None:
            errors.append(f"false offer on ordinary speech: {text!r} → {parsed.when}")
    return errors


def check_confirm_copy() -> list[str]:
    """Stage 3 — the echo names the weekday and the month in words."""
    errors: list[str] = []
    import dates as fd

    commitment = fd.DateCommitment(when=date(2026, 12, 24), title="Kita Fest")
    de = fd.compose_date_confirm_text(commitment, locale="de")
    en = fd.compose_date_confirm_text(commitment, locale="en")
    if "Dezember" not in de or "Donnerstag" not in de:
        errors.append(f"de confirm missing weekday+month in words: {de!r}")
    if "December" not in en or "Thursday" not in en:
        errors.append(f"en confirm missing weekday+month in words: {en!r}")
    for text in (de, en):
        if "?" not in text:
            errors.append(f"confirm must ask, not tell: {text!r}")
    return errors


def check_keep_and_ownership() -> list[str]:
    """Stage 4 — the date lands in the root that owns the conversation."""
    errors: list[str] = []
    import dates as fd

    with tempfile.TemporaryDirectory() as tmp:
        private = Path(tmp) / "kermit"
        shared = Path(tmp) / "family"
        commitment = fd.parse_date_commitment(
            "Maëls Geburtstagsfeier ist am 24. Dezember", locale="de", today=TODAY
        )
        if commitment is None:
            return ["stage 4 could not parse its own fixture"]
        fd.apply_keep_date(private, commitment, captured_by="a member", locale="de")

        kept = fd.list_dates(private)
        if len(kept) != 1:
            errors.append(f"expected 1 kept date, got {len(kept)}")
        elif kept[0]["recurrence"] != "yearly":
            errors.append("a birthday should recur yearly")
        if fd.list_dates(shared):
            errors.append("keep leaked into a root that did not own the turn")
    return errors


def check_surface() -> list[str]:
    """Stage 5 — reminders come due at each lead day and fire once."""
    errors: list[str] = []
    import dates as fd

    with tempfile.TemporaryDirectory() as tmp:
        entry = fd.add_date(
            tmp,
            title="Kita Fest",
            when=(TODAY + timedelta(days=7)).isoformat(),
            lead_days=[7, 0],
        )
        due = fd.due_reminders(tmp, today=TODAY)
        if len(due) != 1:
            errors.append(f"lead-7 reminder not due: {due}")
        else:
            _, lead, occ = due[0]
            fd.mark_reminder_done(tmp, str(entry["id"]), lead, occ)
            if fd.due_reminders(tmp, today=TODAY):
                # due_reminders is not done-filtered by contract; the done-map
                # is what the heartbeat consults, so assert on that instead.
                key = fd.reminder_done_key(str(entry["id"]), lead, occ)
                if key not in fd.list_reminders_done(tmp):
                    errors.append("done-key not recorded after marking")
        # Lead 0 lands on the day itself, not before it.
        if not fd.due_reminders(tmp, today=TODAY + timedelta(days=7)):
            errors.append("lead-0 reminder missing on the day")
        if fd.due_reminders(tmp, today=TODAY + timedelta(days=3)):
            errors.append("reminder fired on a day with no lead")
    return errors


def check_read_back() -> list[str]:
    """Stage 6 — `!dates` answers in the member's language."""
    errors: list[str] = []
    import asyncio
    from unittest.mock import AsyncMock, patch

    import dates as fd
    import mage

    async def listing(tmp: str, locale: str) -> str:
        message = MagicMock()
        message.reply = AsyncMock()
        with patch.object(mage, "get_pd", return_value=tmp), patch.object(
            fd, "locale_for_practice_dir", return_value=locale
        ), patch.object(fd, "local_now", return_value=MagicMock(date=lambda: TODAY)):
            await fd.cmd_dates(message)
        return str(message.reply.await_args.args[0])

    for locale, month in (("de", "Dezember"), ("en", "December")):
        with tempfile.TemporaryDirectory() as tmp:
            fd.add_date(tmp, title="Kita Fest", when="2026-12-24", locale=locale)
            body = asyncio.run(listing(tmp, locale))
            if month not in body:
                errors.append(f"{locale} listing should name the month: {body!r}")
            if "Kita Fest" not in body:
                errors.append(f"{locale} listing lost the member's words: {body!r}")

    # And the ambient block the model reads stays machine-shaped (ISO).
    with tempfile.TemporaryDirectory() as tmp:
        fd.add_date(tmp, title="Kita Fest", when=(TODAY + timedelta(days=3)).isoformat())
        context = fd.render_upcoming_dates_context(tmp, today=TODAY)
        if (TODAY + timedelta(days=3)).isoformat() not in context:
            errors.append(f"ambient block missing the date: {context!r}")
    return errors


def check_typed_path() -> list[str]:
    """Stage 7 — `!date` accepts every form the river accepts."""
    errors: list[str] = []
    import dates as fd

    cases = [
        (["2026-12-24", "Kita", "Fest"], date(2026, 12, 24), "Kita Fest"),
        (["24.12.", "Kita", "Fest"], date(2026, 12, 24), "Kita Fest"),
        (["24.", "Dezember", "Kita", "Fest"], date(2026, 12, 24), "Kita Fest"),
        (["Samstag", "Kita", "Fest"], date(2026, 8, 8), "Kita Fest"),
        (["morgen", "Zahnarzt"], date(2026, 8, 7), "Zahnarzt"),
    ]
    for args, expected, title in cases:
        token, rest = fd.split_when_and_title(args, locale="de", today=TODAY)
        try:
            parsed = fd.parse_date_token(token, locale="de", today=TODAY)
        except fd.DateError as exc:
            errors.append(f"!date {' '.join(args)} → refused: {exc}")
            continue
        if parsed != expected:
            errors.append(f"!date {' '.join(args)} → {parsed}, expected {expected}")
        if " ".join(rest) != title:
            errors.append(f"!date {' '.join(args)} → title {' '.join(rest)!r}")
    return errors


def check_registration() -> list[str]:
    errors: list[str] = []
    from commands import DIRECT_COMMANDS

    for name in ("date", "dates"):
        if name not in DIRECT_COMMANDS:
            errors.append(f"DIRECT_COMMANDS missing {name}")
    return errors


def main() -> int:
    report = {
        "shake": "dates",
        # `status` is the contract scripts/shake_report.py reads; an artifact
        # carrying only per-stage detail parses as "unknown" and quietly
        # degrades the nightly gate to "incomplete".
        "status": "unknown",
        "today": TODAY.isoformat(),
        "offline": {},
        "live": {
            "skipped": True,
            "reason": "operator dogfood — say a date in the river, take the Keep",
        },
    }
    errs: list[str] = []
    for name, fn in (
        ("notice", check_notice),
        ("restraint", check_restraint),
        ("confirm", check_confirm_copy),
        ("keep", check_keep_and_ownership),
        ("surface", check_surface),
        ("read_back", check_read_back),
        ("typed", check_typed_path),
        ("registration", check_registration),
    ):
        e = fn()
        report["offline"][name] = {"ok": not e, "errors": e}
        errs.extend(e)

    report["status"] = "fail" if errs else "pass"
    TEST_RUNS.mkdir(parents=True, exist_ok=True)
    out = TEST_RUNS / "shake-dates-latest.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errs:
        print(f"FAIL: {len(errs)} error(s)", file=sys.stderr)
        return 1
    print("OK: dates journey shake")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
