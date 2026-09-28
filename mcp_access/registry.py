"""Sources a member owns, derived from the registry — never a second list.

A member owns their own practice root (``mages.<member>``) and every space
whose ``subject`` is that member. Membership of a space is not ownership.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

KIND_PRIVATE = "private"
KIND_SUBJECT = "subject"


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    root: Path
    owner: str


def registry_path() -> Path:
    override = os.environ.get("MAGE_REGISTRY")
    if override:
        return Path(os.path.expanduser(override))
    return Path(__file__).resolve().parents[1] / "mage_registry.yaml"


def load_registry(path: Path | None = None) -> dict:
    p = path or registry_path()
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _root(entry: dict) -> Path | None:
    raw = entry.get("practice_dir")
    if not raw:
        return None
    return Path(os.path.expanduser(str(raw)))


def owned_sources(member: str, registry: dict) -> list[Source]:
    out: list[Source] = []
    mage = (registry.get("mages") or {}).get(member)
    if isinstance(mage, dict) and not mage.get("archived"):
        root = _root(mage)
        if root is not None:
            out.append(Source(member, KIND_PRIVATE, root, member))
    for key, space in (registry.get("spaces") or {}).items():
        if not isinstance(space, dict) or space.get("archived"):
            continue
        if str(space.get("subject") or "") != member:
            continue
        root = _root(space)
        if root is not None:
            out.append(Source(str(key), KIND_SUBJECT, root, member))
    return out


def river_channel_id(member: str, registry: dict) -> int | None:
    """The member's personal river — where their consent is asked."""
    for ch_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived") or entry.get("orphaned"):
            continue
        if entry.get("mage") == member and entry.get("type") in ("river", "hosted-river"):
            try:
                return int(ch_id)
            except (TypeError, ValueError):
                continue
    return None


def resolve_sources(member: str, ids: list[str], registry: dict) -> list[Source]:
    """The grant's sources, re-checked against ownership on every call.

    A source the member no longer owns drops out silently; it is not an error
    the client may observe.
    """
    owned = {s.id: s for s in owned_sources(member, registry)}
    return [owned[i] for i in ids if i in owned]


def private_root(member: str, registry: dict) -> Path | None:
    for s in owned_sources(member, registry):
        if s.kind == KIND_PRIVATE:
            return s.root
    return None


def member_for_login(registry: dict, login: str) -> str | None:
    """The member whose registry entry names this tailnet login. Exact match, case-insensitive."""
    wanted = (login or "").strip().casefold()
    if not wanted:
        return None
    for name, entry in (registry.get("mages") or {}).items():
        if str((entry or {}).get("tailscale_login") or "").strip().casefold() == wanted:
            return name
    return None
