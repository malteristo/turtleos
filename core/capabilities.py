"""File-backed Turtle skills and procedures registry."""

from pathlib import Path


TURTLEOS_ROOT = Path.home() / "turtleos"
CAPABILITY_DIRS = {
    "skill": TURTLEOS_ROOT / "skills",
    "procedure": TURTLEOS_ROOT / "procedures",
}


def _safe_slug(name: str) -> str:
    slug = (name or "").strip()
    if slug.endswith(".md"):
        slug = slug[:-3]
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        raise ValueError("capability name must be a simple markdown filename")
    return slug


def _metadata(content: str) -> dict:
    meta = {}
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip().lower()] = value.strip().strip('"')
    for line in lines:
        if line.startswith("# "):
            meta.setdefault("title", line[2:].strip())
            break
    return meta


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"Capability read failed: {type(e).__name__}: {e}"


def list_capabilities(kind: str | None = None) -> list[dict]:
    """Return capability cards as metadata dictionaries."""
    kinds = [kind] if kind else ["skill", "procedure"]
    cards = []
    for card_kind in kinds:
        base = CAPABILITY_DIRS.get(card_kind)
        if not base or not base.is_dir():
            continue
        for path in sorted(base.glob("*.md")):
            content = _read(path)
            meta = _metadata(content)
            cards.append({
                "kind": card_kind,
                "slug": path.stem,
                "title": meta.get("title") or path.stem.replace("-", " ").title(),
                "summary": meta.get("summary", ""),
                "when": meta.get("when", ""),
            })
    return cards


def read_capability(kind: str, name: str) -> str:
    """Read one skill/procedure by slug."""
    if kind not in CAPABILITY_DIRS:
        return f"Unknown capability kind: {kind}"
    try:
        slug = _safe_slug(name)
    except ValueError as e:
        return str(e)
    path = CAPABILITY_DIRS[kind] / f"{slug}.md"
    content = _read(path)
    if not content:
        return f"{kind} not found: {slug}"
    return f"[{kind}:{slug}]\n\n{content[:12000]}"


def format_capability_index(kind: str | None = None) -> str:
    cards = list_capabilities(kind)
    if not cards:
        return "No Turtle skills or procedures are registered yet."
    lines = []
    for card in cards:
        label = f"{card['kind']}:{card['slug']}"
        summary = card.get("summary") or card.get("when") or card["title"]
        lines.append(f"- `{label}` — {card['title']}: {summary}")
    return "\n".join(lines)


def build_capability_summary(limit: int = 10) -> str:
    cards = list_capabilities()
    if not cards:
        return ""
    lines = ["## Turtle Skills and Procedures"]
    for card in cards[:limit]:
        label = f"{card['kind']}:{card['slug']}"
        summary = card.get("summary") or card.get("when") or card["title"]
        lines.append(f"- `{label}` — {summary}")
    if len(cards) > limit:
        lines.append(f"- ... {len(cards) - limit} more capability cards")
    lines.append("")
    lines.append("When a task matches a card, follow it. Use `read_turtle_capability` for the full procedure before acting.")
    return "\n".join(lines)
