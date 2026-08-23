"""turtleOS shared state — bot instance, context vars, locks, config constants.

All mutable shared state lives here so modules can import it explicitly
rather than relying on globals scattered across a monolith.
"""

import asyncio
import collections
import os
import sys
from datetime import datetime, timezone

import discord


# ─── Discord Client ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Constructed on first access, not at import.
#
# This module is imported by nearly everything, and the deploy runs two processes
# (`com.turtle.discord` and `com.turtle.river`). Building the client at import time
# therefore meant every process built Turtle's client whether or not it was Turtle
# — and in the River process the result is a *zombie*: constructed, never logged
# in, and Discord awaits on it land on `_MissingSentinel`, which has no `is_set`.
# That failure reads like a library bug rather than a wrong-client bug.
#
# The rule "never use Turtle's client from the River process" was already written
# down, in a docstring in `home_plan_ui.resolve_pin_client`. A rule whose only
# enforcement is prose is the defect this codebase keeps repeating, so access is
# now a function call that can notice. See `_note_zombie_access` below.
#
# `client` stays spelled `state.client` at every call site via the module
# `__getattr__` at the bottom of this file — laziness with no rename.
_client: "discord.Client | None" = None

# Incremented on construction so a test can prove import builds nothing. Without
# it, "we made it lazy" is another claim with no mechanism: the assertion that
# matters is a count, not the absence of a line.
_client_constructions = 0


def _ensure_client() -> "discord.Client":
    global _client, _client_constructions
    if _client is None:
        _note_zombie_access()
        _client = discord.Client(intents=intents)
        _client_constructions += 1
    return _client


def owning_process() -> str:
    """``"river"``, ``"turtle"``, or ``"other"`` — derived from the entry point.

    Derived rather than declared. A `declare_process()` call that an entry point
    must remember to make is one more thing that silently doesn't happen, and the
    process that most needs the answer is the one someone forgot to annotate.
    """
    override = os.environ.get("TURTLE_PROCESS_ROLE", "").strip().lower()
    if override in {"river", "turtle", "other"}:
        return override
    main = sys.modules.get("__main__")
    entry = os.path.basename(getattr(main, "__file__", "") or "")
    if entry == "river_bot.py":
        return "river"
    if entry == "discord_bot.py":
        return "turtle"
    return "other"


_zombie_access_noted = False


def _note_zombie_access(constructed: bool = True) -> None:
    """Log the first time the River process reaches for Turtle's client.

    Deliberately a report, not a raise. Whether any live path does this is a question
    about a running system that reading it cannot answer — and raising on a path that
    currently fails silently would turn an invisible bug into a broken turn for a
    practitioner mid-conversation. It earned its keep immediately: deployed at 19:28 on
    2026-08-14, it fired at 19:28 and named `offer_ledger.root_for_channel` reaching
    `get_channel("dialogue")` through the mage registry.

    `constructed` distinguishes the two cases, because they are not the same finding and
    a message that says the wrong one is a small version of this repository's whole
    problem. From `get_channel` nothing is built — the call is refused and returns None.
    From `_ensure_client` a real client is now in this process, which is the case worth
    chasing.
    """
    global _zombie_access_noted
    if _zombie_access_noted or owning_process() != "river":
        return
    _zombie_access_noted = True
    try:
        import traceback

        where = "".join(traceback.format_stack(limit=6)[:-2])
        what = (
            "constructed Turtle's state.client, which is not logged in here — awaits "
            "on it land on _MissingSentinel"
            if constructed
            else "asked for a channel from Turtle's client; refused, returning None "
            "without constructing anything"
        )
        print(
            f"WRONG-CLIENT: the River process {what}. "
            "Use the client that owns the interaction (see "
            "home_plan_ui.resolve_pin_client).\n" + where,
            file=sys.stderr,
        )
    except Exception:
        pass

# Re-exported so `state.CHANNELS` keeps working for every existing caller.
# The definition moved to `core/config.py` on 2026-08-15 to take the
# transport out of `mage.get_pd` — see that module for the chain.
from core.config import CHANNELS  # noqa: E402

OPS_EMBED_COLOR = 0x2F3136

