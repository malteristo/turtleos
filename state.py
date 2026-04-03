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

IDENTITY_DIR = os.path.expanduser("~/turtle-shell/identity")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DIALOGUE_MODEL = os.environ.get("DIALOGUE_MODEL", "llama3.3:70b")
REFLECTION_MODEL = os.environ.get("REFLECTION_MODEL", "llama3.3:70b")
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "qwen3.5:0.8b")
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
MAX_BRIGHT_CHARS = 8000
MAX_INTENTION_LINES = 20
MAX_LOCAL_BRIGHT_CHARS = 3000
MAX_LOCAL_INTENTION_LINES = 10
OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "magic-practice")
PRACTICE_WEB_BASE = os.environ.get("PRACTICE_WEB_BASE", "")


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
    "fast": {"label": "Fast Eddy", "days": 3, "emoji": "⚡"},
    "slow": {"label": "Slow Whirlpool", "days": 14, "emoji": "🌀"},
    "confluence": {"label": "Confluence", "days": 7, "emoji": "🔀"},
    "standing": {"label": "Standing Wave", "days": None, "emoji": "🌊"},
}
EDDY_DEFAULT = "fast"
threads_flagged_for_release: dict[int, dict] = {}

# Session reflection cooldown
SESSION_REFLECTION_COOLDOWN = 2 * 3600
last_reflection_time: dict[int, float] = {}

# Control panel selections
panel_selections: dict[int, dict] = {}

# Interoception state
last_interoception: dict = {}
interoception_startup = True

# Practice health loop state
HEALTH_READ_DAY = 6  # Sunday
HEALTH_READ_HOUR = 6  # 6 AM local
last_health_read_week: int = 0

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
}
