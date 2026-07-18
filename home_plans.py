"""Pinned home eddies — working-plan registry (practice-root YAML).

Day-one model: 1:1 home eddy ↔ Tier-1 artifact; discovery via river pin card.
Product speech: river pin + home eddy + file — never side-panel fiction.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_text, file_lock

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SCHEMA_VERSION = 1
REGISTRY_REL = "state/home_plans.yaml"
NOTES_PREFIX = "state/notes/"
_MAX_ARTIFACT_INJECT = 4000
_MAX_TITLE = 80


class HomePlanError(ValueError):
    """Bind/clear refused — message is practitioner-safe."""


_MIN_PLAN_CHARS = 350
_MIN_PLAN_LINES = 6


def looks_like_working_plan(text: str) -> bool:
    """Heuristic: substantial structured plan worth a Keep-as-working-plan offer.

    Length + headings/bullets — not an LLM classifier (design L3).
    """
    t = (text or "").strip()
    if len(t) < _MIN_PLAN_CHARS:
        return False
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) < _MIN_PLAN_LINES:
        return False

    md_heads = 0
    bold_heads = 0
    bullets = 0
    numbered = 0
    questions = 0
    for raw in lines:
        ln = raw.strip()
        if ln.endswith("?"):
            questions += 1
        if re.match(r"^#{1,3}\s+\S", ln):
            md_heads += 1
        elif ln.startswith("**") and ln.endswith("**") and len(ln) < 100:
            bold_heads += 1
        if ln.startswith(("-", "*", "•")) or re.match(r"^[-*•]\s+", ln):
            bullets += 1
        elif re.match(r"^\d+[.)]\s+\S", ln):
            numbered += 1

    structure_hits = bullets + numbered
    heads = md_heads + bold_heads
    structured = (
        (md_heads >= 2 and structure_hits >= 3)
        or (heads >= 1 and structure_hits >= 4 and len(t) >= 400)
        or (structure_hits >= 5 and len(t) >= 500)
    )
    if not structured:
        return False
    if questions > max(2, len(lines) * 0.4):
        return False
    return True


def title_from_plan_body(body: str, *, fallback: str = "Working plan") -> str:
    """Prefer a markdown/bold heading over intro prose or the first bullet."""
    prose_candidate = ""
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()[:_MAX_TITLE] or fallback
        if line.startswith(("-", "*", "•")):
            continue
        if line.startswith("**") and line.endswith("**") and len(line) < 80:
            return line.strip("*").strip()[:_MAX_TITLE] or fallback
        if not prose_candidate and len(line) <= 80 and not line.endswith(":"):
            prose_candidate = line[:_MAX_TITLE]
            # Keep scanning — a later heading wins over intro prose.
    return prose_candidate or fallback


def registry_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / REGISTRY_REL


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_registry() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "plans": []}


def _load(practice_dir: str | Path) -> dict[str, Any]:
    path = registry_path(practice_dir)
    if not path.exists() or yaml is None:
        return _empty_registry()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_registry()
    if not isinstance(loaded, dict):
        return _empty_registry()
    plans = loaded.get("plans")
    if not isinstance(plans, list):
        loaded["plans"] = []
    loaded.setdefault("version", SCHEMA_VERSION)
    return loaded


def _save(practice_dir: str | Path, data: dict[str, Any], *, locked: bool = False) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write home_plans.yaml")
    path = registry_path(practice_dir)
    payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    # Callers that already hold file_lock(registry) must pass locked=True
    # (flock is not re-entrant).
    atomic_write_text(path, payload, lock=not locked)


def list_plans(practice_dir: str | Path) -> list[dict[str, Any]]:
    return list(_load(practice_dir).get("plans") or [])


def get_by_eddy(practice_dir: str | Path, eddy_id: str | int) -> dict[str, Any] | None:
    key = str(eddy_id)
    for plan in list_plans(practice_dir):
        if str(plan.get("home_eddy_id") or "") == key:
            return dict(plan)
    return None


def get_by_artifact(practice_dir: str | Path, path: str) -> dict[str, Any] | None:
    from artifact_viewer import normalize_rel_path

    rel = normalize_rel_path(path, ensure_md=True)
    if not rel:
        return None
    for plan in list_plans(practice_dir):
        if normalize_rel_path(str(plan.get("artifact_path") or ""), ensure_md=True) == rel:
            return dict(plan)
    return None


def get_by_id(practice_dir: str | Path, plan_id: str) -> dict[str, Any] | None:
    for plan in list_plans(practice_dir):
        if str(plan.get("id") or "") == str(plan_id):
            return dict(plan)
    return None


def is_sticky_eddy(practice_dir: str | Path, eddy_id: str | int) -> bool:
    plan = get_by_eddy(practice_dir, eddy_id)
    if not plan:
        return False
    return bool(plan.get("sticky", True))


def slugify_title(title: str) -> str:
    raw = (title or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if not raw:
        raw = "working-plan"
    return raw[:60]


def ensure_artifact(
    practice_dir: str | Path,
    *,
    title: str,
    body: str | None = None,
    artifact_path: str | None = None,
) -> str:
    """Create or accept a Notes-shelf markdown file. Returns relative path."""
    from artifact_viewer import is_artifact_readable, normalize_rel_path

    if artifact_path:
        rel = normalize_rel_path(artifact_path, ensure_md=True)
    else:
        slug = slugify_title(title)
        rel = f"{NOTES_PREFIX}{slug}.md"
        # Avoid clobbering an unrelated existing note with same slug.
        abs_path = Path(practice_dir) / rel
        if abs_path.exists() and get_by_artifact(practice_dir, rel) is None:
            rel = f"{NOTES_PREFIX}{slug}-{uuid.uuid4().hex[:6]}.md"

    if not rel or not rel.startswith(NOTES_PREFIX):
        raise HomePlanError("Working plans must live under Notes (state/notes/).")
    if not is_artifact_readable(rel, mage_type="practitioner"):
        raise HomePlanError("That path is not a readable practice artifact.")

    abs_path = Path(practice_dir) / rel
    if not abs_path.exists():
        clean_title = (title or "Working plan").strip()[:_MAX_TITLE] or "Working plan"
        content = body.strip() if body and body.strip() else (
            f"# {clean_title}\n\n"
            "_Working plan — edit with Turtle in the home eddy._\n"
        )
        if not content.lstrip().startswith("#"):
            content = f"# {clean_title}\n\n{content}"
        atomic_write_text(abs_path, content if content.endswith("\n") else content + "\n")
    return rel


def bind_home(
    practice_dir: str | Path,
    *,
    title: str,
    home_eddy_id: str | int,
    river_channel_id: str | int,
    artifact_path: str | None = None,
    body: str | None = None,
    sticky: bool = True,
) -> dict[str, Any]:
    """Bind 1:1 home eddy ↔ artifact. Raises HomePlanError on conflict."""
    eddy_key = str(home_eddy_id)
    existing_eddy = get_by_eddy(practice_dir, eddy_key)
    if existing_eddy:
        raise HomePlanError(
            "This eddy is already a home for a working plan. "
            "Use `!pin` to refresh the river card, or open a new eddy for another plan."
        )

    rel = ensure_artifact(
        practice_dir, title=title, body=body, artifact_path=artifact_path
    )
    existing_art = get_by_artifact(practice_dir, rel)
    if existing_art:
        raise HomePlanError(
            "That artifact already has a home eddy. Continue from its river pin, "
            "or use a different file."
        )

    clean_title = (title or "Working plan").strip()[:_MAX_TITLE] or "Working plan"
    now = _now_iso()
    plan = {
        "id": uuid.uuid4().hex,
        "title": clean_title,
        "artifact_path": rel,
        "home_eddy_id": eddy_key,
        "river_channel_id": str(river_channel_id),
        "river_pin_message_id": None,
        "created_at": now,
        "updated_at": now,
        "sticky": bool(sticky),
    }

    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        # Re-check under lock
        for p in data.get("plans") or []:
            if str(p.get("home_eddy_id") or "") == eddy_key:
                raise HomePlanError(
                    "This eddy is already a home for a working plan."
                )
            if str(p.get("artifact_path") or "") == rel:
                raise HomePlanError("That artifact already has a home eddy.")
        data.setdefault("plans", []).append(plan)
        data["version"] = SCHEMA_VERSION
        _save(practice_dir, data, locked=True)
    return dict(plan)


def set_pin_message(
    practice_dir: str | Path,
    plan_id: str,
    message_id: str | int,
) -> dict[str, Any] | None:
    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        for plan in data.get("plans") or []:
            if str(plan.get("id") or "") == str(plan_id):
                plan["river_pin_message_id"] = str(message_id)
                plan["updated_at"] = _now_iso()
                _save(practice_dir, data, locked=True)
                return dict(plan)
    return None


def touch_plan(practice_dir: str | Path, plan_id: str) -> dict[str, Any] | None:
    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        for plan in data.get("plans") or []:
            if str(plan.get("id") or "") == str(plan_id):
                plan["updated_at"] = _now_iso()
                _save(practice_dir, data, locked=True)
                return dict(plan)
    return None


def clear_plan(practice_dir: str | Path, plan_id: str) -> dict[str, Any] | None:
    """Remove binding; keep artifact file by default."""
    with file_lock(registry_path(practice_dir)):
        data = _load(practice_dir)
        plans = data.get("plans") or []
        kept: list[dict[str, Any]] = []
        removed: dict[str, Any] | None = None
        for plan in plans:
            if str(plan.get("id") or "") == str(plan_id):
                removed = dict(plan)
            else:
                kept.append(plan)
        if removed is None:
            return None
        data["plans"] = kept
        _save(practice_dir, data, locked=True)
        return removed


def stop_pinning(practice_dir: str | Path, plan_id: str) -> dict[str, Any] | None:
    """Alias for clear_plan — unpin binding; file retained."""
    return clear_plan(practice_dir, plan_id)


def patch_artifact(
    practice_dir: str | Path,
    plan_id: str,
    *,
    new_body: str | None = None,
    append_note: str | None = None,
) -> str:
    """Quiet perform write. Returns relative artifact path."""
    plan = get_by_id(practice_dir, plan_id)
    if not plan:
        raise HomePlanError("No working plan with that id.")
    rel = str(plan.get("artifact_path") or "")
    abs_path = Path(practice_dir) / rel
    if not abs_path.exists():
        raise HomePlanError("Working-plan file is missing.")

    if new_body is not None:
        content = new_body if new_body.endswith("\n") else new_body + "\n"
    elif append_note is not None:
        existing = abs_path.read_text(encoding="utf-8")
        note = append_note.strip()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        block = f"\n- [{stamp}] {note}\n"
        content = existing.rstrip() + "\n" + block
    else:
        raise HomePlanError("Provide new_body or append_note.")

    atomic_write_text(abs_path, content, lock=True)
    touch_plan(practice_dir, plan_id)
    return rel


def read_artifact_body(
    practice_dir: str | Path,
    plan: dict[str, Any],
    *,
    max_chars: int = _MAX_ARTIFACT_INJECT,
) -> str:
    rel = str(plan.get("artifact_path") or "")
    abs_path = Path(practice_dir) / rel
    if not abs_path.is_file():
        return ""
    text = abs_path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 40] + "\n\n…[truncated for attunement]…"


def render_home_attunement_packet(
    practice_dir: str | Path,
    eddy_id: str | int,
) -> str:
    """Shell-injected block for home-eddy turns (vocabulary firewall)."""
    plan = get_by_eddy(practice_dir, eddy_id)
    if not plan:
        return ""
    title = plan.get("title") or "Working plan"
    path = plan.get("artifact_path") or ""
    body = read_artifact_body(practice_dir, plan)
    eddy_note_hint = _latest_eddy_note_pointer(practice_dir, eddy_id)
    lines = [
        "[Working plan — shell-injected, not a practitioner message]",
        f"Home eddy for **{title}** (file: {path}).",
        "This room is for create / revise / perform on that plan. "
        "Quiet writes go to the file; one-line ack in chat. "
        "Do not describe side-panels or shelves beside chat — discovery is the river pin card.",
    ]
    if eddy_note_hint:
        lines.append(f"Latest eddy note: {eddy_note_hint}")
    if body:
        lines.append("--- plan body ---")
        lines.append(body.rstrip())
        lines.append("--- end plan ---")
    lines.append("")
    return "\n".join(lines) + "\n"


def _latest_eddy_note_pointer(practice_dir: str | Path, eddy_id: str | int) -> str | None:
    story = Path(practice_dir) / "story" / "eddies"
    if not story.is_dir():
        return None
    prefix = f"{eddy_id}-"
    candidates = sorted(
        (p for p in story.glob(f"{eddy_id}-*.md") if not p.name.endswith(".lock")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        # Also match string id prefixes
        candidates = sorted(
            (
                p
                for p in story.glob("*.md")
                if p.name.startswith(prefix) and not p.name.endswith(".lock")
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    if not candidates:
        return None
    return f"story/eddies/{candidates[0].name}"
