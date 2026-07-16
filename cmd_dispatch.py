"""turtle-talk dispatch — registries, act digests, River ``!`` execution path."""

from __future__ import annotations

from helpers import get_history, log_activity
from mage import get_mage_type
from state import MAX_DIALOGUE_HISTORY

COMMAND_ACT_FALLBACK = {
    "status": "Platform status act posted (models, uptime, practice root summary).",
    "diagnose": "Stack diagnostic act posted (canary checks).",
    "help": "River command summary posted (full inventory in eddies).",
    "thread-type": "Eddy type updated.",
    "rename": "Eddy renamed on Discord.",
    "eddy-check": "Eddy dissolution scan completed.",
    "fetch": "URL fetched and distilled to practice library cache.",
    "checkpoint": "Checkpoint complete — flow state and/or session note saved.",
    "release": "Session released — checkpoint saved, history cleared.",
    "share": "Share eddy picker opened — choose target and confirm.",
    "focus": "Focus updated — this eddy narrowed (or widened) to one thing.",
    "dissolve": "Eddy dissolved — thread archived, chronicle updated.",
    "flows": "Flow menu opened.",
    "flow": "Flow loaded or flow menu opened.",
    "pin": "Message pinned in river channel.",
    "readiness": "Practice-readiness act posted.",
    "artifacts": "Practice artifact shelves displayed.",
    "export": "Practice artifact exported as .md attachment.",
    "read": "Practice artifact content displayed.",
    "ls": "Allowlisted practice directory listing displayed.",
    "search": "Practice artifact search results displayed.",
}

_PRACTITIONER_COMMANDS = {
    "status",
    "help",
    "checkpoint",
    "release",
    "dissolve",
    "flows",
    "flow",  # alias of !flows — required for !flow <id> on hosted rivers
    "pin",
    "focus",
    "readiness",
    "rename",
    "fetch",
    "share",
    "artifacts",
    "export",
    "read",
    "ls",
    "search",
}

CONTEXTUAL_ACTION_TIMEOUT = 3600
CONTEXTUAL_ACTION_COMMANDS = {
    "status",
    "diagnose",
    "checkpoint",
    "release",
    "dissolve",
    "thread",
    "new",
    "threads",
    "eddy-check",
    "fetch",
    "absorb",
    "absorbed",
    "forget",
    "readiness",
    "flows",
    "artifacts",
    "export",
    "read",
}
# Native eddies: lifecycle bar owns checkpoint / release / dissolve; seneschal extends beyond that.
LIFECYCLE_BAR_COMMANDS = frozenset({"checkpoint", "release", "dissolve"})
# Release/dissolve clear history — act digest would recreate the shared dialogue file.
COMMANDS_SKIP_ACT_DIGEST = frozenset({"release", "dissolve"})
SENESCHAL_ACTION_COMMANDS = frozenset(
    cmd for cmd in CONTEXTUAL_ACTION_COMMANDS if cmd not in LIFECYCLE_BAR_COMMANDS
)

# Multi-step pickers only — re-anchor after the wizard completes (select follow-ups
# edit in place; bar shows active state until artifact pick finishes).
INTERACTIVE_COMMANDS_DEFER_BAR = frozenset({"share", "artifacts"})


def inject_act_digest(channel_id: int, cmd: str, summary: str) -> None:
    """Record a River act outcome for Turtle dialogue context (not Turtle prose)."""
    text = summary.strip()
    if not text:
        text = COMMAND_ACT_FALLBACK.get(cmd, f"Command `!{cmd}` completed.")
    history = get_history(channel_id)
    history.append({"role": "user", "content": f"[Act: !{cmd}] {text}"})
    if len(history) > MAX_DIALOGUE_HISTORY:
        del history[0 : len(history) - MAX_DIALOGUE_HISTORY]
    from helpers import sync_history

    sync_history(channel_id)


async def send_with_actions(channel, message: str, actions: list[tuple[str, str]]):
    """Post seneschal act buttons via River (split-bot) or Turtle (single-bot fallback)."""
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        client = river_client
    else:
        client = getattr(getattr(channel, "_state", None), "_get_client", lambda: None)()
        if client is None:
            return await channel.send(message)

    from eddy_lifecycle_bar import post_act_suggestion_row

    return await post_act_suggestion_row(channel, actions, client, content=message)


async def try_direct_command(message) -> bool:
    text = message.content.strip()
    if not text.startswith("!"):
        return False
    parts = text[1:].split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []
    if get_mage_type() == "practitioner" and cmd not in _PRACTITIONER_COMMANDS:
        return False
    # Registry lives in commands.py until handler modules are extracted (Slice 3+).
    from commands import DIRECT_COMMANDS

    handler = DIRECT_COMMANDS.get(cmd)
    if handler:
        digest = None
        try:
            result = await handler(message, args)
            if isinstance(result, str) and result.strip():
                digest = result.strip()
        except Exception as e:
            await message.reply(f"Command error: {e}", mention_author=False)
            await log_activity(f"Command `!{cmd}` failed: {e}", "\u274c", channel=message.channel)
            digest = f"Failed: {e}"
        if cmd not in COMMANDS_SKIP_ACT_DIGEST:
            inject_act_digest(message.channel.id, cmd, digest or COMMAND_ACT_FALLBACK.get(cmd, ""))
        return True
    return False


async def dispatch_direct_command(message, *, bar_client=None) -> bool:
    """Execute turtle-talk ``!`` command, inject act digest, re-anchor bars."""
    from state import get_channel_lock

    text = message.content.strip()
    parts = text[1:].split(None, 1) if text.startswith("!") else []
    cmd = parts[0].lower() if parts else ""
    args = parts[1].split() if len(parts) > 1 else []

    defer_bar = cmd in INTERACTIVE_COMMANDS_DEFER_BAR

    lock = get_channel_lock(message.channel.id)
    async with lock:
        if not await try_direct_command(message):
            return False
        if defer_bar:
            return True
        from bar_anchor import _ensure_channel_bars_unlocked

        await _ensure_channel_bars_unlocked(message.channel, bar_client)
    return True
