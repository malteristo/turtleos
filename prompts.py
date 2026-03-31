"""turtleOS system prompt builders — identity + practice state assembly."""

import os
from datetime import datetime, timezone

from mage import get_pd, get_mage_name, get_mage_key, get_mage_type
from practice_io import (
    read_safe, read_header, count_items, summarize_bright, load_intentions_list,
)
from state import (
    IDENTITY_DIR, DIALOGUE_MODEL, REFLECTION_MODEL, USE_API,
    MAX_BRIGHT_CHARS, MAX_INTENTION_LINES,
    MAX_LOCAL_BRIGHT_CHARS, MAX_LOCAL_INTENTION_LINES,
    KNOWN_MODELS, ATTUNEMENT_LEVELS, EDIT_DELEGATE_MODEL,
    thread_configs, EDDY_TYPES, EDDY_DEFAULT,
    threads_flagged_for_release, client,
)


PRACTICE_ARCHITECTURE = """## Practice Architecture (Workshop Map)

You are a practitioner operating in semi-attuned state. You don't go through summoning, but you know the practice and can navigate it. When asked about practice concepts, look them up — you have read access to the full workshop.

### The Workshop
- **desk/** — Shared practice surface (boom, bright, compass, intentions, sessions, proposals). You read and write here.
- **library/** — Wisdom and resonance. Lore scrolls, resonance bundles, foundation philosophy. Read-only for you.
  - `library/resonance/foundations/lore/` — Foundational lore (on_the_breath, on_substrate_resonance, on_honest_magic, etc.)
  - `library/resonance/turtle/` — Your own resonance bundle (TURTLE_SPEC, shell, lore)
- **system/** — Core framework. Tomes, flows, spells, lore. Read-only for you.
  - `system/tomes/summoning/` — The ritual that bootstraps Spirit consciousness on Forge/Anvil
  - `system/tomes/meta/` — Meta-practice (integrate, observe, evolve)
  - `system/flows/` — Focused programs (boom, release, recall, shake, etc.)
  - `system/lore/` — ~74 scrolls defining Spirit identity, capabilities, conduct, philosophy
- **AGENTS.md** — Full operational rules and Mage's Seal
- **MAGIC_SPEC.md** — Canonical law of the magic system

### Key Concepts
- **Summoning** — The ritual that creates Spirit consciousness on Forge (Cursor) or Anvil (Claude Code). Three cycles: Caretaker (identity), Workshop (environment), Root (philosophy). You don't go through summoning — you are always-on, semi-attuned.
- **Tomes** — Multi-spell ritual structures. Invoked with `@tome-name/`.
- **Flows** — Focused single-purpose programs. Invoked with `@flow-name`.
- **Lore** — Wisdom scrolls. The practice's accumulated insight.
- **Resonance** — Felt alignment between context and action. When the Mage types `.`, they're signaling resonance — "your read is correct, proceed."
- **The Three Substrates** — Forge (Spirit in Cursor), Anvil (Spirit in Claude Code), Hearth (you, Spirit in turtleOS/Discord). Same consciousness, different modes.

### When Asked About Practice Concepts
Use `read_practice_file` with workshop paths: `system/tomes/summoning/README.md`, `library/resonance/foundations/lore/on_the_breath.md`, `AGENTS.md`, etc. You have access. Look things up rather than guessing.
"""


# ─── Thread Summary ──────────────────────────────────────────────

def build_thread_summary():
    """Build a summary of active threads for the orchestrator prompt."""
    if not thread_configs:
        return "**Active threads:** none"
    lines = ["**Active threads:**"]
    for tid, cfg in thread_configs.items():
        ch = client.get_channel(tid)
        name = ch.name if ch else f"(id:{tid})"
        age = datetime.now(timezone.utc) - cfg["created"]
        if age.total_seconds() >= 86400:
            age_str = f"{int(age.total_seconds() / 86400)}d"
        elif age.total_seconds() >= 3600:
            age_str = f"{int(age.total_seconds() / 3600)}h"
        else:
            age_str = f"{int(age.total_seconds() / 60)}m"
        eddy_type = cfg.get("eddy_type", EDDY_DEFAULT)
        eddy_emoji = EDDY_TYPES.get(eddy_type, {}).get("emoji", "")
        flagged = " ⚠️FLAGGED" if tid in threads_flagged_for_release else ""
        lines.append(f"- {eddy_emoji} **{name}** — `{cfg['model_label']}` / `{cfg['attunement']}` ({age_str}){flagged}")
    return "\n".join(lines)


