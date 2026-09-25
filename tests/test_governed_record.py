"""Role authority, provenance, and atomic/idempotent mutation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from channel_primitives import resolve_primitive
from governed_record import append_jsonl, decide, propose
from provenance_guard import EvidenceKind, guard_distillation, validate_event


def health_primitive():
    return resolve_primitive(
        {
            "spaces": {
                "health": {
                    "members": ["default", "partner"],
                    "subject": "partner",
                    "steward": "default",
                    "memory": "isolated",
                }
            },
            "channels": {"7": {"primitive": "health", "mage": "health"}},
        },
        7,
    )


class ProvenanceTests(unittest.TestCase):
    def test_source_fact_requires_reachable_evidence(self) -> None:
        event = {
            "kind": EvidenceKind.SOURCE_DOCUMENT.value,
            "actor": "partner",
            "subject": "partner",
            "evidence": ["lab.pdf · p. 2 · source:12345678abcdef00"],
        }
        denied = validate_event(event, subject="partner", source_exists=lambda _: False)
        self.assertFalse(denied.ok)
        allowed = validate_event(event, subject="partner", source_exists=lambda _: True)
        self.assertTrue(allowed.ok)

    def test_member_report_cannot_masquerade_as_subject_testimony(self) -> None:
        event = {
            "kind": EvidenceKind.PRACTITIONER_TESTIMONY.value,
            "actor": "default",
            "subject": "partner",
        }
        self.assertFalse(validate_event(event, subject="partner").ok)
        event["kind"] = EvidenceKind.MEMBER_REPORT.value
        self.assertTrue(validate_event(event, subject="partner").ok)

    def test_clinician_statement_requires_a_name(self) -> None:
        event = {
            "kind": EvidenceKind.CLINICIAN_STATEMENT.value,
            "actor": "partner",
            "subject": "partner",
        }
        self.assertFalse(validate_event(event, subject="partner").ok)
        event["clinician"] = "Dr Example"
        self.assertTrue(validate_event(event, subject="partner").ok)

    def test_harmful_unsupported_attribution_is_blocked(self) -> None:
        transcript = [("Ari", "I was tired."), ("Bo", "I made tea.")]
        result = guard_distillation("Ari said Bo is crazy.", transcript)
        self.assertFalse(result.ok)
        grounded = guard_distillation(
            "Ari said she was tired.", transcript
        )
        self.assertTrue(grounded.ok)


class GovernedMutationTests(unittest.TestCase):
    def test_subject_confirmation_applies_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            primitive = health_primitive()
            proposal = propose(
                tmp,
                primitive=primitive,
                actor="partner",
                reason="save this observation",
                explicit=True,
                operations=[
                    {
                        "op": "append_observation",
                        "text": "Headache after lunch",
                        "provenance": {
                            "kind": "practitioner_testimony",
                            "actor": "partner",
                            "subject": "partner",
                        },
                    }
                ],
            )

            def append(root, operation):
                return append_jsonl(root, "record/observations.jsonl", operation)

            first = decide(
                tmp,
                proposal["proposal_id"],
                actor="partner",
                decision="confirm",
                handlers={"append_observation": append},
            )
            second = decide(
                tmp,
                proposal["proposal_id"],
                actor="partner",
                decision="confirm",
                handlers={"append_observation": append},
            )
            self.assertEqual(first["decision"], "applied")
            self.assertEqual(second["decision"], "applied")
            lines = (Path(tmp) / "record" / "observations.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)

    def test_steward_cannot_confirm_subject_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposal = propose(
                tmp,
                primitive=health_primitive(),
                actor="default",
                reason="reported by steward",
                operations=[
                    {
                        "op": "append_observation",
                        "text": "She felt dizzy",
                        "provenance": {
                            "kind": "member_report",
                            "actor": "default",
                            "subject": "partner",
                        },
                    }
                ],
            )
            with self.assertRaises(PermissionError):
                decide(
                    tmp,
                    proposal["proposal_id"],
                    actor="default",
                    decision="confirm",
                    handlers={"append_observation": lambda root, op: {}},
                )


if __name__ == "__main__":
    unittest.main()
