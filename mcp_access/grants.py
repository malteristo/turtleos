"""Grants: one client principal × owned sources × an operation snapshot.

The store holds a hash of each credential, never the credential. It lives on
the host with the service, outside every practice root, and records counts —
not what was read.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.atomic_io import atomic_write_text, file_lock
from mcp_access.operations import snapshot_for

DEFAULT_TTL_DAYS = 30
ACTIVE = "active"
REVOKED = "revoked"


def state_dir() -> Path:
    raw = os.environ.get("TURTLE_MCP_STATE") or "~/.turtleos/mcp"
    return Path(os.path.expanduser(raw))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Grant:
    id: str
    principal: str
    owner: str
    sources: list[str]
    profile: str
    operations: list[str]
    created: str
    expires: str
    token_sha256: str
    revision: int = 1
    status: str = ACTIVE
    bound_login: str | None = None
    bound_addr: str | None = None
    calls: int = 0
    refused: int = 0
    refused_since_brief: int = 0
    extra: dict = field(default_factory=dict)

    def expired(self, now: datetime | None = None) -> bool:
        return (now or _now()) >= datetime.fromisoformat(self.expires)

    def public(self) -> dict:
        data = asdict(self)
        data.pop("token_sha256")
        return data


class GrantStore:
    def __init__(self, directory: Path | None = None):
        self.dir = directory or state_dir()
        self.path = self.dir / "grants.json"

    def _read(self) -> dict[str, Grant]:
        if not self.path.is_file():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        return {k: Grant(**v) for k, v in raw.items()}

    def _write(self, grants: dict[str, Grant]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        atomic_write_text(
            self.path, json.dumps({k: asdict(v) for k, v in grants.items()}, indent=2)
        )
        os.chmod(self.path, 0o600)

    def all(self) -> list[Grant]:
        return list(self._read().values())

    def get(self, grant_id: str) -> Grant | None:
        return self._read().get(grant_id)

    def create(
        self,
        *,
        principal: str,
        owner: str,
        sources: list[str],
        profile: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> tuple[Grant, str]:
        token = "tos_" + secrets.token_urlsafe(32)
        now = _now()
        grant = Grant(
            id="g_" + secrets.token_hex(6),
            principal=principal,
            owner=owner,
            sources=list(sources),
            profile=profile,
            operations=snapshot_for(profile),
            created=now.isoformat(),
            expires=(now + timedelta(days=ttl_days)).isoformat(),
            token_sha256=_hash(token),
        )
        with file_lock(self.path):
            grants = self._read()
            grants[grant.id] = grant
            self._write(grants)
        return grant, token

    def find_by_token(self, token: str) -> Grant | None:
        if not token:
            return None
        digest = _hash(token)
        for grant in self._read().values():
            if hmac.compare_digest(grant.token_sha256, digest):
                return grant
        return None

    def update(self, grant_id: str, **changes) -> Grant | None:
        with file_lock(self.path):
            grants = self._read()
            grant = grants.get(grant_id)
            if grant is None:
                return None
            for key, value in changes.items():
                setattr(grant, key, value)
            self._write(grants)
            return grant

    def count(self, grant_id: str, *, refused: bool) -> None:
        with file_lock(self.path):
            grants = self._read()
            grant = grants.get(grant_id)
            if grant is None:
                return
            grant.calls += 1
            if refused:
                grant.refused += 1
                grant.refused_since_brief += 1
            self._write(grants)

    def revoke(self, grant_id: str, *, if_revision: int) -> Grant | None:
        with file_lock(self.path):
            grants = self._read()
            grant = grants.get(grant_id)
            if grant is None or grant.revision != if_revision:
                return None
            grant.status = REVOKED
            grant.revision += 1
            self._write(grants)
            return grant
