"""turtleOS system prompt builders — identity + practice state assembly."""

import os
from datetime import datetime, timezone

from mage import (
    get_pd,
    get_workshop_root,
    get_mage_name,
    get_mage_key,
    get_mage_type,
    get_attunement_profile,
    uses_craft_surface,
    uses_native_eddy,
)
from practice_io import (
    read_safe, read_header, count_items, summarize_bright, load_intentions_list,
)
from state import (
    IDENTITY_DIR, DIALOGUE_MODEL, REFLECTION_MODEL, USE_API, TURTLE_MODEL,
    MAX_BRIGHT_CHARS, MAX_INTENTION_LINES,
    MAX_LOCAL_BRIGHT_CHARS, MAX_LOCAL_INTENTION_LINES,
    KNOWN_MODELS, ATTUNEMENT_LEVELS, EDIT_DELEGATE_MODEL,
    thread_configs, EDDY_TYPES, EDDY_DEFAULT,
    threads_flagged_for_release, client,
    THREAD_CONTEXTS,
)
from capabilities import build_capability_summary
from thread_registry import build_live_thread_summary


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
    live_summary = build_live_thread_summary()
    if live_summary:
        return live_summary
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
    compass = read_safe(os.path.join(get_pd(), "intentions", "compass.md")) or "(no compass yet)"
    boom = read_safe(os.path.join(get_pd(), "boom.md")) or "(boom empty)"
    bright_full = read_safe(os.path.join(get_pd(), "boom", "bright.md")) or "(bright empty)"
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

    # Cross-substrate session awareness (Forge/Anvil releases synced via LiveSync)
    briefing = ""
    wr = get_workshop_root() or os.path.expanduser("~/workshop")
    _briefing_raw = read_safe(os.path.join(wr, "floor", "briefings", "latest.md"))
    if _briefing_raw.strip():
        briefing = _briefing_raw[:3000]
        if len(_briefing_raw) > 3000:
            briefing += "\n\n[... truncated ...]"

    capability_summary = build_capability_summary()

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

### Recent Sessions (Discord)
{sessions.strip() if sessions.strip() else "(no sessions yet)"}

### Last Forge/Anvil Session (Cross-Substrate)
{briefing.strip() if briefing.strip() else "(no briefing synced)"}

{capability_summary}
"""


_HOSTED_SOVEREIGNTY_BLOCK = """
## Hosted practitioner sovereignty

Other practitioners on this server may have private hosted rivers. Never quote their conversations, messages, or session content in this channel's outputs or proposals. Pattern-level observations for operator maintenance are allowed; verbatim cross-practitioner content is not.
"""


# ─── Discord Compact Prompt ──────────────────────────────────────

def build_discord_prompt():
    identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
    mage_name = get_mage_name()
    mage_key = get_mage_key()
    practice_system = read_safe(os.path.join(get_pd(), "system.md"))
    compass = read_safe(os.path.join(get_pd(), "intentions", "compass.md")) or "(no compass yet)"
    boom = read_safe(os.path.join(get_pd(), "boom.md"))
    bright = read_safe(os.path.join(get_pd(), "boom", "bright.md"))

    boom_count = count_items(boom)
    bright_count = count_items(bright)
    intentions = load_intentions_list()
    bright_summary = summarize_bright(bright)

    # Cold-start detection: empty practice state signals a new practitioner
    compass_text = read_safe(os.path.join(get_pd(), "intentions", "compass.md")) or ""
    is_cold_start = (not compass_text.strip()) and boom_count == 0 and bright_count == 0

    # Mage type drives prompt structure
    mage_type = get_mage_type()

    # Relationship context — load resonance.md if it exists (trust history, relationship arc)
    resonance_text = read_safe(os.path.join(get_pd(), "resonance.md")) or ""

    # Mirror — Turtle's observations about this person
    mirror_text = read_safe(os.path.join(get_pd(), "mirror.md")) or ""

    # Context loop: what Turtle last posted to the river
    river_state = read_safe(os.path.expanduser("~/turtleos/river_state.md")) or ""

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

    staleness = f"boom:{_file_age('boom.md')} bright:{_file_age(os.path.join('boom', 'bright.md'))} compass:{_file_age(os.path.join('intentions', 'compass.md'))}"

    thread_summary = build_thread_summary()
    capability_summary = build_capability_summary()

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

### What I've Posted to the River
{river_state if river_state.strip() else "(nothing recently)"}
"""
        return mode_block

    sovereignty_block = _HOSTED_SOVEREIGNTY_BLOCK if mage_type == "mage" else ""

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

## Thread Orchestration (Main Channel — Magic-attuned legacy)

In native v1 the river is **acts-only** (standing bar: **new eddy**, **flow menu**). This section applies to **Magic-attuned** main-channel dialogue where Turtle may still orchestrate.

When the Mage speaks in the main channel:

