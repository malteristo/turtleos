"""Keep a prepared eddy's shared workspace close behind the conversation.

A prepared eddy pairs a Discord thread with a workspace file: Turtle revises it
as the interview resolves things, and Spirit reads it from the workshop. That
works only if Turtle actually writes, and a best-effort write from a model is
exactly the step this practice keeps finding did not happen — silently, and then
described as having happened.

So the idle checkpoint is the **floor**, not the mechanism. Every 15 minutes
(``SESSION_TIMEOUT_SECONDS``) the checkpoint already synthesises the conversation
into an eddy note; this stamps that same synthesis into the workspace under a
sentinel-delimited block. The guarantee is bounded staleness: whatever else
happened, the workspace is never more than one idle window behind the room.

**No second inference.** The block reuses ``EddyNoteResult.entry_text``, which is
already written. On a one-slot host an extra model call at checkpoint time would
queue behind live turns and time out — the failure mode measured on 2026-08-07,
where a fallback under load became a load multiplier.

**Sentinels, not section rewriting.** Turtle owns the prose in § Live state and
must be able to edit freely without the next checkpoint clobbering it. The auto
block is replaced between markers; everything else is left exactly as found.
"""

from __future__ import annotations

import re
from pathlib import Path

BEGIN = "<!-- checkpoint:begin — auto, do not hand-edit -->"
END = "<!-- checkpoint:end -->"
LIVE_STATE = "## Live state"

_BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
_LAST_UPDATED = re.compile(r"^\*\*Last updated:\*\*.*$", re.MULTILINE)


def workspace_for_thread(
    runtime_dir: str | Path, thread_id: int, *, for_refresh: bool = True
) -> str | None:
    """Practice-relative workspace path for a prepared eddy, or None.

    When ``for_refresh`` is true (checkpoint path), only ``disposition: open``
    returns a path — a ready/harvested eddy must not keep getting idle stamps
    after the interview ended.
    """
    from core.prepared_eddies import OPEN, disposition_of, surface_of

    surface = surface_of(runtime_dir, thread_id)
    if not surface:
        return None
    if for_refresh and disposition_of(runtime_dir, thread_id) != OPEN:
        return None
    return surface


def build_block(*, stamp: str, note_rel: str | None, entry_text: str) -> str:
    """The auto block — synthesis plus its provenance, so nothing looks hand-written."""
    source = f"eddy note `{note_rel}`" if note_rel else "this checkpoint"
    body = (entry_text or "").strip() or "_Checkpoint produced no synthesis for this window._"
    return (
        f"{BEGIN}\n"
        f"### Conversation as of {stamp}\n\n"
        f"*Written by the idle checkpoint from {source} — not by Turtle, and not "
        f"reviewed. Turtle's own account of where things stand is above this block.*\n\n"
        f"{body}\n"
        f"{END}"
    )


def apply_refresh(text: str, block: str, stamp: str) -> str:
    """Insert or replace the auto block, leaving Turtle's prose untouched."""
    if _BLOCK.search(text):
        updated = _BLOCK.sub(lambda _: block, text, count=1)
    elif LIVE_STATE in text:
        head, rest = text.split(LIVE_STATE, 1)
        # End of the § Live state section is the next heading of the same level.
        match = re.search(r"^## ", rest[1:], re.MULTILINE)
        cut = match.start() + 1 if match else len(rest)
        updated = head + LIVE_STATE + rest[:cut].rstrip() + "\n\n" + block + "\n\n" + rest[cut:]
    else:
        updated = text.rstrip() + "\n\n" + LIVE_STATE + "\n\n" + block + "\n"
    replacement = f"**Last updated:** {stamp} (checkpoint)"
    if _LAST_UPDATED.search(updated):
        updated = _LAST_UPDATED.sub(lambda _: replacement, updated, count=1)
    return updated


def refresh_workspace_file(
    workspace_abs: Path, *, stamp: str, note_rel: str | None, entry_text: str
) -> bool:
    """Write the refreshed workspace. False when the file is not there."""
    if not workspace_abs.is_file():
        return False
    text = workspace_abs.read_text(encoding="utf-8")
    block = build_block(stamp=stamp, note_rel=note_rel, entry_text=entry_text)
    workspace_abs.write_text(apply_refresh(text, block, stamp), encoding="utf-8")
    return True
