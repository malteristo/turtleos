"""Turtle Practice flow runner — front matter, state reads/writes (TURTLE_SPEC §10–11)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mage import get_pd
from practice_io import read_safe


@dataclass
class FlowIntakeField:
    id: str
    label: str
    placeholder: str
    required: bool


@dataclass
class FlowIntakeSpec:
    path: str
    fields: list[FlowIntakeField]
    skippable: bool = True


@dataclass
class FlowSpec:
    flow_id: str
    title: str
    body: str
    reads: list[str]
    writes: list[str]
    think_aloud: str
    model: str
    path: str
    entry_contract: str = ""
    intake: FlowIntakeSpec | None = None


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.strip().startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    meta = yaml.safe_load(parts[1]) or {}
    return meta if isinstance(meta, dict) else {}, parts[2].strip()


def _flow_search_dirs(practice_dir: str | None = None) -> list[str]:
    pd = practice_dir or get_pd()
    repo_root = os.path.dirname(os.path.abspath(__file__))
    dirs = [os.path.join(pd, "flows"), os.path.join(repo_root, "template", "flows")]
    return [d for d in dirs if os.path.isdir(d)]


def _slug_candidates(flow_id: str) -> list[str]:
    slug = flow_id.strip().lower().replace(" ", "_")
    return list(dict.fromkeys([slug, slug.replace("_", "-")]))


def resolve_flow_path(flow_id: str, practice_dir: str | None = None) -> str | None:
    for base in _flow_search_dirs(practice_dir):
        for stem in _slug_candidates(flow_id):
            path = os.path.join(base, f"{stem}.md")
            if os.path.isfile(path):
                return path
    return None


def _parse_intake_spec(meta: dict[str, Any], flow_id: str) -> FlowIntakeSpec | None:
    raw = meta.get("intake")
    if not raw or not isinstance(raw, dict):
        return None
    fields_raw = raw.get("fields") or []
    fields: list[FlowIntakeField] = []
    for item in fields_raw:
        if not isinstance(item, dict):
            continue
        field_id = str(item.get("id") or "").strip()
        if not field_id:
            continue
        fields.append(
            FlowIntakeField(
                id=field_id,
                label=str(item.get("label") or field_id).strip(),
                placeholder=str(item.get("placeholder") or "").strip(),
                required=bool(item.get("required", False)),
            )
        )
    if not fields:
        return None
    intake_path = str(raw.get("path") or f"state/notes/{flow_id}-intake.md").strip()
    return FlowIntakeSpec(
        path=intake_path,
        fields=fields,
        skippable=raw.get("skippable", True) is not False,
    )


def load_flow_spec(flow_id: str | None, practice_dir: str | None = None) -> FlowSpec | None:
    if not flow_id or not str(flow_id).strip():
        return None
    slug = flow_id.strip().lower()
    path = resolve_flow_path(flow_id, practice_dir)
    if not path:
        return None
    raw = read_safe(path)
    if not raw.strip():
        return None
    meta, body = split_front_matter(raw)
    reads = list(meta.get("reads") or meta.get("loads") or [])
    writes = list(meta.get("writes") or [])
    title = (meta.get("title") or flow_id).strip()
    return FlowSpec(
        flow_id=slug,
        title=title,
        body=body or raw.strip(),
        reads=[str(r).strip() for r in reads if str(r).strip()],
        writes=[str(w).strip() for w in writes if str(w).strip()],
        think_aloud=str(meta.get("think_aloud") or "auto"),
        model=str(meta.get("model") or "default"),
        path=path,
        entry_contract=str(meta.get("entry_contract") or "").strip(),
        intake=_parse_intake_spec(meta, slug),
    )


def _safe_practice_path(rel: str, practice_dir: str) -> Path | None:
    rel = rel.strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    root = Path(practice_dir).resolve()
    full = (root / rel).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        return None
    return full


def read_state_bundle(spec: FlowSpec, practice_dir: str | None = None) -> dict[str, str]:
    pd = practice_dir or get_pd()
    out: dict[str, str] = {}
    for rel in spec.reads:
        path = _safe_practice_path(rel, pd)
        if not path or not path.is_file():
            out[rel] = ""
            continue
        content = read_safe(str(path))
        out[rel] = content.strip()
    return out


def flow_presence_line(spec: FlowSpec, practice_dir: str | None = None) -> str:
    """Human-readable flow presence for shell injection (not model prose)."""
    pd = practice_dir or get_pd()
    has_checkpoint = False
    has_empty_read = False
    for rel in spec.reads:
        path = _safe_practice_path(rel, pd)
        if path and path.is_file():
            if path.read_text(encoding="utf-8").strip():
                has_checkpoint = True
                break
            has_empty_read = True
    if has_checkpoint:
        return f"{spec.title} · continuing from last time"
    if has_empty_read:
        return f"{spec.title} · starting fresh"
    return spec.title


_FLOW_OPS_LINE = re.compile(r"^\s*-#\s*(?:flow:|read\s).*\s*$", re.MULTILINE | re.IGNORECASE)
_FLOW_PRESENCE_ECHO = re.compile(
    r"^\s*(?:-#\s*)?.+\s·\s+(?:loaded\s+.+|continuing from last time|starting fresh)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_FLOW_META_LINE = re.compile(
    r"^\s*\*\([^)]*(?:no question|end here)[^)]*\)\*\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def strip_model_operational_lines(text: str) -> tuple[str, list[str]]:
    """Remove model-emitted operational and flow-meta lines before Discord send."""
    stripped: list[str] = []

    def _collect(match: re.Match[str]) -> str:
        stripped.append(match.group(0).strip())
        return ""

    cleaned = _FLOW_OPS_LINE.sub(_collect, text)
    cleaned = _FLOW_PRESENCE_ECHO.sub(_collect, cleaned)
    cleaned = _FLOW_META_LINE.sub(_collect, cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, stripped


_SHELTER_FIRST_REPLY_FALLBACK = (
    "You made it. There's no rush here.\n\n"
    "I'm here with you. You don't have to explain anything."
)


def strip_question_sentences(text: str) -> tuple[str, list[str]]:
    """Remove sentences containing question marks."""
    stripped: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sent in sentences:
        if not sent.strip():
            continue
        if "?" in sent:
            stripped.append(sent.strip())
        else:
            kept.append(sent.strip())
    cleaned = " ".join(kept).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, stripped


def apply_flow_reply_guard(
    text: str,
    flow_id: str | None,
    history: list[dict],
) -> tuple[str, list[str]]:
    """Shell enforcement when flow turn contracts are violated."""
    if flow_id != "shelter":
        return text, []
    if any(m.get("role") == "assistant" for m in history):
        return text, []
    if "?" not in text:
        return text, []
    cleaned, stripped = strip_question_sentences(text)
    notes = [f"stripped question sentence: {s}" for s in stripped]
    if not cleaned.strip():
        cleaned = _SHELTER_FIRST_REPLY_FALLBACK
        notes.append("used shelter first-reply fallback")
    return cleaned, notes


def read_flow_intake(spec: FlowSpec, practice_dir: str | None = None) -> str:
    if not spec.intake:
        return ""
    pd = practice_dir or get_pd()
    path = _safe_practice_path(spec.intake.path, pd)
    if not path or not path.is_file():
        return ""
    return read_safe(str(path)).strip()


def parse_flow_intake_markdown(text: str) -> dict[str, str]:
    """Parse ## field_id sections from a written intake artifact."""
    values: dict[str, str] = {}
    if not text.strip():
        return values
    current_id: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_id is not None:
                values[current_id] = "\n".join(buf).strip()
            current_id = line[3:].strip()
            buf = []
            continue
        if current_id is None:
            continue
        buf.append(line)
    if current_id is not None:
        values[current_id] = "\n".join(buf).strip()
    return values


