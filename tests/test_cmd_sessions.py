"""Tests for session lifecycle command handlers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())

import cmd_sessions as cs
import story_notes
from sessions import CheckpointResult, DissolveResult


class _FakeEmbed:
    def __init__(self, *, title=None, description=None, color=None):
        self.title = title
        self.description = description
        self.color = color

    def set_footer(self, *, text):
        self.footer = text

    def add_field(self, *, name, value, inline=False):
        pass


class _FakeThread:
    parent_id = None


PRACTICE_ROOT = "/tmp/practice-036-test"


def _eddy_note(preview: str = "This eddy held a plan to move walks earlier.") -> story_notes.EddyNoteResult:
    """A note result whose file deliberately does NOT exist on disk — reply
    construction must consume CheckpointResult.eddy_note, never re-read."""
    return story_notes.EddyNoteResult(
        note_path=Path(PRACTICE_ROOT) / "story" / "eddies" / "2-morning-walk.md",
        entry_text="---\nthread: '2'\n---\n\nfull entry body\n",
        preview_text=preview,
    )


class TestCmdCheckpoint(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_short_history(self) -> None:
        message = MagicMock()
        message.channel.id = 1
        message.reply = AsyncMock()

        with patch("cmd_sessions.get_history", return_value=[{"role": "user", "content": "hi"}]), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "hi"}]
        ):
            await cs.cmd_checkpoint(message)

        message.reply.assert_awaited_once()
        self.assertIn("Not enough", message.reply.await_args[0][0])

    async def test_posts_embed_on_success(self) -> None:
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        result = CheckpointResult(session_note="2026-06-20.md")

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch("sessions.checkpoint_session", new_callable=AsyncMock, return_value=result), patch(
            "cmd_sessions.mark_artifacts_ui_unlocked"
        ):
            await cs.cmd_checkpoint(message)

        embed = message.reply.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Checkpoint saved")

    async def test_manual_checkpoint_surfaces_note_preview_and_link(self) -> None:
        """TURTLE_SPEC §8.4 checkpoint visibility (issue 036): the manual
        checkpoint reply carries the eddy-note inline preview (expandable
        code block) + the artifact open action for the browser link — all
        consumed from CheckpointResult.eddy_note, never re-read from disk."""
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        note = _eddy_note()
        result = CheckpointResult(
            trigger="manual", session_note="2026-07-15.md", eddy_note=note
        )

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
            "cmd_sessions.get_pd", return_value=PRACTICE_ROOT
        ), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ) as reply:
            await cs.cmd_checkpoint(message)

        surface = reply.await_args.args[1]
        # Inline preview: the artifact-viewer expandable code-block pattern.
        self.assertIsNotNone(surface.content)
        self.assertIn("```md", surface.content)
        self.assertIn(note.preview_text, surface.content)
        # Browser link: practice-relative path through the existing
        # artifact open-action mechanism (link button when a URL resolves).
        self.assertIn(
            ("Open note", "!read story/eddies/2-morning-walk.md"),
            surface.open_actions,
        )
        # The embed names the note artifact.
        self.assertIn("story/eddies/2-morning-walk.md", surface.embed.description)

    async def test_manual_checkpoint_no_note_renders_no_preview(self) -> None:
        """When the reflection degraded (eddy_note is None) but flow captures
        landed, the reply must not render an empty preview block."""
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        result = CheckpointResult(
            trigger="manual", flow_writes=["state/notes/navigator-last.md"]
        )

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ) as reply:
            await cs.cmd_checkpoint(message)

        surface = reply.await_args.args[1]
        self.assertIsNone(surface.content)
        self.assertNotIn(
            "Open note", [label for label, _cmd in surface.open_actions]
        )

    async def test_manual_checkpoint_nothing_captured_keeps_honest_copy(self) -> None:
        """Degradation (035): a deliberate !checkpoint that produced nothing
        keeps the honest no-capture copy — no cooldown blame, no preview."""
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        ack = MagicMock()
        ack.edit = AsyncMock()
        message.reply.return_value = ack

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch(
            "sessions.checkpoint_session",
            new_callable=AsyncMock,
            return_value=CheckpointResult(trigger="manual"),
        ), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ) as reply:
            await cs.cmd_checkpoint(message)

        reply.assert_not_awaited()
        edited = ack.edit.await_args.kwargs["content"]
        self.assertIn("didn't produce a usable note", edited)
        self.assertNotIn("```", edited)
        self.assertNotIn("cooldown", edited.lower())

    async def test_note_link_degrades_to_preview_only_outside_practice_root(self) -> None:
        """Graceful fallback: a note path outside the practice root cannot
        make a practice-relative link — preview still renders, no dead link."""
        message = MagicMock()
        message.channel.id = 2
        message.reply = AsyncMock()
        note = _eddy_note()
        result = CheckpointResult(trigger="manual", eddy_note=note)

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=[{"role": "user", "content": "a"}] * 4
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
            "cmd_sessions.get_pd", return_value="/somewhere/else"
        ), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ) as reply:
            await cs.cmd_checkpoint(message)

        surface = reply.await_args.args[1]
        self.assertIn(note.preview_text, surface.content or "")
        self.assertNotIn(
            "Open note", [label for label, _cmd in surface.open_actions]
        )


class TestLifecycleBarCheckpointParity(unittest.IsolatedAsyncioTestCase):
    """F1 (036 review): the lifecycle-bar Checkpoint button shares
    cmd_checkpoint through the real _LifecycleInteractionMessage adapter.
    The adapter must hand back the sent message so the ack lifecycle
    (edit on no-capture, delete before the preview surface) survives the
    bar path — and the preview surface must actually be sent."""

    def _bar_message(self):
        from eddy_lifecycle_bar import _LifecycleInteractionMessage

        sent: list[tuple[MagicMock, dict]] = []

        async def _send(**kwargs):
            posted = MagicMock()
            posted.edit = AsyncMock()
            posted.delete = AsyncMock()
            sent.append((posted, kwargs))
            return posted

        interaction = MagicMock()
        interaction.channel = MagicMock()
        interaction.channel.id = 7
        interaction.message = MagicMock()
        interaction.message.id = 99
        interaction.followup.send = AsyncMock(side_effect=_send)
        message = _LifecycleInteractionMessage(
            interaction, "!checkpoint", from_lifecycle_bar=True
        )
        return message, sent

    async def test_bar_checkpoint_sends_preview_surface_without_error(self) -> None:
        message, sent = self._bar_message()
        note = _eddy_note()
        result = CheckpointResult(
            trigger="manual", session_note="2026-07-15.md", eddy_note=note
        )

        view = MagicMock()
        view.children = [MagicMock()]
        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}] * 4,
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.mark_artifacts_ui_unlocked"), patch(
            "cmd_sessions.get_pd", return_value=PRACTICE_ROOT
        ), patch(
            # Real reply_artifact_surface; only the button View is stubbed
            # (under the module-level discord mock the real subclass is a
            # shared mock that cannot be constructed twice per process).
            "artifact_presenter.ArtifactPresenterView",
            return_value=view,
        ):
            # Must not raise — pre-fix the adapter returned None and the ack
            # delete crashed with AttributeError on the bar path.
            await cs.cmd_checkpoint(message)

        self.assertEqual(len(sent), 2)
        ack, ack_kwargs = sent[0]
        self.assertEqual(ack_kwargs["embed"].title, "Checkpointing…")
        ack.delete.assert_awaited_once()
        _surface_msg, surface_kwargs = sent[1]
        self.assertIn("```md", surface_kwargs.get("content") or "")
        self.assertIn(note.preview_text, surface_kwargs["content"])
        self.assertEqual(surface_kwargs["embed"].title, "Checkpoint saved")

    async def test_bar_checkpoint_no_capture_edits_ack_without_error(self) -> None:
        message, sent = self._bar_message()

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}] * 4,
        ), patch(
            "sessions.checkpoint_session",
            new_callable=AsyncMock,
            return_value=CheckpointResult(trigger="manual"),
        ):
            await cs.cmd_checkpoint(message)

        self.assertEqual(len(sent), 1)
        ack, _kwargs = sent[0]
        ack.edit.assert_awaited_once()
        edited = ack.edit.await_args.kwargs["content"]
        self.assertIn("didn't produce a usable note", edited)


class TestCmdRelease(unittest.IsolatedAsyncioTestCase):
    async def test_clears_history(self) -> None:
        from state import active_sessions, dialogue_histories

        channel_id = 3
        dialogue_histories[channel_id] = [{"role": "user", "content": "a"}]
        active_sessions[channel_id] = {"closed": False}
        message = MagicMock()
        message.channel.id = channel_id
        message.reply = AsyncMock()

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history", return_value=dialogue_histories[channel_id] * 2
        ), patch("sessions.checkpoint_session", new_callable=AsyncMock, return_value=CheckpointResult()), patch(
            "cmd_sessions.clear_history"
        ) as clear_mock, patch(
            "cmd_sessions.read_safe", return_value=""
        ), patch("cmd_sessions.get_mage_name", return_value="Kermit"):
            await cs.cmd_release(message)

        clear_mock.assert_called_once_with(channel_id)
        self.assertNotIn(channel_id, active_sessions)

    async def test_release_surfaces_note_preview_and_link(self) -> None:
        """Release runs checkpoint first (§8.4) — the release reply carries
        the same eddy-note preview + open action as a manual checkpoint."""
        message = MagicMock()
        message.channel.id = 6
        message.reply = AsyncMock()
        note = _eddy_note("Release preview sentence.")
        result = CheckpointResult(
            trigger="release", session_note="2026-07-15.md", eddy_note=note
        )

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}] * 4,
        ), patch(
            "sessions.checkpoint_session", new_callable=AsyncMock, return_value=result
        ), patch("cmd_sessions.clear_history"), patch(
            "cmd_sessions.mark_artifacts_ui_unlocked"
        ), patch("cmd_sessions.get_pd", return_value=PRACTICE_ROOT), patch(
            "cmd_sessions.get_mage_name", return_value="Kermit"
        ), patch(
            "cmd_sessions.reply_artifact_surface", new_callable=AsyncMock
        ) as reply:
            await cs.cmd_release(message)

        surface = reply.await_args.args[1]
        self.assertIn("Release preview sentence.", surface.content or "")
        self.assertIn("```md", surface.content)
        self.assertIn(
            ("Open note", "!read story/eddies/2-morning-walk.md"),
            surface.open_actions,
        )
        self.assertIn("story/eddies/2-morning-walk.md", surface.embed.description)

    async def test_release_embed_honest_when_nothing_captured(self) -> None:
        message = MagicMock()
        message.channel.id = 5
        message.reply = AsyncMock()

        with patch("cmd_sessions.discord.Embed", _FakeEmbed), patch(
            "cmd_sessions.reload_history",
            return_value=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        ), patch(
            "sessions.checkpoint_session",
            new_callable=AsyncMock,
            return_value=CheckpointResult(),
        ), patch("cmd_sessions.clear_history"), patch("cmd_sessions.read_safe", return_value=""), patch(
            "cmd_sessions.get_mage_name", return_value="Kermit"
        ):
            await cs.cmd_release(message)

        embed = message.reply.await_args_list[-1].kwargs["embed"]
        self.assertIn("No new resonance captured", embed.description)
        # No empty preview block on the honest no-capture path (issue 036).
        self.assertNotIn(
            "```md", message.reply.await_args_list[-1].kwargs.get("content") or ""
        )


class TestCmdDissolve(unittest.IsolatedAsyncioTestCase):
    async def test_requires_thread(self) -> None:
        message = MagicMock()
        message.channel = MagicMock()
        message.reply = AsyncMock()

        with patch.object(cs.discord, "Thread", _FakeThread):
            await cs.cmd_dissolve(message, [])

        message.reply.assert_awaited_once()
        self.assertIn("inside an eddy thread", message.reply.await_args[0][0])

    async def test_blocks_dissolve_for_non_creator_share_eddy(self) -> None:
        message = MagicMock()
        thread = _FakeThread()
        thread.id = 4
        thread.parent_id = 9001
        message.channel = thread
        message.author.id = 222
        message.reply = AsyncMock()

        with patch.object(cs.discord, "Thread", _FakeThread), patch(
            "cmd_sessions.is_practice_channel",
            return_value=True,
        ), patch(
            "share_eddy.check_share_dissolve_authority",
            return_value=type("D", (), {"allowed": False, "reason": "Only the sharer."})(),
        ):
            await cs.cmd_dissolve(message, [])

        message.reply.assert_awaited_once()
        self.assertIn("Only the sharer", message.reply.await_args[0][0])

    async def test_archives_thread(self) -> None:
        from state import dialogue_histories

        channel_id = 4
        dialogue_histories[channel_id] = [{"role": "user", "content": "hi"}]
        message = MagicMock()
        thread = _FakeThread()
        thread.id = channel_id
        message.channel = thread
        message.reply = AsyncMock()
        result = DissolveResult(thread_name="test-eddy", entry_count=2, jump_url="https://discord.example/jump")

        with patch.object(cs.discord, "Thread", _FakeThread), patch(
            "cmd_sessions.discord.Embed", _FakeEmbed
        ), patch("cmd_sessions.is_practice_channel", return_value=True), patch(
            "cmd_sessions.get_history", return_value=dialogue_histories[channel_id]
        ), patch("sessions.dissolve_eddy", new_callable=AsyncMock, return_value=result), patch(
            "share_eddy.check_share_dissolve_authority",
            return_value=type("D", (), {"allowed": True, "reason": None})(),
        ):
            await cs.cmd_dissolve(message, [])

        self.assertNotIn(channel_id, dialogue_histories)
        embed = message.reply.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "Eddy dissolved")


if __name__ == "__main__":
    unittest.main()
