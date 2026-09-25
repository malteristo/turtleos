"""ChatGPT export inventory and offline Entwine writes.

Slice 1 inventories metadata. Slice 3 extracts one conversation at a time
and writes derived notes. The memory agent does not import this module.
The live dialogue path must not open the zip.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from core.atomic_io import atomic_write_json, atomic_write_text


SCHEMA = 1
ORIGIN_PLATFORM = "chatgpt"
ORIGIN_AGENT = "ChatGPT"
INVENTORY_NAME = "inventory.json"
INVENTORY_MD_NAME = "inventory.md"
SHARD_RE = re.compile(r"(?:^|/)conversations(?:-\d+)?\.json$")
NOT_CORPUS = frozenset(
    {
        "shared_conversations.json",
        "chat.html",
        "ads.json",
        "user.json",
        "user_settings.json",
        "message_feedback.json",
        "library_files.json",
        "conversation_asset_file_names.json",
        "export_manifest.json",
    }
)
ENTWINE_ROUTES = frozenset({"health", "personal", "skip"})
SHARED_ROUTES_FORBIDDEN = frozenset({"family", "shared", "craft", "partnership"})
INVENTORY_BODY_KEYS = frozenset(
    {
        "content",
        "parts",
        "mapping",
        "text",
        "body",
        "transcript",
    }
)


def assert_entwine_route(route: str) -> str:
    """Exogenous personal history writes to personal or isolated health only.

    Family-shaped talk in a personal archive still routes ``personal``. Sharing
    into a shared room is a later Discord act by the practitioner, not Entwine.
    """
    key = str(route or "").strip().lower()
    if key in SHARED_ROUTES_FORBIDDEN:
        raise ValueError(
            f"exogenous archive cannot write into a shared room ({key}); "
            "the practitioner shares a Discord link if they want it there"
        )
    if key not in ENTWINE_ROUTES:
        raise ValueError(f"unknown entwine route: {route}")
    return key


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_chatgpt_zip(zip_path: str | Path) -> dict[str, Any]:
    """Read shard metadata only. Message parts never enter the result."""
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"chatgpt export zip not found: {path}")
    digest = sha256_file(path)
    conversations: list[dict[str, Any]] = []
    shards: list[str] = []
    with zipfile.ZipFile(path) as archive:
        _assert_safe_members(archive)
        shard_names = _corpus_shards(archive.namelist())
        if not shard_names:
            raise ValueError(
                "no conversations-*.json (or conversations.json) in export zip"
            )
        for name in shard_names:
            shards.append(name)
            with archive.open(name) as handle:
                chunk = json.load(handle)
            conversations.extend(_inventory_chunk(chunk, name))
    conversations.sort(key=lambda row: (row.get("created_at") or "", row["id"]))
    user_total = sum(int(row["user_messages"]) for row in conversations)
    assistant_total = sum(int(row["assistant_messages"]) for row in conversations)
    payload = {
        "schema": SCHEMA,
        "origin_platform": ORIGIN_PLATFORM,
        "origin_agent": ORIGIN_AGENT,
        "zip_sha256": digest,
        "zip_bytes": path.stat().st_size,
        "zip_name": path.name,
        "inventoried_at": datetime.now(timezone.utc).isoformat(),
        "shard_count": len(shards),
        "shards": shards,
        "conversation_count": len(conversations),
        "message_count": user_total + assistant_total,
        "user_messages": user_total,
        "assistant_messages": assistant_total,
        "conversations": conversations,
    }
    _assert_no_bodies(payload)
    return payload


def write_inventory(out_dir: str | Path, inventory: dict[str, Any]) -> Path:
    """Write inventory.json + inventory.md. Still no bodies."""
    _assert_no_bodies(inventory)
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    json_path = dest / INVENTORY_NAME
    atomic_write_json(json_path, inventory, indent=2)
    atomic_write_text(dest / INVENTORY_MD_NAME, render_inventory_markdown(inventory))
    return json_path


def render_inventory_markdown(inventory: dict[str, Any]) -> str:
    rows = inventory.get("conversations") or []
    lines = [
        "# ChatGPT archive inventory",
        "",
        f"- origin: {inventory.get('origin_platform')} / {inventory.get('origin_agent')}",
        f"- zip: `{inventory.get('zip_name')}`",
        f"- sha256: `{inventory.get('zip_sha256')}`",
        f"- bytes: {inventory.get('zip_bytes')}",
        f"- shards: {inventory.get('shard_count')}",
        f"- conversations: {inventory.get('conversation_count')}",
        f"- messages: {inventory.get('message_count')} "
        f"(user {inventory.get('user_messages')}, "
        f"assistant {inventory.get('assistant_messages')})",
        "",
        "Metadata only. No transcripts. No note writes. Turtle did not have these chats.",
        "",
        "| created | title | user | asst | flags | id |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        flags = []
        if row.get("is_do_not_remember"):
            flags.append("do_not_remember")
        if row.get("is_archived"):
            flags.append("archived")
        title = _md_cell(row.get("title") or "")
        lines.append(
            f"| {row.get('created_at') or ''} | {title} | "
            f"{row.get('user_messages', 0)} | {row.get('assistant_messages', 0)} | "
            f"{','.join(flags) or '—'} | `{row.get('id')}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _corpus_shards(names: Iterable[str]) -> list[str]:
    shards = []
    for name in names:
        base = Path(name).name
        if base in NOT_CORPUS:
            continue
        if SHARD_RE.search(name.replace("\\", "/")):
            shards.append(name)
    return sorted(shards)


def _inventory_chunk(chunk: Any, shard_name: str) -> list[dict[str, Any]]:
    if not isinstance(chunk, list):
        raise ValueError(f"{shard_name} is not a conversation list")
    rows = []
    for item in chunk:
        if not isinstance(item, dict):
            continue
        rows.append(_inventory_conversation(item))
    return rows


def _inventory_conversation(item: dict[str, Any]) -> dict[str, Any]:
    mapping = item.get("mapping") or {}
    user_n = 0
    assistant_n = 0
    if isinstance(mapping, dict):
        for node in mapping.values():
            role = _node_role(node)
            if role == "user":
                user_n += 1
            elif role == "assistant":
                assistant_n += 1
    conv_id = str(item.get("conversation_id") or item.get("id") or "").strip()
    if not conv_id:
        raise ValueError("conversation missing id")
    return {
        "id": conv_id,
        "title": str(item.get("title") or "").strip(),
        "created_at": _unix_iso(item.get("create_time")),
        "updated_at": _unix_iso(item.get("update_time")),
        "user_messages": user_n,
        "assistant_messages": assistant_n,
        "is_archived": bool(item.get("is_archived")),
        "is_do_not_remember": bool(item.get("is_do_not_remember")),
        "default_model_slug": item.get("default_model_slug") or None,
    }


def _node_role(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    message = node.get("message")
    if not isinstance(message, dict):
        return None
    author = message.get("author")
    if isinstance(author, dict):
        role = author.get("role")
        return str(role) if role else None
    return None


def _unix_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        stamp = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()


def _assert_safe_members(archive: zipfile.ZipFile) -> None:
    for item in archive.infolist():
        candidate = Path(item.filename)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("archive contains an unsafe path")


def _assert_no_bodies(payload: Any) -> None:
    """Fail if a transcript-shaped key survived into the inventory."""
    if isinstance(payload, dict):
        leaked = INVENTORY_BODY_KEYS.intersection(payload)
        if leaked:
            raise ValueError(f"inventory must not carry body keys: {sorted(leaked)}")
        for value in payload.values():
            _assert_no_bodies(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_no_bodies(value)


def _md_cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")[:80]


# ─── Slice 3: extract + write (offline job only) ─────────────────────


NOTE_DIR = Path("story") / "exogenous" / "chatgpt"
OBSERVED_HARVEST_NAME = "entwine_observed.md"


@dataclass
class EntwineRoots:
    """Where a distill may write. Family is not a field on purpose."""

    personal: Path
    health: Path | None = None


@dataclass
class DistillSplit:
    route: str
    title: str
    body: str
    conversation_id: str
    split_id: str
    observed: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


def extract_conversation(zip_path: str | Path, conversation_id: str) -> dict[str, Any]:
    """One conversation with messages. Offline job only — not inventory."""
    wanted = str(conversation_id or "").strip()
    if not wanted:
        raise ValueError("conversation id required")
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"chatgpt export zip not found: {path}")
    with zipfile.ZipFile(path) as archive:
        _assert_safe_members(archive)
        for name in _corpus_shards(archive.namelist()):
            with archive.open(name) as handle:
                chunk = json.load(handle)
            if not isinstance(chunk, list):
                raise ValueError(f"{name} is not a conversation list")
            for item in chunk:
                if not isinstance(item, dict):
                    continue
                conv_id = str(item.get("conversation_id") or item.get("id") or "").strip()
                if conv_id == wanted:
                    return _extracted_conversation(item)
    raise KeyError(f"conversation not in export: {wanted}")


def _extracted_conversation(item: dict[str, Any]) -> dict[str, Any]:
    conv_id = str(item.get("conversation_id") or item.get("id") or "").strip()
    messages = _messages_from_mapping(item.get("mapping") or {})
    return {
        "id": conv_id,
        "title": str(item.get("title") or "").strip(),
        "created_at": _unix_iso(item.get("create_time")),
        "updated_at": _unix_iso(item.get("update_time")),
        "is_archived": bool(item.get("is_archived")),
        "is_do_not_remember": bool(item.get("is_do_not_remember")),
        "messages": messages,
        "user_messages": sum(1 for row in messages if row["role"] == "user"),
        "assistant_messages": sum(1 for row in messages if row["role"] == "assistant"),
    }


def _messages_from_mapping(mapping: Any) -> list[dict[str, str]]:
    if not isinstance(mapping, dict):
        return []
    rows: list[tuple[float, dict[str, str]]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        role = _node_role(node)
        if role not in {"user", "assistant"}:
            continue
        text = _message_text(message)
        if not text.strip():
            continue
        stamp = 0.0
        raw = message.get("create_time")
        try:
            stamp = float(raw) if raw not in (None, "") else 0.0
        except (TypeError, ValueError):
            stamp = 0.0
        rows.append((stamp, {"role": role, "text": text}))
    rows.sort(key=lambda item: item[0])
    return [row for _, row in rows]


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, dict):
        parts = content.get("parts") or []
        return "\n".join(str(part) for part in parts if isinstance(part, str)).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


CLASSIFY_SYSTEM = """
You distill one imported ChatGPT conversation into memory notes.
Turtle was not in this conversation. The other model is not a clinician.

