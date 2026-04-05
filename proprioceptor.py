"""turtleOS proprioceptor — connective tissue for context preparation.

A small fast model (qwen3.5:9b) that runs in parallel with triage,
reads the inbound message + practice state, and composes a focused
context brief for the dialogue model. The dialogue model receives
exactly the context it needs for THIS message, not everything.

The proprioceptor is the tissue. The dialogue model is the cell.
The tissue prepares the local context window so the cell can respond
with full awareness without reading the whole body.

Biological analogy (from "The Body That Writes Itself"):
  A cell doesn't read the state of the entire body.
  Its local tissue acts as a context window, giving it
  just the most relevant nearby information.
"""

import os
from datetime import datetime

import httpx

from state import OLLAMA_URL, REFLECTION_MODEL
from mage import get_pd
from practice_io import (
    read_safe, read_header, count_items,
    summarize_bright, load_intentions_list,
    file_age_hours, format_age,
)

# ─── Configuration ────────────────────────────────────────────────

PROPRIOCEPTOR_MODEL = "qwen3.5:9b"
PROPRIOCEPTOR_CTX = 2048
PROPRIOCEPTOR_THINK = False  # Speed over depth — this is tissue, not brain
PROPRIOCEPTOR_TIMEOUT = 30.0  # seconds — httpx read timeout (model needs time for context)


# ─── The Proprioceptor's Attunement ──────────────────────────────

PROPRIOCEPTOR_SYSTEM = """You are the proprioceptive system of a practice partner called Turtle.
Your job: scan the inbound message against practice state and produce TWO outputs.

## Output Format (STRICT)

SIGNALS: <1-3 compact connection signals, pipe-separated>
BRIEF: <context paragraph for the dialogue model, max 100 words>

## Signal Format

Each signal is: source/item → connection
Examples:
  compass/Body → growth confirmation
  boom/"closing the loop" → resolved
  session/03-29 → substrate friction landing
  intention/turtleOS → proprioceptor shipping

## Rules

- SIGNALS line: 1-3 most relevant connections. Terse. Source/item → what it means for THIS message.
- BRIEF paragraph: what the dialogue model needs to respond well. Specific, not generic.
- If nothing connects: SIGNALS: fresh topic
- Never address the human. This is internal body awareness.
- Output ONLY the two lines. No preamble."""


PROPRIOCEPTOR_PROMPT = """## Inbound Message
{message}

## Practice State

### Compass (life landscape)
{compass}

### Boom Buffer ({boom_count} items, last updated {boom_age})
{boom}

### Bright Surface ({bright_count} items)
{bright}

### Active Intentions
{intentions}

### Recent Session Notes
{sessions}

---
Compose the context brief for the dialogue model."""


# ─── Core Function ────────────────────────────────────────────────

async def prepare_context_brief(message_text: str) -> str | None:
    """Run the proprioceptor: read practice state, compose context brief.

    Returns the context brief string, or None if the proprioceptor
    fails or times out (dialogue proceeds without it — graceful degradation).
    """
    pd = get_pd()

    # Read practice state
    compass = read_safe(os.path.join(pd, "intentions", "compass.md")) or "(no compass)"
    boom = read_safe(os.path.join(pd, "boom.md")) or "(boom empty)"
    bright = read_safe(os.path.join(pd, "boom", "bright.md")) or "(bright empty)"
    boom_count = count_items(boom)
    bright_count = count_items(bright)
    boom_age = format_age(file_age_hours(os.path.join(pd, "boom.md")))

    # Truncate aggressively — proprioceptor needs signal, not completeness
    compass_brief = compass[:800]
    boom_brief = boom[-1000:]  # Most recent boom items (bottom of file)
    bright_brief = summarize_bright(bright, limit=600)

    # Load intention headers (just titles and current focus)
    intentions_text = ""
    idir = os.path.join(pd, "intentions")
    if os.path.isdir(idir):
        for fname in sorted(os.listdir(idir)):
            if fname.endswith(".md"):
                header = read_header(os.path.join(idir, fname), max_lines=10)
                if header.strip():
                    intentions_text += f"\n--- {fname} ---\n{header}"
    if not intentions_text.strip():
        intentions_text = "(no intentions)"

    # Load last 2 session notes (brief)
    sessions_text = ""
    sdir = os.path.join(pd, "sessions")
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:2]
        for fname in reversed(recent):
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                sessions_text += f"\n--- {fname} ---\n{content[:500]}"
    if not sessions_text.strip():
        sessions_text = "(no recent sessions)"

    # Build the prompt
    prompt = PROPRIOCEPTOR_PROMPT.format(
        message=message_text[:500],
        compass=compass_brief,
        boom=boom_brief,
        boom_count=boom_count,
        boom_age=boom_age,
        bright=bright_brief,
        bright_count=bright_count,
        intentions=intentions_text,
        sessions=sessions_text,
    )

    # Call the proprioceptor model
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0,
                read=PROPRIOCEPTOR_TIMEOUT,
                write=3.0,
                pool=3.0,
            )
        ) as http:
            payload = {
                "model": PROPRIOCEPTOR_MODEL,
                "messages": [
                    {"role": "system", "content": PROPRIOCEPTOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"num_ctx": PROPRIOCEPTOR_CTX},
                "keep_alive": "10m",
            }
            if PROPRIOCEPTOR_THINK is not None:
                payload["think"] = PROPRIOCEPTOR_THINK

            resp = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        brief = data.get("message", {}).get("content", "").strip()
        if brief and len(brief) > 10:
            return brief
        return None

    except Exception as e:
        print(f"Proprioceptor failed ({type(e).__name__}): {e}")
        return None
