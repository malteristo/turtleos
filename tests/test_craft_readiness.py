"""The readiness gate, and the two ways a gate like this fails open.

Every assertion here was written after breaking the code it covers and watching
this test fail. The two that matter most are negative:

* `confirm` with no condition anywhere on record must raise. A gate that
  requires a target condition on the *proposal* path and accepts a bare confirm
  is a gate with a door beside it.
* `refuse` with an empty gap must raise, because a refusal with no gap takes the
  eddy off the board and gives the Hearth nothing — which from inside the eddy
  is indistinguishable from being ignored.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import craft_readiness as cr
from core.prepared_eddies import load_sidecar, save_sidecar

THREAD = 102
CONDITION = "TURTLE_SPEC carries a channel-primitives section and the tests name it"


class CraftReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- the gate ---------------------------------------------------------

    def test_propose_requires_a_target_condition(self) -> None:
        for empty in ("", "   ", "\n", "spec it"):
            with self.subTest(value=empty):
                with self.assertRaises(cr.ReadinessError):
                    cr.propose(self.runtime, THREAD, target_condition=empty)
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    def test_confirm_without_a_condition_on_record_raises(self) -> None:
        """The gate's second door. Nothing proposed, nothing supplied."""
        with self.assertRaises(cr.ReadinessError):
            cr.confirm(self.runtime, THREAD)
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    def test_confirm_accepts_the_proposals_condition(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION, evidence="line 40")
        entry = cr.confirm(self.runtime, THREAD)
        self.assertEqual(entry["state"], cr.READY)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), CONDITION)
        self.assertEqual(entry["confirmed_by"], "practitioner")

    def test_confirm_may_correct_the_wording(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        better = "the spec section exists and cmd_admin stops naming channels by hand"
        cr.confirm(self.runtime, THREAD, target_condition=better)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), better)

    def test_confirm_still_refuses_a_correction_that_is_a_label(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        with self.assertRaises(cr.ReadinessError):
            cr.confirm(self.runtime, THREAD, target_condition="done")
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)

    # --- transitions ------------------------------------------------------

    def test_a_proposal_is_not_readiness(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)
        self.assertEqual(cr.list_by_state(self.runtime, cr.READY), [])

    def test_proposal_may_not_overwrite_a_confirmation(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        with self.assertRaises(cr.ReadinessError):
            cr.propose(self.runtime, THREAD, target_condition="something else entirely")
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.READY)

    def test_reproposing_over_a_stale_proposal_overwrites(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        moved_on = "the spec exists and the eddy bar reads it"
        cr.propose(self.runtime, THREAD, target_condition=moved_on)
        self.assertEqual(cr.target_condition_of(self.runtime, THREAD), moved_on)

    def test_refuse_requires_a_gap(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        with self.assertRaises(cr.ReadinessError):
            cr.refuse(self.runtime, THREAD, gap="  ")
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)

    def test_refusal_records_the_gap_as_the_next_thing_to_talk_about(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        gap = "which channels are primitives and which are instances is undecided"
        entry = cr.refuse(self.runtime, THREAD, gap=gap)
        self.assertEqual(entry["state"], cr.REFUSED)
        self.assertEqual(entry["gap"], gap)

    def test_a_new_proposal_clears_the_old_gap(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.refuse(self.runtime, THREAD, gap="undecided which channels are primitives")
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        entry = cr.entry_for(self.runtime, THREAD)
        self.assertNotIn("gap", entry)
        self.assertEqual(entry["state"], cr.PROPOSED)

    def test_work_is_planned_against_a_confirmation_not_a_proposal(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        with self.assertRaises(cr.ReadinessError):
            cr.mark_acted(self.runtime, THREAD)
        cr.confirm(self.runtime, THREAD)
        self.assertEqual(cr.mark_acted(self.runtime, THREAD)["state"], cr.ACTED)

    def test_acted_is_kept_so_the_proposal_take_rate_is_measurable(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        cr.mark_acted(self.runtime, THREAD)
        self.assertEqual(len(cr.list_by_state(self.runtime, cr.ACTED)), 1)
        with self.assertRaises(cr.ReadinessError):
            cr.propose(self.runtime, THREAD, target_condition=CONDITION)

    # --- waiting is not refused -------------------------------------------

    def test_a_wait_needs_something_to_wait_for(self) -> None:
        """A wait with no condition is a drop wearing a state name."""
        for empty in ("", "   ", None):
            with self.subTest(value=empty):
                with self.assertRaises(cr.ReadinessError):
                    cr.mark_waiting(self.runtime, THREAD, on=empty)
        self.assertIsNone(cr.state_of(self.runtime, THREAD))

    def test_waiting_on_the_practitioner_is_the_default(self) -> None:
        entry = cr.mark_waiting(self.runtime, THREAD)
        self.assertEqual(entry["state"], cr.WAITING)
        self.assertEqual(entry["waiting_on"], cr.WAITING_ON_PRACTITIONER)

    def test_a_named_trigger_is_kept_in_the_conversations_own_words(self) -> None:
        trigger = "the family trial thread shows week-on-week use"
        self.assertEqual(cr.mark_waiting(self.runtime, THREAD, on=trigger)["waiting_on"], trigger)

    def test_waiting_carries_no_gap(self) -> None:
        """The eddy already says what it waits for; a gap would invent one."""
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.refuse(self.runtime, THREAD, gap="undecided which channels are primitives")
        entry = cr.mark_waiting(self.runtime, THREAD)
        self.assertNotIn("gap", entry)

    def test_waiting_is_distinguishable_from_refused_on_the_board(self) -> None:
        """The distinction the first real triage was made of: 3 of 5 warm eddies."""
        cr.mark_waiting(self.runtime, THREAD)
        cr.refuse(self.runtime, THREAD + 1, gap="the target is undecided in the thread")
        self.assertEqual(len(cr.list_by_state(self.runtime, cr.WAITING)), 1)
        self.assertEqual(len(cr.list_by_state(self.runtime, cr.REFUSED)), 1)

    def test_an_open_move_is_heat_whoever_holds_it(self) -> None:
        """A waiting eddy must not age to cold — it is the row that needs a person."""
        self.assertEqual(
            cr.temperature(state=cr.WAITING, last_practitioner_message_at=self._ago(400)),
            cr.WARM,
        )

    def test_a_wait_may_not_overwrite_a_finished_session(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        cr.mark_acted(self.runtime, THREAD)
        with self.assertRaises(cr.ReadinessError):
            cr.mark_waiting(self.runtime, THREAD)

    # --- ready is a waypoint ----------------------------------------------

    def _ready(self, condition=CONDITION):
        cr.propose(self.runtime, THREAD, target_condition=condition)
        cr.confirm(self.runtime, THREAD)

    def test_a_confirmed_target_can_be_sharpened(self) -> None:
        self._ready()
        sharper = CONDITION + ", and topics are eddies that may graduate"
        entry = cr.revise(self.runtime, THREAD, target_condition=sharper, kind=cr.REFINE)
        self.assertEqual(entry["target_condition"], sharper)
        self.assertEqual(entry["state"], cr.READY)
        self.assertEqual(len(entry["target_history"]), 1)
        self.assertEqual(entry["target_history"][0]["condition"], CONDITION)

    def test_a_replacement_is_recorded_as_a_replacement(self) -> None:
        """The distinction is the whole measurement; it must not collapse."""
        self._ready()
        elsewhere = "the eddy bar renders temperature without opening a thread"
        cr.revise(self.runtime, THREAD, target_condition=elsewhere, kind=cr.REPLACE)
        entry = cr.entry_for(self.runtime, THREAD)
        self.assertFalse(cr.target_survived(entry))

    def test_a_refined_target_still_counts_as_survived(self) -> None:
        self._ready()
        cr.revise(self.runtime, THREAD, target_condition=CONDITION + " and the tests name it")
        self.assertTrue(cr.target_survived(cr.entry_for(self.runtime, THREAD)))

    def test_nothing_revised_has_survived(self) -> None:
        self._ready()
        self.assertTrue(cr.target_survived(cr.entry_for(self.runtime, THREAD)))

    def test_a_revision_needs_a_confirmation_to_revise(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        with self.assertRaises(cr.ReadinessError):
            cr.revise(self.runtime, THREAD, target_condition="a different target entirely")

    def test_an_unknown_revision_kind_is_refused(self) -> None:
        """A third label would silently join the survival count as 'not replace'."""
        self._ready()
        with self.assertRaises(cr.ReadinessError):
            cr.revise(self.runtime, THREAD, target_condition="something else here", kind="tweak")

    def test_a_no_op_revision_is_refused(self) -> None:
        """A history row saying nothing changed makes the survival count noise."""
        self._ready()
        with self.assertRaises(cr.ReadinessError):
            cr.revise(self.runtime, THREAD, target_condition=CONDITION)

    def test_the_overlap_is_recorded_beside_the_declared_kind(self) -> None:
        """Evidence beside the label, so the labels can be audited later."""
        self._ready()
        cr.revise(self.runtime, THREAD, target_condition=CONDITION + " and the tests name it")
        near = cr.entry_for(self.runtime, THREAD)["target_history"][0]["overlap_with_next"]
        cr.revise(
            self.runtime,
            THREAD,
            target_condition="the eddy bar renders temperature on the parent channel",
            kind=cr.REPLACE,
        )
        far = cr.entry_for(self.runtime, THREAD)["target_history"][1]["overlap_with_next"]
        self.assertGreater(near, far)

    # --- staleness --------------------------------------------------------

    def test_an_eddy_that_kept_talking_reads_stale(self) -> None:
        """The live case: confirmed 08:53, the conversation moved at 09:00."""
        self._ready()
        entry = cr.entry_for(self.runtime, THREAD)
        later = (datetime.now(timezone.utc) + timedelta(minutes=7)).isoformat()
        self.assertTrue(cr.is_stale_ready(entry, later))

    def test_a_quiet_confirmed_eddy_is_not_stale(self) -> None:
        self._ready()
        entry = cr.entry_for(self.runtime, THREAD)
        earlier = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.assertFalse(cr.is_stale_ready(entry, earlier))

    def test_revising_clears_the_staleness(self) -> None:
        """Otherwise the flag is permanent and stops meaning anything."""
        self._ready()
        mid = datetime.now(timezone.utc).isoformat()
        cr.revise(self.runtime, THREAD, target_condition=CONDITION + " and topics are eddies")
        self.assertFalse(cr.is_stale_ready(cr.entry_for(self.runtime, THREAD), mid))

    def test_only_a_ready_row_can_be_stale(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.assertFalse(cr.is_stale_ready(cr.entry_for(self.runtime, THREAD), later))

    def test_staleness_survives_unreadable_timestamps(self) -> None:
        self._ready()
        entry = cr.entry_for(self.runtime, THREAD)
        for bad in (None, "", "not a date"):
            with self.subTest(value=bad):
                self.assertFalse(cr.is_stale_ready(entry, bad))

    # --- the gate refuses shape, not size ---------------------------------

    def test_a_thin_target_is_valid(self) -> None:
        """Small is the point of the model; unstatable is the failure."""
        cr.propose(self.runtime, THREAD, target_condition="topics are eddies")
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.PROPOSED)

    def test_a_machine_target_that_reads_as_an_action_is_refused(self) -> None:
        """44 characters, sails through the length floor, useless to a session."""
        with self.assertRaises(cr.ReadinessError):
            cr.propose(
                self.runtime,
                THREAD,
                target_condition="write a specification for channel primitives",
                by="turtle",
            )

    def test_his_own_wording_is_authoritative(self) -> None:
        """A false refusal of his sentence costs more than an imperfect target."""
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(
            self.runtime,
            THREAD,
            target_condition="write the primitives spec, topics as eddies",
            by=cr.PRACTITIONER,
        )
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.READY)

    # --- the spark --------------------------------------------------------

    SPARK = "whether channel primitives are relational or thematic is undecided"

    def test_a_spark_leaves_the_eddy_waiting_on_him(self) -> None:
        """No fifth state: after a spark the ball genuinely is in his court."""
        entry = cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)
        self.assertEqual(entry["state"], cr.WAITING)
        self.assertEqual(entry["waiting_on"], cr.WAITING_ON_PRACTITIONER)
        self.assertEqual(entry["spark_count"], 1)

    def test_a_spark_needs_a_delta(self) -> None:
        for empty in ("", "   ", None):
            with self.subTest(value=empty):
                with self.assertRaises(cr.ReadinessError):
                    cr.mark_sparked(self.runtime, THREAD, spark=empty)

    def test_a_second_spark_into_silence_is_refused(self) -> None:
        """Scarcity enforced against something observable, not a session counter.

        The moves channel and the handoff flag both died of a mechanism that kept
        speaking into silence; this is that lesson as a guard.
        """
        cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)
        quiet = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with self.assertRaises(cr.ReadinessError):
            cr.mark_sparked(self.runtime, THREAD, spark="a different delta entirely", last_activity=quiet)

    def test_a_second_spark_is_allowed_once_he_has_spoken(self) -> None:
        cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)
        spoke = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        entry = cr.mark_sparked(
            self.runtime, THREAD, spark="a different delta entirely", last_activity=spoke
        )
        self.assertEqual(entry["spark_count"], 2)

    def test_an_eddy_with_a_target_is_not_sparked(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        with self.assertRaises(cr.ReadinessError):
            cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)

    def test_spark_worked_asks_whether_a_target_followed(self) -> None:
        """Not "does it read well" — whether the eddy crossed into work."""
        self.assertIsNone(cr.spark_worked(cr.entry_for(self.runtime, THREAD)))
        cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)
        self.assertFalse(cr.spark_worked(cr.entry_for(self.runtime, THREAD)))
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        self.assertTrue(cr.spark_worked(cr.entry_for(self.runtime, THREAD)))

    def test_a_suggested_delta_is_recorded_without_changing_state(self) -> None:
        """Recorded, never posted — a delta in every idle eddy is the clutter."""
        cr.record_suggested_spark(self.runtime, THREAD, self.SPARK)
        entry = cr.entry_for(self.runtime, THREAD)
        self.assertEqual(entry["suggested_spark"], self.SPARK)
        self.assertIsNone(entry.get("state"))

    def test_a_suggestion_is_not_recorded_over_a_target(self) -> None:
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        self.assertIsNone(cr.record_suggested_spark(self.runtime, THREAD, self.SPARK))

    def test_posting_a_spark_clears_the_suggestion_it_came_from(self) -> None:
        cr.record_suggested_spark(self.runtime, THREAD, self.SPARK)
        entry = cr.mark_sparked(self.runtime, THREAD, spark=self.SPARK)
        self.assertNotIn("suggested_spark", entry)

    # --- the shared sidecar ----------------------------------------------

    def test_readiness_does_not_disturb_the_prepared_lifecycle(self) -> None:
        """One file, two concerns. A write to either must not lose the other."""
        save_sidecar(
            self.runtime,
            {"prepared": {str(THREAD): {"surface": "craft/s.md", "disposition": "open"}}},
        )
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        data = load_sidecar(self.runtime)
        self.assertEqual(data["prepared"][str(THREAD)]["disposition"], "open")
        self.assertEqual(data["readiness"][str(THREAD)]["state"], cr.READY)

    def test_an_eddy_with_no_workspace_can_still_be_ready(self) -> None:
        """The defect this module exists for: readiness required a surface."""
        cr.propose(self.runtime, THREAD, target_condition=CONDITION)
        cr.confirm(self.runtime, THREAD)
        self.assertEqual(load_sidecar(self.runtime).get("prepared"), {})
        self.assertEqual(cr.state_of(self.runtime, THREAD), cr.READY)

    # --- temperature ------------------------------------------------------

    def _ago(self, hours: float) -> str:
        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    def test_temperature_reads_recency_when_nothing_is_claimed(self) -> None:
        cases = [(1, cr.HOT), (12, cr.WARM), (72, cr.COLD), (400, cr.COLD)]
        for hours, expected in cases:
            with self.subTest(hours=hours):
                self.assertEqual(
                    cr.temperature(state=None, last_practitioner_message_at=self._ago(hours)),
                    expected,
                )

    def test_readiness_outranks_idleness(self) -> None:
        """A confirmed eddy that went quiet is waiting for a session, not cooling."""
        for state in (cr.PROPOSED, cr.READY):
            with self.subTest(state=state):
                self.assertEqual(
                    cr.temperature(state=state, last_practitioner_message_at=self._ago(400)),
                    cr.TEMP_READY,
                )

    def test_a_refusal_keeps_an_eddy_warm_past_the_ordinary_threshold(self) -> None:
        """A refusal leaves an open question, and a question is heat."""
        quiet = self._ago(72)
        self.assertEqual(cr.temperature(state=cr.REFUSED, last_practitioner_message_at=quiet), cr.WARM)
        self.assertEqual(cr.temperature(state=None, last_practitioner_message_at=quiet), cr.COLD)

    def test_an_acted_eddy_reads_cooling(self) -> None:
        self.assertEqual(
            cr.temperature(state=cr.ACTED, last_practitioner_message_at=self._ago(1)),
            cr.COOLING,
        )

    def test_temperature_survives_an_unreadable_timestamp(self) -> None:
        """A glance must never raise — the parent surface renders many rows."""
        for bad in (None, "", "not a date", "2026-13-45"):
            with self.subTest(value=bad):
                self.assertEqual(
                    cr.temperature(state=None, last_practitioner_message_at=bad), cr.COLD
                )

    def test_naive_timestamps_are_read_as_utc_rather_than_crashing(self) -> None:
        naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        self.assertEqual(
            cr.temperature(state=None, last_practitioner_message_at=naive.isoformat()),
            cr.HOT,
        )


if __name__ == "__main__":
    unittest.main()