Return JSON only:
{"splits":[{"route":"health|personal|skip","title":"short","body":"compressed","observed":[]}]}

Routes — only these three:
- health: body, course, clinicians, sick leave, medications of the archive owner
- personal: everything kept that is not health, including talk about family or other people
- skip: empty, one-shot toys, export junk, do-not-remember

Never use family, shared, craft, or another person's river as a route.
If the talk is about family, still route personal.

Mixed conversations: more than one split. Do not copy one note to both roots.

body: the owner's words and durable facts, compressed. Not a transcript.
Drop the other model's diagnoses, or mark them inference — never as fact.
observed: health splits only. Owner symptom/course words and clinician statements.
""".strip()


def format_classify_user(conversation: dict[str, Any], *, max_messages: int = 80, max_chars: int = 2000) -> str:
    """User turn for the classifier. Truncated on purpose — not a dump."""
    lines = [f"title: {conversation.get('title') or ''}", ""]
    for row in (conversation.get("messages") or [])[:max_messages]:
        role = row.get("role") or ""
        text = (row.get("text") or "")[:max_chars]
        lines.append(f"{role}: {text}")
    return "\n".join(lines).strip()


def deterministic_skip(conversation: dict[str, Any]) -> str | None:
    """Return a skip reason, or None if a classifier should see it."""
    if conversation.get("is_do_not_remember"):
        return "do_not_remember"
    messages = conversation.get("messages") or []
    user_texts = [row["text"] for row in messages if row.get("role") == "user"]
    if not any(text.strip() for text in user_texts):
        return "no_user_text"
    return None


def parse_classifier_reply(raw: str, conversation: dict[str, Any]) -> list[DistillSplit]:
    """Read splits from a model reply. Family / shared routes fail closed."""
    payload = _json_object(raw)
    splits = payload.get("splits")
    if not isinstance(splits, list) or not splits:
        raise ValueError("classifier reply has no splits")
    conv_id = str(conversation.get("id") or "").strip()
    out: list[DistillSplit] = []
    used_routes: list[str] = []
    for index, item in enumerate(splits):
        if not isinstance(item, dict):
            continue
        route = assert_entwine_route(str(item.get("route") or ""))
        title = str(item.get("title") or conversation.get("title") or conv_id).strip()
        body = redact_assistant_only(
            str(item.get("body") or "").strip(),
            conversation.get("messages") or [],
        )
        observed = []
        for bullet in item.get("observed") or []:
            text = redact_assistant_only(str(bullet).strip(), conversation.get("messages") or [])
            if text:
                observed.append(text)
        if route == "skip":
            continue
        if not body:
            continue
        used_routes.append(route)
        suffix = f"-{route}" if len(splits) > 1 else ""
        if used_routes.count(route) > 1:
            suffix = f"-{route}-{used_routes.count(route)}"
        out.append(
            DistillSplit(
                route=route,
                title=title,
                body=body,
                conversation_id=conv_id,
                split_id=f"{conv_id}{suffix}",
                observed=observed if route == "health" else [],
                created_at=conversation.get("created_at"),
                updated_at=conversation.get("updated_at"),
            )
        )
    return out


def redact_assistant_only(text: str, messages: list[dict[str, str]]) -> str:
    """Drop spans that appear only in the other model's turns."""
    if not text:
        return ""
    user_blob = "\n".join(
        row.get("text") or "" for row in messages if row.get("role") == "user"
    ).lower()
    assistant_only = []
    for row in messages:
        if row.get("role") != "assistant":
            continue
        for token in _redact_tokens(row.get("text") or ""):
            if token.lower() not in user_blob:
                assistant_only.append(token)
    cleaned = text
    for token in assistant_only:
        cleaned = cleaned.replace(token, "")
    return " ".join(cleaned.split()).strip()