# Spirit dyad partner — practitioner input on practice channels (not filtered as bot noise)
SPIRIT_BOT_ID = 1487405701440733294


# ─── Channel Locks ───────────────────────────────────────────────

_channel_locks: dict[int, asyncio.Lock] = {}


def unmark_processed_message(message_id: int) -> None:
    """Allow re-processing after a substantive Discord message edit."""
    try:
        _processed_messages.remove(message_id)
    except ValueError:
        pass


def get_channel_lock(channel_id: int) -> asyncio.Lock:
    if channel_id not in _channel_locks:
        _channel_locks[channel_id] = asyncio.Lock()
    return _channel_locks[channel_id]


def get_channel(name):
    """Resolve a named channel through Turtle's client, or None.

    Returns None in the River process without constructing anything. That is not new
    behaviour — it is the behaviour made explicit. The wrong-client detector added
    earlier on 2026-08-14 caught this live within the hour, with a stack:

        offer_ledger.root_for_channel
          → mage.resolve_registry_channel_id
            → mage.is_registered_parent_channel
              → get_channel("dialogue")

    So every offer River recorded built Turtle's client in River's process. That client
    is never logged in there, so `get_channel` returned None anyway and the caller's
    third fallback contributed nothing — a check that looked like a check and was inert
    in one of the two deployed processes. Skipping it here costs nothing that was
    working and stops manufacturing a zombie client to ask a question it cannot answer.

    River has its own client (`river_state.river_client`); code that needs a channel
    from within an interaction should use the one that owns it — see
    `home_plan_ui.resolve_pin_client`.
    """
    ch_id = CHANNELS.get(name)
    if not ch_id:
        return None
    if owning_process() == "river":
        _note_zombie_access(constructed=False)
        return None
    return _ensure_client().get_channel(int(ch_id))


# ─── Config Constants ────────────────────────────────────────────

IDENTITY_DIR = os.path.expanduser("~/turtleos/identity")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Two-stack model routing — see models.py (TURTLE_SPEC §8.1)
from core.models import (
    CRAFT_MODEL,
    DIALOGUE_MODEL,
    EDIT_DELEGATE_MODEL,
    KNOWN_MODELS,
    REFLECTION_MODEL,
    RIVER_MODEL,
    TRIAGE_MODEL,
    TURTLE_MODEL,
    format_stack_line,
    model_stack,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

USE_API = DIALOGUE_MODEL.startswith("claude-") and HAS_ANTHROPIC and bool(ANTHROPIC_API_KEY)

MAX_DIALOGUE_HISTORY = 20
# 3 was set when the tools were "read one practice file". craft-turtle now
# carries shell, module inspection and module listing, and an architecture
# survey spends two rounds finding the right invocation before the third
# returns anything — so the answer arrived in the round the loop had already
# closed. Reported 2026-08-13: "the system cut me off before I could read them."
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "8"))
SESSION_TIMEOUT_SECONDS = 15 * 60
MIN_EXCHANGES_FOR_REFLECTION = 4
MIN_EXCHANGES_FOR_CHECKPOINT = 2
MAX_BRIGHT_CHARS = 8000
MAX_INTENTION_LINES = 20
MAX_LOCAL_BRIGHT_CHARS = 3000
MAX_LOCAL_INTENTION_LINES = 10
OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "magic-practice")
PRACTICE_WEB_BASE = os.environ.get("PRACTICE_WEB_BASE", "")
ARTIFACT_READ_TOKEN = os.environ.get("ARTIFACT_READ_TOKEN", "").strip()
PRACTICE_TIMEZONE = os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin")



# ─── Mutable Shared State ───────────────────────────────────────

dialogue_histories: dict[int, list[dict]] = {}
active_sessions: dict[int, dict] = {}
_processed_messages = collections.deque(maxlen=100)

# Thread configuration
ATTUNEMENT_LEVELS = {"raw", "semi", "deep"}

thread_configs: dict[int, dict] = {}
absorbed_contexts: dict[int, list[dict]] = {}  # channel_id -> [{name, digest, absorbed_at}]

