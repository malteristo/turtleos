"""Per-practice-root dates registry + proactive reminder surfacing.

Mirrors ``home_plans.py``: versioned YAML under ``state/dates.yaml``,
locked/atomic writes. Reminders hook the hourly daily-note heartbeat
(INT-046 per-root iteration; done-keys keyed by entry/lead/occurrence).

Product speech: members / practitioners — never "user". Reminder copy is
care language (offers), never demands.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.atomic_io import atomic_write_text, file_lock
from helpers import local_now

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SCHEMA_VERSION = 1
REGISTRY_REL = "state/dates.yaml"
DEFAULT_LEAD_DAYS = [7, 0]
_MAX_TITLE = 120
_RECURRENCE = frozenset({"none", "yearly"})

# ISO, or German D.M. / D.M.YYYY (trailing dot optional on day.month.)
_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DE_FULL_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\.?$")
_DE_SHORT_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.?$")


class DateError(ValueError):
    """Capture refused — message is practitioner-safe."""


_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
_MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
_WEEKDAYS_EN = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _alt(words: Any) -> str:
    """Regex alternation, longest first so `September` beats `Sep`."""
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


# Name forms. These tables were rendering-only until 2026-08-06 — the parser
# could echo "Samstag" back at a member but could not read it.
_MONTH_FULL: dict[str, int] = {
    **{n.lower(): i for i, n in enumerate(_MONTHS_DE, 1)},
    **{n.lower(): i for i, n in enumerate(_MONTHS_EN, 1)},
    "maerz": 3,
}
_MONTH_SHORT: dict[str, int] = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "okt": 10, "oct": 10, "nov": 11,
    "dez": 12, "dec": 12,
}
_WEEKDAY_FULL: dict[str, int] = {
    **{n.lower(): i for i, n in enumerate(_WEEKDAYS_DE)},
    **{n.lower(): i for i, n in enumerate(_WEEKDAYS_EN)},
}
# Two-letter forms are typed-command only — "so", "do" and "mi" are ordinary
# words in a German river and would fire the conversational offer constantly.
_WEEKDAY_SHORT: dict[str, int] = {
    "mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
    "fri": 4, "sat": 5, "sun": 6,
}
_WEEKDAY_QUALIFIER = (
    "nächsten", "nächste", "nächster", "naechsten", "naechste",
    "kommenden", "kommende", "diesen", "next", "this", "on", "am",
)
_RELATIVE_OFFSETS: dict[str, int] = {
    "heute": 0, "today": 0,
    "morgen": 1, "tomorrow": 1,
    "übermorgen": 2, "uebermorgen": 2, "day after tomorrow": 2,
    "nächste woche": 7, "naechste woche": 7, "next week": 7,
}

_MONTHS_ALL_PAT = _alt({**_MONTH_FULL, **_MONTH_SHORT})
_MONTHS_FULL_PAT = _alt(_MONTH_FULL)
_WEEKDAYS_ALL_PAT = _alt({**_WEEKDAY_FULL, **_WEEKDAY_SHORT})
_WEEKDAYS_FULL_PAT = _alt(_WEEKDAY_FULL)
_QUALIFIER_PAT = _alt(_WEEKDAY_QUALIFIER)
_RELATIVE_PAT = _alt(_RELATIVE_OFFSETS)


def _name_form_pattern(months: str) -> str:
    """`24. Dezember [2026]` or `December 24[th][, 2026]`."""
    return (
        rf"(?:(?P<nd_day>\d{{1,2}})\.?\s+(?P<nd_mon>{months})\.?"
        rf"(?:\s+(?P<nd_year>\d{{4}}))?)"
        rf"|(?:(?P<nm_mon>{months})\.?\s+(?P<nm_day>\d{{1,2}})"
        rf"(?:st|nd|rd|th)?(?:,?\s+(?P<nm_year>\d{{4}}))?)"
    )


def _weekday_pattern(weekdays: str) -> str:
    return rf"(?:(?:{_QUALIFIER_PAT})\s+)?(?P<wd>{weekdays})"


_RELATIVE_FULL_PAT = (
    rf"(?:(?P<rel>{_RELATIVE_PAT})"
    rf"|in\s+(?P<rel_n>\d{{1,3}})\s+(?:tagen|tage|days))"
)

# The wrapping group is load-bearing: `A|B` + `$` anchors only B, which lets
# a name form swallow the first title word.
_NAME_TOKEN_RE = re.compile(r"(?:" + _name_form_pattern(_MONTHS_ALL_PAT) + r")$", re.I)
_WEEKDAY_TOKEN_RE = re.compile(r"(?:" + _weekday_pattern(_WEEKDAYS_ALL_PAT) + r")$", re.I)
_RELATIVE_TOKEN_RE = re.compile(r"(?:" + _RELATIVE_FULL_PAT + r")$", re.I)


def _roll_forward(year: int | None, month: int, day: int, base: date, *, locale: str) -> date:
    """Build the date; without an explicit year, take the next occurrence."""
    if year is not None:
        return _build_date(year, month, day, locale=locale)
    candidate = _build_date(base.year, month, day, locale=locale)
    if candidate < base:
        return _build_date(base.year + 1, month, day, locale=locale)
    return candidate


def _date_from_name_match(m: "re.Match[str]", base: date, *, locale: str) -> date:
    if m.group("nd_day"):
        day = int(m.group("nd_day"))
        month_word = (m.group("nd_mon") or "").lower()
        year = int(m.group("nd_year")) if m.group("nd_year") else None
    else:
        day = int(m.group("nm_day"))
        month_word = (m.group("nm_mon") or "").lower()
        year = int(m.group("nm_year")) if m.group("nm_year") else None
    month = _MONTH_FULL.get(month_word) or _MONTH_SHORT.get(month_word)
    if month is None:  # pragma: no cover — the pattern is built from the tables
        raise DateError(f"Unknown month `{month_word}`.")
    return _roll_forward(year, month, day, base, locale=locale)


def _date_from_weekday_match(m: "re.Match[str]", base: date) -> date:
    word = (m.group("wd") or "").lower()
    target = _WEEKDAY_FULL.get(word)
    if target is None:
        target = _WEEKDAY_SHORT[word]
    # Strictly future: "Samstag" said on a Saturday means the one coming.
    ahead = (target - base.weekday()) % 7 or 7
    return base + timedelta(days=ahead)


def _date_from_relative_match(m: "re.Match[str]", base: date) -> date:
    if m.group("rel_n"):
        return base + timedelta(days=int(m.group("rel_n")))
    return base + timedelta(days=_RELATIVE_OFFSETS[(m.group("rel") or "").lower()])


def human_date(d: date, *, locale: str = "en", with_weekday: bool = True) -> str:
    """Render a date in words so day/month order can't be misread.

    The month name is the dd.mm-vs-mm.dd disambiguator: a member who meant
    September sees "Dezember" in the echo and corrects before confirming.
    """
    if locale == "de":
        core = f"{d.day}. {_MONTHS_DE[d.month - 1]} {d.year}"
        return f"{_WEEKDAYS_DE[d.weekday()]}, {core}" if with_weekday else core
    core = f"{_MONTHS_EN[d.month - 1]} {d.day}, {d.year}"
    return f"{_WEEKDAYS_EN[d.weekday()]}, {core}" if with_weekday else core


def _build_date(year: int, month: int, day: int, *, locale: str = "en") -> date:
    """Construct a date; on impossible values, refuse with a helpful hint.

    A month slot > 12 with a plausible day slot is the mm.dd-typed-as-dd.mm
    signature — suggest the swapped reading instead of a bare error.
    """
    try:
        return date(year, month, day)
    except ValueError:
        if month > 12 and 1 <= day <= 12:
            if locale == "de":
                raise DateError(
                    f"`{day}.{month}.` gibt es nicht — meintest du "
                    f"**{month}.{day}.** (Tag.Monat)?"
                ) from None
            raise DateError(
                f"`{day}.{month}.` isn't a real date — did you mean "
                f"**{month}.{day}.** (day.month)?"
            ) from None
        if locale == "de":
            raise DateError(
                f"`{day}.{month}.{year}` gibt es nicht — bitte als Tag.Monat "
                "(z. B. `24.12.`) oder ISO (`2026-12-24`)."
            ) from None
        raise DateError(
            f"`{day}.{month}.{year}` isn't a real date — use day.month "
            "(`24.12.`) or ISO (`2026-12-24`)."
        ) from None


@dataclass(frozen=True)
class DateCommitment:
    when: date
    title: str
    recurrence: str = "none"
    lead_days: list[int] | None = None
    birth_year: int | None = None


def registry_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / REGISTRY_REL


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_registry() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "entries": [], "reminders_done": {}}


def _load(practice_dir: str | Path) -> dict[str, Any]:
    path = registry_path(practice_dir)
    if not path.exists() or yaml is None:
        return _empty_registry()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_registry()
    if not isinstance(loaded, dict):
        return _empty_registry()
    if not isinstance(loaded.get("entries"), list):
        loaded["entries"] = []
    if not isinstance(loaded.get("reminders_done"), dict):
        loaded["reminders_done"] = {}
    loaded.setdefault("version", SCHEMA_VERSION)
    return loaded


def _save(practice_dir: str | Path, data: dict[str, Any], *, locked: bool = False) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write dates.yaml")
    path = registry_path(practice_dir)
    payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    atomic_write_text(path, payload, lock=not locked)


def list_dates(practice_dir: str | Path) -> list[dict[str, Any]]:
    return list(_load(practice_dir).get("entries") or [])


def get_by_id(practice_dir: str | Path, entry_id: str) -> dict[str, Any] | None:
    for entry in list_dates(practice_dir):
        if str(entry.get("id") or "") == str(entry_id):
            return dict(entry)
    return None


def list_reminders_done(practice_dir: str | Path) -> dict[str, str]:
    data = _load(practice_dir)
    done = data.get("reminders_done") or {}
    return {str(k): str(v) for k, v in done.items()}


def reminder_done_key(entry_id: str, lead_day: int, occurrence: date) -> str:
    return f"{entry_id}:{int(lead_day)}:{occurrence.isoformat()}"


def parse_date_token(
    when: str,
    *,
    locale: str = "en",
    today: date | None = None,
) -> date:
    """Parse a capture token into a calendar date.

    Supports ISO ``YYYY-MM-DD`` always; ``D.M.`` / ``D.M.YYYY`` when locale
    is ``de`` (or the token clearly matches German day.month form).
    """
    raw = (when or "").strip()
    if not raw:
        raise DateError("Need a date — try `!date 2026-12-24 title` or `!date 24.12. title`.")

    loc = (locale or "en").strip().lower()

    m = _ISO_RE.match(raw)
    if m:
        return _build_date(
            int(m.group(1)), int(m.group(2)), int(m.group(3)), locale=loc
        )

    de_shape = bool(_DE_FULL_RE.match(raw) or _DE_SHORT_RE.match(raw))
    if loc == "de" or de_shape:
        m_full = _DE_FULL_RE.match(raw)
        if m_full:
            day, month, year = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
            return _build_date(year, month, day, locale=loc)
        m_short = _DE_SHORT_RE.match(raw)
        if m_short:
            day, month = int(m_short.group(1)), int(m_short.group(2))
            base = today or local_now().date()
            try:
                candidate = date(base.year, month, day)
            except ValueError:
                # 29.2. in a non-leap year rolls to the next valid year;
                # anything else gets the helpful refusal.
                if month == 2 and day == 29:
                    for offset in (1, 2, 3, 4):
                        try:
                            return date(base.year + offset, month, day)
                        except ValueError:
                            continue
                return _build_date(base.year, month, day, locale=loc)
            if candidate < base:
                try:
                    candidate = date(base.year + 1, month, day)
                except ValueError:
                    return _build_date(base.year + 1, month, day, locale=loc)
            return candidate

    # Name forms, weekdays and relative words — how members actually write
    # a date when they are not filling in a form.
    base = today or local_now().date()
    m_name = _NAME_TOKEN_RE.match(raw)
    if m_name:
        return _date_from_name_match(m_name, base, locale=loc)
    m_weekday = _WEEKDAY_TOKEN_RE.match(raw)
    if m_weekday:
        return _date_from_weekday_match(m_weekday, base)
    m_relative = _RELATIVE_TOKEN_RE.match(raw)
    if m_relative:
        return _date_from_relative_match(m_relative, base)

    raise DateError(
        f"Couldn't parse date `{raw}`. Use ISO (`2026-12-24`), day.month "
        "(`24.12.`), a month name (`24. Dezember`), a weekday (`Samstag`) "
        "or `morgen`."
    )


def next_occurrence(entry: dict[str, Any], today: date | None = None) -> date:
    """Next calendar occurrence for an entry (yearly rolls forward)."""
    base = today or local_now().date()
    stored = date.fromisoformat(str(entry.get("date") or ""))
    recurrence = (entry.get("recurrence") or "none").strip().lower()
    if recurrence != "yearly":
        return stored
    candidate = date(base.year, stored.month, stored.day)
    if candidate < base:
        candidate = date(base.year + 1, stored.month, stored.day)
    return candidate


def _normalize_lead_days(lead_days: list[int] | None) -> list[int]:
    if not lead_days:
        return list(DEFAULT_LEAD_DAYS)
    cleaned: list[int] = []
    seen: set[int] = set()
    for raw in lead_days:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n < 0 or n in seen:
            continue
        seen.add(n)
        cleaned.append(n)
    return cleaned or list(DEFAULT_LEAD_DAYS)


def add_date(
    practice_dir: str | Path,
    *,
    title: str,
    when: str | date,
    recurrence: str = "none",
    lead_days: list[int] | None = None,
    captured_by: str | None = None,
    notes: str | None = None,
    birth_year: int | None = None,
    locale: str = "en",
    today: date | None = None,
) -> dict[str, Any]:
    """Append a date entry. Returns the stored dict."""
    clean_title = " ".join((title or "").split())[:_MAX_TITLE]
    if not clean_title:
        raise DateError("Need a title for the date.")

    if isinstance(when, date):
        when_date = when
    else:
        when_date = parse_date_token(str(when), locale=locale, today=today)

    rec = (recurrence or "none").strip().lower()
    if rec not in _RECURRENCE:
        raise DateError("Recurrence must be `none` or `yearly`.")

    leads = _normalize_lead_days(lead_days)
    now = _now_iso()
    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "title": clean_title,
        "date": when_date.isoformat(),
        "recurrence": rec,
        "lead_days": leads,
        "captured_by": (captured_by or "").strip() or None,
        "captured_at": now,
        "notes": (notes or "").strip() or None,
    }
    if birth_year is not None:
        try:
            by = int(birth_year)
        except (TypeError, ValueError) as exc:
            raise DateError("Birth year must be a number.") from exc
        if by < 1900 or by > when_date.year:
            raise DateError("Birth year looks off.")
        entry["birth_year"] = by
        # Yearly birthdays store the birth date for age math.
        if rec == "yearly" and when_date.year == by:
            pass
        elif rec == "yearly":
            # Normalize stored date to month/day with birth year when provided.
            entry["date"] = date(by, when_date.month, when_date.day).isoformat()

    # Drop null optional fields for a lean YAML surface.
    if entry["captured_by"] is None:
        del entry["captured_by"]
    if entry["notes"] is None:
        del entry["notes"]

    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        data.setdefault("entries", []).append(entry)
        data["version"] = SCHEMA_VERSION
        _save(practice_dir, data, locked=True)
    return dict(entry)


def remove_date(practice_dir: str | Path, entry_id: str) -> dict[str, Any] | None:
    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        kept: list[dict[str, Any]] = []
        removed: dict[str, Any] | None = None
        for entry in data.get("entries") or []:
            if str(entry.get("id") or "") == str(entry_id):
                removed = dict(entry)
            else:
                kept.append(entry)
        if removed is None:
            return None
        data["entries"] = kept
        _save(practice_dir, data, locked=True)
        return removed


def mark_reminder_done(
    practice_dir: str | Path,
    entry_id: str,
    lead_day: int,
    occurrence: date,
) -> str:
    key = reminder_done_key(entry_id, lead_day, occurrence)
    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        done = data.setdefault("reminders_done", {})
        done[key] = local_now().date().isoformat()
        _save(practice_dir, data, locked=True)
    return key


def due_reminders(
    practice_dir: str | Path,
    today: date | None = None,
) -> list[tuple[dict[str, Any], int, date]]:
    """Entries whose lead day lands on ``today`` (not yet filtered by done-map)."""
    base = today or local_now().date()
    out: list[tuple[dict[str, Any], int, date]] = []
    for entry in list_dates(practice_dir):
        try:
            occ = next_occurrence(entry, today=base)
        except ValueError:
            continue
        leads = _normalize_lead_days(entry.get("lead_days"))
        for lead in leads:
            if occ - timedelta(days=int(lead)) == base:
                out.append((dict(entry), int(lead), occ))
    return out


def locale_for_practice_dir(practice_dir: str | Path) -> str:
    """Honor registry locale on mage/space; default ``en``."""
    from mage import _MAGE_REGISTRY, registry_key_for_practice_dir

    key, kind = registry_key_for_practice_dir(practice_dir)
    if not key or not kind:
        return "en"
    section = "mages" if kind == "mage" else "spaces"
    entry = (_MAGE_REGISTRY.get(section) or {}).get(key) or {}
    locale = str(entry.get("locale") or "en").strip().lower()
    return locale if locale in ("de", "en") else "en"


def owning_channel_id_for_practice_dir(practice_dir: str | Path) -> int | None:
    """Channel that owns this root for date reminders.

    Mage roots → personal river / hosted-river.
    Space roots → shared-river parent (unlike daily notes, which fail closed
    for spaces — family dates must surface in the family room).
    """
    from mage import (
        _MAGE_REGISTRY,
        _resolve_dialogue_channel_id,
        registry_key_for_practice_dir,
        river_channel_id_for_mage_key,
    )

    if not (_MAGE_REGISTRY.get("channels") or {}):
        return _resolve_dialogue_channel_id()

    key, kind = registry_key_for_practice_dir(practice_dir)
    if key is None:
        return None
    if kind == "mage":
        return river_channel_id_for_mage_key(key)

    # space → shared-river bound to this space key
    for ch_id_str, entry in (_MAGE_REGISTRY.get("channels") or {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("archived") or entry.get("orphaned"):
            continue
        if entry.get("mage") != key:
            continue
        if entry.get("type") != "shared-river":
            continue
        try:
            return int(ch_id_str)
        except (TypeError, ValueError):
            continue
    return None


def _lead_phrase(lead_day: int, *, locale: str) -> str:
    if locale == "de":
        if lead_day == 0:
            return "heute"
        if lead_day == 1:
            return "morgen"
        if lead_day == 7:
            return "in einer Woche"
        if lead_day == 14:
            return "in zwei Wochen"
        return f"in {lead_day} Tagen"
    if lead_day == 0:
        return "today"
    if lead_day == 1:
        return "tomorrow"
    if lead_day == 7:
        return "in a week"
    if lead_day == 14:
        return "in two weeks"
    return f"in {lead_day} days"


def _age_phrase(entry: dict[str, Any], occurrence: date, *, locale: str) -> str:
    birth_year = entry.get("birth_year")
    if birth_year is None:
        return ""
    try:
        age = occurrence.year - int(birth_year)
    except (TypeError, ValueError):
        return ""
    if age < 0 or age > 120:
        return ""
    if locale == "de":
        return f" — wird {age}"
    return f" — turns {age}"


def compose_reminder_text(
    entry: dict[str, Any],
    *,
    lead_day: int,
    occurrence: date,
    locale: str = "en",
) -> str:
    """Care-language reminder — offer, not demand."""
    title = str(entry.get("title") or "a date")
    when = _lead_phrase(lead_day, locale=locale)
    age = _age_phrase(entry, occurrence, locale=locale)
    occ_label = human_date(occurrence, locale=locale)

    if locale == "de":
        if lead_day == 0:
            return (
                f"**{title}** ist heute ({occ_label}){age}. "
                f"Nur als Erinnerung — nichts muss erledigt werden."
            )
        return (
            f"**{title}** ist {when} ({occ_label}){age} — "
            f"die Vorlaufzeit, die ihr festgehalten habt."
        )
    if lead_day == 0:
        return (
            f"**{title}** is today ({occ_label}){age}. "
            f"Just a heads-up — nothing required."
        )
    return (
        f"**{title}** is {when} ({occ_label}){age} — "
        f"the lead time you asked for."
    )


def render_upcoming_dates_context(
    practice_dir: str | Path,
    *,
    within_days: int = 30,
    today: date | None = None,
) -> str:
    """Compact block for daily-note / attunement ambient awareness."""
    base = today or local_now().date()
    horizon = base + timedelta(days=max(0, within_days))
    rows: list[tuple[date, str]] = []
    for entry in list_dates(practice_dir):
        try:
            occ = next_occurrence(entry, today=base)
        except ValueError:
            continue
        if base <= occ <= horizon:
            rows.append((occ, str(entry.get("title") or "date")))
    if not rows:
        return ""
    rows.sort(key=lambda r: r[0])
    lines = ["[Upcoming dates — shell-injected]"]
    for occ, title in rows[:8]:
        lines.append(f"- {occ.isoformat()}: {title}")
    lines.append("")
    return "\n".join(lines)


async def post_date_reminder(
    channel_id: int,
    entry: dict[str, Any],
    lead_day: int,
    occurrence: date,
    *,
    locale: str = "en",
) -> None:
    """Post one reminder as a compact river act in the owning channel."""
    from sessions import post_command_act

    body = compose_reminder_text(
        entry, lead_day=lead_day, occurrence=occurrence, locale=locale
    )
    await post_command_act(
        channel_id,
        title="Date reminder",
        body=body,
        emoji="📅",
    )


async def run_scheduled_date_reminders(
    practice_dirs: list[Path | str] | None = None,
) -> int:
    """Hourly heartbeat path: surface due reminders once per done-key.

    INT-046: iterates roots explicitly — never ambient ``get_pd()``.
    Returns the number of reminders posted.
    """
    from mage import list_registered_practice_dirs

    roots = (
        [Path(p) for p in practice_dirs]
        if practice_dirs is not None
        else [Path(p) for p in list_registered_practice_dirs()]
    )
    today = local_now().date()
    posted = 0
    for root in roots:
        channel_id = owning_channel_id_for_practice_dir(root)
        if not channel_id:
            continue
        locale = locale_for_practice_dir(root)
        done = list_reminders_done(root)
        for entry, lead_day, occ in due_reminders(root, today=today):
            key = reminder_done_key(str(entry.get("id") or ""), lead_day, occ)
            if key in done:
                continue
            try:
                await post_date_reminder(
                    channel_id, entry, lead_day, occ, locale=locale
                )
            except Exception as exc:
                print(
                    f"Date reminder post failed for {root}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            mark_reminder_done(root, str(entry["id"]), lead_day, occ)
            posted += 1
    return posted


# ─── Conversational capture (Keep-style confirm) ─────────────────


_DATE_HINT_RE = re.compile(
    r"(?P<de>\b\d{1,2}\.\d{1,2}(?:\.\d{4})?\.?)"
    r"|(?P<iso>\b\d{4}-\d{2}-\d{2}\b)",
    re.IGNORECASE,
)
# German compounds the word: Geburtstagsfeier, Geburtstagsparty.
_BIRTHDAY_RE = re.compile(r"\b(birthdays?|geburtstag\w*|turns?\s+\d+)\b", re.IGNORECASE)

# Tier 1 fires on its own: a member who writes "24. Dezember" has already
# been specific. Tier 2 — a weekday, "morgen" — is ordinary river speech and
# only counts as a commitment when something worth keeping is named with it.
_NAME_HINT_RE = re.compile(r"\b(?:" + _name_form_pattern(_MONTHS_FULL_PAT) + r")", re.I)
_WEEKDAY_HINT_RE = re.compile(r"\b(?:" + _weekday_pattern(_WEEKDAYS_FULL_PAT) + r")\b", re.I)
_RELATIVE_HINT_RE = re.compile(r"\b(?:" + _RELATIVE_FULL_PAT + r")\b", re.I)
_COMMITMENT_CUE_RE = re.compile(
    r"\b("
    r"geburtstag\w*|birthday|jahrestag|anniversary|hochzeit|wedding|"
    r"termin\w*|appointment|arzt\w*|zahnarzt\w*|doctor|dentist|"
    r"elternabend|kita|schule|school|"
    r"fest\w*|feier\w*|party|"
    r"erinner\w*|remind|merk(?:e|en|st)?|keep|denk dran|don'?t forget"
    r")\b",
    re.IGNORECASE,
)


def _find_date_phrase(
    raw: str, *, locale: str, today: date | None
) -> tuple[date, int, int] | None:
    """Earliest tier-1 phrase; else earliest tier-2 phrase behind a cue."""
    base = today or local_now().date()

    tier1: list[tuple[int, int, date]] = []
    m_num = _DATE_HINT_RE.search(raw)
    if m_num:
        token = m_num.group("de") or m_num.group("iso")
        try:
            tier1.append(
                (m_num.start(), m_num.end(), parse_date_token(token, locale=locale, today=base))
            )
        except DateError:
            pass
    m_name = _NAME_HINT_RE.search(raw)
    if m_name:
        try:
            tier1.append(
                (m_name.start(), m_name.end(), _date_from_name_match(m_name, base, locale=locale))
            )
        except DateError:
            pass
    if tier1:
        start, end, when = min(tier1, key=lambda row: row[0])
        return when, start, end

    if not _COMMITMENT_CUE_RE.search(raw):
        return None

    tier2: list[tuple[int, int, date]] = []
    m_weekday = _WEEKDAY_HINT_RE.search(raw)
    if m_weekday:
        tier2.append((m_weekday.start(), m_weekday.end(), _date_from_weekday_match(m_weekday, base)))
    m_relative = _RELATIVE_HINT_RE.search(raw)
    if m_relative:
        tier2.append(
            (m_relative.start(), m_relative.end(), _date_from_relative_match(m_relative, base))
        )
    if not tier2:
        return None
    start, end, when = min(tier2, key=lambda row: row[0])
    return when, start, end


def parse_date_commitment(
    text: str,
    *,
    locale: str = "en",
    today: date | None = None,
) -> DateCommitment | None:
    """Heuristic extract of a date-worthy commitment from chat text."""
    raw = (text or "").strip()
    if not raw or len(raw) < 8:
        return None
    found = _find_date_phrase(raw, locale=locale, today=today)
    if found is None:
        return None
    when, start, end = found

    # Title: cut the date phrase out by span, then strip light filler.
    title = raw[:start] + " " + raw[end:]
    for filler in (
        "bitte erinnern",
        "remind me",
        "remember",
        "am ",
        "on ",
        "ist ",
        "is ",
        "—",
        "-",
    ):
        title = re.sub(re.escape(filler), " ", title, flags=re.IGNORECASE)
    title = " ".join(title.split()).strip(" .,;:")
    if len(title) < 2:
        title = "important date"
    title = title[:_MAX_TITLE]

    recurrence = "yearly" if _BIRTHDAY_RE.search(raw) else "none"
    return DateCommitment(when=when, title=title, recurrence=recurrence)


def compose_date_confirm_text(commitment: DateCommitment, *, locale: str = "en") -> str:
    # Weekday + month name — the echo that catches a dd.mm/mm.dd misread.
    when = human_date(commitment.when, locale=locale)
    if locale == "de":
        return (
            f"Soll ich **{commitment.title}** am **{when}** merken?\n\n"
            "Ich erinnere rechtzeitig — nichts weiter nötig."
        )
    return (
        f"Keep **{commitment.title}** on **{when}**?\n\n"
        "I'll surface it at the lead times — nothing else needed."
    )


def address_for_capture(user=None) -> str | None:
    """Registry address for the capturing member, if resolvable."""
    if user is None:
        return None
    try:
        from continuity_confirm import address_for_user

        return address_for_user(user)
    except Exception:
        return None


def apply_keep_date(
    practice_dir: str | Path,
    commitment: DateCommitment,
    *,
    captured_by: str | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    return add_date(
        practice_dir,
        title=commitment.title,
        when=commitment.when,
        recurrence=commitment.recurrence,
        lead_days=commitment.lead_days,
        captured_by=captured_by,
        birth_year=commitment.birth_year,
        locale=locale,
    )


def _record_offer_accepted(practice_dir: str | Path, channel_id: int | None) -> None:
    """A date-keep offer was taken. Never raises into an interaction.

    Took an `event` argument until 2026-08-14, when the decline buttons went and
    `accepted` became the only outcome anything clicks. The variable also made
    the kind invisible to the scan that checks every claimed take rate is really
    recorded — an indirection with no remaining caller is worth less than a
    literal a guard can read.
    """
    try:
        from offer_ledger import record

        record(practice_dir, kind="date_keep", event="accepted", channel_id=channel_id)
    except Exception:
        pass


try:
    import discord
except ImportError:  # pragma: no cover
    discord = None  # type: ignore


if discord is not None:

    class DateKeepConfirmView(discord.ui.View):
        """Keep this date — timeout leaves the registry unchanged."""

        def __init__(
            self,
            channel_id: int,
            commitment: DateCommitment,
            practice_dir: str,
            *,
            locale: str = "en",
        ):
            super().__init__(timeout=180)
            self._channel_id = channel_id
            self._commitment = commitment
            self._practice_dir = practice_dir
            self._locale = locale
            self._resolved = False

            from runtime.offers import accept_action

            keep_btn = discord.ui.Button(
                label=accept_action("date_keep", locale=locale or "en").label,
                custom_id=f"dates:keep:{channel_id}",
                style=discord.ButtonStyle.primary,
            )
            keep_btn.callback = self._on_keep
            self.add_item(keep_btn)

        async def on_timeout(self) -> None:
            self._resolved = True

        async def _on_keep(self, interaction: discord.Interaction) -> None:
            if self._resolved:
                await interaction.response.send_message(
                    "Already answered.", ephemeral=True
                )
                return
            if interaction.channel and interaction.channel.id != self._channel_id:
                await interaction.response.send_message("Wrong thread.", ephemeral=True)
                return
            self._resolved = True
            entry = apply_keep_date(
                self._practice_dir,
                self._commitment,
                captured_by=address_for_capture(interaction.user),
                locale=self._locale,
            )
            _record_offer_accepted(self._practice_dir, self._channel_id)
            self.stop()
            kept_when = human_date(
                date.fromisoformat(entry["date"]), locale=self._locale
            )
            body = (
                f"Kept: **{entry['title']}** on **{kept_when}** — "
                "I'll surface it at the lead times."
            )
            if self._locale == "de":
                body = (
                    f"Gemerkt: **{entry['title']}** am **{kept_when}** — "
                    "ich erinnere zur Vorlaufzeit."
                )
            await interaction.response.edit_message(content=body, view=None)



async def offer_date_keep(
    message,
    commitment: DateCommitment,
    *,
    practice_dir: str | Path | None = None,
    locale: str | None = None,
) -> bool:
    """Post the Keep-this-date offer. Returns True when offered."""
    from mage import get_pd

    pd = str(practice_dir or get_pd())
    loc = locale or locale_for_practice_dir(pd)
    text = compose_date_confirm_text(commitment, locale=loc)
    if discord is None:
        return False
    view = DateKeepConfirmView(message.channel.id, commitment, pd, locale=loc)
    await message.reply(text, view=view, mention_author=False)
    return True


# ─── Typed commands ──────────────────────────────────────────────


def _usage_date() -> str:
    return (
        "Usage: `!date <when> <what>`\n"
        "Examples: `!date 2026-12-24 kita fest` · `!date 24.12. kita fest` · "
        "`!date 24. Dezember kita fest` · `!date Samstag kita fest`\n"
        "Optional yearly birthday: `!date 15.03.2019 a member birthday` "
        "(birth year enables age on reminders).\n"
        "List upcoming: `!dates`"
    )


# `24. Dezember` and `next Saturday` are two and three tokens; the date is
# whatever longest leading run parses, so long as a title survives it.
_MAX_WHEN_TOKENS = 3


def _token_carries_year(token: str) -> bool:
    """True when the member wrote an explicit year, in any accepted form."""
    raw = (token or "").strip()
    if _ISO_RE.match(raw) or _DE_FULL_RE.match(raw):
        return True
    m = _NAME_TOKEN_RE.match(raw)
    return bool(m and (m.group("nd_year") or m.group("nm_year")))


def split_when_and_title(
    args: list[str], *, locale: str = "en", today: date | None = None
) -> tuple[str, list[str]]:
    """Split `!date` args into the when-token(s) and the remaining title."""
    limit = min(_MAX_WHEN_TOKENS, max(1, len(args) - 1))
    for count in range(limit, 1, -1):
        token = " ".join(args[:count])
        try:
            parse_date_token(token, locale=locale, today=today)
        except DateError:
            continue
        return token, list(args[count:])
    return args[0], list(args[1:])


async def cmd_date(message, args: list[str]) -> str:
    """`!date <when> <what>` — capture into this root's dates registry."""
    from mage import get_pd

    if len(args) < 2:
        await message.reply(_usage_date(), mention_author=False)
        return "Usage: !date <when> <what>"

    pd_locale_today = local_now().date()
    when_token, title_parts = split_when_and_title(
        args, locale="de", today=pd_locale_today
    )
    if not title_parts:
        await message.reply(_usage_date(), mention_author=False)
        return "Usage: !date <when> <what>"
    birth_year: int | None = None
    recurrence = "none"

    # A birthday recurs; a birth year in the token also buys "turns N" on the
    # reminder. Year detection is by shape, so `15. März 2019` counts the same
    # as `15.03.2019` — anything the parser accepts, this sees.
    if _BIRTHDAY_RE.search(" ".join(title_parts)):
        recurrence = "yearly"
        try:
            parsed = parse_date_token(when_token, locale="de", today=pd_locale_today)
            if _token_carries_year(when_token):
                birth_year = parsed.year
        except DateError:
            pass

    pd = get_pd()
    locale = locale_for_practice_dir(pd)
    title = " ".join(title_parts).strip()
    try:
        entry = add_date(
            pd,
            title=title,
            when=when_token,
            recurrence=recurrence,
            birth_year=birth_year,
            captured_by=address_for_capture(getattr(message, "author", None)),
            locale=locale,
            today=local_now().date(),
        )
    except DateError as exc:
        await message.reply(str(exc), mention_author=False)
        return f"Date capture refused: {exc}"

    leads = ", ".join(str(d) for d in entry["lead_days"])
    kept_when = human_date(date.fromisoformat(entry["date"]), locale=locale)
    if locale == "de":
        body = (
            f"Gemerkt: **{entry['title']}** am **{kept_when}** "
            f"(Erinnerung {leads} Tag(e) vorher)."
        )
    else:
        body = (
            f"Kept **{entry['title']}** on **{kept_when}** "
            f"(reminders at {leads} day(s) before)."
        )
    await message.reply(body, mention_author=False)
    return f"Date kept: {entry['title']} on {entry['date']}"


