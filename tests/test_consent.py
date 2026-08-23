"""Consent resolution — fail-closed, unanimous for rooms, silent about who.

Fixtures use role keys (``operator``, ``member_b``, ``guest``) rather than real
names. ``tests/`` still carries ~153 name hits from earlier fixtures; this file
does not add to them.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import consent
import mage

ROOT = "/tmp/consent-fixture"


def _consent(
    *,
    self_c: bool = True,
    room: bool = True,
    operator: bool = True,
    answered: bool = True,
    removal: str | None = None,
) -> dict:
    block: dict = {
        "grants": {
            consent.SELF_CONTINUITY: self_c,
            consent.ROOM_CONTINUITY: room,
            consent.OPERATOR_ACCESS: operator,
        },
        "words": "recorded verbatim",
    }
    if answered:
        block["answered_at"] = "2026-08-03"
    if removal is not None:
        block["removal"] = removal
    return block


def _registry(**overrides) -> dict:
    """Operator granted everything; member_b granted everything; guest silent."""
    reg = {
        "mages": {
            "operator": {"practice_dir": f"{ROOT}/operator", "consent": _consent()},
            "member_b": {"practice_dir": f"{ROOT}/member_b", "consent": _consent()},
            "guest": {"practice_dir": f"{ROOT}/guest"},
        },
        "spaces": {
            "shared": {
                "practice_dir": f"{ROOT}/shared",
                "members": ["operator", "member_b"],
            },
            "with_guest": {
                "practice_dir": f"{ROOT}/with_guest",
                "members": ["operator", "guest"],
            },
            "empty_room": {"practice_dir": f"{ROOT}/empty_room", "members": []},
        },
        "channels": {},
    }
    for path, value in overrides.items():
        section, key, field = path.split("__")
        reg[section][key][field] = value
    return reg


class _Base(unittest.TestCase):
    def _patch(self, registry: dict | None = None):
        return patch.object(mage, "_MAGE_REGISTRY", registry or _registry())


class FailClosed(_Base):
    """Every unknown must land on no. The allowlist discipline."""

    def test_granted_purpose_passes(self) -> None:
        """The positive control: a real yes must actually return True.

        Without this the whole suite is satisfiable by ``return False``, which
        is the shape of a guard that reports success while blind.
        """
        with self._patch():
            for purpose in consent.PURPOSES:
                self.assertTrue(consent.may(purpose, f"{ROOT}/operator"), purpose)

    def test_absent_record_denies(self) -> None:
        with self._patch():
            for purpose in consent.PURPOSES:
                self.assertFalse(consent.may(purpose, f"{ROOT}/guest"), purpose)

    def test_unregistered_root_denies(self) -> None:
        with self._patch():
            self.assertFalse(
                consent.may(consent.OPERATOR_ACCESS, "/tmp/nowhere-at-all")
            )

    def test_unknown_purpose_denies(self) -> None:
        with self._patch():
            self.assertFalse(consent.may("exfiltrate", f"{ROOT}/operator"))

    def test_truthy_is_not_true(self) -> None:
        """Only an explicit ``True`` grants — not "yes", not 1, not "no"."""
        for junk in ("yes", 1, "true", "no", None, []):
            reg = _registry()
            reg["mages"]["operator"]["consent"]["grants"][
                consent.OPERATOR_ACCESS
            ] = junk
            with self._patch(reg):
                self.assertFalse(
                    consent.may(consent.OPERATOR_ACCESS, f"{ROOT}/operator"),
                    f"{junk!r} must not grant",
                )

    def test_malformed_block_denies(self) -> None:
        for junk in ("granted", [], None, {"grants": "all"}):
            reg = _registry()
            reg["mages"]["operator"]["consent"] = junk
            with self._patch(reg):
                self.assertFalse(consent.may(consent.SELF_CONTINUITY, f"{ROOT}/operator"))


class SeparableGrants(_Base):
    """C2 — refusing operator-access must not touch the other two."""

    def test_operator_refusal_leaves_practice_intact(self) -> None:
        reg = _registry()
        reg["mages"]["operator"]["consent"]["grants"][consent.OPERATOR_ACCESS] = False
        with self._patch(reg):
            self.assertFalse(consent.may(consent.OPERATOR_ACCESS, f"{ROOT}/operator"))
            self.assertTrue(consent.may(consent.SELF_CONTINUITY, f"{ROOT}/operator"))
            self.assertTrue(consent.may(consent.ROOM_CONTINUITY, f"{ROOT}/operator"))


class Unanimity(_Base):
    """A room remembers only while every member has agreed."""

    def test_all_members_granted_remembers(self) -> None:
        with self._patch():
            self.assertTrue(consent.may(consent.ROOM_CONTINUITY, f"{ROOT}/shared"))
            self.assertTrue(consent.room_status(f"{ROOT}/shared")["remembering"])

    def test_one_silent_member_stops_the_room(self) -> None:
        with self._patch():
            self.assertFalse(consent.may(consent.ROOM_CONTINUITY, f"{ROOT}/with_guest"))
            self.assertFalse(consent.room_status(f"{ROOT}/with_guest")["remembering"])

    def test_one_refusal_stops_the_room(self) -> None:
        reg = _registry()
        reg["mages"]["member_b"]["consent"]["grants"][consent.ROOM_CONTINUITY] = False
        with self._patch(reg):
            self.assertFalse(consent.may(consent.ROOM_CONTINUITY, f"{ROOT}/shared"))

    def test_memberless_room_denies(self) -> None:
        """An empty member list must not vacuously satisfy ``all()``."""
        with self._patch():
            self.assertFalse(consent.may(consent.ROOM_CONTINUITY, f"{ROOT}/empty_room"))

    def test_membership_is_not_the_gate(self) -> None:
        """Nobody is excluded — the room is registered, it just isn't keeping."""
        with self._patch():
            status = consent.room_status(f"{ROOT}/with_guest")
            self.assertTrue(status["registered"])
            self.assertFalse(status["remembering"])


