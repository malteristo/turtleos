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


def resolve_sources(member: str, ids: list[str], registry: dict) -> list[Source]:
    """The grant's sources, re-checked against ownership on every call.

    A source the member no longer owns drops out silently; it is not an error
    the client may observe.
    """
    owned = {s.id: s for s in owned_sources(member, registry)}
    return [owned[i] for i in ids if i in owned]