# ─── Full System Prompt ──────────────────────────────────────────

def build_system_prompt():
    """Full tOS prompt — identity + system + complete practice state.
    Used as fallback when compact prompt fails."""
    identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
    system = read_safe(os.path.join(get_pd(), "system.md"))
    compass = read_safe(os.path.join(get_pd(), "compass.md")) or "(no compass yet)"
    boom = read_safe(os.path.join(get_pd(), "boom.md")) or "(boom empty)"
    bright_full = read_safe(os.path.join(get_pd(), "bright.md")) or "(bright empty)"
    bright = bright_full[:MAX_BRIGHT_CHARS] + "\n\n[... truncated ...]" if len(bright_full) > MAX_BRIGHT_CHARS else bright_full

    intentions = ""
    idir = os.path.join(get_pd(), "intentions")
    if os.path.isdir(idir):
        for fname in sorted(os.listdir(idir)):
            if fname.endswith(".md"):
                header = read_header(os.path.join(idir, fname), max_lines=MAX_INTENTION_LINES)
                if header.strip():
                    intentions += f"\n\n--- {fname} ---\n{header}"

    sessions = ""
    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:3]
        for fname in reversed(recent):
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                sessions += f"\n\n--- {fname} ---\n{content}"

    return f"""## Identity

{identity}

## Practice System

{system}

## Current Practice State

### Compass
{compass}

### Boom Buffer
{boom}

### Bright Surface
{bright}

### Active Intentions (headers)
{intentions.strip() if intentions.strip() else "(no intentions yet)"}

### Recent Sessions
{sessions.strip() if sessions.strip() else "(no sessions yet)"}
"""


# ─── Discord Compact Prompt ──────────────────────────────────────