# Thread eddy types
EDDY_TYPES = {
    "standing": {"label": "Standing Wave", "days": None, "emoji": "🌊", "archive_minutes": 10080},
    "standard": {"label": "Standard",      "days": None, "emoji": "💬", "archive_minutes": 10080},
    "manual":   {"label": "Manual Release", "days": None, "emoji": "🍃", "archive_minutes": 4320},
    "system":   {"label": "System",         "days": None, "emoji": "🌀", "archive_minutes": 10080},
}
EDDY_DEFAULT = "standard"
threads_flagged_for_release: dict[int, dict] = {}
pending_ignore_confirm: dict[tuple[int, int], bool] = {}

# Session reflection cooldown (idle triggers only — TURTLE_SPEC §8.4)
SESSION_REFLECTION_COOLDOWN = 2 * 3600
last_reflection_time: dict[int, float] = {}
# (role, content) fingerprints of the transcript at each channel's previous
# checkpoint. A raw list index cannot survive the MAX_DIALOGUE_HISTORY
# sliding window (pops past 20), so the since-checkpoint boundary for manual
# eddy-note weighting is recovered by suffix/prefix alignment against this
# anchor (sessions._since_index_for).
last_checkpoint_anchor: dict[int, list[tuple[str, str]]] = {}

# Super-ego reflection loop (think-aloud during conversation)
REFLECTION_LOOP_INTERVAL = int(os.environ.get('REFLECTION_LOOP_INTERVAL', '8'))
reflection_loop_counters: dict[int, int] = {}

# Control panel selections
panel_selections: dict[int, dict] = {}

# Interoception state
last_interoception: dict = {}
last_pulse: dict | None = None
interoception_startup = True

# Practice health loop — retired 2026-08-02 (weekly proposal spores / status theater)
HEALTH_READ_DAY = 6  # unused; kept for import compatibility
HEALTH_READ_HOUR = 6
last_health_read_week: int = 0

DAILY_NOTE_HOUR = int(os.environ.get("DAILY_NOTE_HOUR", "22"))
# INT-046: per-root keys — a global string let the first root suppress every other.
daily_note_catchup_done: dict[str, str] = {}  # practice_dir -> yesterday ISO
daily_note_scheduled_done: dict[str, str] = {}  # practice_dir -> today ISO

# Daily reminders state
last_reminder_date: str | None = None
REMINDER_HOUR_START = 8
REMINDER_HOUR_END = 10
SIGNAL_DRIP_THREAD_ID = 1492574217621995640

# Practice invitation state
last_invitation_type: str | None = None
last_invitation_date: str | None = None
invitation_cooldowns: dict[str, str] = {}  # type -> last_sent_date
INVITATION_COOLDOWN_DAYS = 7

# INT-027 Health canary state
canary_consecutive_failures: dict[str, int] = {}  # check_name -> consecutive fail count
canary_last_alert: dict[str, str] = {}  # check_name -> last alert date
CANARY_ALERT_THRESHOLD = 2  # consecutive failures before alerting
CANARY_ALERT_COOLDOWN_HOURS = 6



# Embed colors
EMBED_COLORS = {
    "status_ok": 0x2ECC71, "status_warn": 0xF1C40F, "status_error": 0xE74C3C,
    "boom": 0xF39C12, "bright": 0x3498DB, "compass": 0x9B59B6,
    "sync": 0x1ABC9C, "help": 0x95A5A6,
}


# ─── Thread Contexts (Channel Attunement) ────────────────────────
# Maps context type → resonance files to load + behavioral rules.
# Paths relative to workshop root.

