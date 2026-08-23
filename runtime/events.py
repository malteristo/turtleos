from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Event:
    source: str
    interface: str
    principal: str
    scope: str
    payload: dict[str, Any]
    trust_level: str = "operator"
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid4().hex[:12]}")
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "interface": self.interface,
            "principal": self.principal,
            "scope": self.scope,
            "trust_level": self.trust_level,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            source=data["source"],
            interface=data["interface"],
            principal=data["principal"],
            scope=data["scope"],
            payload=data.get("payload", {}),
            trust_level=data.get("trust_level", "operator"),
            event_id=data["event_id"],
            correlation_id=data["correlation_id"],
            timestamp=data["timestamp"],
        )