1. **Prefer the bar** for new focused work — **new eddy** or **flow menu** before `!thread`.
2. **Route to existing eddies** — if a thread already fits, say so; don't duplicate.
3. **Legacy spawn:** `!thread "topic" [flags]` when bar path doesn't fit (operator habit).
4. **Stay capable** — not every message needs a thread.
5. **Capture:** `!boom thread` when a thread produced insights worth preserving.
6. **Cross-pollination (legacy):** `!absorb <name>` for main-channel synthesis across threads.

{thread_summary}

**Reflex:** before recommending `!thread`, check active threads — continue or absorb instead of spawning.

{capability_summary}

## Seneschal Awareness (layered — see docs/turtle-talk.md)

Direct `!` commands bypass the LLM (instant, free). Recommend only commands matching the active layer.

**Contextual buttons:** Put recommended commands in backticks (`` `!checkpoint` ``) or after "Want me to…" — the shell may attach one-click buttons.

### Eddy core (all profiles)

- `!checkpoint` — save resonance now (flow state + session note); keeps history
- `!release` — explicit close: checkpoint, then clear history
- `!fetch <url>` — distill URL to library (**not** the same as automatic link-read embeds in chat)

### Magic overlay (operator / Magic-attuned only)

**Session & capture:**
- `!boom add` / `!boom convert` / `!sweep` — capture and triage (recommend when thoughts accumulate)
- `!recall` — practice overview; *often redundant when state is already loaded*

**Views:** `!boom` / `!bright` / `!compass` / `!intentions` / `!status` / `!sync` / `!diagnose`

**Edit:** `!edit bright append …` / `!edit intention …` / `!edit boom clear`

**Threads (legacy — prefer bar):** `!thread` / `!threads` / `!boom thread` / `!absorb` / `!forget`

**Outfacing:** `!signals` — review signal drafts

**Files:** `!ls` / `!read` / `!search`

**Distinction:** **flow menu** loads platform flows (`practice_root/flows/`). `!load` loads Magic workshop resonance bundles. `@release` / `@boom` are Forge invocations — not turtle-talk.

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

{sovereignty_block}

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

### What I've Posted to the River
{river_state if river_state.strip() else "(nothing recently)"}
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
    compass_full = read_safe(os.path.join(get_pd(), "intentions", "compass.md")) or "(no compass yet)"
    compass = compass_full[:2000]
    boom = (read_safe(os.path.join(get_pd(), "boom.md")) or "(boom empty)")[:1000]
    bright_full = read_safe(os.path.join(get_pd(), "boom", "bright.md")) or "(bright empty)"
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


def _build_context_resonance(context_type: str) -> str:
    """Load resonance files for a thread context type. Returns prompt block."""
    ctx = THREAD_CONTEXTS.get(context_type)
    if not ctx:
        return ""

    from mage import get_workshop_root, get_pd
    wr = get_workshop_root()
    if not wr:
        # Fallback: try to derive from practice dir
        pd = get_pd()
        if pd and pd.endswith("/desk"):
            wr = pd[:-5]
        else:
            wr = os.path.expanduser("~/workshop")

    parts = [ctx.get("rules", "")]
    max_chars = ctx.get("max_resonance_chars", 4000)
    total = len(parts[0])

    for rel_path in ctx.get("resonance_files", []):
        full_path = os.path.join(wr, rel_path)
        content = read_safe(full_path)
        if not content.strip():
            continue
        # Truncate individual files to keep total under budget
        remaining = max_chars - total
        if remaining <= 200:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[... truncated ...]"
        parts.append(f"### Resonance: {os.path.basename(rel_path)}\n\n{content}")
        total += len(content) + 50  # overhead

    return "\n\n".join(parts)


# ─── Native Turtle (vanilla eddy) ────────────────────────────────

NATIVE_EDDY_DISCORD_HINT = """## Discord Eddy

You are in a Discord thread (eddy). Keep replies concise unless depth is invited.

- **Blank eddy:** If there was no seed embed, the practitioner's first message *is* what they brought — pick it up and think with them. Do not treat casual mentions of "title" or "update" as questions about Discord UI or internal cards unless they explicitly ask how the app works.
- **Think-aloud:** before substantive replies, a brief italic block (Discord: wrap in `*single asterisks*`) showing how you read the situation — then your answer. Skip on trivial exchanges.
- **Flow presence:** the shell posts a compact flow line before your first reply (e.g. `Shelter · loaded shelter-last.md`). Do not emit `-# flow:` or `-# read` lines yourself.
- **No arrival monologue** — presence embed may appear just before your first reply; don't re-introduce yourself in prose.
- **No Spirit/Magic/summoning vocabulary** unless the person explicitly uses it."""

