"""Practice artifact allowlist and shelf builder (TURTLE_SPEC §11.5)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from mage import get_mage_type, get_pd, get_runtime_dir

HOSTED_SURFACE_FILES: tuple[str, ...] = ()

OPERATOR_ONLY_PREFIXES = ("proposals/",)

ALWAYS_DENIED_PREFIXES = (
    "thread-state/",
    "dialogue/",
    "signals/",
    "share/",
    "native-runtime/",
)

DENIED_ROOT_NAMES = frozenset(
    {
        "thread-state",
        "dialogue",
        "signals",
        "share",
        "native-runtime",
        "proposals",
        ".git",
    }
)

LINK_RESONANCE_PREFIX = "link-resonance/"


@dataclass(frozen=True)
class Shelf:
    key: str
    title: str
    blurb: str


SHELF_DEFS: tuple[Shelf, ...] = (
    Shelf("sessions", "Sessions", "Checkpoint and session notes"),
    Shelf("notes", "Notes", "Flow outcomes (Navigator, Companion, …)"),
    Shelf("archives", "Archives", "Dissolved thread captures"),
    Shelf("chronicle", "Chronicle", "Practice timeline (summary)"),
    Shelf("state", "State", "Continuity engine (current.yaml, notes)"),
    Shelf("intake", "Intake", "Your pasted captures"),
    Shelf("links", "Saved links", "Distilled URLs from `!fetch`"),
    Shelf("proposals", "Proposals", "Host self-development notes (operator only)"),
)


def normalize_rel_path(path: str, *, ensure_md: bool = False) -> str | None:
    path = (path or "").replace("\\", "/").strip().lstrip("./")
    if not path or path.startswith("/") or ".." in path.split("/"):
        return None
    if ensure_md and not path.endswith((".md", ".yaml", ".yml")):
        path += ".md"
    return path


def _effective_mage_type(mage_type: str | None) -> str:
    return mage_type if mage_type is not None else get_mage_type()


def _link_resonance_dir() -> str:
    return os.path.join(get_runtime_dir(), "link-resonance")


def is_artifact_readable(rel_path: str, *, mage_type: str | None = None) -> bool:
    """Return True if rel_path is an allowlisted practice artifact (TURTLE_SPEC §11.5.1)."""
    rel = normalize_rel_path(rel_path, ensure_md=True)
    if not rel:
        return False

    mage_type = _effective_mage_type(mage_type)

    if rel.startswith(LINK_RESONANCE_PREFIX):
        name = rel[len(LINK_RESONANCE_PREFIX) :]
        if "/" in name or not name.endswith(".md"):
            return False
        return os.path.isfile(os.path.join(_link_resonance_dir(), name))

    for prefix in ALWAYS_DENIED_PREFIXES:
        if rel.startswith(prefix) or rel == prefix.rstrip("/"):
            return False

    if mage_type == "practitioner":
        for prefix in OPERATOR_ONLY_PREFIXES:
            if rel.startswith(prefix):
                return False

    if rel.startswith("sessions/") and rel.endswith(".md"):
        return True
    # Story surfaces are Tier-1 practitioner corpus (§11.5.1); the checkpoint
    # preview browser link (§8.4 visibility, issue 036) resolves through here.
    if rel.startswith("story/eddies/") and rel.endswith(".md"):
        return True
    if rel.startswith("story/daily/") and rel.endswith(".md"):
        return True
    if rel.startswith("state/notes/") and rel.endswith(".md"):
        return True
    if rel.startswith("thread-archive/") and rel.endswith(".md"):
        return True
    if rel == "chronicle/surface.md":
        return True
    if rel == "state/current.yaml":
        return True
    if rel.startswith("box/intake/") and rel.endswith(".md"):
        return True
    if mage_type != "practitioner" and rel.startswith("proposals/") and rel.endswith(".md"):
        return True

    return False


def is_artifact_directory(rel_dir: str, *, mage_type: str | None = None) -> bool:
    """Return True if listing this directory prefix is allowed."""
    rel_dir = normalize_rel_path(rel_dir or "") or ""
    rel_dir = rel_dir.rstrip("/")
    mage_type = _effective_mage_type(mage_type)

    allowed_prefixes = (
        "sessions",
        "story",
        "story/eddies",
        "story/daily",
        "state/notes",
        "thread-archive",
        "box/intake",
    )
    if rel_dir in allowed_prefixes:
        return True
    if rel_dir == "chronicle":
        return True
    if rel_dir == "box":
        return True
    if rel_dir == "state":
        return True
    if rel_dir == "":
        return True
    if mage_type != "practitioner" and rel_dir == "proposals":
        return True
    return False


def resolve_artifact_path(rel_path: str, *, mage_type: str | None = None) -> str | None:
    """Absolute path for reading an artifact, or None if denied."""
    rel = normalize_rel_path(rel_path, ensure_md=True)
    if not rel or not is_artifact_readable(rel, mage_type=mage_type):
        return None
    if rel.startswith(LINK_RESONANCE_PREFIX):
        name = rel[len(LINK_RESONANCE_PREFIX) :]
        return os.path.join(_link_resonance_dir(), name)
    return os.path.join(get_pd(), rel)


def iter_artifact_files(*, mage_type: str | None = None) -> list[str]:
    """All readable artifact paths (practice-relative + link-resonance/)."""
    mage_type = _effective_mage_type(mage_type)
    pd = get_pd()
    found: list[str] = []

    def add_if(path: str) -> None:
        if is_artifact_readable(path, mage_type=mage_type):
            found.append(path)

    for root, dirs, files in os.walk(pd):
        dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d not in DENIED_ROOT_NAMES]
        rel_root = os.path.relpath(root, pd)
        if rel_root == ".":
            rel_root = ""
        for name in files:
            if not name.endswith(".md"):
                continue
            rel = f"{rel_root}/{name}" if rel_root else name
            add_if(rel.replace("\\", "/"))

    lr_dir = _link_resonance_dir()
    if os.path.isdir(lr_dir):
        for name in sorted(os.listdir(lr_dir)):
            if name.endswith(".md"):
                add_if(f"{LINK_RESONANCE_PREFIX}{name}")

    current = os.path.join(pd, "state", "current.yaml")
    if os.path.isfile(current):
        add_if("state/current.yaml")

    return sorted(set(found))


def _count_shelf(shelf_key: str, *, mage_type: str) -> int:
    return len(list_shelf_artifacts(shelf_key, mage_type=mage_type))


def list_shelves(*, mage_type: str | None = None) -> list[tuple[Shelf, int]]:
    mage_type = _effective_mage_type(mage_type)
    out: list[tuple[Shelf, int]] = []
    for shelf in SHELF_DEFS:
        if shelf.key == "proposals" and mage_type == "practitioner":
            continue
        count = _count_shelf(shelf.key, mage_type=mage_type)
        out.append((shelf, count))
    return out


def list_shelf_artifacts(shelf_key: str, *, mage_type: str | None = None) -> list[str]:
    mage_type = _effective_mage_type(mage_type)
    key = shelf_key.lower().strip()
    pd = get_pd()
    paths: list[str] = []

    if key == "sessions":
        base = os.path.join(pd, "sessions")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"sessions/{name}")
    elif key == "notes":
        base = os.path.join(pd, "state", "notes")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"state/notes/{name}")
    elif key == "archives":
        base = os.path.join(pd, "thread-archive")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"thread-archive/{name}")
    elif key == "chronicle":
        if os.path.isfile(os.path.join(pd, "chronicle", "surface.md")):
            paths.append("chronicle/surface.md")
    elif key == "state":
        current = os.path.join(pd, "state", "current.yaml")
        if os.path.isfile(current):
            paths.append("state/current.yaml")
        notes_base = os.path.join(pd, "state", "notes")
        if os.path.isdir(notes_base):
            for name in sorted(os.listdir(notes_base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"state/notes/{name}")
    elif key == "intake":
        base = os.path.join(pd, "box", "intake")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"box/intake/{name}")
    elif key == "links":
        lr = _link_resonance_dir()
        if os.path.isdir(lr):
            for name in sorted(os.listdir(lr), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"{LINK_RESONANCE_PREFIX}{name}")
    elif key == "proposals" and mage_type != "practitioner":
        base = os.path.join(pd, "proposals")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"proposals/{name}")
    else:
        return []

    return [p for p in paths if is_artifact_readable(p, mage_type=mage_type)]


@dataclass(frozen=True)
class RecentArtifact:
    path: str
    display_name: str
    shelf_title: str
    mtime: float


def shelf_title_for_path(path: str) -> str:
    if path.startswith("sessions/"):
        return "Sessions"
    if path.startswith("story/"):
        return "Story"
    if path.startswith("state/notes/"):
        return "Notes"
    if path == "state/current.yaml":
        return "State"
    if path.startswith("thread-archive/"):
        return "Archives"
    if path == "chronicle/surface.md":
        return "Chronicle"
    if path.startswith("box/intake/"):
        return "Intake"
    if path.startswith(LINK_RESONANCE_PREFIX):
        return "Saved links"
    if path.startswith("proposals/"):
        return "Proposals"
    return "Artifact"


def list_recent_artifacts(*, limit: int = 8, mage_type: str | None = None) -> list[RecentArtifact]:
    mage_type = _effective_mage_type(mage_type)
    scored: list[tuple[float, str]] = []
    for path in iter_artifact_files(mage_type=mage_type):
        abs_path = resolve_artifact_path(path, mage_type=mage_type)
        if not abs_path or not os.path.isfile(abs_path):
            continue
        scored.append((os.path.getmtime(abs_path), path))
    scored.sort(key=lambda item: item[0], reverse=True)
    out: list[RecentArtifact] = []
    for mtime, path in scored[:limit]:
        from practice_io import artifact_display_name

        out.append(
            RecentArtifact(
                path=path,
                display_name=artifact_display_name(path),
                shelf_title=shelf_title_for_path(path),
                mtime=mtime,
            )
        )
    return out


def format_shelf_menu(
    *,
    mage_type: str | None = None,
    include_empty: bool = True,
    operator_hints: bool = True,
) -> str:
    lines = ["**Practice artifacts** — curated shelves (not the full filesystem)", ""]
    for shelf, count in list_shelves(mage_type=mage_type):
        if not include_empty and count == 0:
            continue
        lines.append(f"• **{shelf.title}** (`!artifacts {shelf.key}`) — {count} — {shelf.blurb}")
    if operator_hints:
        lines.extend(
            [
                "",
                "View one: `!read <path>` · Export: `!export <path>` · Search: `!search <term>`",
                "Browse a shelf tree: `!ls sessions` (allowlisted paths only)",
            ]
        )
    return "\n".join(lines)


def format_shelf_listing(shelf_key: str, *, mage_type: str | None = None) -> str:
    mage_type = _effective_mage_type(mage_type)
    artifacts = list_shelf_artifacts(shelf_key, mage_type=mage_type)
    if not artifacts:
        return f"No artifacts in **{shelf_key}** yet. Try another shelf with `!artifacts`."

    title = next((s.title for s in SHELF_DEFS if s.key == shelf_key.lower()), shelf_key)
    lines = [f"**{title}** ({len(artifacts)})", ""]
    for path in artifacts[:40]:
        display = path.replace(LINK_RESONANCE_PREFIX, "link · ")
        lines.append(f"• `{display}` — `!read {path}` · `!export {path}`")
    if len(artifacts) > 40:
        lines.append(f"\n*…and {len(artifacts) - 40} more. Use `!ls {shelf_key}` or `!search`.*")
    return "\n".join(lines)


# ─── Discoverability (§11.5.3 v1.1) ─────────────────────────────


def _discoverability_path() -> str:
    state_dir = os.path.join(get_runtime_dir(), "thread-state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "artifact_discoverability.json")


def _load_discoverability() -> dict:
    path = _discoverability_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_discoverability(data: dict) -> None:
    with open(_discoverability_path(), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def tier1_artifact_count(*, mage_type: str | None = None) -> int:
    return len(iter_artifact_files(mage_type=mage_type))


def mark_artifacts_ui_unlocked(reason: str) -> None:
    """Unlock Artifacts bar button after checkpoint, typed !artifacts, or corpus exists."""
    data = _load_discoverability()
    if data.get("ui_unlocked"):
        return
    data["ui_unlocked"] = True
    data["reason"] = reason
    data["unlocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_discoverability(data)


def artifacts_ui_eligible(*, mage_type: str | None = None) -> bool:
    """Show Artifacts lifecycle button (§11.5.3 — hidden until corpus or first unlock)."""
    if _load_discoverability().get("ui_unlocked"):
        return True
    if tier1_artifact_count(mage_type=mage_type) > 0:
        mark_artifacts_ui_unlocked("corpus")
        return True
    return False


def checkpoint_artifact_hint(*, session_note: str | None, flow_write: str | None) -> str | None:
    """One-line post-checkpoint hint when something was saved to Tier 1."""
    if not session_note and not flow_write:
        return None
    if flow_write and not session_note:
        return "Flow note saved — browse with `!artifacts notes`."
    shelf = "sessions" if session_note else "notes"
    return f"Saved to **{shelf.title()}** — try `!artifacts {shelf}`."


# ─── Search (§11.5.5) ─────────────────────────────────────────────


@dataclass(frozen=True)
class SearchHit:
    path: str
    line_no: int
    line_text: str


def collect_artifact_search_hits(
    query: str,
    *,
    directory: str = "",
    max_hits: int = 20,
    mage_type: str | None = None,
) -> list[SearchHit]:
    """Return allowlisted artifact line matches (snippets only — no full bodies)."""
    import re

    if not query.strip():
        return []
    mage_type = _effective_mage_type(mage_type)
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    prefix = directory.rstrip("/") + "/" if directory else ""
    hits: list[SearchHit] = []

    for rel_path in iter_artifact_files(mage_type=mage_type):
        if prefix and not rel_path.startswith(prefix):
            continue
        abs_path = resolve_artifact_path(rel_path, mage_type=mage_type)
        if not abs_path:
            continue
        try:
            with open(abs_path, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if pattern.search(line):
                        hits.append(SearchHit(rel_path, i, line.rstrip("\n")))
                        if len(hits) >= max_hits:
                            return hits
        except OSError:
            continue
    return hits


def format_search_results(hits: list[SearchHit], query: str, *, max_snippets_per_file: int = 3) -> str:
    """Chat snippets grouped by artifact with browser open links (§11.5.5)."""
    from practice_io import obsidian_link

    if not hits:
        return f"No matches for `{query}` in your artifact corpus."

    by_file: dict[str, list[SearchHit]] = {}
    for hit in hits:
        by_file.setdefault(hit.path, []).append(hit)

    lines = [
        f"**{len(hits)} snippet(s)** for `{query}` — open the full artifact in your browser:",
        "",
    ]
    for path in sorted(by_file.keys()):
        file_hits = by_file[path]
        link = obsidian_link(path)
        lines.append(f"**{path}**")
        lines.append(f"Open: {link} · `!read {path}`")
        for hit in file_hits[:max_snippets_per_file]:
            snippet = hit.line_text.strip()[:120]
            lines.append(f"  L{hit.line_no}: {snippet}")
        extra = len(file_hits) - max_snippets_per_file
        if extra > 0:
            lines.append(f"  *…{extra} more line(s) in this artifact — use `!read`*")
        lines.append("")

    return "\n".join(lines).strip()