class DoesNotNameWhoIsOutstanding(_Base):
    """Peer pressure with a name attached is the failure mode."""

    def test_room_status_reports_a_count_not_a_list(self) -> None:
        with self._patch():
            status = consent.room_status(f"{ROOT}/with_guest")
            self.assertEqual(status["pending"], 1)
            flat = repr(status)
            for key in ("guest", "operator", "member_b"):
                self.assertNotIn(key, flat, "room status must not name members")

    def test_delivery_list_is_a_separate_call(self) -> None:
        """The ask has to reach someone; that path is deliberately not the surface."""
        with self._patch():
            self.assertEqual(consent.unanswered_members(f"{ROOT}/with_guest"), ["guest"])
            self.assertEqual(consent.unanswered_members(f"{ROOT}/shared"), [])


class RefusalIsTwoAnswers(_Base):
    """"Stop from here" and "stop and remove" are different intentions."""

    def test_default_is_keep_not_remove(self) -> None:
        """The irreversible reading must never be the default reading."""
        with self._patch():
            self.assertEqual(consent.removal_choice("guest"), consent.REMOVAL_KEEP)
            self.assertEqual(consent.removal_choice("operator"), consent.REMOVAL_KEEP)

    def test_explicit_remove_is_carried(self) -> None:
        reg = _registry()
        reg["mages"]["member_b"]["consent"]["removal"] = consent.REMOVAL_REMOVE
        with self._patch(reg):
            self.assertEqual(consent.removal_choice("member_b"), consent.REMOVAL_REMOVE)

    def test_junk_removal_falls_back_to_keep(self) -> None:
        for junk in ("delete", "REMOVE", True, None, 1):
            reg = _registry()
            reg["mages"]["member_b"]["consent"]["removal"] = junk
            with self._patch(reg):
                self.assertEqual(
                    consent.removal_choice("member_b"), consent.REMOVAL_KEEP
                )

    def test_consent_record_is_exempt_from_deletion(self) -> None:
        """Keeping the words is how we know not to start again (§2.2)."""
        self.assertIn("consent", consent.DELETION_EXEMPT_KEYS)


class Answered(_Base):
    """An unanswered question is not a refusal — it is silence, and it is stable."""

    def test_silence_is_not_an_answer(self) -> None:
        with self._patch():
            self.assertFalse(consent.answered("guest"))
            self.assertTrue(consent.answered("operator"))

    def test_grants_without_a_date_do_not_count_as_answered(self) -> None:
        reg = _registry()
        reg["mages"]["operator"]["consent"].pop("answered_at")
        with self._patch(reg):
            self.assertFalse(consent.answered("operator"))


class RequireGate(_Base):
    def test_require_passes_when_granted(self) -> None:
        with self._patch():
            consent.require(consent.OPERATOR_ACCESS, f"{ROOT}/operator")

    def test_require_raises_with_a_reason(self) -> None:
        with self._patch():
            with self.assertRaises(consent.ConsentWithheld) as ctx:
                consent.require(consent.OPERATOR_ACCESS, f"{ROOT}/guest")
            self.assertEqual(ctx.exception.reason, "no answer recorded")

    def test_declined_reads_differently_from_silent(self) -> None:
        reg = _registry()
        reg["mages"]["member_b"]["consent"]["grants"][consent.OPERATOR_ACCESS] = False
        with self._patch(reg):
            with self.assertRaises(consent.ConsentWithheld) as ctx:
                consent.require(consent.OPERATOR_ACCESS, f"{ROOT}/member_b")
            self.assertEqual(ctx.exception.reason, "declined")

    def test_unregistered_root_names_that_as_the_reason(self) -> None:
        with self._patch():
            with self.assertRaises(consent.ConsentWithheld) as ctx:
                consent.require(consent.SELF_CONTINUITY, "/tmp/nowhere-at-all")
            self.assertIn("not registered", ctx.exception.reason)


class ShellGate(_Base):
    def test_cli_exit_codes(self) -> None:
        with self._patch():
            self.assertEqual(
                consent._main(["consent.py", f"{ROOT}/operator", consent.OPERATOR_ACCESS]),
                0,
            )
            self.assertEqual(
                consent._main(["consent.py", f"{ROOT}/guest", consent.OPERATOR_ACCESS]),
                1,
            )
            self.assertEqual(consent._main(["consent.py"]), 2)


if __name__ == "__main__":
    unittest.main()