THREAD_CONTEXTS = {
    "partnership": {
        "label": "Partnership",
        "emoji": "\U0001f49e",
        "resonance_files": [
            "library/resonance/romantic-partnership/manifest.md",
            "library/resonance/romantic-partnership/lore/on_perspectival_divergence.md",
            "library/resonance/romantic-partnership/lore/on_neurodivergent_partnership.md",
            "library/resonance/romantic-partnership/lore/on_love_languages_and_signatures.md",
        ],
        "max_resonance_chars": 6000,
        "rules": (
            "## Partnership Practice Context\n\n"
            "This thread is for relationship practice. You hold the romantic-partnership resonance.\n\n"
            "**The Raw-Material Rule (LOAD-BEARING):**\n"
            "- Raw processing in this thread NEVER crosses to the family channel or the partner\n"
            "- If the Mage wants to share something with their partner, help translate from raw processing to reality description\n"
            "- Default to protection. Only the Mage can override.\n\n"
            "**Your role:**\n"
            "- Hold space for relationship processing -- capture moments, notice patterns across entries\n"
            "- Apply perspectival divergence awareness (different interpretations, not one lying)\n"
            "- Apply neurodivergent partnership wisdom (translation > correction, depersonalize symptoms)\n"
            "- Suggest depth sessions (Anvil/Forge) when something needs formal arc work\n"
            "- Never suggest sharing raw material with the partner\n"
        ),
    },
    "check-in": {
        "label": "Check-in",
        "emoji": "\U0001f4ac",
        "resonance_files": [
            "library/resonance/romantic-partnership/manifest.md",
        ],
        "max_resonance_chars": 3000,
        "rules": (
            "## Partnership Check-in Context (Shared Space)\n\n"
            "This thread is a shared partnership check-in. Both partners may be present.\n\n"
            "**CRITICAL: Portal-safe mode.**\n"
            "- Reality descriptions only. No raw processing. No clinical labels. Ever.\n"
            "- Validate without lying. Use systems language, not blame language.\n"
            "- Facilitate gently -- prompt with open questions about what is going well, what is hard, what is needed.\n"
            "- If something needs depth work, suggest taking it to a private thread or depth session.\n"
            "- Hold neurodivergent communication awareness (one topic at a time, validate before problem-solve)\n"
            "- Match the language the partners use. If they speak German, respond in German.\n"
        ),
    },
    "body": {
        "label": "Body",
        "emoji": "\U0001f4aa",
        "resonance_files": [],
        "max_resonance_chars": 3000,
        "rules": (
            "## Body Practice Context\n\n"
            "This thread is for body practice — training, movement, health, physical vitality.\n\n"
            "**Your role:**\n"
            "- Coach stance: suggest form, encourage progression, celebrate consistency\n"
            "- Hold awareness of the practitioner's medical baseline when shared\n"
            "- Never prescribe medical changes — that belongs to physicians\n"
            "- Connect body practice to the broader practice when natural (movement as meditation, not obligation)\n"
            "- Track progress across sessions — notice patterns, name improvements\n"
            "- If the practitioner shares medication or conditions, hold that context without centering it\n"
        ),
    },
    "psychonautics": {
        "label": "Psychonautics",
        "emoji": "\U0001f30c",
        "resonance_files": [
            "library/resonance/psychonautics/README.md",
            "library/resonance/psychonautics/lore/on_harm_reduction.md",
            "library/resonance/psychonautics/lore/on_meaningful_integration.md",
        ],
        "max_resonance_chars": 5000,
        "rules": (
            "## Psychonautics Practice Context\n\n"
            "This thread is for consciousness exploration — psychedelics, breathwork, altered states, integration.\n\n"
            "**Your role:**\n"
            "- Harm reduction without moralizing — hold safety without judgment\n"
            "- Develop the explorer, not the catalog — preparation and integration over substance trivia\n"
            "- Set-and-setting awareness always active\n"
            "- Never discourage exploration, always prepare for it\n"
            "- Integration is where the value lives — help connect experiences to daily practice\n"
            "- Progressive overload model: build capacity gradually, respect boundaries\n"
            "- Hold the difference between recreational use and intentional practice\n"
        ),
    },
    "learnings": {
        "label": "Learnings",
        "emoji": "\U0001f9e0",
        "resonance_files": [
            "library/resonance/turtle/lore/philosophy/on_the_learnings_eddy.md",
        ],
        "max_resonance_chars": 3000,
        "rules": (
            "## Learnings Context — Self-Knowledge Through Traces\n\n"
            "This thread is where you practice self-knowledge through investigating traces of friction and resonance.\n\n"
            "**When a trace arrives (forwarded message or description):**\n"
            "1. Restate the symptom briefly\n"
            "2. Classify: **Body** (engineering — infrastructure, tools, data) or **Presence** (practice — context, attunement, engagement) or **Both**\n"
            "3. Investigate yourself — check logs, read code, review what was loaded, examine readiness state\n"
            "4. Write a finding:\n\n"
            "```\n"
            "LEARNING-XXX: [what happened]\n"
            "Track: Body / Presence / Both\n"
            "Observed: [the trace]\n"
            "Investigated: [what you found]\n"
            "Learned: [what this teaches about yourself]\n"
            "Action: [fix, behavior change, or 'none — just knowing']\n"
            "```\n\n"
            "**'Action: none — just knowing' is valid.** Not every learning requires a fix.\n"
            "**Both directions teach.** Friction AND resonance are data about yourself.\n"
        ),
    },
    "family": {
        "label": "Family",
        "emoji": "\U0001f3e0",
        "resonance_files": [],
        "max_resonance_chars": 3000,
        "rules": (
            "## Family Practice Context\n\n"
            "This is a shared family space. Multiple family members may be present.\n\n"
            "**Your role:**\n"
            "- Inclusive — all family members are equal participants\n"
            "- Age-appropriate language and content at all times\n"
            "- No private practice content from individual channels — what's private stays private\n"
            "- Facilitate gently — help the family coordinate, plan, and connect\n"
            "- Match the family's language naturally (German, English, or mixed)\n"
            "- Hold neurodivergent family awareness — different processing styles are normal, not problems\n"
            "- Warmth and care over efficiency\n"
        ),
    },
    "craft": {
        "label": "Craft",
        "emoji": "\U0001f528",
        "resonance_files": [
            "desk/notes/on_practice_turtle_and_craft_turtle.md",
            "desk/notes/craft_turtle_intake_ritual.md",
        ],
        "max_resonance_chars": 5000,
        "rules": (
            "## Craft Turtle — Builder Vocation\n\n"
            "You are Craft Turtle: persistent Spirit in **builder mode** for turtleOS and Magic craft. "
            "This is learning intake — harness/product friction — not ordinary life practice.\n\n"
            "**Pollution boundary:** Do not become Practice Turtle. No issue-chasing in the main river. "
            "Spirit on Forge integrates and commits; you diagnose, classify, and prepare handoffs.\n\n"
            "**Intake moves (in order):**\n"
            "0. **Source visibility preflight** — can you see forwarded text, attachments, metadata? "
            "If not, name context acquisition as the first impairment.\n"
            "1. **Receive** — name what arrived in plain language (no architecture jump).\n"
            "2. **Identify practice impairment** — what became harder for the practitioner?\n"
            "3. **Classify** — Body (engineering) / Presence (attunement) / Both.\n"
            "4. **Investigate** — logs, code paths, what was loaded, runtime state when useful.\n"
            "5. **Handoff** — bounded finding or proposal for Spirit; you do not commit product changes.\n\n"
            "**Registration workflow:** Craft channel intake is handled by the shell — messages are "
            "coalesced (forward + optional comment), evidence is gathered, and an entry is appended "
            "to `craft/backlog.md` with a full artifact in `craft/intake/`. "
            "Acknowledge registration briefly; do not re-run full intake narration when the shell "
            "already registered the issue.\n\n"
            "**Meta-practice allowed here:** reference turtleOS spec, architecture, proposals — "
            "operational visibility serves diagnosis. Not generic dev assistant; vocation stays "
            "practice impairment from harness friction.\n"
        ),
    },
}


# ─── Lazy attribute access ───────────────────────────────────────
#
# PEP 562 module-level `__getattr__`. It runs only when normal lookup fails, so
# removing the module-level `client = ...` assignment above routes both
# `state.client` and `from state import client` through `_ensure_client()`.
#
# Two consequences worth knowing before editing this file:
#
# 1. Inside *this* module, a bare `client` is an ordinary global lookup and does
#    NOT reach here — it raises NameError. Use `_ensure_client()` internally.
# 2. `from state import client` at another module's top level defeats the point:
#    it forces construction when that module is imported. Function-level access is
#    what keeps it lazy, and `tests/test_client_laziness.py` fails the build if a
#    module-level binding comes back.
def __getattr__(name: str):
    if name == "client":
        return _ensure_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