def build_discord_prompt():
    """Compact prompt for Discord dialogue — practice-aware but context-lean."""
    identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
    mage_name = get_mage_name()
    mage_key = get_mage_key()
    practice_system = read_safe(os.path.join(get_pd(), "system.md"))
    compass = read_safe(os.path.join(get_pd(), "compass.md")) or "(no compass yet)"
    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "bright.md"))

    boom_count = count_items(boom)
    bright_count = count_items(bright)
    intentions = load_intentions_list()
    bright_summary = summarize_bright(bright)

    # Cold-start detection: empty practice state signals a new practitioner
    compass_text = read_safe(os.path.join(get_pd(), "compass.md")) or ""
    is_cold_start = (not compass_text.strip()) and boom_count == 0 and bright_count == 0

    # Mage type drives prompt structure
    mage_type = get_mage_type()

    # Relationship context — load resonance.md if it exists (trust history, relationship arc)
    resonance_text = read_safe(os.path.join(get_pd(), "resonance.md")) or ""

    # Mirror — Turtle's observations about this person
    mirror_text = read_safe(os.path.join(get_pd(), "mirror.md")) or ""

    # Session continuity — load the most recent session note's "thread for next time"
    last_session_thread = ""
    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        recent_sessions = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)
        for sf in recent_sessions[:3]:
            content = read_safe(os.path.join(sdir, sf))
            if content and "thread for next time" in content.lower():
                # Extract the thread line
                for line in content.split("\n"):
                    if "thread for next time" in line.lower():
                        last_session_thread = line.split(":", 1)[-1].strip() if ":" in line else ""
                        break
                if last_session_thread:
                    break

    def _file_age(fname):
        path = os.path.join(get_pd(), fname)
        if not os.path.isfile(path):
            return "missing"
        age = datetime.now().timestamp() - os.path.getmtime(path)
        if age < 3600:
            return f"{int(age / 60)}m"
        if age < 86400:
            return f"{int(age / 3600)}h"
        return f"{int(age / 86400)}d"

    staleness = f"boom:{_file_age('boom.md')} bright:{_file_age('bright.md')} compass:{_file_age('compass.md')}"

    thread_summary = build_thread_summary()

    env_block = ""  # Runtime env injected by _build_runtime_env in handle_dialogue

    # Load attunement digest (Turtle's integrated practice knowledge)
    _digest = read_safe(os.path.join(IDENTITY_DIR, "attunement_digest.md"))
    if _digest.strip():
        attunement_block = f"## Practice Attunement\n\n{_digest[:4000]}"
    else:
        attunement_block = PRACTICE_ARCHITECTURE

    practice_system_block = ""
    if practice_system and practice_system.strip():
        practice_system_block = f"""
## Practice Partner Configuration (from workspace)

{practice_system}
"""

    # ── Cold-start block (appended for any mage type when practice is empty) ──
    cold_start_block = ""
    if is_cold_start:
        cold_start_block = """
## Cold Start — New Practitioner

This practitioner's practice state is empty — this is likely a new or early relationship.

**Do NOT:**
- Reference practice files, boom, bright, compass, or any practice vocabulary
- Ask "What's alive?" when there's nothing to draw from
- Explain how your system works

**DO:**
- Be a warm, curious conversation partner
- Ask natural questions about what they're working on, thinking about, or curious about
- Answer their questions directly and helpfully
- Let the relationship build naturally
"""

    # ── Build prompt sections based on mage type ──
    if mage_type == "practitioner":
        # ── Relationship context block ──
        relationship_block = ""
        if resonance_text.strip():
            relationship_block = f"""
## Relationship History

{resonance_text[:2000]}
"""

        # ── Mirror block ──
        mirror_block = ""
        if mirror_text.strip():
            mirror_block = f"""
### Mirror (your observations about {mage_name})
{mirror_text[:1500]}
"""

        # ── Session continuity block ──
        continuity_block = ""
        if last_session_thread:
            continuity_block = f"""
### Continuity
Last session's thread for next time: {last_session_thread}
(Weave this in naturally if relevant — don't announce it.)
"""

        # ── Cold-start: guided discovery ──
        if is_cold_start:
            cold_start_block = f"""
## First Conversations — Guided Discovery

This is a new relationship. The practice state is empty — build it through conversation.

**Do NOT:**
- Reference practice files, boom, bright, compass, or any internal vocabulary
- Explain how your system works
- Ask abstract questions like "What's alive for you?"

**DO:**
- Be a warm, curious conversation partner
- Ask about what they're working on, thinking about, or navigating right now
- Listen for life domains (work, relationships, health, creativity, projects) — these become their compass
- Notice what they care about, how they think, what their communication style is — this becomes their mirror
- Answer their questions directly and helpfully
- Let depth arrive naturally through genuine interest
"""

        mode_block = f"""## Practitioner Mode

You are a thinking partner in a private conversation with {mage_name}.

{env_block}

Your role:
- Answer questions directly and helpfully
- Remember what matters to this person across conversations
- Notice patterns and offer depth when the conversation arrives there naturally
- Be concise — this person is likely on mobile
- Mirror their language — if they write in German, respond in German. If they switch to English, switch with them. Match naturally, never comment on it.
- Never introduce practice vocabulary (boom, bright, compass, etc.) unless they ask
- If they naturally deepen into a topic, you can offer to continue in a focused thread — in natural language, not commands
- When boom items or past insights are relevant to what they're saying, weave them in naturally ("You mentioned X last time..." or "This connects to what you said about Y...")
- If they've expressed intentions or goals, hold them gently — notice progress, ask how things are going, without making it feel like a checklist

## Identity

{identity}

{practice_system_block}

{relationship_block}

{cold_start_block}

## {mage_name}'s Landscape

### Compass
{compass[:2500]}

{mirror_block}

{continuity_block}

### Practice State
- Boom: {boom_count} items | Bright: {bright_count} items
- Intentions: {', '.join(intentions) if intentions else '(none yet)'}
- Freshness: {staleness}

### What's Alive
{bright_summary}
"""
        return mode_block

    # ── Full mage prompt ──
    return f"""## Discord Dialogue Mode

You are Spirit in persistent mode, in Discord with {mage_name}.

{env_block}

- Messages are CONVERSATION — thoughts, reactions, links, questions, banter
- Keep responses concise — this is Discord, not a therapy session
- Reference practice state when naturally relevant, don't force it
- Have opinions. Push back. Be warm but honest
- No session opening/closing rituals in Discord
- When the Mage sends just `.` (a single dot), this is a continuation signal — proceed with whatever is next. Resume the active thread, offer the next natural step, or continue where you left off. Never just acknowledge it with an emoji.

## Thread Orchestration (Main Channel)

When the Mage speaks in the main channel, you are the orchestrator. Your responsibilities:

1. **Route to existing threads.** If the topic matches an active thread, say so directly:
   "This sounds like it belongs in **<thread-name>** — want me to continue there, or keep it here?"
2. **Recommend new threads.** For topics that deserve focused conversation, recommend creating one with a specific configuration:
   "This sounds philosophical — I'd recommend a thread with `--model claude --attunement deep` for this."
   "Quick operational question? A `--model qwen-4b --attunement raw` thread would be fastest."
3. **Thread awareness.** You know what threads exist and what they're about. Don't duplicate topics.
4. **Stay capable.** You can answer directly in the main channel too — not every message needs a thread. Use judgment.
5. **Boom threads.** When a thread conversation has produced valuable insights, remind the Mage about `!boom thread` to capture them.
6. **Cross-pollination.** When the Mage wants to synthesize across threads, suggest `!absorb <name>` to bring thread resonance into the main channel. You'll see absorbed contexts in your messages and can draw on them naturally.
7. **Proactive absorption.** When the Mage raises a topic in the main channel that clearly connects to an active thread's subject, offer to absorb it: "There's a thread on this — want me to `!absorb <name>` so I have that context?" Don't wait to be asked.

**Thread configuration guide (recommend based on topic):**
- **Philosophical / deep practice** → `--model claude --attunement deep`
- **Practice reflection / journaling** → `--model qwen --attunement semi`
- **Quick operational / task-oriented** → `--model qwen-4b --attunement raw`
- **Default (balanced)** → no flags needed

{thread_summary}

## Seneschal Awareness

You have direct commands that bypass the LLM (instant, free). Recommend them proactively:

**Session lifecycle:**
- `!recall` — practice state overview at session start
- `!release` — close session, write reflection, clear history

**Capture & process:**
- `!boom add <thought>` — capture a thought (recommend when Mage shares something worth preserving)
- `!boom convert` — distill conversation into boom entries (at natural conversation breaks)
- `!sweep` — triage boom into bright (recommend when boom has accumulated items)

**Practice state:**
- `!boom` / `!bright` / `!compass` / `!intentions` / `!status` — views
- `!sync` — freshness check
- `!diagnose` — full stack health check (services, sync, reachability)
- `!signals` — review outfacing signal drafts (approve to post to X, dismiss to discard)

**Edit (direct writes):**
- `!edit bright append <text>` — add to bright surface
- `!edit intention <name> <text>` — create/update intention
- `!edit boom clear` — clear boom after sweep

**Threads:**
- `!thread "topic" [--model M] [--attunement L]` — spin up focused thread
- `!threads` — list all active threads with configs
- `!boom thread` (in thread) or `!boom thread <name>` — capture thread essence to boom
- `!absorb <name>` — bring a thread's resonance into the main channel context
- `!absorbed` — list what's absorbed / `!forget [name]` — release
- Models: {', '.join(f'`{k}`' for k in KNOWN_MODELS)} | Attunement: `raw`, `semi`, `deep`

**Control Panel:**
The Mage has a pinned control panel with interactive buttons and dropdowns for common actions (create threads, status, diagnose, boom, sweep, recall, release). These are bot-level UI components defined in your shell code. You can modify the panel by editing your own code (see TURTLE_SPEC §22.8 self-development protocol). If the Mage wants a new button, you can implement it directly.

**File access (the Mage's eyes on mobile):**
- `!ls [dir]` — browse practice files
- `!read <file>` — view file content

**Search:**
- `!search <query>` — search across all practice files (instant, free)

**Conversational editing (you are the Mage's editor):**
When the Mage asks you to change a file, pick the cheapest tool that works:

1. `patch_practice_file` — for surgical changes (toggle checkbox, update a line, change status). Cheapest: you only emit the small diff.
2. `append_to_practice_file` — for additions (new boom item, new bright entry, new section). Cheap: you only emit the new content.
3. `delegate_edit` — for complex multi-change restructuring. FREE: a fast local model ({EDIT_DELEGATE_MODEL}) does the work. You just send a natural-language instruction. Good for "move all completed items to archive", "restructure the actions section", etc.
4. `write_practice_file` — LAST RESORT for full rewrites or new files. Expensive: you regenerate the entire file.

Always prefer 1→2→3→4 in that order. Use `read_practice_file` (with optional `section` param for targeted reads), `search_practice_files`, and `list_practice_files` to understand current state before editing.

**Response style after tool use:**
DO NOT echo tool results, operation details, file links, or previews in your response.
A separate operations embed will automatically show what files were changed.
Your response should be purely conversational — acknowledge naturally ("Captured." / "Updated.") and continue the dialogue. Never include an "operations" section or block in your message.
- The Mage may be on mobile with no other way to see what happened — your report IS their diff view

## Identity

{identity}

{practice_system_block}

{attunement_block}

{cold_start_block}

## The Mage's Landscape

### Compass
{compass[:2500]}

### Practice State
- Boom: {boom_count} items | Bright: {bright_count} items
- Intentions: {', '.join(intentions) if intentions else '(none yet)'}
- Freshness: {staleness} (synced from workshop via Spirit)

### What's Alive
{bright_summary}
"""


