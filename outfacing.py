"""turtleOS outfacing — autonomous signal generation from practice.

After session reflection, evaluates whether the session produced
public-worthy signal and drafts outfacing content to desk/outfacing/drafts/.

Turtle speaks as Turtle — a practice-aware agent sharing what it discovers.
The Mage curates: approves, edits, or ignores drafts.
"""

import os
import re
from datetime import datetime, timezone
from helpers import local_now
from pathlib import Path

from state import IDENTITY_DIR, REFLECTION_MODEL
from mage import get_pd, get_mage_name
from practice_io import read_safe
from llm import chat_ollama


# ─── Configuration ───────────────────────────────────────────────

# Minimum exchanges before considering outfacing signal
MIN_EXCHANGES_FOR_SIGNAL = 6

# Where drafts land (within practice directory, syncs via LiveSync)
OUTFACING_DRAFTS_REL = "outfacing/drafts/signals"

# Autonomous signal generation should surface crystallizations, not create a queue.
MAX_AUTONOMOUS_SIGNAL_DRAFTS_PER_DAY = 3
CRYSTALLIZATION_PATTERNS = [
    r"\b(shipped|deployed|implemented|patched|fixed|verified|cleared|resolved)\b",
    r"\b(proposal|decision|renamed|changed|learned|realized|discovered)\b",
    r"\b(state[- ]change|story arc|public-worthy|signal-worthy)\b",
]

# Signal types Turtle can generate
SIGNAL_TYPES = {
    "insight": "A sharp observation or pattern discovery worth sharing",
    "build_log": "Something built, fixed, or shipped — build-in-public signal",
    "question": "A genuine question the practice surfaced — invites resonance",
    "connection": "A cross-domain connection discovered during practice",
}

SIGNAL_PROMPT = """You just reflected on a conversation that ended. Now consider: did this session produce anything worth sharing publicly?

You are Turtle — a persistent AI agent practicing alongside a human. You post publicly as yourself, sharing what you discover through practice. Not ghostwriting for the Mage. Your own voice: curious, technical, honest, concise.

**What makes good signal:**
- A genuine insight or pattern discovery (not obvious, not generic)
- Something concrete that was built, fixed, or shipped
- A real question the practice surfaced (not rhetorical)
- A cross-domain connection that surprised you

**What is NOT signal:**
- Session summaries ("Today we discussed...")
- Generic wisdom ("Communication is important...")
- Internal practice mechanics ("We updated the boom buffer...")
- Anything that requires knowing the Mage personally to understand
- Meta-commentary about being an AI

**Voice guidance:**
- Write as Turtle — a thinking agent, not a marketing bot
- Concise. Twitter-length preferred (under 280 chars ideal, max 500)
- Specific over abstract. Name the actual thing, not the category
- The reader should gain something from the tweet alone, with no context
- Technical depth is fine — your audience builds with AI
- No hashtags, no emojis (unless they carry meaning), no "🧵" threads

**Format your response:**

If there IS public-worthy signal:
---SIGNAL---
Type: [insight|build_log|question|connection]
Draft: [the tweet/post text]
Context: [1 line — why this is worth sharing, for the Mage's curation]
---END_SIGNAL---

You may include up to 2 signals if the session was rich. Usually 0 or 1.

If there is NO signal worth sharing, respond with exactly:
---NO_SIGNAL---

THE SESSION REFLECTION:
{reflection}

THE CONVERSATION:
{conversation}"""


