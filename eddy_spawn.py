"""turtleOS eddy spawn — auto-create focused threads from rich content.

Core pattern: the standing vortex (🌀 new eddy) acts as a thread launcher.
Anything posted into the vortex auto-spawns a new eddy
in the parent channel, seeded with the content. The vortex
is the front door — drop content, get a focused conversation.

Also supports:
  !new [topic]  — explicit command from main channel
  Auto-detect   — URL/long-text messages in main channel get a button
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import discord

from llm import chat_ollama
from mage import get_pd
from practice_io import read_safe
from state import EDDY_TYPES, EDDY_DEFAULT, REFLECTION_MODEL
from helpers import local_now, split_message

TOPIC_MODEL = "qwen3.5:9b"
TOPIC_CTX = 2048
TOPIC_TIMEOUT = 15

INTAKE_PATTERNS = {"vortex", "new", "new thread", "intake", "new eddy"}
INTAKE_EMOJI_PREFIXES = {"🌀"}

URL_PATTERN = re.compile(r'https?://\S+')
LONG_TEXT_THRESHOLD = 250
MULTI_PARAGRAPH_THRESHOLD = 3

TOPIC_PROMPT = (
    "Generate a short, specific thread title (2-5 words) for a conversation "
    "about the following content. Be concrete, not generic. No quotes, no "
    "punctuation, lowercase preferred.\n\nContent:\n{content}"
)

INTAKE_PROMPT = (
    "You are Turtle, a practice companion. Someone just dropped content into "
    "the intake to start a focused conversation. Read what they shared and "
    "respond with a brief opening (2-4 sentences) that shows you understood "
    "the core of what they're bringing. Don't summarize — reflect the intent "
    "back, name what seems most alive, and invite the thread forward. "
    "Be warm but concise."
)

PRISM_PROMPT = (
    "You are a resonance router. Given incoming content and a list of active "
    "conversation threads, determine if the content strongly resonates with "
    "an existing thread.\n\n"
    "Rules:\n"
    "- Only match if the content is clearly about the same topic\n"
    "- Prefer an existing thread over creating a new one when there is genuine overlap\n"
    "- If no thread is a strong match, respond with exactly: NEW\n"
    "- If a thread matches, respond with exactly its number (e.g. 3)\n"
    "- Respond with ONLY the number or NEW, nothing else\n"
)

THREAD_OPENING_MODEL = "qwen3.5:9b"
THREAD_OPENING_CTX = 4096
THREAD_OPENING_TIMEOUT = 20

OPERATIONAL_TOPIC_PATTERNS = (
    "fix", "debug", "ship", "implement", "deploy", "refactor", "diagnose",
    "bug", "issue", "error", "test", "tool", "command", "script", "api",
    "runtime", "canary", "sync", "git", "commit",
)

THREAD_OPENING_PROMPT = (
    "You are Turtle opening a newly-created Discord thread for a practice conversation.\n"
    "Write the first message in the thread. Keep it short: 3-5 lines max.\n"
    "Do not over-explain. Do not produce a generic welcome.\n"
    "Name where the thread came from, what it is for, and the live question.\n"
    "If practice state is relevant, weave in at most one concrete signal from it.\n\n"
    "Mode: {mode}\n"
    "Topic: {topic}\n"
    "Origin: {origin}\n"
    "Source excerpt: {source_excerpt}\n"
    "Practice state:\n{practice_state}\n\n"
    "Opening message:"
)

SYSTEM_EDDY_NAMES = {"vortex", "boom", "new eddy", "new thread", "intake"}
SYSTEM_EDDY_PREFIXES = {"🌀", "🐢"}
_PENDING_EDDY_TOPICS: dict[tuple[int, int], str] = {}


def _is_operational_topic(topic: str) -> bool:
    lower = topic.lower()
    return any(pattern in lower for pattern in OPERATIONAL_TOPIC_PATTERNS)


def _is_explicit_test_thread(topic: str) -> bool:
    """Detect model/substrate test threads where auto-openings can prime behavior."""
    lower = topic.lower().strip()
    tokens = re.split(r'[\s_-]+', lower)
    return (
        lower.startswith('model-test')
        or lower.endswith('-test')
        or 'model-test' in lower
        or ('test' in tokens and any(t in tokens for t in ('model', 'qwen', 'sonnet', 'claude')))
    )


def _practice_state_excerpt(topic: str, limit: int = 1800) -> str:
    """Pull small practice-state slices so openings can orient without becoming briefings."""
    pd = get_pd()
    topic_terms = [t for t in re.findall(r"\w+", topic.lower()) if len(t) >= 4]
    sections = []

    bright = read_safe(os.path.join(pd, "boom", "bright.md"))
    if bright:
        bright_lines = []
        for line in bright.splitlines():
            lower = line.lower()
            if any(term in lower for term in topic_terms):
                bright_lines.append(line.strip())
            if len(bright_lines) >= 3:
                break
        if bright_lines:
            sections.append("Bright:\n" + "\n".join(bright_lines))

    compass = read_safe(os.path.join(pd, "intentions", "compass.md"))
    if compass:
        sections.append("Compass excerpt:\n" + compass[:700])

    intentions_dir = os.path.join(pd, "intentions", "active")
    try:
        intention_hits = []
        for name in os.listdir(intentions_dir):
            if not name.endswith(".md"):
                continue
            path = os.path.join(intentions_dir, name)
            text = read_safe(path)
            lower = (name + "\n" + text).lower()
            if any(term in lower for term in topic_terms):
                title = name[:-3].replace("_", " ")
                intention_hits.append(f"- {title}")
            if len(intention_hits) >= 3:
                break
        if intention_hits:
            sections.append("Active intentions:\n" + "\n".join(intention_hits))
    except Exception:
        pass

    return "\n\n".join(sections)[:limit] if sections else "No matching practice state found."


def _fallback_thread_opening(topic: str, origin: str, source_excerpt: str = "") -> str:
    topic = topic.strip() or "this thread"
    if source_excerpt:
        return (
            f"Opening this thread from {origin}.\n"
            f"The focus is **{topic}**.\n"
            f"What I’m carrying in: {source_excerpt[:220].strip()}\n"
            "Let’s continue from there."
        )
    return (
        f"Opening this thread from {origin}.\n"
        f"The focus is **{topic}**.\n"
        "I’ll hold this as the live question and we can shape it from here."
    )


async def compose_thread_opening(topic: str, origin: str, source_text: str = "") -> str:
    """Generate a compact first message for newly-created eddies."""
    source_excerpt = " ".join(source_text.split())[:700] if source_text else ""
    mode = "task/operational" if _is_operational_topic(topic) else "resonance/practice"
    practice_state = _practice_state_excerpt(topic) if mode == "resonance/practice" else "Not needed for this operational thread."

    prompt = THREAD_OPENING_PROMPT.format(
        mode=mode,
        topic=topic,
        origin=origin,
        source_excerpt=source_excerpt or "(none)",
        practice_state=practice_state,
    )
    try:
        opening = await asyncio.wait_for(
            chat_ollama(
                prompt,
                [{"role": "user", "content": "Open the thread now."}],
                model=THREAD_OPENING_MODEL,
                num_ctx=THREAD_OPENING_CTX,
                think=False,
            ),
            timeout=THREAD_OPENING_TIMEOUT,
        )
        if opening and opening.strip():
            return opening.strip()
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Thread opening generation failed: {type(e).__name__}: {e}")

    return _fallback_thread_opening(topic, origin, source_excerpt)


async def post_thread_opening(thread, topic: str, origin: str, source_text: str = ""):
    """Post the orientation message for a newly-created thread."""
    if _is_explicit_test_thread(topic):
        print(f'Thread opening suppressed for test thread: {topic}')
        return ""

    opening = await compose_thread_opening(topic, origin, source_text)
    for chunk in split_message(opening):
        await thread.send(chunk)
    return opening


def _is_system_eddy(name: str) -> bool:
    """Check if a thread name indicates a system eddy (not routable)."""
    lower = name.lower().strip()
    if lower in SYSTEM_EDDY_NAMES:
        return True
    for prefix in SYSTEM_EDDY_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


async def detect_resonance(content: str, active_threads: list[dict]) -> dict | None:
    """Prism: detect if content resonates with an existing eddy.

    Returns the matching thread dict, or None if content is novel.
    active_threads: list of {"id": str, "name": str} for routable eddies.
    """
    if not active_threads:
        return None

    numbered = "\n".join(
        f"{i+1}. {t['name']}" for i, t in enumerate(active_threads)
    )
    snippet = content[:1500]
    user_msg = f"Active threads:\n{numbered}\n\nIncoming content:\n{snippet}"

    try:
        result = await asyncio.wait_for(
            chat_ollama(
                PRISM_PROMPT,
                [{"role": "user", "content": user_msg}],
                model=TOPIC_MODEL,
                num_ctx=TOPIC_CTX,
                think=False,
            ),
            timeout=TOPIC_TIMEOUT,
        )
        if not result:
            return None

        answer = result.strip()
        if answer.upper() == "NEW":
            return None

        # Extract number
        import re as _re
        m = _re.search(r'(\d+)', answer)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(active_threads):
                match = active_threads[idx]
                print(f"Prism: routed to \"{match['name']}\" (idx {idx+1})")
                return match

    except (asyncio.TimeoutError, Exception) as e:
        print(f"Prism detection failed: {type(e).__name__}: {e}")

    return None


async def get_routable_eddies(guild_id: str) -> list[dict]:
    """Get active non-system eddies from the river channel."""
    from state import client

    guild = client.get_guild(int(guild_id))
    if not guild:
        return []

    eddies = []
    for thread in guild.threads:
        if thread.parent_id != int("1479428854513664030"):
            continue
        if _is_system_eddy(thread.name):
            continue
        if thread.archived:
            continue
        eddies.append({"id": str(thread.id), "name": thread.name, "thread": thread})

    return eddies


def _build_route_embed(author_name: str, content: str, url_content: str = "") -> discord.Embed:
    """Build an embed for content routed to an existing eddy."""
    embed = discord.Embed(
        description=content[:4000],
        color=0x9B59B6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=author_name)
    if url_content:
        preview = url_content[:1000]
        if len(url_content) > 1000:
            preview += "\n\u2026"
        embed.add_field(name="Linked content", value=preview, inline=False)
    embed.set_footer(text="\U0001f300 routed from vortex")
    return embed


async def route_to_eddy(message, target_thread, url_content: str = ""):
    """Route vortex content to an existing eddy."""
    from state import dialogue_histories
    from helpers import split_message

    content = message.content.strip()

    # Post routed content embed in target thread
    route_embed = _build_route_embed(
        message.author.display_name,
        content,
        url_content=url_content[:2000] if url_content else "",
    )
    await target_thread.send(embed=route_embed)

    # Build user entry for dialogue history
    user_entry = f"[{message.author.display_name}]: {content}"
    if url_content:
        user_entry += f"\n\n[Linked content]:\n{url_content[:6000]}"

    # Append to existing dialogue history (or create new)
    if target_thread.id not in dialogue_histories:
        dialogue_histories[target_thread.id] = []
    dialogue_histories[target_thread.id].append({"role": "user", "content": user_entry})

    # Generate Turtle's response in the thread
    from prompts import get_thread_prompt
    system_prompt = get_thread_prompt("semi", False)
    history = dialogue_histories[target_thread.id]

    try:
        async with target_thread.typing():
            from llm import chat_ollama_with_tools
            from tos_tools import TOS_TOOLS, execute_tos_tool
            reply, _ = await chat_ollama_with_tools(
                system_prompt, history[-20:],
                tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool,
            )
            if not reply:
                reply = "*listening*"
    except Exception as e:
        print(f"Route response failed: {e}")
        reply = "*listening*"

    dialogue_histories[target_thread.id].append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await target_thread.send(chunk)

    # Confirmation in vortex
    await message.reply(
        f"\U0001f300 \u2192 **{target_thread.name}** *(routed)*\n-# {target_thread.mention}",
        mention_author=False,
    )

    print(f"Prism: routed to {target_thread.name} (id: {target_thread.id})")
    return target_thread



def _is_thread_channel(channel) -> bool:
    return getattr(channel, "parent_id", None) is not None


def is_native_river_eddy(channel) -> bool:
    """River-materialized blank eddy — not the legacy vortex/intake thread."""
    if not _is_thread_channel(channel):
        return False
    parent_id = channel.parent_id
    if is_awaiting_title(channel.id, parent_id):
        return True
    try:
        from commands import thread_configs

        cfg = thread_configs.get(channel.id)
        if cfg and cfg.get("native_vanilla"):
            return True
    except Exception:
        pass
    return False


def is_intake_thread(channel) -> bool:
    """Check if a channel is the standing intake eddy.

    Matches by name (case-insensitive, stripped) or emoji prefix + known pattern.
    Examples: "new thread", "🌀 new eddy", "🌀 intake"
    """
    if not _is_thread_channel(channel):
        return False
    if is_native_river_eddy(channel):
        return False
    name = channel.name.strip()
    name_lower = name.lower()
    if name_lower in INTAKE_PATTERNS:
        return True
    for prefix in INTAKE_EMOJI_PREFIXES:
        if name.startswith(prefix):
            stripped = name[len(prefix):].strip().lower()
            if stripped in INTAKE_PATTERNS:
                return True
    return False


def should_offer_eddy(message) -> bool:
    """Detect whether a main-channel message is a thread seed."""
    if isinstance(message.channel, discord.Thread):
        return False

    text = message.content.strip()

    if not text and not message.attachments:
        return False
    if text.startswith("!"):
        return False

    has_urls = bool(URL_PATTERN.search(text))
    is_long = len(text) > LONG_TEXT_THRESHOLD
    is_multi = text.count("\n\n") >= MULTI_PARAGRAPH_THRESHOLD
    has_attachments = bool(message.attachments)
    has_code = "```" in text

    if has_urls:
        return True
    if is_long and (is_multi or has_code):
        return True
    if has_attachments:
        return True

    return False


async def generate_topic(content: str) -> str:
    """Generate a thread topic from content using a fast local model."""
    snippet = content[:1500]
    try:
        result = await asyncio.wait_for(
            chat_ollama(
                "You generate short thread titles. Respond with ONLY the title, nothing else.",
                [{"role": "user", "content": TOPIC_PROMPT.format(content=snippet)}],
                model=TOPIC_MODEL,
                num_ctx=TOPIC_CTX,
                think=False,
            ),
            timeout=TOPIC_TIMEOUT,
        )
        if result:
            topic = result.strip().strip('"\'').strip()
            topic = topic.split("\n")[0][:80]
            if topic:
                return topic
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Topic generation failed: {type(e).__name__}: {e}")

    urls = URL_PATTERN.findall(content)
    if urls:
        from urllib.parse import urlparse
        domain = urlparse(urls[0]).netloc.replace("www.", "")
        return f"shared from {domain}"

    first_line = content.strip().split("\n")[0][:60]
    return first_line if first_line else "new thread"


async def spawn_eddy_in_channel(channel, content: str, topic: str | None = None,
                                 eddy_type: str = "standard"):
    """Create a thread in a channel (not from a message). Used by the intake pattern.

    Returns the created thread, or None on failure.
    """
    from commands import thread_configs, _build_config_line, ThreadConfigView
    from llm import resolve_model
    from mage import get_thread_member_ids
    from thread_registry import register_thread
    from state import client

    if not topic:
        topic = await generate_topic(content)

    model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)

    try:
        thread = await channel.create_thread(
            name=topic,
            auto_archive_duration=eddy_archive,
            type=discord.ChannelType.public_thread,
        )
    except discord.HTTPException as e:
        print(f"Eddy spawn in channel failed: {e}")
        return None

    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": None,
        "created": datetime.now(timezone.utc),
    }

    for uid in get_thread_member_ids(channel.id):
        try:
            user = await client.fetch_user(int(uid))
            await thread.add_user(user)
        except Exception:
            pass

    register_thread(
        thread.id, topic,
        parent_channel=channel.name if hasattr(channel, "name") else "unknown",
        model="local", attunement=attunement, eddy_type=eddy_type,
    )

    print(f"Eddy spawned in channel: {topic} (id: {thread.id})")
    return thread


async def spawn_eddy(message, topic: str | None = None, eddy_type: str = "standard"):
    """Create a thread from a message (used by !new and button spawn).

    Returns the created thread, or None on failure.
    """
    from commands import thread_configs, _build_config_line, ThreadConfigView
    from llm import resolve_model
    from mage import get_thread_member_ids
    from thread_registry import register_thread
    from state import client

    text = message.content.strip()

    if not topic:
        topic = await generate_topic(text)

    model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)

    try:
        thread = await message.create_thread(
            name=topic,
            auto_archive_duration=eddy_archive,
        )
    except discord.HTTPException as e:
        if e.code == 160004:
            return None
        print(f"Eddy spawn failed: {e}")
        return None

    thread_configs[thread.id] = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": None,
        "created": datetime.now(timezone.utc),
    }

    await post_thread_opening(
        thread,
        topic,
        origin=f"{getattr(message.channel, 'name', 'the parent channel')} via `!new` / eddy spawn",
        source_text=text,
    )

    config_line = _build_config_line(thread.id)
    view = ThreadConfigView(current_type=eddy_type)
    await thread.send(config_line, view=view)

    parent_id = message.channel.id
    for uid in get_thread_member_ids(parent_id):
        try:
            user = await client.fetch_user(int(uid))
            await thread.add_user(user)
        except Exception:
            pass

    register_thread(
        thread.id, topic,
        parent_channel=message.channel.name if hasattr(message.channel, "name") else "unknown",
        model="local", attunement=attunement, eddy_type=eddy_type,
    )

    print(f"Eddy spawned: {topic} (id: {thread.id}) from message {message.id}")
    return thread


def _pending_native_eddy_path(thread_id: int, parent_channel_id: int) -> Path:
    from mage import set_practice_context_for_channel, get_runtime_dir

    set_practice_context_for_channel(parent_channel_id)
    pending_dir = Path(get_runtime_dir()) / "thread-state" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    return pending_dir / f"{thread_id}.json"


def write_pending_native_eddy(thread_id: int, parent_channel_id: int, payload: dict) -> None:
    path = _pending_native_eddy_path(thread_id, parent_channel_id)
    path.write_text(json.dumps(payload), encoding="utf-8")


def pop_pending_native_eddy(thread_id: int, parent_channel_id: int) -> dict | None:
    path = _pending_native_eddy_path(thread_id, parent_channel_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    path.unlink(missing_ok=True)
    return data


BLANK_EDDY_NAME = "new eddy"
NEW_EDDY_NAME = BLANK_EDDY_NAME


def _awaiting_title_path(thread_id: int, parent_channel_id: int) -> Path:
    from mage import set_practice_context_for_channel, get_runtime_dir

    set_practice_context_for_channel(parent_channel_id)
    awaiting_dir = Path(get_runtime_dir()) / "thread-state" / "awaiting-title"
    awaiting_dir.mkdir(parents=True, exist_ok=True)
    return awaiting_dir / f"{thread_id}.json"


def write_awaiting_title(thread_id: int, parent_channel_id: int, extra: dict | None = None) -> None:
    path = _awaiting_title_path(thread_id, parent_channel_id)
    payload = {
        "thread_id": thread_id,
        "parent_channel_id": parent_channel_id,
        **(extra or {}),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def is_awaiting_title(thread_id: int, parent_channel_id: int) -> bool:
    return _awaiting_title_path(thread_id, parent_channel_id).exists()


def pop_awaiting_title(thread_id: int, parent_channel_id: int) -> dict | None:
    path = _awaiting_title_path(thread_id, parent_channel_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    path.unlink(missing_ok=True)
    return data


def _materialize_client(message):
    channel = getattr(message, "channel", message)
    return _materialize_client_for_channel(channel)


async def finalize_native_eddy_from_river(thread: discord.Thread, pending: dict) -> None:
    """Turtle bot joins a native eddy — config only, no entry chrome until first turn."""
    from commands import thread_configs

    eddy_type = pending.get("eddy_type", EDDY_DEFAULT)
    thread_configs[thread.id] = {
        "model": pending.get("model"),
        "use_api": pending.get("use_api", False),
        "attunement": pending.get("attunement", "semi"),
        "model_label": pending.get("model_label", "local"),
        "eddy_type": eddy_type,
        "context_type": pending.get("context_type"),
        "created": datetime.now(timezone.utc),
        "native_vanilla": True,
        "blank_eddy": pending.get("blank_eddy", False),
        "awaiting_title": pending.get("awaiting_title", False),
        "presence_posted": False,
    }

    print(f"Turtle native eddy config ready: {thread.name} (id: {thread.id})")


async def river_add_turtle_to_eddy(thread) -> bool:
    """River adds Turtle to the eddy — Discord native 'river added turtle' system line."""
    from mage import river_bot_enabled

    if not river_bot_enabled():
        return False

    from river_state import river_client

    guild = getattr(thread, "guild", None)
    if guild is None:
        parent = getattr(thread, "parent", None)
        guild = getattr(parent, "guild", None) if parent else None

    turtle_id = _resolve_turtle_bot_user_id(guild)
    if not turtle_id:
        print("River add turtle: could not resolve Turtle bot user id")
        return False

    try:
        await thread.add_user(discord.Object(id=turtle_id))
        print(f"River added Turtle to {thread.name!r} (id: {thread.id})")
        return True
    except discord.HTTPException as exc:
        # Already a member — fine
        if getattr(exc, "code", None) in (30083, 50025):
            return True
        print(f"River add turtle failed: {type(exc).__name__}: {exc}")
        return False


def _turtle_bot_id_cache_path() -> Path:
    from mage import get_runtime_dir

    cache_dir = Path(get_runtime_dir()) / "thread-state" / "river"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "turtle_bot_user_id"


def cache_turtle_bot_user_id(user_id: int) -> None:
    _turtle_bot_id_cache_path().write_text(str(user_id), encoding="utf-8")


def _resolve_turtle_bot_user_id(guild) -> int | None:
    import os

    raw = os.environ.get("TURTLE_BOT_USER_ID", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass

    cache_path = _turtle_bot_id_cache_path()
    if cache_path.exists():
        try:
            return int(cache_path.read_text(encoding="utf-8").strip())
        except ValueError:
            pass

    if guild:
        for member in guild.members:
            if member.bot and member.name.lower() == "turtle":
                return member.id

    return None


async def wait_for_native_eddy_handoff(thread) -> None:
    """Turtle waits for River rename + add_user before first reply (split-bot)."""
    import asyncio
    from mage import river_bot_enabled

    if not river_bot_enabled() or not _is_thread_channel(thread):
        return

    parent_id = thread.parent_id
    for _ in range(40):
        if not is_awaiting_title(thread.id, parent_id):
            break
        await asyncio.sleep(0.1)

    try:
        from state import client

        if not client.user:
            return
        for _ in range(20):
            try:
                await thread.fetch_member(client.user.id)
                return
            except discord.HTTPException:
                await asyncio.sleep(0.1)
    except Exception:
        pass


async def ensure_native_presence(thread: discord.Thread) -> bool:
    """Native presence — split-bot uses River add_user; single-bot uses thread.join()."""
    from commands import thread_configs
    from mage import get_attunement_profile, river_bot_enabled

    cfg = thread_configs.get(thread.id)
    if not cfg:
        if get_attunement_profile() != "native":
            return False
        cfg = {
            "native_vanilla": True,
            "presence_posted": False,
            "context_type": None,
        }
        thread_configs[thread.id] = cfg
    elif not cfg.get("native_vanilla"):
        if get_attunement_profile() != "native":
            return False
        cfg["native_vanilla"] = True

    if cfg.get("presence_posted"):
        return False

    if river_bot_enabled():
        await wait_for_native_eddy_handoff(thread)
        cfg["presence_posted"] = True
        return False

    try:
        await thread.join()
        cfg["presence_posted"] = True
        print(f"Turtle joined {thread.name} (single-bot, id: {thread.id})")
        return True
    except discord.HTTPException as exc:
        print(f"Turtle join failed: {type(exc).__name__}: {exc}")
        return False


async def spawn_river_eddy(
    message,
    topic: str | None = None,
    flow_id: str | None = None,
    eddy_type: str = "standard",
):
    """Materialize eddy from River act — thread on source message; rename on first in-eddy post."""
    from commands import thread_configs
    from llm import resolve_model
    from mage import get_thread_member_ids, river_bot_enabled, get_attunement_profile
    from thread_registry import register_thread
    from state import TURTLE_MODEL

    bot_client = _materialize_client(message)
    thread_name = NEW_EDDY_NAME

    if get_attunement_profile() == "native":
        model_id = TURTLE_MODEL
        use_api = False
    else:
        model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)
    split_bot = river_bot_enabled()

    try:
        thread = await message.create_thread(
            name=thread_name[:100],
            auto_archive_duration=eddy_archive,
        )
    except discord.HTTPException as e:
        if e.code == 160004:
            return None
        print(f"River eddy spawn failed: {e}")
        return None

    config = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": flow_id,
        "topic": thread_name,
        "awaiting_title": True,
        "blank_eddy": True,
    }

    write_awaiting_title(thread.id, message.channel.id, {"flow_id": flow_id})

    parent_id = message.channel.id
    if split_bot:
        from mage import set_practice_context_for_channel

        set_practice_context_for_channel(parent_id)
        for uid in get_thread_member_ids(parent_id):
            try:
                user = await bot_client.fetch_user(int(uid))
                await thread.add_user(user)
            except Exception as exc:
                print(f"River add_user failed for {uid}: {exc}")
        write_pending_native_eddy(
            thread.id,
            parent_id,
            config,
        )
    else:
        thread_configs[thread.id] = {
            **config,
            "created": datetime.now(timezone.utc),
            "native_vanilla": get_attunement_profile() == "native",
            "presence_posted": False,
        }

    if not split_bot:
        parent_id = message.channel.id
        for uid in get_thread_member_ids(parent_id):
            try:
                user = await bot_client.fetch_user(int(uid))
                await thread.add_user(user)
            except Exception:
                pass

    register_thread(
        thread.id,
        thread_name,
        parent_channel=message.channel.name if hasattr(message.channel, "name") else "river",
        model="local",
        attunement=attunement,
        eddy_type=eddy_type,
    )

    try:
        from river_handler import _append_chronicle
        from mage import get_pd

        _append_chronicle(
            get_pd(),
            f"🌀 opened: {thread_name}",
            {"thread_id": str(thread.id), "jump_url": thread.jump_url, "flow_id": flow_id},
        )
    except Exception as exc:
        print(f"Chronicle write failed: {exc}")

    print(f"River eddy materialized: {thread_name} (id: {thread.id}) split_bot={split_bot}")
    return thread


async def spawn_blank_river_eddy(
    channel,
    *,
    flow_id: str | None = None,
    eddy_type: str = "standard",
    topic: str | None = None,
):
    """Open a blank native eddy from the standing door — no seed until first message."""
    from mage import get_thread_member_ids, river_bot_enabled, get_attunement_profile
    from thread_registry import register_thread
    from state import TURTLE_MODEL

    bot_client = _materialize_client_for_channel(channel)
    if get_attunement_profile() == "native":
        model_id = TURTLE_MODEL
        use_api = False
    else:
        from llm import resolve_model

        model_id, use_api = resolve_model("local")
    attunement = "semi"
    eddy_archive = EDDY_TYPES.get(eddy_type, {}).get("archive_minutes", 10080)
    split_bot = river_bot_enabled()
    thread_name = (topic or BLANK_EDDY_NAME)[:100]

    try:
        thread = await channel.create_thread(
            name=thread_name,
            auto_archive_duration=eddy_archive,
            type=discord.ChannelType.public_thread,
        )
    except discord.HTTPException as e:
        print(f"Blank river eddy spawn failed: {e}")
        return None

    config = {
        "model": model_id,
        "use_api": use_api,
        "attunement": attunement,
        "model_label": "local",
        "eddy_type": eddy_type,
        "context_type": flow_id,
        "topic": thread_name,
        "blank_eddy": True,
        "awaiting_title": True,
        "presence_posted": False,
    }

    if split_bot:
        write_pending_native_eddy(thread.id, channel.id, config)
        write_awaiting_title(thread.id, channel.id, {"flow_id": flow_id})
    else:
        from commands import thread_configs

        thread_configs[thread.id] = {
            **config,
            "created": datetime.now(timezone.utc),
            "native_vanilla": True,
            "presence_posted": False,
        }
        write_awaiting_title(thread.id, channel.id, {"flow_id": flow_id})

        for uid in get_thread_member_ids(channel.id):
            try:
                user = await bot_client.fetch_user(int(uid))
                await thread.add_user(user)
            except Exception:
                pass

    register_thread(
        thread.id,
        thread_name,
        parent_channel=channel.name if hasattr(channel, "name") else "river",
        model="local",
        attunement=attunement,
        eddy_type=eddy_type,
    )

    try:
        from river_handler import _append_chronicle
        from mage import get_pd

        _append_chronicle(
            get_pd(),
            f"🌀 opened blank eddy",
            {"thread_id": str(thread.id), "jump_url": thread.jump_url, "flow_id": flow_id},
        )
    except Exception as exc:
        print(f"Chronicle write failed: {exc}")

    print(f"Blank river eddy opened (id: {thread.id}) split_bot={split_bot}")
    return thread


def _materialize_client_for_channel(channel):
    from mage import river_bot_enabled

    if river_bot_enabled():
        from river_state import river_client

        return river_client
    from state import client

    return client


def _build_seed_embed(author_name: str, content: str, url_content: str = "") -> discord.Embed:
    """Build an embed that faithfully represents the intake message."""
    embed = discord.Embed(
        description=content[:4000],
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=author_name, icon_url=None)
    if url_content:
        preview = url_content[:1000]
        if len(url_content) > 1000:
            preview += "\n…"
        embed.add_field(name="Linked content", value=preview, inline=False)
    embed.set_footer(text="seeded from intake")
    return embed



TRIAGE_PROMPT = (
    "You are the vortex — a standing intake structure in a river of conversation. "
    "Someone just posted a message. Decide how to handle it.\n\n"
    "Rules:\n"
    "- SPAWN: The content is substantive — a topic, a question worth exploring, "
    "a long text, a URL to discuss, or material that deserves its own focused thread.\n"
    "- RESPOND: The content is a quick question, meta-commentary about the vortex itself, "
    "a casual remark, a greeting, a follow-up to something just said, or a short "
    "message that doesn't need its own thread.\n\n"
    "Respond with EXACTLY one word: SPAWN or RESPOND. Nothing else."
)

VORTEX_RESPOND_PROMPT = (
    "You are Turtle, speaking from the vortex — the intake point of the river. "
    "This is a brief exchange, not a deep thread. Be concise (1-3 sentences). "
    "If someone asks about the vortex or how it works, explain naturally. "
    "If someone drops something that seems like it should be its own thread, "
    "suggest they share more substantive content and you\'ll spin off an eddy."
)


async def triage_message(content: str) -> str:
    """Decide whether to SPAWN an eddy or RESPOND in-place."""
    # Quick heuristics first
    stripped = content.strip()

    # Very short messages are almost never eddy-worthy
    if len(stripped) < 60 and not URL_PATTERN.search(stripped):
        return "RESPOND"

    # Messages with URLs or very long content are almost always eddy-worthy
    if URL_PATTERN.search(stripped) and len(stripped) > 100:
        return "SPAWN"
    if len(stripped) > 500:
        return "SPAWN"

    # Ambiguous range — ask the model
    try:
        result = await asyncio.wait_for(
            chat_ollama(
                TRIAGE_PROMPT,
                [{"role": "user", "content": stripped[:1000]}],
                model=TOPIC_MODEL,
                num_ctx=TOPIC_CTX,
                think=False,
            ),
            timeout=10,
        )
        if result:
            answer = result.strip().upper()
            if "SPAWN" in answer:
                return "SPAWN"
            if "RESPOND" in answer:
                return "RESPOND"
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Triage failed: {type(e).__name__}: {e}")

    # Default: if it has URLs or attachments, spawn; otherwise respond
    if URL_PATTERN.search(stripped):
        return "SPAWN"
    return "RESPOND"


async def respond_in_vortex(message):
    """Handle a message directly in the vortex without spawning an eddy."""
    from state import dialogue_histories
    from helpers import split_message

    thread_id = message.channel.id
    content = message.content.strip()
    user_entry = f"[{message.author.display_name}]: {content}"

    if thread_id not in dialogue_histories:
        dialogue_histories[thread_id] = []
    dialogue_histories[thread_id].append({"role": "user", "content": user_entry})

    # Keep vortex history short — it's not a deep conversation space
    history = dialogue_histories[thread_id][-10:]

    try:
        async with message.channel.typing():
            from llm import chat_ollama_with_tools
            from tos_tools import TOS_TOOLS, execute_tos_tool
            reply, _ = await chat_ollama_with_tools(
                VORTEX_RESPOND_PROMPT, history,
                tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool,
            )
            if not reply:
                reply = "*listening*"
    except Exception as e:
        print(f"Vortex response failed: {e}")
        reply = "*listening*"

    dialogue_histories[thread_id].append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)

    print(f"Vortex: responded in-place to \"{content[:50]}...\"")


async def handle_intake_message(message):
    """Handle a message posted in the intake eddy.

    Flow:
    1. Generate topic from content
    2. Spawn new thread in parent channel
    3. Post seed embed (faithful copy of original message) in new thread
    4. Post compact config line
    5. Generate and post Turtle's intake response (brief comprehension)
    6. Post confirmation link in intake eddy
    """
    from state import dialogue_histories
    from helpers import split_message
    from commands import thread_configs, _build_config_line, ThreadConfigView

    parent = message.channel.parent
    if not parent:
        print("Intake: no parent channel found")
        return None

    content = message.content.strip()
    if not content and not message.attachments:
        return None
    if content.startswith("!"):
        return None

    # TRIAGE: decide whether to spawn/route or respond in-place
    decision = await triage_message(content)
    if decision == "RESPOND":
        await respond_in_vortex(message)
        return None

    # Fetch URLs early so topic generation has richer context
    url_content = ""
    urls = URL_PATTERN.findall(content)
    if urls:
        try:
            from content_fetch import process_urls
            url_content = await process_urls(urls)
        except Exception as e:
            print(f"Intake URL fetch failed: {e}")

    # PRISM: check if content resonates with an existing eddy
    guild_id = str(parent.guild.id) if hasattr(parent, 'guild') and parent.guild else None
    routed = False
    if guild_id:
        try:
            routable = await get_routable_eddies(guild_id)
            match = await detect_resonance(content + ("\n" + url_content if url_content else ""), routable)
            if match and "thread" in match:
                await route_to_eddy(message, match["thread"], url_content=url_content)
                return match["thread"]
        except Exception as e:
            print(f"Prism routing failed, falling back to spawn: {e}")

    thread = await spawn_eddy_in_channel(parent, content)
    if not thread:
        await message.reply("Couldn't create thread.", mention_author=False)
        return None

    # 1. Seed embed — faithful copy of the Mage's original message
    seed_embed = _build_seed_embed(
        message.author.display_name,
        content,
        url_content=url_content[:2000] if url_content else "",
    )
    await thread.send(embed=seed_embed)

    # 2. Compact config line with type buttons
    config_line = _build_config_line(thread.id)
    view = ThreadConfigView(current_type=thread_configs.get(thread.id, {}).get("eddy_type", "standard"))
    await thread.send(f"-# {config_line}", view=view)

    # 3. Generate Turtle's intake response — brief comprehension, not full dialogue
    user_entry = f"[{message.author.display_name}]: {content}"
    if url_content:
        user_entry += f"\n\n[Linked content]:\n{url_content[:6000]}"

    history = [{"role": "user", "content": user_entry}]
    dialogue_histories[thread.id] = list(history)

    try:
        async with thread.typing():
            from llm import chat_ollama_with_tools
            from tos_tools import TOS_TOOLS, execute_tos_tool
            reply, _ = await chat_ollama_with_tools(
                INTAKE_PROMPT, history,
                tos_tools=TOS_TOOLS, execute_tool=execute_tos_tool,
            )
            if not reply:
                reply = "*listening*"
    except Exception as e:
        print(f"Intake opening response failed: {e}")
        reply = "*listening*"

    dialogue_histories[thread.id].append({"role": "assistant", "content": reply})
    for chunk in split_message(reply):
        await thread.send(chunk)

    # 4. Confirmation in intake eddy with thread link
    await message.reply(
        f"🌀 → **{thread.name}**\n-# {thread.mention}",
        mention_author=False,
    )

    print(f"Intake: spawned {thread.name} (id: {thread.id}) with opening response")
    return thread


def make_eddy_spawn_view(source_message, topic: str | None = None) -> discord.ui.View:
    """Create a view with a thread-spawn button. Encodes source IDs in custom_id."""
    channel_id = source_message.channel.id
    message_id = source_message.id
    if topic:
        _PENDING_EDDY_TOPICS[(channel_id, message_id)] = topic

    view = discord.ui.View(timeout=None)
    custom_id = f"eddy:spawn:{channel_id}:{message_id}"
    button = discord.ui.Button(
        label="Open eddy",
        custom_id=custom_id,
        style=discord.ButtonStyle.secondary,
        emoji="🌀",
    )

    async def button_callback(interaction: discord.Interaction):
        await handle_eddy_spawn_interaction(interaction)

    button.callback = button_callback
    view.add_item(button)
    return view


async def handle_eddy_spawn_interaction(interaction: discord.Interaction):
    """Handle eddy:spawn button clicks."""
    custom_id = interaction.data.get("custom_id", "")
    parts = custom_id.split(":")
    if len(parts) < 4:
        await interaction.response.send_message(
            "Button data missing. Use `!new` instead.", ephemeral=True
        )
        return

    channel_id = int(parts[2])
    message_id = int(parts[3])

    await interaction.response.defer(thinking=True)
    try:
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("Channel not found.", ephemeral=True)
            return

        source = await channel.fetch_message(message_id)
        topic = _PENDING_EDDY_TOPICS.pop((channel_id, message_id), None)
        thread = await spawn_eddy(source, topic=topic)

        if thread:
            view = discord.ui.View(timeout=None)
            done_button = discord.ui.Button(
                label=f"→ {thread.name}",
                custom_id=f"eddy:done:{thread.id}",
                style=discord.ButtonStyle.success,
                emoji="🌀",
                disabled=True,
            )
            view.add_item(done_button)
            await interaction.message.edit(view=view)
            await interaction.followup.send(
                f"🌀 Thread created: **{thread.name}**",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Couldn't create thread — this message may already have one.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(
            f"Spawn failed: {type(e).__name__}: {e}",
            ephemeral=True,
        )
