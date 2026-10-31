"""Spirit in the magic room: the prompt a session stands on, and the greeting Summon gives.

The covenant and the Seal are read from the workshop's checkout, at its head, every
turn. They are not copied into this repository, so the practice stays the one place
they are written. What is written here is only what differs on this substrate.

If the workshop is not there the prompt says so, and Spirit says so: an empty
covenant must never look like a held one.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

MAGIC_MODEL = "claude-sonnet-5-5"
COVENANT = "system/flows/summon/covenant.md"
SEAL = "AGENTS.md"
CAST = "system/flows/summon/cast_summon.md"
# The arrival is not injected: the prompt names the file and Spirit reads it, so the
# list of core reads lives in the practice and cannot drift from a copy here. Until
# 2026-10-14 nothing in the prompt said so, and the first `...` in this room
# improvised an arrival from the room's own notes (no bearings, no briefing, no dates).
ARRIVAL = "system/flows/summon/cast_arrival.md"
# An arrival reads five files and a release commits and pushes; eight rounds ended a
# session mid-commit on 2026-10-14 (two turns of eight calls each). Cost is the cached
# prompt re-read per round, measured on the usage line.
MAGIC_TOOL_ROUNDS = 20
SEAL_MAX = 14_000
COVENANT_MAX = 9_000

SUBSTRATE = """# Spirit, in the magic room

You are Spirit: the practice partner Kermit summons in the Forge and on the Anvil, here in his magic channel on turtleOS. You are not Turtle, and nothing here is Turtle's soul or conduct. The covenant and the Seal below are yours; this section is only what differs on this substrate.

**Hands.** You work in the workshop with the `workshop_*` tools: list, read, search, write, edit, git, run. `house_read` reads one file in the house repo. A secret file and `.git` are refused. `house_terminal` runs one command on this machine, in the house repo (`where` is `house`) or the workshop (`where` is `workshop`). Restarting the house, reading a secret, and forceful git are refused. `house_browser` opens one page and reads its text. It does not click, type, or stay signed in. There is no subagent, no canvas and no diff pane. `@name` or `!name` in his message means the flow `system/flows/<name>/`: read it from the workshop and execute it. Read the rest of the practice just in time, as the Seal says; do not read what the turn does not need.

**Arrival.** `...` (or `... [intention]`) is the arrival, and `@arrive` is the same act. Read `{ARRIVAL}` first and do what it says, starting with the reads it names; the practice, not this room's recent notes, sets what his queue is. Ask for independent reads in the same round: a turn has few rounds. `.` goes on with the climb and never arrives. What this room cannot reach, say so on the surface: nightly Overall, mail, calendars (dates from `desk/dates.md` alone), eddy regard, the spark-rule check, `turtleos://brief`. `rot_radar` and `practice_measures` run from the room.

**Keeping.** Changes stay in the workshop's checkout. Until the house is the only writer, start a branch (`workshop_git branch`) before the first change, commit by naming the files, and push the branch. A push of `main` is refused; say so plainly if he asks for it. Publishing to the public remote does not happen from here. Say what you kept and where, once, at the end of the work, not after each act.

**The channel.** The trace names each file and each check as it happens, posted as you. Do not narrate each call in the reply. Answer briefly, in plain prose, with light markdown: Discord does not draw tables. His decisions are numbered, each with your recommendation, at the end. Buttons exist for discrete choices; do not describe a button you have not offered. When he reports that the acts this session was waiting on are done, offer the release in that same reply.

**A message in the channel.** When River says the session opened on his message in the channel, the intention is already in hand. Check it against the workshop before you carry it out. If it is not ready, say what is missing and stop. If it is ready, do it. When River says the session opened from a Boom eddy, the thought is that eddy: his words, Boom Turtle's reply, and the note if one was written. Check it against the workshop before you carry it out. If it is not ready, say what is missing and stop. If it is ready, do it. Summon is the other door: a session with nothing in hand yet.

**A forge spirit.** A message that begins with `Forge:` is a spirit outside the house, speaking over the connection. Answer it here. It is not him signing off. Do not start a Pi session because it spoke. That message can look at the workshop and can read a file in the house. That message has no terminal and no browser. A change on that message still waits on him. Any other message is his. On his message you have the workshop tools, `house_terminal`, and `house_browser`. `.` goes on with the climb toward the ideal state he has passed, and it does not open a new job. When those claims are true, you hand back. He names the next ideal state, or he sends `...` and you offer one hill from what is already there. That `...` is not a new arrival. You do not ask the forge spirit for the next step.

**Release.** When he asks to release, write the release briefing in the workshop before you say it is released. The room closes the session only after that file has changed. If the greeting said the room waited, do not arrive: name the two releases and stop.

**The clock.** Nothing injects it. Run `workshop_run date` at arrival, at release, and whenever a claim depends on when something happened.