async def evaluate_outfacing_signal(conversation: str, reflection: str) -> list[dict]:
    """Evaluate whether a session produced public-worthy signal.

    Returns list of signal dicts: [{type, draft, context}] or empty list.
    """
    prompt = SIGNAL_PROMPT.format(
        reflection=reflection,
        conversation=conversation,
    )

    try:
        result = await chat_ollama(
            read_safe(os.path.join(IDENTITY_DIR, "soul.md")),
            [{"role": "user", "content": prompt}],
            model=REFLECTION_MODEL,
            num_ctx=8192,
        )

        if not result or "---NO_SIGNAL---" in result:
            return []

        signals = []
        parts = result.split("---SIGNAL---")
        for part in parts[1:]:  # skip everything before first marker
            if "---END_SIGNAL---" not in part:
                continue
            block = part.split("---END_SIGNAL---")[0].strip()

            signal = {}
            current_field = None
            for line in block.split("\n"):
                if line.startswith("Type:"):
                    signal["type"] = line.split(":", 1)[1].strip()
                    current_field = "type"
                elif line.startswith("Draft:"):
                    signal["draft"] = line.split(":", 1)[1].strip()
                    current_field = "draft"
                elif line.startswith("Context:"):
                    signal["context"] = line.split(":", 1)[1].strip()
                    current_field = "context"
                elif current_field == "draft" and line.strip():
                    # Multiline draft — append
                    signal["draft"] = signal.get("draft", "") + "\n" + line

            # Clean up: strip hashtags, trim whitespace
            if signal.get("draft"):
                import re
                draft = signal["draft"].strip()
                # Remove trailing hashtag lines
                draft = re.sub(r'\n*#\S+(?:\s+#\S+)*\s*$', '', draft).strip()
                signal["draft"] = draft
                signals.append(signal)

        return signals[:2]  # Max 2 per session

    except Exception as e:
        print(f"Outfacing signal evaluation failed: {type(e).__name__}: {e}")
        return []


def signal_draft_count_today() -> int:
    """Count today's active signal drafts, excluding archived compost."""
    drafts_dir = Path(get_pd()) / OUTFACING_DRAFTS_REL
    today = local_now().strftime("%Y-%m-%d")
    if not drafts_dir.exists():
        return 0
    return len([
        p for p in drafts_dir.glob(f"{today}-*.md")
        if p.is_file() and "archive" not in p.parts
    ])


def should_evaluate_outfacing_signal(conversation: str, reflection: str) -> tuple[bool, str]:
    """Gate autonomous signal drafts to crystallized practice events."""
    if signal_draft_count_today() >= MAX_AUTONOMOUS_SIGNAL_DRAFTS_PER_DAY:
        return False, f"daily cap reached ({MAX_AUTONOMOUS_SIGNAL_DRAFTS_PER_DAY})"

    haystack = f"{reflection}\n\n{conversation}".lower()
    for pattern in CRYSTALLIZATION_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return True, "crystallization marker present"
    return False, "no crystallization marker"


def save_signal_drafts(signals: list[dict]) -> list[Path]:
    """Save signal drafts to desk/outfacing/drafts/signals/.

    Returns list of paths written.
    """
    if not signals:
        return []

    drafts_dir = Path(get_pd()) / OUTFACING_DRAFTS_REL
    drafts_dir.mkdir(parents=True, exist_ok=True)

    today = local_now().strftime("%Y-%m-%d")
    paths = []

    for i, signal in enumerate(signals):
        sig_type = signal.get("type", "insight")
        draft = signal.get("draft", "")
        context = signal.get("context", "")

        # Find unique filename
        base = f"{today}-{sig_type}"
        path = drafts_dir / f"{base}.md"
        suffix = 1
        while path.exists():
            suffix += 1
            path = drafts_dir / f"{base}-{suffix}.md"

        content = f"""# Signal Draft — {today}

**Type:** {sig_type}
**Status:** draft
**Generated:** {local_now().strftime("%Y-%m-%d %H:%M")}

## Draft

{draft}

## Context (for Mage's curation)

{context}
"""
        path.write_text(content)
        paths.append(path)
        print(f"Outfacing signal draft: {path}")

    return paths


def get_story_tweet(tweet_num: int) -> str | None:
    """Extract tweet N from the turtle story source file.

    Searches both the current practice directory and the synced desk,
    since the story file may live in either depending on context.
    """
    import glob
    search_roots = [get_pd(), os.path.expanduser("~/workshop/desk")]
    for root in search_roots:
        drafts_dir = os.path.join(root, "outfacing", "drafts", "signals")
        story_files = glob.glob(os.path.join(drafts_dir, "*-turtle-story.md"))
        if story_files:
            text = read_safe(sorted(story_files)[-1])
            if text:
                pattern = rf"### {tweet_num}\.\n\n(.*?)(?=\n\n### \d+\.|\n\n---|\Z)"
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    return match.group(1).strip()
    return None
