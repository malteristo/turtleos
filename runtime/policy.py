from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .paths import RuntimePaths


RiskLevel = Literal["low", "medium", "high"]


class PolicyDenied(RuntimeError):
    pass


class ApprovalRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityPolicy:
    capability_id: str
    risk: RiskLevel
    allowed_principals: frozenset[str]
    allowed_root: Literal["practice_dir", "runtime_dir"]
    requires_approval: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "risk": self.risk,
            "allowed_principals": sorted(self.allowed_principals),
            "allowed_root": self.allowed_root,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class PolicyDecision:
    capability: CapabilityPolicy
    status: Literal["allowed"]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "reason": self.reason, "capability": self.capability.to_dict()}


class CapabilityRegistry:
    def __init__(self, paths: RuntimePaths, policies: dict[str, CapabilityPolicy]):
        self.paths = paths
        self.policies = policies

    @classmethod
    def default(cls, paths: RuntimePaths) -> "CapabilityRegistry":
        principals = frozenset({paths.principal})
        policies = {
            "practice.append_boom": CapabilityPolicy(
                "practice.append_boom", risk="low", allowed_principals=principals, allowed_root="practice_dir"
            ),
            "practice.write_session": CapabilityPolicy(
                "practice.write_session", risk="low", allowed_principals=principals, allowed_root="practice_dir"
            ),
            "practice.write_proposal": CapabilityPolicy(
                "practice.write_proposal", risk="low", allowed_principals=principals, allowed_root="practice_dir"
            ),
            "model.run_probe": CapabilityPolicy(
                "model.run_probe", risk="medium", allowed_principals=principals, allowed_root="runtime_dir"
            ),
        }
        return cls(paths, policies)

    def authorize(self, *, capability_id: str, principal: str, approved: bool = False) -> PolicyDecision:
        capability = self.policies.get(capability_id)
        if capability is None:
            raise PolicyDenied(f"Unknown capability: {capability_id}")
        if principal not in capability.allowed_principals:
            raise PolicyDenied(f"Principal {principal!r} is not allowed to use {capability_id}")
        if capability.requires_approval and not approved:
            raise ApprovalRequired(f"Capability {capability_id} requires approval")
        return PolicyDecision(capability=capability, status="allowed", reason="policy matched")

    def validate_artifact_path(self, *, capability_id: str, artifact_path: str | None) -> dict[str, str]:
        capability = self.policies.get(capability_id)
        if capability is None:
            raise PolicyDenied(f"Unknown capability: {capability_id}")
        if not artifact_path:
            return {"status": "skipped", "reason": "capability returned no artifact path"}

        root = getattr(self.paths, capability.allowed_root).resolve()
        path = Path(artifact_path).expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PolicyDenied(f"Artifact path {path} escaped allowed root {root}") from exc
        return {"status": "ok", "artifact_path": str(path), "allowed_root": str(root)}
