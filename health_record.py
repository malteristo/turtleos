"""Health-specific composition over governed record and corpus capabilities."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.atomic_io import atomic_write_json, atomic_write_text
from governed_record import append_jsonl, decide, propose
from practice_corpus import search, source_trace


BOARD_MAX_CHARS = 8000
MANAGED_START = "<!-- health-record:managed:start -->"
MANAGED_END = "<!-- health-record:managed:end -->"
RECAP_NOW_START = "<!-- health-record:recap-now:start -->"
RECAP_NOW_END = "<!-- health-record:recap-now:end -->"
RECAP_DOC_START = "<!-- health-record:recap-documented:start -->"
RECAP_DOC_END = "<!-- health-record:recap-documented:end -->"
RECORD_EVENT_FILES = (
    "observations.jsonl",
    "questions.jsonl",
    "dates.jsonl",
    "medications.jsonl",
    "corrections.jsonl",
)


def ensure_record_structure(practice_dir) -> list[str]:
    """Create empty event files. Return names this call created.

    Recap also lazy-creates. This is the empty structure the provisioner
    writes so both instances start with the same paths.
    """
    record = Path(practice_dir).expanduser() / "record"
    record.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name in RECORD_EVENT_FILES:
        path = record / name
        if path.exists():
            continue
        path.write_text("", encoding="utf-8")
        created.append(name)
    return created


def recap_health_visit(
    practice_dir,
    *,
    primitive,
    actor: str,
    observations: str = "",
    clinician_said: str = "",
    questions: str = "",
    dates: str = "",
    medications: str = "",
    ideas: str = "",
    occurred_at: str | None = None,
) -> dict:
    """One writer for a visit recap. Fields of one call, not four features.

    Writes only under ``practice_dir``. Owner recap is consent and applies.
    A steward or other member stays pending. Dates stay local — never a
    Google Calendar write. Ideas are labelled inference. Clinician words
    are attributed, not owner testimony.
    """
    root = Path(practice_dir).resolve()
    operations: list[dict] = []
    skipped: list[str] = []
    when = _clean_text(occurred_at) or None

    for text in _lines(observations):
        event = _event(
            "observation",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="practitioner_testimony",
            occurred_at=when,
        )
        operations.append(
            {
                "op": "append_observation",
                "event": event,
                "provenance": {
                    "kind": "practitioner_testimony",
                    "actor": actor,
                    "subject": primitive.subject,
                },
            }
        )

    for raw in _lines(clinician_said):
        clinician, text = _split_speaker(raw)
        if not clinician:
            skipped.append("clinician line had no name")
            continue
        event = _event(
            "observation",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="clinician_statement",
            clinician=clinician,
            occurred_at=when,
        )
        operations.append(
            {
                "op": "append_observation",
                "event": event,
                "provenance": {
                    "kind": "clinician_statement",
                    "actor": actor,
                    "subject": primitive.subject,
                    "clinician": clinician,
                },
            }
        )

    for text in _lines(questions):
        event = _event(
            "question",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="open_question",
        )
        operations.append({"op": "append_question", "event": event})

    for text in _lines(dates):
        event = _event(
            "date",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="practitioner_testimony",
            calendar_status="not_on_primary",
            occurred_at=when,
        )
        operations.append(
            {
                "op": "append_date",
                "event": event,
                "provenance": {
                    "kind": "practitioner_testimony",
                    "actor": actor,
                    "subject": primitive.subject,
                },
            }
        )

    for raw in _lines(medications):
        status, text = _medication_status(raw)
        event = _event(
            "medication",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="practitioner_testimony",
            medication_status=status,
            occurred_at=when,
        )
        operations.append(
            {
                "op": "append_medication",
                "event": event,
                "provenance": {
                    "kind": "practitioner_testimony",
                    "actor": actor,
                    "subject": primitive.subject,
                },
            }
        )

    for text in _lines(ideas):
        event = _event(
            "inference",
            text,
            actor=actor,
            subject=primitive.subject,
            provenance="turtle_inference",
            uncertainty="unconfirmed model from the recap; labelled until confirmed",
            occurred_at=when,
        )
        operations.append(
            {
                "op": "append_observation",
                "event": event,
                "provenance": {
                    "kind": "turtle_inference",
                    "actor": actor,
                    "subject": primitive.subject,
                    "uncertainty": event["uncertainty"],
                },
            }
        )

    if not operations:
        raise ValueError("recap is empty")

    proposal = propose(
        root,
        primitive=primitive,
        actor=actor,
        reason="visit recap",
        explicit=True,
        operations=operations,
    )
    if actor != primitive.subject:
        proposal["skipped"] = skipped
        return proposal
    applied = decide(
        root,
        proposal["proposal_id"],
        actor=actor,
        decision="confirm",
        handlers=mutation_handlers(),
    )
    applied["skipped"] = skipped
    applied["practice_dir"] = str(root)
    applied["dates"] = [
        {
            "text": op["event"]["text"],
            "calendar_status": op["event"].get("calendar_status", "not_on_primary"),
        }
        for op in operations
        if op.get("op") == "append_date"
    ]
    return applied


def save_observation(
    practice_dir,
    *,
    primitive,
    actor: str,
    text: str,
    occurred_at: str | None = None,
    verdict: str | None = None,
    turtle_draft: str | None = None,
) -> dict:
    """Explicit self-report: consent is in the request, so apply immediately.

    ``verdict`` and ``turtle_draft`` ride on the same event. A correction does
    not open a second authority path.
    """
    text = _clean_text(text)
    if not text:
        raise ValueError("observation is empty")
    extra: dict = {}
    if verdict:
        extra["verdict"] = verdict
    draft = _clean_text(turtle_draft or "")
    if draft:
        extra["turtle_draft"] = draft
    event = _event(
        "observation",
        text,
        actor=actor,
        subject=primitive.subject,
        provenance=(
            "practitioner_testimony"
            if actor == primitive.subject
            else "member_report"
        ),
        occurred_at=occurred_at,
        **extra,
    )
    proposal = propose(
        practice_dir,
        primitive=primitive,
        actor=actor,
        reason="explicit save observation",
        explicit=True,
        operations=[
            {
                "op": "append_observation",
                "event": event,
                "provenance": {
                    "kind": event["provenance"],
                    "actor": actor,
                    "subject": primitive.subject,
                },
            }
        ],
    )
    if actor != primitive.subject:
        return proposal
    return decide(
        practice_dir,
        proposal["proposal_id"],
        actor=actor,
        decision="confirm",
        handlers=mutation_handlers(),
    )


def keep_question(
    practice_dir,
    *,
    primitive,
    actor: str,
    text: str,
) -> dict:
    text = _clean_text(text)
    if not text:
        raise ValueError("question is empty")
    event = _event(
        "question",
        text,
        actor=actor,
        subject=primitive.subject,
        provenance="open_question",
    )
    proposal = propose(
        practice_dir,
        primitive=primitive,
        actor=actor,
        reason="explicit keep question",
        explicit=True,
        operations=[{"op": "append_question", "event": event}],
    )
    if actor != primitive.subject:
        return proposal
    return decide(
        practice_dir,
        proposal["proposal_id"],
        actor=actor,
        decision="confirm",
        handlers=mutation_handlers(),
    )


def propose_source_claims(
    practice_dir,
    *,
    primitive,
    actor: str,
    claims: list[dict],
    source_id: str,
) -> dict:
    """Stage evidence-linked findings. They never land without subject review."""
    trace = source_trace(practice_dir, source_id)
    if trace is None:
        raise ValueError("source is not in the local corpus")
    operations = []
    for raw in claims[:30]:
        text = _clean_text(raw.get("text", ""))
        page = int(raw.get("page") or 1)
        if not text:
            continue
        citation = f"{trace['filename']} · p. {page} · source:{source_id}"
        claim_id = hashlib.sha256(f"{source_id}:{page}:{text}".encode()).hexdigest()[:16]
        operations.append(
            {
                "op": "replace_claim",
                "claim": {
                    "claim_id": claim_id,
                    "text": text,
                    "kind": raw.get("kind") or "measured_result",
                    "value": raw.get("value"),
                    "unit": raw.get("unit"),
                    "document_date": raw.get("document_date"),
                    "confidence": raw.get("confidence", 1.0),
                    "status": "current",
                    "evidence": [citation],
                },
                "provenance": {
                    "kind": "source_document",
                    "actor": actor,
                    "subject": primitive.subject,
                    "evidence": [citation],
                },
            }
        )
    if not operations:
        raise ValueError("no supported claims")
    return propose(
        practice_dir,
        primitive=primitive,
        actor=actor,
        reason=f"review findings from source:{source_id}",
        operations=operations,
    )


def correct_event(
    practice_dir,
    *,
    primitive,
    actor: str,
    event_id: str,
    correction: str,
) -> dict:
    if actor != primitive.subject:
        raise PermissionError("only the record owner can correct subject-owned state")
    operation = {
        "op": "supersede_event",
        "event_id": event_id,
        "correction": _clean_text(correction),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    proposal = propose(
        practice_dir,
        primitive=primitive,
        actor=actor,
        reason=f"correct {event_id}",
        explicit=True,
        operations=[operation],
    )
    return decide(
        practice_dir,
        proposal["proposal_id"],
        actor=actor,
        decision="confirm",
        handlers=mutation_handlers(),
    )


def confirm_proposal(practice_dir, proposal_id: str, *, actor: str) -> dict:
    return decide(
        practice_dir,
        proposal_id,
        actor=actor,
        decision="confirm",
        handlers=mutation_handlers(),
    )


def reject_proposal(practice_dir, proposal_id: str, *, actor: str) -> dict:
    return decide(
        practice_dir,
        proposal_id,
        actor=actor,
        decision="reject",
        handlers=mutation_handlers(),
    )


def mutation_handlers():
    return {
        "append_observation": _append_observation,
        "append_question": _append_question,
        "append_date": _append_date,
        "append_medication": _append_medication,
        "replace_claim": _replace_claim,
        "supersede_event": _supersede_event,
    }


def trace_claim(practice_dir, claim_id: str) -> dict | None:
    path = Path(practice_dir) / "record" / "claims.json"
    if not path.is_file():
        return None
    return (json.loads(path.read_text(encoding="utf-8")) or {}).get(claim_id)


def appointment_prep(practice_dir, title: str = "Appointment preparation") -> Path:
    root = Path(practice_dir)
    questions = _read_events(root / "record" / "questions.jsonl")
    observations = _read_events(root / "record" / "observations.jsonl")
    claims = _read_json(root / "record" / "claims.json", {})
    now = datetime.now(timezone.utc)
    target = root / "artifacts" / f"appointment-prep-{now.date().isoformat()}.md"
    body = [
        f"# {title}",
        "",
        f"Prepared {now.date().isoformat()} from the local health record.",
        "",
        "## Questions to bring",
        *([f"- {row['text']}" for row in questions if not row.get("superseded_by")] or ["- No saved questions yet."]),
        "",
        "## Recent observations",
        *([f"- {row['text']} ({row.get('occurred_at') or row.get('created_at', '')[:10]})" for row in observations[-12:] if not row.get("superseded_by")] or ["- No saved observations yet."]),
        "",
        "## Dates named",
        *(
            [
                f"- {row['text']} — {row.get('calendar_status') or 'not_on_primary'}"
                for row in _read_events(root / "record" / "dates.jsonl")
                if not row.get("superseded_by")
            ]
            or ["- No saved dates yet."]
        ),
        "",
        "## Current evidence-linked findings",
        *(
            [
                f"- {row['text']} — {'; '.join(row.get('evidence') or [])}"
                for row in claims.values()
                if row.get("status") == "current"
            ][:20]
            or ["- No confirmed source-linked findings yet."]
        ),
        "",
        "This is preparation. The board holds the best current model. Clinicians decide treatment.",
    ]
    atomic_write_text(target, "\n".join(body) + "\n")
    return target


def likely_duplicates(practice_dir, text: str, *, limit: int = 5) -> list[dict]:
    """Content candidates only; exact duplicate remains SHA-256."""
    terms = " ".join(_keywords(text)[:10])
    if not terms:
        return []
    return search(practice_dir, terms, limit=limit)


def render_board(practice_dir) -> str:
    root = Path(practice_dir)
    path = root / "health_model.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# Health model\n"
    base = _strip_managed(existing).rstrip()
    superseded_ids = {
        row.get("event_id")
        for row in _read_events(root / "record" / "corrections.jsonl")
        if row.get("event_id")
    }
    observations = [
        row for row in _read_events(root / "record" / "observations.jsonl")
        if row.get("event_id") not in superseded_ids
    ]
    questions = [
        row for row in _read_events(root / "record" / "questions.jsonl")
        if row.get("event_id") not in superseded_ids
    ]
    claims = [
        row for row in _read_json(root / "record" / "claims.json", {}).values()
        if row.get("status") == "current"
    ]
    dates = [
        row
        for row in _read_events(root / "record" / "dates.jsonl")
        if row.get("event_id") not in superseded_ids
    ]
    medications = [
        row
        for row in _read_events(root / "record" / "medications.jsonl")
        if row.get("event_id") not in superseded_ids
    ]
    now_lines = [
        f"- {row['text']} — not on primary (source-derived, unconfirmed)"
        for row in dates
    ] + [
        f"- {row['text']} — named (source-derived, unconfirmed)"
        for row in medications
        if row.get("medication_status") != "refused"
    ]
    documented_lines = [
        f"- {row['text']} — refused (source-derived, unconfirmed)"
        for row in medications
        if row.get("medication_status") == "refused"
    ] + [
        f"- Inference (unconfirmed): {row['text']}"
        for row in observations
        if row.get("provenance") == "turtle_inference"
    ]
    managed = [
        MANAGED_START,
        "## Confirmed record additions",
        "",
        "### Evidence-linked findings",
        *(
            [f"- {row['text']}  \n  Evidence: {'; '.join(row.get('evidence') or [])}" for row in claims[-12:]]
            or ["- None yet." ]
        ),
        "",
        "### Record owner's observations",
        *([f"- {row['text']}" for row in observations[-12:]] or ["- None yet."]),
        "",
        "### Open questions",
        *([f"- {row['text']}" for row in questions[-12:]] or ["- None yet."]),
        "",
        "### Dates named",
        *(
            [
                f"- {row['text']} — {row.get('calendar_status') or 'not_on_primary'}"
                for row in dates[-12:]
            ]
            or ["- None yet."]
        ),
        MANAGED_END,
    ]
    suffix = "\n\n" + "\n".join(managed) + "\n"
    recap_blocks = 0
    if now_lines:
        recap_blocks += len("\n".join([RECAP_NOW_START, *now_lines, RECAP_NOW_END])) + 8
    if documented_lines:
        recap_blocks += len("\n".join([RECAP_DOC_START, *documented_lines, RECAP_DOC_END])) + 8
    budget = BOARD_MAX_CHARS - len(suffix) - recap_blocks
    base = _fit_paragraphs(base, max(0, budget))
    if now_lines:
        base = _append_in_section(
            base,
            "Now",
            "\n".join([RECAP_NOW_START, *now_lines, RECAP_NOW_END]),
        )
    if documented_lines:
        base = _append_in_section(
            base,
            "Documented",
            "\n".join([RECAP_DOC_START, *documented_lines, RECAP_DOC_END]),
        )
    board = base + suffix
    atomic_write_text(path, board, lock=True)
    return board


def _append_observation(root: Path, operation: dict) -> dict:
    effect = append_jsonl(root, "record/observations.jsonl", operation["event"])
    render_board(root)
    return effect


def _append_question(root: Path, operation: dict) -> dict:
    effect = append_jsonl(root, "record/questions.jsonl", operation["event"])
    render_board(root)
    return effect


def _append_date(root: Path, operation: dict) -> dict:
    effect = append_jsonl(root, "record/dates.jsonl", operation["event"])
    render_board(root)
    return effect


def _append_medication(root: Path, operation: dict) -> dict:
    effect = append_jsonl(root, "record/medications.jsonl", operation["event"])
    render_board(root)
    return effect


def _replace_claim(root: Path, operation: dict) -> dict:
    path = root / "record" / "claims.json"
    claims = _read_json(path, {})
    claim = operation["claim"]
    previous = claims.get(claim["claim_id"])
    if previous:
        claim["supersedes"] = previous.get("claim_id")
    claims[claim["claim_id"]] = claim
    atomic_write_json(path, claims, indent=2, lock=True)
    render_board(root)
    return {"path": "record/claims.json", "claim_id": claim["claim_id"]}


def _supersede_event(root: Path, operation: dict) -> dict:
    event = {
        "correction_id": hashlib.sha256(
            f"{operation['event_id']}:{operation['at']}".encode()
        ).hexdigest()[:16],
        "kind": "correction",
        **operation,
    }
    effect = append_jsonl(root, "record/corrections.jsonl", event)
    render_board(root)
    return effect


def _event(event_type: str, text: str, *, actor: str, subject: str, **extra) -> dict:
    created = datetime.now(timezone.utc).isoformat()
    event_id = hashlib.sha256(
        f"{event_type}:{actor}:{created}:{text}".encode()
    ).hexdigest()[:16]
    return {
        "event_id": event_id,
        "event_type": event_type,
        "text": text,
        "actor": actor,
        "subject": subject,
        "created_at": created,
        **extra,
    }


def _read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _fit_paragraphs(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    parts = text.split("\n\n")
    kept = []
    used = 0
    for part in parts:
        cost = len(part) + (2 if kept else 0)
        if used + cost > max(0, budget - 80):
            break
        kept.append(part)
        used += cost
    return "\n\n".join(kept) + "\n\n[… details remain in the governed record …]"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:2000]


def _keywords(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", text or "", flags=re.UNICODE)


def _lines(text: str) -> list[str]:
    return [_clean_text(line) for line in str(text or "").splitlines() if _clean_text(line)]


def _split_speaker(raw: str) -> tuple[str, str]:
    text = _clean_text(raw)
    if ":" not in text:
        return "", text
    name, rest = text.split(":", 1)
    name, rest = name.strip(), rest.strip()
    if len(name.split()) > 4 or not name or not rest:
        return "", text
    return name, rest


def _medication_status(raw: str) -> tuple[str, str]:
    text = _clean_text(raw)
    lowered = text.lower()
    if lowered.startswith("refused:") or lowered.startswith("refused "):
        return "refused", _clean_text(text.split(":", 1)[-1] if ":" in text else text[7:])
    return "named", text


def _strip_managed(text: str) -> str:
    for start, end in (
        (MANAGED_START, MANAGED_END),
        (RECAP_NOW_START, RECAP_NOW_END),
        (RECAP_DOC_START, RECAP_DOC_END),
    ):
        text = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            "",
            text,
            flags=re.DOTALL,
        )
    return text


def _append_in_section(text: str, heading: str, block: str) -> str:
    if not block:
        return text
    pat = re.compile(
        rf"(^## {re.escape(heading)}\s*\n)(.*?)(?=^## |\Z)",
        re.M | re.S,
    )
    match = pat.search(text)
    if not match:
        return text.rstrip() + f"\n\n## {heading}\n\n{block}\n"
    body = match.group(2).rstrip()
    new_body = (body + "\n\n" if body else "") + block + "\n"
    return text[: match.start()] + match.group(1) + new_body + text[match.end() :]
