"""Practice artifact allowlist and shelf builder (TURTLE_SPEC §11.5)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from mage import get_mage_type, get_pd, get_runtime_dir

HOSTED_SURFACE_FILES = (
    "boom.md",
    "bright.md",
    "compass.md",
    "mirror.md",
    "resonance.md",
)

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
    Shelf("intake", "Intake", "Your pasted captures"),
    Shelf("surface", "Surface", "Portable practice surface files"),
    Shelf("intentions", "Intentions", "Active intention files"),
    Shelf("links", "Saved links", "Distilled URLs from `!fetch`"),
    Shelf("proposals", "Proposals", "Host self-development notes (operator only)"),
)


def normalize_rel_path(path: str, *, ensure_md: bool = False) -> str | None:
    path = (path or "").replace("\\", "/").strip().lstrip("./")
    if not path or path.startswith("/") or ".." in path.split("/"):
        return None
    if ensure_md and not path.endswith(".md"):
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
    if rel.startswith("state/notes/") and rel.endswith(".md"):
        return True
    if rel.startswith("thread-archive/") and rel.endswith(".md"):
        return True
    if rel == "chronicle/surface.md":
        return True
    if rel.startswith("box/intake/") and rel.endswith(".md"):
        return True
    if rel.startswith("intentions/") and rel.endswith(".md"):
        return True
    if rel in HOSTED_SURFACE_FILES:
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
        "state/notes",
        "thread-archive",
        "box/intake",
        "intentions",
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

    return sorted(set(found))


def _count_shelf(shelf_key: str, *, mage_type: str) -> int:
    return len(list_shelf_artifacts(shelf_key, mage_type=mage_type))


def list_shelves(*, mage_type: str | None = None) -> list[tuple[Shelf, int]]:
    mage_type = _effective_mage_type(mage_type)
    out: list[tuple[Shelf, int]] = []
    for shelf in SHELF_DEFS:
        if shelf.key == "proposals" and mage_type == "practitioner":
            continue
        if shelf.key == "surface" and not any(
            os.path.isfile(os.path.join(get_pd(), name)) for name in HOSTED_SURFACE_FILES
        ):
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
    elif key == "intake":
        base = os.path.join(pd, "box", "intake")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                if name.endswith(".md"):
                    paths.append(f"box/intake/{name}")
    elif key == "surface":
        for name in HOSTED_SURFACE_FILES:
            if os.path.isfile(os.path.join(pd, name)):
                paths.append(name)
    elif key == "intentions":
        base = os.path.join(pd, "intentions")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                if name.endswith(".md"):
                    paths.append(f"intentions/{name}")
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


def format_shelf_menu(*, mage_type: str | None = None) -> str:
    lines = ["**Practice artifacts** — curated shelves (not the full filesystem)", ""]
    for shelf, count in list_shelves(mage_type=mage_type):
        lines.append(f"• **{shelf.title}** (`!artifacts {shelf.key}`) — {count} — {shelf.blurb}")
    lines.extend(
        [
            "",
            "View one: `!read <path>` · Search: `!search <term>`",
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
        lines.append(f"• `{display}` — `!read {path}`")
    if len(artifacts) > 40:
        lines.append(f"\n*…and {len(artifacts) - 40} more. Use `!ls {shelf_key}` or `!search`.*")
    return "\n".join(lines)
