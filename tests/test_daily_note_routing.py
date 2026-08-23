"""Daily-note delivery routes to the owning river, never the global channel.

INT-042: every practice root's daily note was published into the operator's
river because delivery resolved through DISCORD_CHANNEL_DIALOGUE rather than
the root the note was synthesized for. A hosted practitioner's private daily
synthesis reached the host's channel under a "your day in story" embed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", sys.modules["discord"])
sys.modules.setdefault("discord.ext.tasks", sys.modules["discord"])

import mage
import story_daily


OPERATOR_RIVER = 1479428854513664030
HOSTED_RIVER = 201
FAMILY_CHANNEL = 202


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "kermit": {"practice_dir": f"{tmp}/kermit", "primary": True},
            "partner": {"practice_dir": f"{tmp}/partner"},
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["kermit", "partner"],
            },
        },
        "channels": {
            str(OPERATOR_RIVER): {"mage": "kermit", "type": "river"},
            str(HOSTED_RIVER): {"mage": "partner", "type": "hosted-river"},
            str(FAMILY_CHANNEL): {"mage": "family", "type": "shared-river"},
        },
    }


class RiverResolutionTests(unittest.TestCase):
    def test_each_root_resolves_to_its_own_river(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertEqual(
                    mage.river_channel_id_for_practice_dir(f"{tmp}/kermit"),
                    OPERATOR_RIVER,
                )
                self.assertEqual(
                    mage.river_channel_id_for_practice_dir(f"{tmp}/partner"),
                    HOSTED_RIVER,
                )

    def test_hosted_root_never_resolves_to_the_operator_river(self) -> None:
        """The INT-042 regression, stated directly."""
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertNotEqual(
                    mage.river_channel_id_for_practice_dir(f"{tmp}/partner"),
                    OPERATOR_RIVER,
                )

    def test_shared_space_root_resolves_to_no_river(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertIsNone(
                    mage.river_channel_id_for_practice_dir(f"{tmp}/family")
                )

    def test_unregistered_root_resolves_to_no_river(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertIsNone(
                    mage.river_channel_id_for_practice_dir(f"{tmp}/stranger")
                )

    def test_vanilla_install_without_registry_falls_back_to_dialogue(self) -> None:
        """Single-practitioner install: no channels registered, dialogue is it."""
        with patch.object(mage, "_MAGE_REGISTRY", {"mages": {}, "channels": {}}):
            with patch.object(
                mage, "_resolve_dialogue_channel_id", return_value=OPERATOR_RIVER
            ):
                self.assertEqual(
                    mage.river_channel_id_for_practice_dir("~/workshops/default"),
                    OPERATOR_RIVER,
                )


class DailyNotePostingTests(unittest.IsolatedAsyncioTestCase):
    def _result(self, root: Path) -> story_daily.DailyNoteResult:
        note = root / "story" / "daily" / "2026-07-27.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("---\ndate: '2026-07-27'\n---\n\nBody.\n", encoding="utf-8")
        return story_daily.DailyNoteResult(note, "preview", True)

    async def test_hosted_note_posts_to_hosted_river(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            result = self._result(Path(tmp, "partner"))
            send = AsyncMock()
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch("artifact_presenter.send_artifact_surface", send),
                patch.object(story_daily, "build_daily_note_surface", return_value=MagicMock()),
            ):
                await story_daily.post_daily_note_river_visibility(
                    date(2026, 7, 27), result
                )
            send.assert_awaited_once()
            self.assertEqual(send.await_args.args[0], HOSTED_RIVER)

    async def test_shared_space_note_is_not_posted_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("kermit", "partner", "family"):
                Path(tmp, name).mkdir()
            result = self._result(Path(tmp, "family"))
            send = AsyncMock()
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch("artifact_presenter.send_artifact_surface", send),
                patch.object(story_daily, "build_daily_note_surface", return_value=MagicMock()),
            ):
                await story_daily.post_daily_note_river_visibility(
                    date(2026, 7, 27), result
                )
            send.assert_not_awaited()

    async def test_uncreated_note_is_not_posted(self) -> None:
        result = story_daily.DailyNoteResult(None, "", False)
        send = AsyncMock()
        with patch("artifact_presenter.send_artifact_surface", send):
            await story_daily.post_daily_note_river_visibility(
                date(2026, 7, 27), result
            )
        send.assert_not_awaited()



class SharedSpaceDeliveryTests(unittest.IsolatedAsyncioTestCase):
    """Nothing is delivered into or out of a shared space (INT-048).

    Per-member notes used to carry a space's day to each member's river and
    inverted whose day they told; the delivery they existed for is withdrawn
    and the synthesis with it. The communal record is still written — it is
    the space's record, and retrieval reads it — but it goes nowhere.
    """

    async def test_shared_root_synthesis_delivers_nothing(self) -> None:
        import story_daily

        send = AsyncMock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "family")
            (root / "story" / "daily").mkdir(parents=True)
            note = root / "story" / "daily" / "2026-07-28.md"
            note.write_text("---\ndate: '2026-07-28'\n---\n\nThe space's day.\n")
            result = story_daily.DailyNoteResult(
                note_path=note, preview_text="The space's day.", created=True
            )
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch("artifact_presenter.send_artifact_surface", send),
            ):
                await story_daily.post_daily_note_river_visibility(
                    date(2026, 7, 28), result
                )
        send.assert_not_awaited()

    def test_per_member_synthesis_is_gone(self) -> None:
        """Removed, not disabled — a dormant inverting path is latent by position."""
        import story_daily

        for name in (
            "write_member_daily_notes",
            "post_member_daily_notes",
            "MemberNoteResult",
            "_MEMBER_SYSTEM_PROMPT",
            "MEMBER_NOTES_WITHHELD",
        ):
            self.assertFalse(
                hasattr(story_daily, name),
                f"{name} survived the withdrawal — remove it, don't flag it",
            )


if __name__ == "__main__":
    unittest.main()
