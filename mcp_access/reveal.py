"""What one connection shows. The owner opens and closes each thing they own.

The grant's source list is what is open. Anything they own that this profile
can reach, and that is not in the list, is closed. The next request sees the
change, because every request reads the grant again. A profile that cannot
use a kind of source cannot open one: a rooms connection cannot grow a workshop.
"""

from __future__ import annotations

from mcp_access.grants import ACTIVE, Grant, GrantStore
from mcp_access.operations import ROOM_OPERATIONS, WORKSHOP_OPERATIONS, snapshot_for
from mcp_access.registry import KIND_SUBJECT, KIND_WORKSHOP, Source, owned_sources

_ORDER = {"private": 0, KIND_SUBJECT: 1, KIND_WORKSHOP: 2}

LABELS = {
    "en": {
        "private": "your notes",
        KIND_SUBJECT: "your health picture",
        KIND_WORKSHOP: "your practice",
        "nothing": "Nothing is open on this connection.",
        "open_line": "Open on this connection: {labels}.",
    },
    "de": {
        "private": "deine Notizen",
        KIND_SUBJECT: "dein Gesundheitsbild",
        KIND_WORKSHOP: "deine Praxis",
        "nothing": "Auf dieser Verbindung ist nichts offen.",
        "open_line": "Offen auf dieser Verbindung: {labels}.",
    },
}


class RevealError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _t(locale: str) -> dict:
    return LABELS.get(locale) or LABELS["en"]


def label(kind: str, locale: str) -> str:
    return _t(locale).get(kind) or _t("en").get(kind) or kind


def reachable(profile: str, source: Source) -> bool:
    ops = set(snapshot_for(profile))
    needed = WORKSHOP_OPERATIONS if source.kind == KIND_WORKSHOP else ROOM_OPERATIONS
    return bool(ops & needed)


def rows(grant: Grant, registry: dict) -> list[dict]:
    """Each thing this connection can show, and whether it is open. Plain kinds, stable order."""
    found = [s for s in owned_sources(grant.owner, registry) if reachable(grant.profile, s)]
    found.sort(key=lambda s: _ORDER.get(s.kind, 9))
    return [{"id": s.id, "kind": s.kind, "open": s.id in grant.sources} for s in found]


def opening_sentence(sources: list[Source], locale: str) -> str:
    t = _t(locale)
    labels = [label(s.kind, locale) for s in sorted(sources, key=lambda s: _ORDER.get(s.kind, 9))]
    if not labels:
        return t["nothing"]
    return t["open_line"].format(labels=", ".join(labels))


def _audit(grant: Grant, registry: dict, operation: str) -> None:
    """The owner's own act is a line in the owner's audit: who, which connection, what. No source id."""
    from mcp_access import audit
    from mcp_access.registry import private_root

    root = private_root(grant.owner, registry)
    if root is not None:
        audit.append(root, grant=grant.id, principal=grant.principal, operation=operation, decision="done")


def listed_grants(store: GrantStore, owner: str, registry: dict) -> list[Grant]:
    """The owner's live connections that can show something, oldest first. Nobody else's."""
    found = [
        g
        for g in store.all()
        if g.owner == owner and g.status == ACTIVE and not g.expired() and rows(g, registry)
    ]
    return sorted(found, key=lambda g: g.created)


def programs(grant: Grant) -> list[str]:
    """Program names this connection has introduced itself as, most recent last, no repeats."""
    names: list[str] = []
    for entry in ((grant.extra or {}).get("mcp_clients") or {}).values():
        name = str((entry or {}).get("name") or "").strip()
        if name:
            if name in names:
                names.remove(name)
            names.append(name)
    return names[-2:]


def program_of(grant: Grant) -> str:
    """The program on the other end as a person says it, or "" before it has introduced itself."""
    names = programs(grant)
    return friendly_program(names[-1]) if names else ""


_PROGRAMS = (("cursor", "Cursor"), ("claude", "Claude"), ("codex", "Codex"), ("vscode", "VS Code"), ("zed", "Zed"))


def friendly_program(name: str) -> str:
    """A program as a person says it. A name we do not know is shown as it is, never hidden."""
    lowered = (name or "").lower()
    for needle, shown in _PROGRAMS:
        if needle in lowered:
            return shown
    return name or ""


def unix(iso: str) -> int | None:
    """A stored time as the number Discord renders as relative time. None if it is not a time."""
    from datetime import datetime, timezone

    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return int(then.timestamp())


def end(store: GrantStore, grant_id: str, *, owner: str, registry: dict) -> Grant:
    """The owner ends their own connection: it stops reading and has to be connected again."""
    grant = store.get(grant_id)
    if grant is None or grant.status != ACTIVE or grant.owner != owner:
        raise RevealError("inactive")
    ended = store.revoke(grant_id, if_revision=grant.revision)
    if ended is None:
        raise RevealError("inactive")
    _audit(ended, registry, "owner_end")
    return ended


def set_open(
    store: GrantStore, grant_id: str, source_id: str, *, opened: bool, registry: dict, owner: str | None = None
) -> Grant:
    grant = store.get(grant_id)
    if grant is None or grant.status != ACTIVE or (owner is not None and grant.owner != owner):
        raise RevealError("inactive")
    allowed = {row["id"] for row in rows(grant, registry)}
    if source_id not in allowed:
        raise RevealError("unreachable")
    sources = [s for s in grant.sources if s in allowed]
    if opened and source_id not in sources:
        sources.append(source_id)
    if not opened:
        sources = [s for s in sources if s != source_id]
    updated = store.update(grant_id, sources=sources)
    if updated is None:
        raise RevealError("inactive")
    _audit(updated, registry, "owner_open" if opened else "owner_close")
    return updated
