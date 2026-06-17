"""turtleOS shared state — bot instance, context vars, locks, config constants.

All mutable shared state lives here so modules can import it explicitly
rather than relying on globals scattered across a monolith.
"""

import asyncio
import collections
import os
from datetime import datetime, timezone

import discord


# ─── Discord Client ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

CHANNELS = {
    "dialogue": os.environ.get("DISCORD_CHANNEL_DIALOGUE"),
}

OPS_EMBED_COLOR = 0x2F3136


# ─── Channel Locks ───────────────────────────────────────────────

_channel_locks: dict[int, asyncio.Lock] = {}


def get_channel_lock(channel_id: int) -> asyncio.Lock:
    if channel_id not in _channel_locks:
        _channel_locks[channel_id] = asyncio.Lock()
    return _channel_locks[channel_id]


def get_channel(name):
    ch_id = CHANNELS.get(name)
    if ch_id:
        return client.get_channel(int(ch_id))
    return None


# ─── Config Constants ────────────────────────────────────────────

IDENTITY_DIR = os.path.expanduser("~/turtleos/identity")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DIALOGUE_MODEL = os.environ.get("DIALOGUE_MODEL", "llama3.3:70b")
TURTLE_MODEL = os.environ.get("TURTLE_MODEL", os.environ.get("DIALOGUE_MODEL", "qwen3.5:9b"))
REFLECTION_MODEL = os.environ.get("REFLECTION_MODEL", "llama3.3:70b")
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "qwen3.5:0.8b")
RIVER_MODEL = os.environ.get("RIVER_MODEL", os.environ.get("TRIAGE_MODEL", "qwen3.5:4b"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
EDIT_DELEGATE_MODEL = os.environ.get("EDIT_DELEGATE_MODEL", "qwen3.5:4b")

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
MAX_TOOL_ROUNDS = 3
SESSION_TIMEOUT_SECONDS = 15 * 60
MIN_EXCHANGES_FOR_REFLECTION = 4
MIN_EXCHANGES_FOR_CHECKPOINT = 2
MAX_BRIGHT_CHARS = 8000
MAX_INTENTION_LINES = 20
MAX_LOCAL_BRIGHT_CHARS = 3000
MAX_LOCAL_INTENTION_LINES = 10
OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "magic-practice")
PRACTICE_WEB_BASE = os.environ.get("PRACTICE_WEB_BASE", "")
PRACTICE_TIMEZONE = os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin")


# ─── Boom Thread ─────────────────────────────────────────────

BOOM_THREAD_NAME = "boom"  # standing thread for universal intake
boom_thread_id: int | None = None  # set on startup or first creation

# ─── Mutable Shared State ───────────────────────────────────────

dialogue_histories: dict[int, list[dict]] = {}
active_sessions: dict[int, dict] = {}
_processed_messages = collections.deque(maxlen=100)

# Thread configuration
ATTUNEMENT_LEVELS = {"raw", "semi", "deep"}
KNOWN_MODELS = {
    "local": None,
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "qwen": "qwen3.5:9b",
    "qwen-4b": "qwen3.5:4b",
    "qwen-27b": "qwen3.5:27b",
}

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

# Session reflection cooldown
SESSION_REFLECTION_COOLDOWN = 2 * 3600
last_reflection_time: dict[int, float] = {}

# Super-ego reflection loop (think-aloud during conversation)
REFLECTION_LOOP_INTERVAL = int(os.environ.get('REFLECTION_LOOP_INTERVAL', '8'))
reflection_loop_counters: dict[int, int] = {}

# Control panel selections
panel_selections: dict[int, dict] = {}

# Interoception state
last_interoception: dict = {}
last_pulse: dict | None = None
interoception_startup = True

# Practice health loop state
HEALTH_READ_DAY = 6  # Sunday
HEALTH_READ_HOUR = 6  # 6 AM local
last_health_read_week: int = 0

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
}