async def cmd_dates(message, args: list[str] | None = None) -> str:
    """`!dates` — list upcoming dates for this practice root."""
    from mage import get_pd

    pd = get_pd()
    locale = locale_for_practice_dir(pd)
    today = local_now().date()
    rows: list[tuple[date, dict[str, Any]]] = []
    for entry in list_dates(pd):
        try:
            occ = next_occurrence(entry, today=today)
        except ValueError:
            continue
        if occ >= today:
            rows.append((occ, entry))
    rows.sort(key=lambda r: r[0])

    if not rows:
        body = (
            "Noch keine Termine. Mit `!date <wann> <was>` festhalten."
            if locale == "de"
            else "No upcoming dates yet. Capture one with `!date <when> <what>`."
        )
        await message.reply(body, mention_author=False)
        return "No upcoming dates"

    lines = ["**Kommende Termine**" if locale == "de" else "**Upcoming dates**"]
    for occ, entry in rows[:20]:
        title = entry.get("title") or "date"
        leads = entry.get("lead_days") or DEFAULT_LEAD_DAYS
        age = ""
        if entry.get("birth_year") is not None:
            try:
                years = occ.year - int(entry["birth_year"])
                age = f" (wird {years})" if locale == "de" else f" (turns {years})"
            except (TypeError, ValueError):
                age = ""
        occ_label = human_date(occ, locale=locale, with_weekday=False)
        lines.append(
            f"• **{occ_label}** — {title}{age} "
            f"(lead: {', '.join(str(d) for d in leads)})"
        )
    body = "\n".join(lines)
    await message.reply(body, mention_author=False)
    return f"Listed {len(rows)} upcoming date(s)"