def _redact_tokens(text: str) -> list[str]:
    """Long tokens and obvious planted secrets — not a medical dictionary."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{11,}", text)
    return [token for token in tokens if token.lower() not in {"chatgpt"}]


def destination_for(route: str, roots: EntwineRoots) -> Path | None:
    key = assert_entwine_route(route)
    if key == "skip":
        return None
    if key == "health":
        if roots.health is None:
            raise ValueError("health route needs the owner's isolated health root")
        return Path(roots.health).expanduser()
    return Path(roots.personal).expanduser()


def write_exogenous_note(
    split: DistillSplit,
    roots: EntwineRoots,
    *,
    entwined: str | None = None,
    forbidden_roots: Iterable[str | Path] = (),
) -> Path | None:
    """Write one derived note. Skip writes nothing. Shared roots fail."""
    dest = destination_for(split.route, roots)
    if dest is None:
        return None
    dest = dest.resolve()
    for raw in forbidden_roots:
        forbidden = Path(raw).expanduser().resolve()
        if dest == forbidden or forbidden in dest.parents:
            raise ValueError(f"entwine will not write into forbidden root {forbidden}")
    note_dir = dest / NOTE_DIR
    note_dir.mkdir(parents=True, exist_ok=True)
    path = note_dir / f"{split.split_id}.md"
    when = entwined or date.today().isoformat()
    body = "\n".join(
        [
            "---",
            "source: exogenous/chatgpt",
            f"conversation_id: {split.conversation_id}",
            f"title: {split.title}",
            f"created: '{split.created_at or ''}'",
            f"updated: '{split.updated_at or ''}'",
            f"origin_platform: {ORIGIN_PLATFORM}",
            f"origin_agent: {ORIGIN_AGENT}",
            f"route: {split.route}",
            f"entwined: '{when}'",
            "---",
            "",
            split.body.strip(),
            "",
        ]
    )
    atomic_write_text(path, body)
    return path


def append_observed_harvest(
    health_root: str | Path,
    splits: list[DistillSplit],
    *,
    conversation_id: str,
) -> Path | None:
    """Append owner/clinician bullets. Not ChatGPT differentials. Not the board."""
    bullets = []
    for split in splits:
        if split.route != "health":
            continue
        bullets.extend(split.observed)
    if not bullets:
        return None
    path = Path(health_root).expanduser() / "record" / OBSERVED_HARVEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    block = [f"## {conversation_id}", ""]
    block.extend(f"- {bullet}" for bullet in bullets)
    block.append("")
    existing = path.read_text(encoding="utf-8") if path.exists() else (
        "# Entwine Observed harvest\n\n"
        "Owner words and clinician statements from imported chats. "
        "Not a diagnosis. Not yet on the compact board.\n\n"
    )
    atomic_write_text(path, existing + "\n".join(block) + "\n")
    return path


def entwine_conversation(
    zip_path: str | Path,
    conversation_id: str,
    roots: EntwineRoots,
    *,
    classify: Callable[[dict[str, Any]], str] | None = None,
    forbidden_roots: Iterable[str | Path] = (),
    entwined: str | None = None,
) -> list[Path]:
    """Extract, classify, write. The live path does not call this."""
    conversation = extract_conversation(zip_path, conversation_id)
    reason = deterministic_skip(conversation)
    if reason:
        return []
    if classify is None:
        raise ValueError("classifier required for a kept conversation")
    splits = parse_classifier_reply(classify(conversation), conversation)
    written: list[Path] = []
    for split in splits:
        path = write_exogenous_note(
            split, roots, entwined=entwined, forbidden_roots=forbidden_roots
        )
        if path is not None:
            written.append(path)
    if roots.health is not None:
        append_observed_harvest(roots.health, splits, conversation_id=conversation_id)
    return written


def _json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty classifier reply")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("classifier reply is not JSON")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("classifier reply must be an object")
    return payload