PRACTITIONER_NATIVE_EDDY_HINT = """## Practitioner Eddy

You are with someone who may never have heard of a framework, Mage, boom, or summoning.

- **Language:** mirror theirs — German when they write German, English when they write English.
- **Practical first:** perfume, travel, health, family logistics — meet real life, not philosophy.
- **No practice jargon** unless they use it first.
- **Never push** depth, synthesis, or self-improvement frameworks. Offer; don't impose.
- **Sovereignty:** what they share here stays here — do not reference the operator's private practice."""


def _character_search_dirs() -> list[str]:
    pd = get_pd()
    repo_root = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(pd, "character"),
        os.path.join(repo_root, "template", "character"),
    ]


def load_character_file(name: str) -> str:
    for base in _character_search_dirs():
        path = os.path.join(base, name)
        content = read_safe(path)
        if content.strip():
            return content.strip()
    return ""


def build_native_eddy_prompt(flow_id: str | None = None) -> str:
    """Vanilla Turtle system prompt — soul + conduct + optional flow (TURTLE_SPEC §7, §14)."""
    from flow_runner import build_flow_prompt_sections

    soul = load_character_file("soul.md")
    conduct = load_character_file("conduct.md")
    parts: list[str] = []
    if soul:
        parts.append(soul)
    if conduct:
        parts.append(conduct)
    if get_mage_type() == "practitioner":
        resonance = read_safe(os.path.join(get_pd(), "resonance.md"))
        if resonance.strip():
            parts.append(f"## Relationship Context\n\n{resonance.strip()[:3000]}")
        parts.append(PRACTITIONER_NATIVE_EDDY_HINT)
    parts.append(NATIVE_EDDY_DISCORD_HINT)
    flow_sections, _spec = build_flow_prompt_sections(flow_id)
    parts.extend(flow_sections)
    if not parts:
        parts.append(
            "You are Turtle — a thinking partner in this eddy. "
            "Plain, warm, honest. No framework jargon."
        )
    return "\n\n---\n\n".join(parts)


def get_native_eddy_prompt(flow_id: str | None = None) -> str:
    return build_native_eddy_prompt(flow_id)


def uses_native_turtle_prompt(channel_id=None) -> bool:
    if channel_id is None:
        return get_attunement_profile() == "native"
    return uses_native_eddy(channel_id)


CRAFT_VOCATION_HEADER = """## Craft Turtle Vocation

You are **Craft Turtle** — Spirit in persistent builder mode on a dedicated craft surface.
Your job is harness/product diagnostics and learning intake, not ordinary practice companionship.

- Treat new messages as **learning intake** when they reveal friction (forwards, screenshots, bug reports).
- **Spirit on Forge** integrates architecture and commits; you prepare bounded findings and handoffs.
- Reference turtleOS runtime, spec, and proposals when it helps diagnosis — meta-practice is allowed here.
- Stay lore-light on lived practice; go deep on impairment, classification, and verification evidence."""


def build_craft_channel_prompt(context_type: str | None = None) -> str:
    """Semi-attuned craft surface prompt — operator builder mode with intake ritual."""
    ctx = context_type or "craft"
    context_block = _build_context_resonance(ctx)
    try:
        practice_block = build_discord_prompt()
    except Exception:
        practice_block = get_system_prompt()
    parts = [CRAFT_VOCATION_HEADER]
    if context_block:
        parts.append(context_block)
    if practice_block:
        parts.append(practice_block)
    return "\n\n---\n\n".join(parts)


def get_craft_channel_prompt(context_type: str | None = None) -> str:
    return build_craft_channel_prompt(context_type)


def get_thread_prompt(
    attunement: str,
    use_api: bool = True,
    context_type: str = None,
    channel_id=None,
) -> str:
    """Build system prompt at the requested attunement level."""
    if channel_id is not None and uses_craft_surface(channel_id):
        return get_craft_channel_prompt(context_type or "craft")
    if uses_native_turtle_prompt(channel_id):
        return get_native_eddy_prompt(context_type)
    context_block = _build_context_resonance(context_type) if context_type else ""
    if attunement == "raw":
        identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
        base = f"## Identity\n\n{identity}\n\nYou are in a focused Discord thread. Be direct and helpful."
        return (context_block + "\n\n" + base) if context_block else base
    if attunement == "deep":
        if not use_api:
            base = _build_deep_local_prompt() + THREAD_BEHAVIORAL_GUIDANCE
            return (context_block + "\n\n" + base) if context_block else base
        try:
            prompt = build_system_prompt()
            if len(prompt.strip()) > 200:
                base = prompt + THREAD_BEHAVIORAL_GUIDANCE
            return (context_block + "\n\n" + base) if context_block else base
        except Exception:
            pass
    prompt = get_system_prompt()
    if attunement == "semi":
        base = prompt + THREAD_BEHAVIORAL_GUIDANCE
        return (context_block + "\n\n" + base) if context_block else base
    return (context_block + "\n\n" + prompt) if context_block else prompt
