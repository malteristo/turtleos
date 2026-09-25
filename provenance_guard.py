"""Persisted-state provenance and attribution backstop."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable


class EvidenceKind(str, Enum):
    SOURCE_DOCUMENT = "source_document"
    PRACTITIONER_TESTIMONY = "practitioner_testimony"
    MEMBER_REPORT = "member_report"
    CLINICIAN_STATEMENT = "clinician_statement"
    TURTLE_INFERENCE = "turtle_inference"
    OPEN_QUESTION = "open_question"


@dataclass(frozen=True)
class GuardFinding:
    code: str
    detail: str
    hard: bool = True


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    findings: tuple[GuardFinding, ...]


_ATTRIBUTION = re.compile(
    r"\b(?P<name>[\wÀ-ÖØ-öø-ÿ'-]{2,})\s+"
    r"(?P<verb>said|called|thinks?|felt|dismissed|admitted|"
    r"sagte|nannte|findet|fühlte|hielt)\b(?P<claim>[^.!?\n]{0,180})",
    re.IGNORECASE,
)
_HARM = re.compile(
    r"\b(crazy|narcissist|abusive|liar|stupid|verrückt|narzisst|"
    r"missbräuchlich|lügner)\b",
    re.IGNORECASE,
)
_SOURCE_CLAIM = re.compile(
    r"\b(?:I|we|Turtle|ich|wir)\s+(?:read|reviewed|checked|looked through|"
    r"habe[n]?\s+(?:gelesen|geprüft|durchgesehen))\s+"
    r"(?P<source>[^.!?\n]{2,120})",
    re.IGNORECASE,
)


def validate_event(
    event: dict,
    *,
    subject: str,
    source_exists: Callable[[str], bool] | None = None,
) -> GuardResult:
    """Validate provenance before a derived health/practice event is persisted."""
    findings: list[GuardFinding] = []
    try:
        kind = EvidenceKind(str(event.get("kind") or ""))
    except ValueError:
        return GuardResult(False, (GuardFinding("unknown_kind", "unknown provenance kind"),))
    actor = str(event.get("actor") or "").strip()
    about = str(event.get("subject") or subject).strip()
    evidence = [str(item) for item in (event.get("evidence") or []) if str(item)]

    if kind is EvidenceKind.SOURCE_DOCUMENT:
        if not evidence:
            findings.append(GuardFinding("source_without_evidence", "source-derived fact has no citation"))
        elif source_exists:
            for citation in evidence:
                source_id = source_id_from_citation(citation)
                if not source_id or not source_exists(source_id):
                    findings.append(
                        GuardFinding("unreachable_evidence", f"citation is not reachable: {citation}")
                    )
    elif kind is EvidenceKind.PRACTITIONER_TESTIMONY:
        if actor != subject or about != subject:
            findings.append(
                GuardFinding(
                    "borrowed_testimony",
                    "only the record owner can author their practitioner testimony",
                )
            )
    elif kind is EvidenceKind.MEMBER_REPORT:
        if not actor or actor == about:
            findings.append(
                GuardFinding(
                    "report_without_distinction",
                    "another member's report must name a different speaker and subject",
                )
            )
    elif kind is EvidenceKind.CLINICIAN_STATEMENT:
        clinician = str(event.get("clinician") or "").strip()
        if not clinician:
            findings.append(
                GuardFinding(
                    "unattributed_clinician",
                    "a clinician statement must name who said it",
                )
            )
    elif kind is EvidenceKind.TURTLE_INFERENCE:
        if not event.get("uncertainty"):
            findings.append(
                GuardFinding("unmarked_inference", "Turtle inference must name uncertainty")
            )

    return GuardResult(not any(item.hard for item in findings), tuple(findings))


def guard_distillation(
    candidate: str,
    transcript: Iterable[tuple[str, str]],
    *,
    reachable_sources: Iterable[str] = (),
) -> GuardResult:
    """Check generated durable prose against visible speakers and source reach."""
    utterances: dict[str, str] = {}
    for speaker, body in transcript:
        utterances.setdefault(_norm(speaker), "")
        utterances[_norm(speaker)] += " " + _norm(body)
    reachable = {_norm(item) for item in reachable_sources}
    findings: list[GuardFinding] = []

    for match in _ATTRIBUTION.finditer(candidate or ""):
        speaker = _norm(match.group("name"))
        claim = _keywords(match.group("claim"))
        source = utterances.get(speaker, "")
        grounded = bool(claim and sum(word in source for word in claim) >= min(2, len(claim)))
        if grounded:
            continue
        harmful = bool(_HARM.search(match.group(0)))
        findings.append(
            GuardFinding(
                "harmful_ungrounded_attribution" if harmful else "ungrounded_attribution",
                match.group(0).strip(),
                hard=harmful,
            )
        )

    for match in _SOURCE_CLAIM.finditer(candidate or ""):
        named = _norm(match.group("source"))
        if not any(item and item in named for item in reachable):
            findings.append(
                GuardFinding("unreachable_source_claim", match.group(0).strip(), hard=True)
            )
    return GuardResult(not any(item.hard for item in findings), tuple(findings))


def source_id_from_citation(citation: str) -> str | None:
    match = re.search(r"\bsource:([a-f0-9]{8,64})\b", citation or "", re.IGNORECASE)
    return match.group(1).lower() if match else None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _keywords(text: str) -> list[str]:
    stop = {"that", "this", "with", "have", "said", "sagte", "dass", "eine", "einen", "und"}
    return [
        word
        for word in re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", _norm(text))
        if word not in stop
    ][:12]