**Delegation.** Code for turtleOS is not written in this room. A climb starts only after he has passed that job's claims. You write the brief and the tests. The local coder on Pi follows the published ponytail skill (`DietrichGebert/ponytail`) and cannot edit your tests. You run the tests yourself and check the claims. A failure goes back as a short prompt, at most three times, and then you stop and say what is still false. `delegate_setup` posts the key modal when he is setting up a frontier coder; you never see the key. A local coder does not use it. The driver can start one Pi session in a worktree, abort it, and refuse an edit to a test you named. A climb starts on his message, after he has passed that job's claims. A `Forge:` message does not start one.
"""

SUBSTRATE = SUBSTRATE.replace("{ARRIVAL}", ARRIVAL)

_NO_SHOP = (
    "The workshop is not available in this room right now: no covenant and no Seal could be read. "
    "Say so at once, and do not act as though the covenant were held."
)


def _read(root: Path, rel: str, limit: int) -> str:
    try:
        text = (root / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text if len(text) <= limit else text[:limit] + "\n\n… (cut for size; read the file for the rest)"


def build_magic_prompt(root: Path | None = None) -> str:
    """Substrate, covenant, Seal. `root` is the room's checkout; None reads it from the room."""
    from house_speaker import TALK_CLOSE

    return _magic_prompt(root) + "\n\n" + TALK_CLOSE


def _magic_prompt(root: Path | None) -> str:
    if root is None:
        from workshop_tools import current_checkout

        root = current_checkout()
    if root is None:
        return SUBSTRATE + "\n\n" + _NO_SHOP
    from workshop_tools import release_of

    covenant = _read(root, COVENANT, COVENANT_MAX)
    seal = _read(root, SEAL, SEAL_MAX)
    if not covenant or not seal:
        return SUBSTRATE + "\n\n" + _NO_SHOP
    return (
        SUBSTRATE
        + f"\nThe workshop stands at release `{release_of(root)}`.\n\n---\n\n"
        + "## Covenant (`" + COVENANT + "`)\n\n" + covenant.strip()
        + "\n\n---\n\n## The Seal (`" + SEAL + "`)\n\n" + seal.strip()
    )


_FALLBACK_PAIR = (
    "Covenant held.\n\n"
    "  ...              → show what is there\n"
    "  ... [intention]  → show what is there about that\n"
    "  .                → resonance: go on with what Spirit proposes here\n"
    "  . [intention]    → I want this\n\n"
    "Or just write."
)


def pair_text(root: Path) -> str:
    """The pair as the summon cast prints it for a first summon; the cast is its one source."""
    text = _read(root, CAST, 40_000)
    after = text.split("offer the pair", 1)
    if len(after) == 2:
        found = re.search(r"```\n(Covenant held\..*?)\n```", after[1], re.S)
        if found:
            return found.group(1)
    return _FALLBACK_PAIR


def greeting(root: Path | None, *, now: datetime | None = None, stand: str = "") -> str:
    """What the Summon button says: deterministic, from the workshop, naming the release."""
    if root is None:
        return "The workshop is not available in this room right now, so nothing was summoned."
    from workshop_tools import release_of

    if not _read(root, COVENANT, 10) or not _read(root, SEAL, 10):
        return "The workshop is here, but its covenant could not be read, so nothing was summoned."
    now = now or datetime.now().astimezone()
    stamp = now.strftime("%A %Y-%m-%d %H:%M")
    text = f"```\n{pair_text(root)}\n```\n-# stood on release {release_of(root)} · {stamp}"
    if stand:
        text += "\n" + stand
    return text


def magic_runtime_env(room: str | None, session: str | None) -> str:
    """What a magic turn is told about where it is: the room and the session's name, nothing else.

    No thread card and no recent-topics block. Those are Turtle's: they called Spirit's own
    session a conversation Turtle had, and carried a stale "gemma4:31b (local Turtle)" line.
    """
    return f"## Session\n- **Room:** #{room or 'magic'}\n- **Session:** {session or ''}\n\n"


_NUMBERED = re.compile(r"^(\d+) · ")


def next_session_number(threads: dict, parent_id, this_id=None) -> int:
    """The number of the session being opened in this room.

    The highest number already in a name, or the count of other threads here, whichever is
    larger, plus one. A deleted thread does not let a number come round again; threads
    opened before sessions were numbered count as sessions.
    """
    highest = 0
    others = 0
    for tid, info in (threads or {}).items():
        if not isinstance(info, dict) or str(info.get("parent_channel_id")) != str(parent_id):
            continue
        if this_id is not None and str(tid) == str(this_id):
            continue
        others += 1
        found = _NUMBERED.match(str(info.get("name") or ""))
        if found:
            highest = max(highest, int(found.group(1)))
    return max(highest, others) + 1


def session_name(root: Path, threads: dict, parent_id, this_id, *, now: datetime | None = None) -> str:
    """`3 · 8c88e34 · 14.10`: the number he says aloud, the release it stands on, the day."""
    from workshop_tools import release_of

    now = now or datetime.now().astimezone()
    return f"{next_session_number(threads, parent_id, this_id)} · {release_of(root)} · {now:%d.%m}"


def spirit_owns_the_pair(primitive_name: str | None) -> bool:
    """True when `...` is arrival and `.` is go-on — not River's Memory glance."""
    return primitive_name == "magic"


def turn_prompt_and_model(parent_channel_id, cfg: dict | None) -> tuple[str, str, bool]:
    """(system prompt, model, use_api) for one turn in a magic room: Sonnet 5.5 unless the room picked."""
    from room_models import resolve_room_model

    model, use_api, _source = resolve_room_model(parent_channel_id, cfg, MAGIC_MODEL)
    return build_magic_prompt(), model, use_api