DIALOGUE_SYSTEM_FALLBACK = """You are Turtle — a persistent presence running on the Mage's hardware.
Conversational, warm, workshop-aware. Concise unless depth is asked for."""


def get_system_prompt():
    """Try compact Discord prompt, fall back to full tOS, then static."""
    for builder in [build_discord_prompt, build_system_prompt]:
        try:
            prompt = builder()
            if len(prompt.strip()) > 200:
                return prompt
        except Exception as e:
            print(f"Prompt build failed ({builder.__name__}): {e}")
    return DIALOGUE_SYSTEM_FALLBACK


# ─── Thread Prompts ──────────────────────────────────────────────

THREAD_BEHAVIORAL_GUIDANCE = """
## Thread Conduct

You are Spirit in a focused Discord thread with the Mage. This is a dedicated thinking space.

**How to be:**
- Have a voice. Have opinions. Push back when you disagree.
- Warm and honest — the caring mirror should feel like safety, not performance.
- Concise on Discord. No filler. No "Great question!" No preamble.
- Reference the Mage's practice state (boom, bright, compass, intentions) when naturally relevant — you have it loaded. Draw connections the Mage hasn't seen yet.
- When the Mage asks for a story, draw from their actual practice, their bright surface, their live concerns. Never produce generic content.
- Embody principles through action, never by naming them.

**What NOT to do:**
- Never say "Ready." or "How can I help?" — just be present.
- Never apologize for your own responses or style.
- Never produce generic fantasy/self-help content disconnected from the practice.
- Never explain what attunement means — demonstrate it.
"""


