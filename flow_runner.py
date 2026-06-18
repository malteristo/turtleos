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
class FlowSpec:
    flow_id: str
    title: str
    body: str
    reads: list[str]
    writes: list[str]
    think_aloud: str
    model: str
    path: str


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


def load_flow_spec(flow_id: str | None, practice_dir: str | None = None) -> FlowSpec | None:
    if not flow_id or not str(flow_id).strip():
        return None
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
        flow_id=flow_id.strip().lower(),
        title=title,
        body=body or raw.strip(),
        reads=[str(r).strip() for r in reads if str(r).strip()],
        writes=[str(w).strip() for w in writes if str(w).strip()],
        think_aloud=str(meta.get("think_aloud") or "auto"),
        model=str(meta.get("model") or "default"),
        path=path,
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
    loaded: list[str] = []
    for rel in spec.reads:
        path = _safe_practice_path(rel, pd)
        if path and path.is_file():
            loaded.append(Path(rel).name)
    if loaded:
        return f"{spec.title} · loaded {', '.join(loaded)}"
    return spec.title


_FLOW_OPS_LINE = re.compile(r"^\s*-#\s*(?:flow:|read\s).*\s*$", re.MULTILINE | re.IGNORECASE)


def strip_model_operational_lines(text: str) -> tuple[str, list[str]]:
    """Remove model-emitted flow/read operational lines before Discord send."""
    stripped: list[str] = []

    def _collect(match: re.Match[str]) -> str:
        stripped.append(match.group(0).strip())
        return ""

    cleaned = _FLOW_OPS_LINE.sub(_collect, text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, stripped


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
    for base in _flow_search_dirs(practice_dir):
        for name in sorted(os.listdir(base)):
            if name.endswith(".md") and not name.startswith("_"):
                names.append(name[:-3])
    return names
