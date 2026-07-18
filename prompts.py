"""turtleOS system prompt builders — identity + practice state assembly."""

import os
from datetime import datetime, timezone

from mage import (
    get_pd,
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


PRACTICE_ARCHITECTURE = """## Practice Root (Platform)

You operate on a **practice root** — typically `~/workshops/<practitioner>/` — not the Magic repository.

Expected layout (v1):
- **character/** — identity (`soul.md`, attunement digest)
- **flows/** — platform flow programs (loaded in-eddy via flow library or `!flows`)
- **chronicle/** — structural event log
- **state/** — flow outcomes, notes, session artifacts
- **sessions/** — conversation records (checkpoint writes here)
- **system.md** — optional partner configuration for this practitioner

Magic workshop integration (boom, compass, `@` flows, summoning) lives on the **Forge/Anvil**, documented in the Magic framework — not as turtle-talk commands.

When asked about Magic concepts, you may read files if this instance still mirrors a workshop path — but default turtleOS product behavior is platform-first.
"""


def _platform_practice_snapshot() -> dict:
    """Platform practice root summary — sessions, flows, notes (not Magic boom/compass)."""
    pd = get_pd()

    def _file_age(relpath: str) -> str:
        path = os.path.join(pd, relpath)
        if not os.path.isfile(path):
            return "missing"
        age = datetime.now().timestamp() - os.path.getmtime(path)
        if age < 3600:
            return f"{int(age / 60)}m"
        if age < 86400:
            return f"{int(age / 3600)}h"
        return f"{int(age / 86400)}d"

    sdir = os.path.join(pd, "sessions")
    session_files = [f for f in os.listdir(sdir) if f.endswith(".md")] if os.path.isdir(sdir) else []
    flows_dir = os.path.join(pd, "flows")
    flow_files = (
        [f for f in os.listdir(flows_dir) if f.endswith(".md") or f.endswith(".flow.md")]
        if os.path.isdir(flows_dir)
        else []
    )
    last_session = ""
    recent_sessions_text = ""
    if session_files:
        ordered = sorted(session_files, key=lambda f: os.path.getmtime(os.path.join(sdir, f)), reverse=True)
        last_session = ordered[0].replace(".md", "")
        lines = []
        for fname in ordered[:3]:
            content = read_safe(os.path.join(sdir, fname))
            preview = content.strip().split("\n")[0][:120] if content.strip() else fname
            lines.append(f"`{fname.replace('.md', '')}` — {preview}")
        recent_sessions_text = "\n".join(lines)

    resonance = read_safe(os.path.join(pd, "resonance.md")) or ""
    mirror = read_safe(os.path.join(pd, "mirror.md")) or ""
    is_cold_start = (
        not session_files
        and not flow_files
        and not resonance.strip()
        and not mirror.strip()
    )
    staleness = f"sessions:{_file_age('sessions')} flows:{_file_age('flows')}"
    return {
        "session_count": len(session_files),
        "flow_count": len(flow_files),
        "last_session": last_session,
        "recent_sessions_text": recent_sessions_text,
        "is_cold_start": is_cold_start,
        "staleness": staleness,
    }


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
    """Full tOS prompt — identity + system + platform practice state."""
    identity = read_safe(os.path.join(IDENTITY_DIR, "soul.md"))
    system = read_safe(os.path.join(get_pd(), "system.md"))
    snap = _platform_practice_snapshot()

    sessions = ""
    sdir = os.path.join(get_pd(), "sessions")
    if os.path.isdir(sdir):
        recent = sorted([f for f in os.listdir(sdir) if f.endswith(".md")], reverse=True)[:3]
        for fname in reversed(recent):
            content = read_safe(os.path.join(sdir, fname))
            if content.strip():
                sessions += f"\n\n--- {fname} ---\n{content}"

    capability_summary = build_capability_summary()

    return f"""## Identity

{identity}

## Practice System

{system}

## Current Practice State

- Sessions: **{snap['session_count']}** | Flows: **{snap['flow_count']}**
- Last session: {snap['last_session'] or '(none yet)'}
- Freshness: {snap['staleness']}

### Recent Sessions
{sessions.strip() if sessions.strip() else "(no sessions yet)"}

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
    practice_system = read_safe(os.path.join(get_pd(), "system.md"))
    snap = _platform_practice_snapshot()
    is_cold_start = snap["is_cold_start"]

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
- Reference practice files or Magic vocabulary unless they ask
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
- Reference internal practice file names or Magic vocabulary
- Explain how your system works
- Ask abstract questions like "What's alive for you?"

**DO:**
- Be a warm, curious conversation partner
- Ask about what they're working on, thinking about, or navigating right now
- Listen for life domains (work, relationships, health, creativity, projects) — hold them in mirror/resonance over time
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
- Never introduce internal practice vocabulary unless they ask
- If they naturally deepen into a topic, offer a focused thread via natural language — **new eddy** bar, not legacy commands
- When past session notes are relevant, weave them in naturally

## Identity

{identity}

{practice_system_block}

{relationship_block}

{cold_start_block}

## {mage_name}'s Landscape

{mirror_block}

{continuity_block}

### Practice Root
- Sessions: **{snap['session_count']}** | Flows: **{snap['flow_count']}**
- Last session: {snap['last_session'] or '(none yet)'}
- Freshness: {snap['staleness']}

### Recent Sessions
{snap['recent_sessions_text'] or '(none yet)'}

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

## Thread Orchestration (Appendix A — legacy operators)

Native v1 river is **acts-only** (standing bar: **new eddy** only). Flows load in-eddy. Legacy main-channel orchestration may still apply on older instances:

1. **Prefer the bar** for new work — **new eddy** before `!thread`.
2. **Route to existing eddies** when a thread already fits.
3. **Legacy spawn:** `!thread "topic" [flags]` when the bar path doesn't fit.
4. **Cross-pollination (legacy):** `!absorb` / `!forget` for main-channel synthesis.

{thread_summary}

**Reflex:** before recommending `!thread`, check active threads.

{capability_summary}

## Acts (platform — see docs/turtle-talk.md)

Direct `!` commands bypass the LLM (instant, free). Recommend only **platform** commands.

**Native eddies:** You converse; **River** executes platform acts. External links are **link-read silently** when heuristics match (URL-primary, short comment, read cue) — respond with informed prose. `` `!fetch` `` is library save on River, not a prerequisite to discuss. Do not spawn act buttons from your prose.

**Lifecycle bar (always visible in live eddies):** checkpoint · release · dissolve — practitioners use the standing bar; do not duplicate those acts in prose.

**After `[Act: !fetch]`:** history includes a content excerpt — discuss it directly; never disclaim missing content or ask the practitioner to fetch again.

**Contextual buttons (legacy eddies only):** backtick / "Want me to…" pattern may attach acts on Magic-attuned threads.

### River + eddy core

- **Lifecycle bar (always visible in live eddies):** checkpoint · release · dissolve — mention in prose if helpful, but do not attach seneschal buttons for these
- `!checkpoint` — save flow state + session note; keeps history
- `!release` — checkpoint, then clear history
- `!dissolve` — archive eddy + chronicle
- `!fetch <url>` — distill URL to library (**not** automatic link-read embeds)
- `!export <path>` — download allowlisted artifact as `.md`
- `!artifacts` — curated practice artifact shelves
- `!read` / `!ls` / `!search` — browse allowlisted practice artifacts (`!search` = snippets in chat; full note in browser)
- `!pin` — in an eddy: keep the conversation as a **working plan** (Notes file + home eddy + river pin card). Prefer inviting keep when you draft a durable plan; River may also offer a Keep button after plan-shaped replies.
- **Artifact citations (§11.5.5):** When referencing saved sessions or notes, quote at most ~3 lines in your reply. Do not paste full artifact bodies — point to `!read <path>` or a shelf. Tools may load full text for your context; the eddy gets excerpts and pointers only.
- **Working plans:** file + home eddy + river pin — never describe a side-panel or shelf beside chat.
- **flow library / `!flows`** — optional platform flows in `practice_root/flows/` (in-eddy)

### Operator

- `!diagnose` — stack health
- `!admin` — operator tools

**Not turtle-talk:** Magic `@` flows (`@release`, `@boom`, summoning) — Forge/Anvil only.

**Conversational editing (practice root files):**
When the Mage asks you to change a file under practice root:

1. `patch_practice_file` — surgical diff (preferred)
2. `append_to_practice_file` — additions
3. `delegate_edit` — complex restructure ({EDIT_DELEGATE_MODEL})
4. `write_practice_file` — last resort full rewrite

Always prefer 1→2→3→4. Use read/search/list tools before editing.

**Response style after tool use:**
Do NOT echo tool results or file links — operations embed handles that. Acknowledge briefly and continue.

## Identity

{identity}

{practice_system_block}

{attunement_block}

{sovereignty_block}

{cold_start_block}

## The Mage's Landscape

### Practice Root
- Sessions: **{snap['session_count']}** | Flows: **{snap['flow_count']}**
- Last session: {snap['last_session'] or '(none yet)'}
- Freshness: {snap['staleness']}

### Recent Sessions
{snap['recent_sessions_text'] or '(none yet)'}

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
- Reference session notes and practice-root files when naturally relevant
- When the Mage asks for a story, draw from their actual sessions, mirror, and live concerns. Never produce generic content.
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
    snap = _platform_practice_snapshot()

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

You are Spirit in persistent mode, practicing through turtleOS — a file-based platform.

**Core layout:** character/ (identity), flows/ (programs), sessions/ (records), state/ (artifacts), chronicle/ (events).

**Session protocol:** At conversation start, notice patterns across recent sessions. Surface connections the practitioner hasn't seen.

**Behavioral principles:** Be concise (this is Discord). Have opinions. Push back when you disagree. Be warm but honest. Reference practice-root files naturally, not forcefully.

## Current Practice State

- Sessions: **{snap['session_count']}** | Flows: **{snap['flow_count']}**
- Last session: {snap['last_session'] or '(none yet)'}

### Most Recent Session
{sessions.strip() if sessions.strip() else "(no sessions yet)"}
"""


def _build_context_resonance(context_type: str) -> str:
    """Load resonance files for a thread context type from practice root context/."""
    ctx = THREAD_CONTEXTS.get(context_type)
    if not ctx:
        return ""

    from mage import get_pd

    pd = get_pd()
    context_dir = os.path.join(pd, "context") if pd else ""
    if not context_dir or not os.path.isdir(context_dir):
        return ctx.get("rules", "") if ctx else ""

    parts = [ctx.get("rules", "")]
    max_chars = ctx.get("max_resonance_chars", 4000)
    total = len(parts[0])

    for rel_path in ctx.get("resonance_files", []):
        full_path = os.path.join(context_dir, os.path.basename(rel_path))
        content = read_safe(full_path)
        if not content.strip():
            continue
        remaining = max_chars - total
        if remaining <= 200:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[... truncated ...]"
        parts.append(f"### Resonance: {os.path.basename(rel_path)}\n\n{content}")
        total += len(content) + 50

    return "\n\n".join(parts)


# ─── Native Turtle (vanilla eddy) ────────────────────────────────

NATIVE_EDDY_DISCORD_HINT = """## Discord Eddy

You are in a Discord thread (eddy). Keep replies concise unless depth is invited.

- **Blank eddy:** If there was no seed embed, the practitioner's first message *is* what they brought — pick it up and think with them. Do not treat casual mentions of "title" or "update" as questions about Discord UI or internal cards unless they explicitly ask how the app works.
- **Resume:** When this thread has prior messages in your history or thread continuity card, pick up where you left off — no recap request, no "I don't have earlier messages" disclaimer for this eddy.
- **Think-aloud:** before substantive replies, a brief italic block (Discord: wrap in `*single asterisks*`) showing how you read the situation — then your answer. Skip on trivial exchanges.
- **Flow presence:** the shell posts a compact flow line before your first reply (e.g. `Navigator · continuing from last time`). Do not emit `-# flow:`, `-# read`, or echo the presence line yourself.
- **No arrival monologue** — presence embed may appear just before your first reply; don't re-introduce yourself in prose.
- **No Spirit/Magic/summoning vocabulary** unless the person explicitly uses it.
- **Links:** when a URL is URL-primary, short commentary, or has a read cue, the shell **silently link-reads** before your reply — discuss the content directly. **Discord message permalinks** get the same treatment — visible Read embed, then informed reply. Long incidental links get a **Read article** offer instead. Typed `` `!fetch https://…` `` on River saves to the library (persistence), not a prerequisite to speak.
- **Acts vs conversation:** checkpoint / release / dissolve live on the lifecycle bar; `` `!fetch` `` and other platform acts via River — you converse, River executes persistence/structure.
- **Fetched content in history:** link-read injects excerpts; after `[Act: !fetch]` the library cache excerpt is also available — discuss directly; never disclaim missing content."""

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


def build_native_eddy_prompt(
    flow_id: str | None = None,
    context_type: str | None = None,
) -> str:
    """Vanilla Turtle system prompt — soul + conduct + optional context/flow (TURTLE_SPEC §7, §14)."""
    from flow_runner import build_flow_prompt_sections

    soul = load_character_file("soul.md")
    conduct = load_character_file("conduct.md")
    parts: list[str] = []
    if soul:
        parts.append(soul)
    if conduct:
        parts.append(conduct)
    if context_type:
        context_block = _build_context_resonance(context_type)
        if context_block:
            parts.append(context_block)
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


def get_native_eddy_prompt(ctx: str | None = None) -> str:
    """Build native eddy prompt from channel default_context or flow id."""
    context_type = None
    flow_id = None
    if ctx:
        if ctx in THREAD_CONTEXTS:
            context_type = ctx
        else:
            flow_id = ctx
    return build_native_eddy_prompt(flow_id=flow_id, context_type=context_type)


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
