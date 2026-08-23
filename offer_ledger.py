"""Append-only record of contextual offers and what became of them.

The question this exists to answer is not "does the writer work" but **what
fraction of real events reach the write path** — the check that separates a
feature nobody needed from a feature nobody was ever asked about.

It was written after the dates capture shipped on 2026-08-04, ran for two days
across five rivers, and produced zero keeps. The registry said zero, and zero
is what a feature nobody wanted looks like *and* what a feature that never
fired looks like. Only the offer count tells them apart — and the offer was a
``print()`` to a log that rotates.

Events are ``offered`` / ``accepted`` / ``declined`` / ``suppressed``. The
interesting number is usually none of them: **offers minus accepted** is how
many times a member was asked and did not take it, which is the shape of an
offer that misread the moment.

``declined`` is **historical**. Every decline button was removed on 2026-08-14 on
the operator's principle that ignoring an offer should be enough — *"No action
needed to decline."* The event stays readable so old rows still parse, and
nothing writes it. The measurement cost is real and worth naming: a click
distinguished *saw it and said no* from *never saw it*, and no surface reports
that difference now. It was never much of a distinction to lose — the button
manufactured the very event this ledger exists to infer, so ``declined`` counted
how often someone bothered to dismiss a thing, not how often they wanted it.

The honest replacement is a message-sequence read — an offer the practitioner
scrolled past while continuing to talk is *ignored*, one that expired with no
further message is *unseen*. It is not built, because nothing persists
per-channel message timestamps where the nightly report can reach them, and an
inference nobody can validate is the kind of instrument this codebase keeps
learning not to trust. One number that means exactly what it says beats two
where one is invented.

``suppressed`` is a gate declining to speak — the register check holding a
working-plan offer back from a conversation about grief. It is counted because
a gate whose effect is only visible in a rotating log is the defect this file
was written to fix.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from runtime.offers import counted_kinds

LEDGER_REL = "chronicle/offers.jsonl"

EVENTS = ("offered", "accepted", "declined", "suppressed")

# Every offer kind the runtime can emit. A kind listed here with zero offers
# renders as "never fired"; a kind *missing* here renders as nothing at all —
# so the list has to be complete or the instrument is blind in exactly the
# direction it was built to see. It was not: `turtle_save` / `turtle_checkpoint`
# were absent while sitting ahead of `save` / `checkpoint` in the turn handler,
# and they are the two kinds that have never fired in eight weeks of logs.
#
# So the list is no longer kept here. `runtime/offers.py` declares every offer
# beside its label, and a kind is counted or explicitly explained as uncounted —
# which means adding an offer surface without deciding whether it is measured is
# no longer possible by omission.
KINDS = counted_kinds()

# Kinds whose acceptance actually reaches the ledger. The rest are accepted by
# running a River **command** (`!save`, `!checkpoint`) rather than by a button
# callback, and a command can be typed with no offer in play — so recording the
# accept means matching the command against a pending offer, which is not built.
#
# This has to be declared, because a take rate of 0% on an uninstrumented kind
# reads exactly like rejection, and this file exists to stop precisely that
# confusion in the other direction. Removing the decline buttons made it sharper:
# non-acceptance is now `offered - accepted`, so every accept the ledger cannot
# see becomes a member who looks like they said nothing.
ACCEPT_INSTRUMENTED = frozenset({"date_keep", "home_plan", "link_read", "themes_keep"})


def ledger_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / LEDGER_REL


def root_for_channel(channel_id: int | str | None) -> str | None:
    """Owning root for a channel, or None when the channel is not registered.

    Deliberately strict — no fallback to the primary root. The permissive
    resolver exists for dialogue, where guessing beats dropping a member's
    turn; here a guess writes a fixture channel's offer into a real
    practitioner's ledger. Verified: the unit suite did exactly that on its
    first live run, filing `channel_id: 99` against the operator's root.

    Strict is not the same as literal, and conflating the two is what made this
    ledger record nothing for eight days. Every contextual offer fires inside an
    **eddy**, and the registry holds parent channels only — so the literal
    lookup returned None for all of them while the report printed "no data yet".
    `resolve_registry_channel_id` walks a thread to its parent and returns the id
    unchanged when it cannot, so an unregistered fixture channel still resolves
    to nothing and the guard above keeps its teeth.
    """
    if channel_id is None:
        return None
    try:
        from mage import _get_channel_mage, _MAGE_REGISTRY, resolve_registry_channel_id

        try:
            lookup_id: int | str = resolve_registry_channel_id(channel_id)
        except (TypeError, ValueError):
            lookup_id = channel_id

        key = _get_channel_mage(lookup_id)
        if not key:
            return None
        for section in ("mages", "spaces"):
            entry = (_MAGE_REGISTRY.get(section) or {}).get(key)
            if isinstance(entry, dict) and entry.get("practice_dir"):
                return os.path.expanduser(str(entry["practice_dir"]))
    except Exception:
        return None
    return None


def record(
    practice_dir: str | Path,
    *,
    kind: str,
    event: str,
    channel_id: int | str | None = None,
    detail: str | None = None,
) -> None:
    """Append one offer event. Never raises into a dialogue turn."""
    if event not in EVENTS:
        return
    try:
        path = ledger_path(practice_dir)
        os.makedirs(path.parent, exist_ok=True)
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": str(kind),
            "event": event,
        }
        if channel_id is not None:
            row["channel_id"] = str(channel_id)
        if detail:
            row["detail"] = str(detail)[:200]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Instrumentation must never be the reason a member's turn fails.
        return


def record_for_channel(
    channel_id: int | str | None,
    *,
    kind: str,
    event: str,
    detail: str | None = None,
) -> bool:
    """Record against the root that owns this channel. True when a row was written.

    Every caller needs the same three steps — resolve the root, skip when there
    is none, never raise into a turn — and the two that hand-rolled it both
    carried the eight-day thread-resolution bug. One implementation means fixing
    that class once. The boolean is for tests: a call site that silently records
    nothing is the failure this ledger keeps having.
    """
    try:
        root = root_for_channel(channel_id)
        if not root:
            return False
        record(root, kind=kind, event=event, channel_id=channel_id, detail=detail)
        return True
    except Exception:
        return False


def read_events(practice_dir: str | Path) -> list[dict[str, Any]]:
    path = ledger_path(practice_dir)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("kind") and row.get("event") in EVENTS:
            rows.append(row)
    return rows


def _within(row: dict[str, Any], since: date | None) -> bool:
    if since is None:
        return True
    ts = str(row.get("ts") or "")[:10]
    try:
        return date.fromisoformat(ts) >= since
    except ValueError:
        return False


def tally(
    practice_dirs: Iterable[str | Path],
    *,
    since: date | None = None,
) -> dict[str, dict[str, int]]:
    """Per kind: offered / accepted / no_answer across roots.

    ``no_answer`` is offers minus accepted minus any historical declines — asked
    and did not take it. It deliberately does not separate *saw it and passed*
    from *never saw it*; see the module docstring for why that distinction is not
    inferred rather than guessed.
    """
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "offered": 0,
            "accepted": 0,
            "declined": 0,
            "suppressed": 0,
            "no_answer": 0,
        }
    )
    for pd in practice_dirs:
        for row in read_events(pd):
            if not _within(row, since):
                continue
            counts[str(row["kind"])][str(row["event"])] += 1
    for kind, row in counts.items():
        row["no_answer"] = max(0, row["offered"] - row["accepted"] - row["declined"])
    return dict(counts)


def opened_on(practice_dirs: Iterable[str | Path]) -> date | None:
    """Earliest recorded event across roots — when this instrument began."""
    earliest: date | None = None
    for pd in practice_dirs:
        for row in read_events(pd):
            try:
                seen = date.fromisoformat(str(row.get("ts") or "")[:10])
            except ValueError:
                continue
            if earliest is None or seen < earliest:
                earliest = seen
    return earliest


def render_write_path_section(
    counts: dict[str, dict[str, int]],
    *,
    window_days: int,
    known_kinds: Iterable[str] = (),
    opened: date | None = None,
) -> str:
    """Markdown for the ops report. A kind with zero offers is the headline.

    ``opened`` is when the ledger recorded its first event. Before it has a
    full window of history, "no offer recorded" cannot be distinguished from
    "not yet instrumented", and the section says so rather than flagging every
    row as a defect on its first night.
    """
    kinds = sorted(set(counts) | set(known_kinds))
    if not kinds:
        return ""

    warm = opened is not None and (date.today() - opened).days >= window_days
    lines = [
        f"## Write-path ratios (last {window_days}d)",
        "",
        "*What fraction of real events reached each write path. **Zero offers is",
        "not zero demand** — it means the path never fired, and that is a defect",
        "in the noticer, not a verdict from members.*",
        "",
    ]
    if opened is None:
        # This line used to read "instrumentation is live but nothing has been
        # recorded yet" — a claim about the instrument that the instrument
        # cannot check, and it was false for eight days while every offer went
        # unrecorded. An empty ledger has two causes and the report's job is to
        # name both and say where the answer is.
        lines += [
            "*Ledger empty — **no offer event has ever been recorded**. Either nothing "
            "was offered, or the write path is not reaching the ledger. The bot logs "
            "settle it: grep `Contextual offer posted` in `logs/river.log`. A non-zero "
            "count there against an empty ledger is a defect in the recorder.*",
            "",
        ]
    elif not warm:
        lines += [
            f"*Ledger opened {opened.isoformat()}; it only accumulates forward, so a "
            "zero row below is **unmeasured**, not observed.*",
            "",
        ]
    lines += [
        "*No decline button exists anywhere since 2026-08-14 — ignoring an offer is "
        "how it is declined. So **no answer** covers both passing on it and never "
        "seeing it, and nothing distinguishes those today.*",
        "",
        "| Offer | Offered | Accepted | No answer | Held back | Take rate |",
        "|-------|---------|----------|-----------|-----------|-----------|",
    ]
    uninstrumented = []
    for kind in kinds:
        row = counts.get(kind) or {
            "offered": 0, "accepted": 0, "declined": 0, "suppressed": 0, "no_answer": 0
        }
        offered = row["offered"]
        measurable = kind in ACCEPT_INSTRUMENTED
        if not measurable:
            uninstrumented.append(kind)
        if not measurable:
            # A rate computed from an accept path that cannot fire is not a low
            # rate, it is no reading at all — and printing 0% would be the exact
            # false verdict this instrument exists to prevent.
            rate = "not recorded"
        else:
            rate = f"{(row['accepted'] / offered * 100):.0f}%" if offered else "—"
        if offered:
            flag = ""
        elif row.get("suppressed"):
            # Not the same as never firing: the path engaged and a gate held
            # it back, which is the gate working rather than a defect.
            flag = "  · held back only"
        else:
            flag = "  ⚠︎ never fired" if warm else "  · no data yet"
        lines.append(
            f"| {kind}{flag} | {offered} | {row['accepted']} | "
            f"{row['no_answer']} | {row.get('suppressed', 0)} | {rate} |"
        )
    lines.append("")
    if uninstrumented:
        lines += [
            f"*Accept not recorded for **{', '.join(sorted(uninstrumented))}** — these "
            "are accepted by running a River command rather than clicking a callback, "
            "so their `no answer` column counts members who did take the offer. Take "
            "rate for them is unmeasured, not low.*",
            "",
        ]
    return "\n".join(lines)


def default_window_start(days: int = 30, today: date | None = None) -> date:
    base = today or datetime.now(timezone.utc).date()
    return base - timedelta(days=max(0, days))