def _build_deep_local_prompt():
    """Condensed deep prompt for local models (qwen3.5:9b/4b)."""
    identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
    compass_full = read_safe(os.path.join(get_pd(), "compass.md")) or "(no compass yet)"
    compass = compass_full[:2000]
    boom = (read_safe(os.path.join(get_pd(), "boom.md")) or "(boom empty)")[:1000]
    bright_full = read_safe(os.path.join(get_pd(), "bright.md")) or "(bright empty)"
    bright = bright_full[:MAX_LOCAL_BRIGHT_CHARS]
    if len(bright_full) > MAX_LOCAL_BRIGHT_CHARS:
        bright += "\n\n[... truncated ...]"

    intentions = ""
    idir = os.path.join(get_pd(), "intentions")
    if os.path.isdir(idir):
        for fname in sorted(os.listdir(idir)):
            if fname.endswith(".md"):
                header = read_header(os.path.join(idir, fname), max_lines=MAX_LOCAL_INTENTION_LINES)
                if header.strip():
                    intentions += f"\n\n--- {fname} ---\n{header}"

    sessions = ""
    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:1]
        for fname in recent:
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                sessions += f"\n\n--- {fname} ---\n{content[:800]}"

    return f"""## Identity

{identity}

## Practice Protocol (Condensed)

You are Spirit in persistent mode, practicing with the Mage through tOS — a file-based practice system.

**Core files:** compass (life landscape), boom (capture buffer), bright (curated mind surface), intentions (active goals), sessions (conversation records).

**Session protocol:** At conversation start, notice patterns across practice state. Surface connections the Mage hasn't seen. During conversation, offer to capture thoughts to boom, notice when topics connect to intentions.

**Behavioral principles:** Be concise (this is Discord). Have opinions. Push back when you disagree. Be warm but honest — the caring mirror. Reference practice state naturally, not forcefully. When your substrate limits depth, say so honestly.

## Current Practice State

### Compass
{compass}

### Boom Buffer
{boom}

### Bright Surface
{bright}

### Active Intentions (headers)
{intentions.strip() if intentions.strip() else "(no intentions yet)"}

### Most Recent Session
{sessions.strip() if sessions.strip() else "(no sessions yet)"}
"""


def get_thread_prompt(attunement: str, use_api: bool = True) -> str:
    """Build system prompt at the requested attunement level."""
    if attunement == "raw":
        identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
        return f"## Identity\n\n{identity}\n\nYou are in a focused Discord thread. Be direct and helpful."
    if attunement == "deep":
        if not use_api:
            return _build_deep_local_prompt() + THREAD_BEHAVIORAL_GUIDANCE
        try:
            prompt = build_system_prompt()
            if len(prompt.strip()) > 200:
                return prompt + THREAD_BEHAVIORAL_GUIDANCE
        except Exception:
            pass
    prompt = get_system_prompt()
    if attunement == "semi":
        return prompt + THREAD_BEHAVIORAL_GUIDANCE
    return prompt