def read_flow_intake_values(spec: FlowSpec, practice_dir: str | None = None) -> dict[str, str]:
    """Field values from the last intake capture — used to prefill return visits."""
    return parse_flow_intake_markdown(read_flow_intake(spec, practice_dir))


def write_flow_intake(
    spec: FlowSpec,
    values: dict[str, str],
    practice_dir: str | None = None,
) -> str | None:
    if not spec.intake:
        return None
    pd = practice_dir or get_pd()
    path = _safe_practice_path(spec.intake.path, pd)
    if not path:
        return None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {spec.title} — intake", f"**Captured:** {now}", ""]
    for field in spec.intake.fields:
        value = (values.get(field.id) or "").strip()
        if value:
            lines.append(f"## {field.id}\n\n{value}")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return spec.intake.path


def format_intake_summary(spec: FlowSpec, values: dict[str, str]) -> str:
    if not spec.intake:
        return ""
    parts: list[str] = []
    for field in spec.intake.fields:
        value = (values.get(field.id) or "").strip()
        if not value:
            continue
        snippet = value if len(value) <= 280 else value[:277] + "..."
        parts.append(f"**{field.label}:** {snippet}")
    if not parts:
        return "Intake captured — ready to begin."
    return "\n\n".join(parts) + "\n\nTurtle will pick up from here — not from zero."


def build_flow_prompt_sections(
    flow_id: str | None, practice_dir: str | None = None
) -> tuple[list[str], FlowSpec | None]:
    spec = load_flow_spec(flow_id, practice_dir)
    if not spec:
        return [], None
    sections = [f"## Active Flow: {spec.title}\n\n{spec.body}"]
    reads = read_state_bundle(spec, practice_dir)
    if spec.reads:
        blocks = []
        for rel in spec.reads:
            content = reads.get(rel, "")
            if content:
                blocks.append(f"### {rel}\n\n{content[:4000]}")
            else:
                blocks.append(f"### {rel}\n\n(empty — file not present yet)")
        sections.append("## Flow State (loaded)\n\n" + "\n\n".join(blocks))
    intake_content = read_flow_intake(spec, practice_dir)
    if intake_content:
        rel = spec.intake.path if spec.intake else "intake"
        sections.append(
            "## Flow Intake (captured — do not re-ask these)\n\n"
            f"### {rel}\n\n{intake_content[:4000]}"
        )
    if spec.flow_id == "shelter":
        sections.append(
            "## Turn override (final — wins over character defaults)\n\n"
            "If this is your **first reply** in this eddy: presence only. "
            "**Zero question marks.** Do not offer choices, invites, or 'would you like' — "
            "just be here."
        )
    return sections, spec


