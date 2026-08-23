"""Nothing carries into a shared room unconfirmed (INT-047).

``set_last_checkpoint`` fires on *every* idle checkpoint — unconfirmed and
model-authored — and writes to the practice root. In a personal root that is
"where we left off" and is exactly right. In a shared space it is one member's
last moment, persisted at the root both members read, and recited into every
turn of the room by ``render_substrate_packet``.

The consent gate the practice already has (``continuity_confirm``, CE Slice 2)
is reachable only from a manual ``!checkpoint``. This guard closes the ungated
door until the confirm ask moves to re-entry.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Stub only when the real dependency is absent (dev machines without the
# runtime installed). Never alias ``discord.ext`` to the ``discord`` module:
# under unittest discovery sys.modules is process-global, so an early test
# module doing that shadows the real ``discord.ext`` for every module imported
# after it — which fails as "cannot import name 'tasks' from 'discord'" in
# files that have nothing to do with this one.
try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import continuity_engine as ce
import mage


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "kermit": {"practice_dir": f"{tmp}/kermit", "address": "Kermit"},
            "partner": {"practice_dir": f"{tmp}/partner", "address": "Partner"},
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["kermit", "partner"],
            },
            "solo_space": {
                "practice_dir": f"{tmp}/solo_space",
                "members": ["kermit"],
            },
        },
        "channels": {},
    }


LINE = "Kermit expressed difficulty with the framing; Partner countered."


class CarryGuardTests(unittest.TestCase):
    def test_personal_root_still_carries(self) -> None:
        """The regression floor — a solo river must keep its continuity."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.set_last_checkpoint(f"{tmp}/kermit", LINE)
                self.assertEqual(
                    (ce.read_current(f"{tmp}/kermit") or {}).get(
                        "last_checkpoint_one_liner"
                    ),
                    LINE,
                )

    def test_shared_space_does_not_carry(self) -> None:
        """The defect, stated directly."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.set_last_checkpoint(f"{tmp}/family", LINE)
                self.assertIsNone(
                    (ce.read_current(f"{tmp}/family") or {}).get(
                        "last_checkpoint_one_liner"
                    ),
                )

    def test_single_member_space_is_the_degenerate_case(self) -> None:
        """One member → one referent → carrying is safe. No special-casing."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.set_last_checkpoint(f"{tmp}/solo_space", LINE)
                self.assertEqual(
                    (ce.read_current(f"{tmp}/solo_space") or {}).get(
                        "last_checkpoint_one_liner"
                    ),
                    LINE,
                )

    def test_unregistered_root_carries(self) -> None:
        """Vanilla registry-less install keeps single-practitioner behaviour."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", {}):
                ce.set_last_checkpoint(f"{tmp}/anywhere", LINE)
                self.assertEqual(
                    (ce.read_current(f"{tmp}/anywhere") or {}).get(
                        "last_checkpoint_one_liner"
                    ),
                    LINE,
                )

    def test_unresolvable_membership_fails_closed(self) -> None:
        """Resolution failure withholds rather than falling back to ambient."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                mage,
                "space_members_for_practice_dir",
                side_effect=RuntimeError("registry unreadable"),
            ):
                ce.set_last_checkpoint(f"{tmp}/kermit", LINE)
                self.assertIsNone(
                    (ce.read_current(f"{tmp}/kermit") or {}).get(
                        "last_checkpoint_one_liner"
                    ),
                )

    def test_shared_space_packet_carries_no_checkpoint_line(self) -> None:
        """End to end: the room's packet must not recite an unconfirmed line."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                ce.set_last_checkpoint(f"{tmp}/family", LINE)
                block = ce.render_substrate_packet(f"{tmp}/family")
                self.assertNotIn("Last checkpoint:", block)
                self.assertNotIn("Partner countered", block)


if __name__ == "__main__":
    unittest.main()
