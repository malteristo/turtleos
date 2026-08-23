"""A practitioner closing an eddy must be distinguishable from the archive timer.

`entry.changes` is an `AuditLogChanges` and is not iterable; the fields live on
`changes.before` / `changes.after`. Iterating it raised `TypeError` on every
archive transition and the blanket except turned that into "not deliberate".
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from runtime.adapters.lifecycle import _archive_transition_is_deliberate


class _Entry:
    def __init__(self, target_id, *, archived, by_bot):
        self.target = SimpleNamespace(id=target_id)
        self.user = SimpleNamespace(bot=by_bot)
        # Shaped like discord.py: a non-iterable holder with before/after diffs.
        self.changes = _Changes(archived)


class _Changes:
    """Non-iterable on purpose — this is the shape that broke the old code."""

    def __init__(self, archived):
        self.before = SimpleNamespace(archived=not archived if archived is not None else None)
        self.after = SimpleNamespace(archived=archived)


class _Guild:
    def __init__(self, entries):
        self._entries = entries

    def audit_logs(self, **kwargs):
        entries = self._entries

        class _Iter:
            def __aiter__(self):
                async def gen():
                    for e in entries:
                        yield e
                return gen()

        return _Iter()


def _run(thread_id, entries):
    thread = SimpleNamespace(id=thread_id, guild=_Guild(entries), guild_id=1)
    return asyncio.run(_archive_transition_is_deliberate(thread, discord_client=None))


class ArchiveTransitionTests(unittest.TestCase):
    def test_practitioner_archive_is_deliberate(self) -> None:
        self.assertTrue(_run(42, [_Entry(42, archived=True, by_bot=False)]))

    def test_bot_archive_is_not_deliberate(self) -> None:
        self.assertFalse(_run(42, [_Entry(42, archived=True, by_bot=True)]))

    def test_unarchive_is_not_deliberate(self) -> None:
        self.assertFalse(_run(42, [_Entry(42, archived=False, by_bot=False)]))

    def test_entry_for_another_thread_is_ignored(self) -> None:
        self.assertFalse(_run(42, [_Entry(99, archived=True, by_bot=False)]))

    def test_changes_object_is_never_iterated(self) -> None:
        """Positive control: the shape that used to raise must now pass through."""
        changes = _Changes(True)
        with self.assertRaises(TypeError):
            list(changes)
        self.assertTrue(_run(42, [_Entry(42, archived=True, by_bot=False)]))

    def test_audit_failure_still_falls_back_to_not_deliberate(self) -> None:
        class _Boom:
            def audit_logs(self, **kwargs):
                raise RuntimeError("audit log unavailable")

        thread = SimpleNamespace(id=7, guild=_Boom(), guild_id=1)
        self.assertFalse(
            asyncio.run(_archive_transition_is_deliberate(thread, discord_client=None))
        )


if __name__ == "__main__":
    unittest.main()