def write_flow_checkpoint(
    spec: FlowSpec,
    history: list[dict],
    mage_label: str = "Practitioner",
    practice_dir: str | None = None,
) -> list[str]:
    """Write declared `writes` paths on flow session close."""
    if not spec.writes:
        return []
    pd = practice_dir or get_pd()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {spec.title} — session checkpoint", f"**Closed:** {now}", ""]
    for msg in history[-8:]:
        role = mage_label if msg.get("role") == "user" else "Turtle"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"**{role}:** {content[:500]}")
    body = "\n\n".join(lines) + "\n"
    written: list[str] = []
    for rel in spec.writes:
        path = _safe_practice_path(rel, pd)
        if not path:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        written.append(rel)
    return written


def list_flow_ids(practice_dir: str | None = None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for base in _flow_search_dirs(practice_dir):
        for name in sorted(os.listdir(base)):
            if name.endswith(".md") and not name.startswith("_"):
                fid = name[:-3]
                if fid in seen:
                    continue
                seen.add(fid)
                names.append(fid)
    return names


def list_resolvable_flow_ids(practice_dir: str | None = None) -> list[str]:
    """Flow ids that resolve to a spec — for menus and close-time inference."""
    return [fid for fid in list_flow_ids(practice_dir) if load_flow_spec(fid, practice_dir)]


def _flow_summary_line(spec: FlowSpec) -> str:
    if spec.entry_contract:
        return spec.entry_contract
    for line in spec.body.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or text.startswith("**") or text.startswith("---"):
            continue
        if text.startswith("*") and text.endswith("*"):
            continue
        return text[:240]
    return "Practice flow — speak when you are ready."


def _checkpoint_line(spec: FlowSpec, practice_dir: str) -> str:
    for rel in spec.reads:
        path = _safe_practice_path(rel, practice_dir)
        if path and path.is_file() and path.stat().st_size > 40:
            return f"Last checkpoint: `{Path(rel).name}`"
    return "Fresh start — no prior checkpoint."


def flow_entry_blurb(spec: FlowSpec, practice_dir: str | None = None) -> str:
    """One-screen orientation for River at flow eddy materialize."""
    pd = practice_dir or get_pd()
    return f"{_flow_summary_line(spec)}\n\n{_checkpoint_line(spec, pd)}"


def flow_orientation_description(spec: FlowSpec, practice_dir: str | None = None) -> str:
    """Rich orientation when flow declares River intake."""
    pd = practice_dir or get_pd()
    prefill = read_flow_intake_values(spec, pd)
    prepare_line = (
        "• **Prepare** — review or update your last answers (recommended)"
        if prefill
        else "• **Prepare** — two short questions (recommended)"
    )
    lines = [
        _flow_summary_line(spec),
        "",
        prepare_line,
        "• **Skip** — talk freely; Turtle joins on your first message",
        "",
        _checkpoint_line(spec, pd),
    ]
    return "\n".join(lines)


def resolve_flow_for_close(
    channel_id: int,
    history: list[dict],
    thread_configs: dict,
    channel_name: str | None = None,
    practice_dir: str | None = None,
) -> FlowSpec | None:
    """Resolve which flow checkpoint to write on session close."""
    cfg = thread_configs.get(channel_id) or {}
    flow_id = cfg.get("context_type")
    if not flow_id:
        try:
            from thread_registry import load_registry

            entry = load_registry().get("threads", {}).get(str(channel_id), {})
            flow_id = entry.get("context_type")
        except Exception:
            flow_id = None
    if flow_id:
        spec = load_flow_spec(flow_id, practice_dir)
        if spec and spec.writes:
            return spec

    name = (channel_name or "").lower().replace("-", " ").replace("_", " ")
    for fid in list_resolvable_flow_ids(practice_dir):
        slug = fid.lower().replace("_", " ")
        if slug in name or fid.lower() in name:
            spec = load_flow_spec(fid, practice_dir)
            if spec and spec.writes:
                return spec

    if len(history) < 2:
        return None

    blob = " ".join((m.get("content") or "") for m in history).lower()
    if any(
        phrase in blob
        for phrase in (
            "need shelter",
            "shelter flow",
            "!shelter",
            "hold space with me",
            "holding space",
        )
    ):
        spec = load_flow_spec("shelter", practice_dir)
        if spec and spec.writes:
            return spec
    return None
