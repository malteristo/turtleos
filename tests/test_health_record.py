"""Health extension: owner-held state, citations, correction, board budget."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from channel_primitives import resolve_primitive
from health_record import (
    BOARD_MAX_CHARS,
    RECORD_EVENT_FILES,
    appointment_prep,
    confirm_proposal,
    correct_event,
    ensure_record_structure,
    keep_question,
    propose_source_claims,
    recap_health_visit,
    render_board,
    save_observation,
    trace_claim,
)
from practice_sources import intake_file, process_source


def primitive():
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


class HealthRecordTests(unittest.TestCase):
    def test_explicit_owner_observation_and_question_land_without_extra_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = save_observation(
                tmp,
                primitive=primitive(),
                actor="partner",
                text="I felt dizzy after lunch.",
            )
            question = keep_question(
                tmp,
                primitive=primitive(),
                actor="partner",
                text="Could iron status be relevant?",
            )
            self.assertEqual(observation["decision"], "applied")
            self.assertEqual(question["decision"], "applied")
            board = (Path(tmp) / "health_model.md").read_text()
            self.assertIn("dizzy after lunch", board)
            self.assertIn("Could iron status", board)

    def test_steward_report_stays_pending_for_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = save_observation(
                tmp,
                primitive=primitive(),
                actor="default",
                text="The subject looked tired.",
            )
            self.assertEqual(result["decision"], "pending")
            self.assertEqual(
                result["operations"][0]["provenance"]["kind"], "member_report"
            )
            self.assertFalse((Path(tmp) / "record" / "observations.jsonl").exists())

    def test_source_claim_requires_confirmation_and_keeps_units_and_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "labs.txt"
            source.write_text("Ferritin: 21 ng/mL", encoding="utf-8")
            saved = intake_file(tmp, source, actor="migration")
            process_source(tmp, saved.source_id)
            proposal = propose_source_claims(
                tmp,
                primitive=primitive(),
                actor="partner",
                source_id=saved.source_id,
                claims=[
                    {
                        "text": "Ferritin measured 21 ng/mL",
                        "page": 1,
                        "kind": "measured_result",
                        "value": 21,
                        "unit": "ng/mL",
                    }
                ],
            )
            self.assertEqual(proposal["decision"], "pending")
            applied = confirm_proposal(
                tmp, proposal["proposal_id"], actor="partner"
            )
            self.assertEqual(applied["decision"], "applied")
            claim_id = proposal["operations"][0]["claim"]["claim_id"]
            claim = trace_claim(tmp, claim_id)
            self.assertEqual(claim["unit"], "ng/mL")
            self.assertIn(f"source:{saved.source_id}", claim["evidence"][0])

    def test_correction_supersedes_without_erasing_source_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            applied = save_observation(
                tmp,
                primitive=primitive(),
                actor="partner",
                text="Pain began Monday.",
            )
            operation = applied["operations"][0]
            event_id = operation["event"]["event_id"]
            correct_event(
                tmp,
                primitive=primitive(),
                actor="partner",
                event_id=event_id,
                correction="It began Tuesday.",
            )
            original = (Path(tmp) / "record" / "observations.jsonl").read_text()
            correction = (Path(tmp) / "record" / "corrections.jsonl").read_text()
            self.assertIn("Pain began Monday", original)
            self.assertIn("It began Tuesday", correction)
            self.assertNotIn("Pain began Monday", (Path(tmp) / "health_model.md").read_text())

    def test_board_budget_keeps_details_in_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "health_model.md").write_text(
                "# Existing\n\n" + ("long existing paragraph " * 800),
                encoding="utf-8",
            )
            save_observation(
                tmp,
                primitive=primitive(),
                actor="partner",
                text="A recent concise observation.",
            )
            board = render_board(tmp)
            self.assertLessEqual(len(board), BOARD_MAX_CHARS)
            self.assertIn("A recent concise observation", board)

    def test_appointment_artifact_uses_confirmed_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            keep_question(
                tmp,
                primitive=primitive(),
                actor="partner",
                text="What should I ask about the lab trend?",
            )
            path = appointment_prep(tmp)
            self.assertIn("lab trend", path.read_text(encoding="utf-8"))

    def test_recap_writes_record_and_prep_is_not_hollow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "health_model.md").write_text(
                "# Health model\n\n## Now\n\n- Keep this existing now line.\n\n"
                "## Documented\n\n- Keep this documented line.\n",
                encoding="utf-8",
            )
            applied = recap_health_visit(
                tmp,
                primitive=primitive(),
                actor="partner",
                observations="Dizzy after the wait.",
                clinician_said="Dr Example: come back in two weeks",
                questions="Ask about the 116117 code",
                dates="28.10 blood draw",
                medications="named tablet\nrefused: other tablet",
                ideas="maybe related to sleep",
                occurred_at="Friday morning",
            )
            self.assertEqual(applied["decision"], "applied")
            questions = (Path(tmp) / "record" / "questions.jsonl").read_text()
            self.assertIn("116117", questions)
            clinician = (Path(tmp) / "record" / "observations.jsonl").read_text()
            self.assertIn("come back in two weeks", clinician)
            self.assertIn("clinician_statement", clinician)
            self.assertIn("Dr Example", clinician)
            dates = (Path(tmp) / "record" / "dates.jsonl").read_text()
            self.assertIn("not_on_primary", dates)
            board = (Path(tmp) / "health_model.md").read_text()
            self.assertIn("Keep this existing now line", board)
            self.assertIn("Keep this documented line", board)
            self.assertIn("not on primary", board)
            self.assertIn("Inference (unconfirmed)", board)
            prep = appointment_prep(tmp).read_text(encoding="utf-8")
            self.assertIn("116117", prep)
            (Path(tmp) / "record" / "questions.jsonl").unlink()
            (Path(tmp) / "record" / "observations.jsonl").unlink()
            hollow = appointment_prep(tmp).read_text(encoding="utf-8")
            self.assertNotIn("116117", hollow)
            self.assertIn("No saved questions yet", hollow)

    def test_ensure_record_structure_creates_empty_event_files_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created = ensure_record_structure(tmp)
            self.assertEqual(set(created), set(RECORD_EVENT_FILES))
            record = Path(tmp) / "record"
            for name in RECORD_EVENT_FILES:
                path = record / name
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_text(), "")
            again = ensure_record_structure(tmp)
            self.assertEqual(again, [])

    def test_recap_on_shared_root_does_not_write_a_sibling_solo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "health"
            solo = Path(tmp) / "health-kermit"
            shared.mkdir()
            solo.mkdir()
            recap_health_visit(
                shared,
                primitive=primitive(),
                actor="partner",
                questions="Ask about the next slot",
            )
            self.assertTrue((shared / "record" / "questions.jsonl").is_file())
            self.assertFalse((solo / "record").exists())
            self.assertFalse(any(solo.rglob("*")))

    def test_recap_does_not_write_a_sibling_house_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kermit = Path(tmp) / "health-kermit"
            house = Path(tmp) / "health"
            kermit.mkdir()
            house.mkdir()
            recap_health_visit(
                kermit,
                primitive=primitive(),
                actor="partner",
                questions="Ask about the next slot",
            )
            self.assertTrue((kermit / "record" / "questions.jsonl").is_file())
            self.assertFalse((house / "record").exists())
            self.assertFalse(any(house.rglob("*")))

    def test_model_shaped_idea_is_written_as_labelled_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            applied = recap_health_visit(
                tmp,
                primitive=primitive(),
                actor="partner",
                questions="What would help the next hour?",
                ideas="best current model: lupus would explain the labs",
            )
            self.assertEqual(applied["decision"], "applied")
            observations = Path(tmp) / "record" / "observations.jsonl"
            self.assertTrue(observations.is_file())
            text = observations.read_text()
            self.assertIn("lupus", text)
            self.assertIn("labelled until confirmed", text)
            self.assertFalse(applied["skipped"])


if __name__ == "__main__":
    unittest.main()
