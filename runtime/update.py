from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_REF = "origin/main"


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


class UpdateCheckError(RuntimeError):
    pass


def check_update(*, repo: Path | None = None, base_ref: str | None = None) -> dict[str, Any]:
    repo_root = _repo_root(repo or Path.cwd())
    base = base_ref or _upstream_ref(repo_root) or DEFAULT_BASE_REF
    current_branch = _git_stdout(repo_root, "branch", "--show-current") or "(detached)"
    current_sha = _git_stdout(repo_root, "rev-parse", "HEAD")
    base_sha = _optional_git_stdout(repo_root, "rev-parse", "--verify", base)
    status = _git_stdout(repo_root, "status", "--porcelain")
    remote_name, remote_branch = _split_remote_ref(base)
    remote_url = _optional_git_stdout(repo_root, "remote", "get-url", remote_name) if remote_name else ""
    remote_head = (
        _optional_git_stdout(repo_root, "ls-remote", "--heads", remote_name, remote_branch).split("\t")[0]
        if remote_name and remote_branch
        else ""
    )

    divergence = _divergence(repo=repo_root, current_sha=current_sha, base_ref=base, base_sha=base_sha)
    stale_tracking_ref = bool(remote_head and base_sha and remote_head != base_sha)

    return {
        "repo": str(repo_root),
        "source": {
            "base_ref": base,
            "remote": remote_name,
            "remote_branch": remote_branch,
            "remote_url": remote_url,
            "tracking_sha": base_sha,
            "remote_head_sha": remote_head,
            "tracking_ref_stale": stale_tracking_ref,
        },
        "current": {
            "branch": current_branch,
            "sha": current_sha,
            "dirty": bool(status.strip()),
            "dirty_files": status.splitlines(),
        },
        "divergence": divergence,
        "safe_to_apply": False,
        "next_action": _next_action(divergence=divergence, dirty=bool(status.strip()), stale=stale_tracking_ref),
        "reassurance": _reassurance(),
    }


def plan_update(*, repo: Path | None = None, base_ref: str | None = None) -> dict[str, Any]:
    check = check_update(repo=repo, base_ref=base_ref)
    repo_root = Path(check["repo"])
    base = check["source"]["base_ref"]
    divergence = check["divergence"]
    commits: list[str] = []
    changed_files: list[str] = []

    if divergence["state"] in {"behind", "diverged"}:
        commits = _git_lines(repo_root, "log", "--oneline", f"HEAD..{base}")
        changed_files = _git_lines(repo_root, "diff", "--name-only", f"HEAD..{base}")

    impact = classify_changed_files(changed_files)
    approval = _approval_for_impact(impact)
    restart = _restart_for_impact(impact)

    return {
        **check,
        "available_commits": commits,
        "changed_files": changed_files,
        "impact": impact,
        "approval": approval,
        "restart": restart,
        "manual_apply_ritual": [
            "Confirm this plan still matches the intended update.",
            "Ensure the live working tree is clean.",
            "Record the current SHA as the rollback target.",
            "Apply the update manually.",
            "Run compile checks for changed Python files.",
            "Run canary before any restart decision and again after restart if restarted.",
            "Report the outcome in the relevant craft/admin surface.",
        ],
    }


def classify_changed_files(paths: list[str]) -> dict[str, Any]:
    buckets = {
        "docs_only": [],
        "runtime_code": [],
        "dependencies": [],
        "config_examples": [],
        "protected_or_governance": [],
        "other": [],
    }
    for path in paths:
        if path in {"TURTLE_SPEC.md", "identity/soul.md"}:
            buckets["protected_or_governance"].append(path)
        elif path in {".env", "mage_registry.yaml"} or path.endswith(".plist"):
            buckets["protected_or_governance"].append(path)
        elif path in {"requirements.txt", "pyproject.toml", "uv.lock", "poetry.lock"}:
            buckets["dependencies"].append(path)
        elif path in {".env.template", "mage_registry.example.yaml"}:
            buckets["config_examples"].append(path)
        elif path.endswith(".py") or path.startswith("runtime/"):
            buckets["runtime_code"].append(path)
        elif path.endswith(".md"):
            buckets["docs_only"].append(path)
        else:
            buckets["other"].append(path)

    if buckets["protected_or_governance"]:
        tier = "explicit_mage_operator_approval"
    elif buckets["dependencies"]:
        tier = "explicit_operator_approval"
    elif buckets["runtime_code"]:
        tier = "spirit_operator_approval"
    elif buckets["config_examples"] or buckets["other"]:
        tier = "operator_review"
    elif buckets["docs_only"]:
        tier = "low_risk_docs"
    else:
        tier = "none"

    return {"tier": tier, "buckets": buckets}


def _repo_root(path: Path) -> Path:
    result = _git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise UpdateCheckError(result.stderr.strip() or "not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def _upstream_ref(repo: Path) -> str | None:
    return _optional_git_stdout(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or None


def _divergence(*, repo: Path, current_sha: str, base_ref: str, base_sha: str) -> dict[str, Any]:
    if not base_sha:
        return {"state": "unknown", "ahead": None, "behind": None, "reason": f"base ref not found: {base_ref}"}
    if current_sha == base_sha:
        return {"state": "up_to_date", "ahead": 0, "behind": 0, "reason": "HEAD matches base ref"}

    counts = _optional_git_stdout(repo, "rev-list", "--left-right", "--count", f"HEAD...{base_ref}")
    if counts:
        parts = counts.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
            if ahead and behind:
                state = "diverged"
            elif ahead:
                state = "ahead"
            elif behind:
                state = "behind"
            else:
                state = "up_to_date"
            return {"state": state, "ahead": ahead, "behind": behind, "reason": f"compared to {base_ref}"}

    return {"state": "unknown", "ahead": None, "behind": None, "reason": f"could not compare to {base_ref}"}


def _approval_for_impact(impact: dict[str, Any]) -> dict[str, str]:
    tier = impact["tier"]
    labels = {
        "none": "No update to apply.",
        "low_risk_docs": "Operator may apply after review; no restart expected.",
        "operator_review": "Operator review required before applying.",
        "spirit_operator_approval": "Spirit/operator approval required; restart may be needed.",
        "explicit_operator_approval": "Explicit operator approval required; dependencies may change.",
        "explicit_mage_operator_approval": "Explicit Mage/operator approval required; protected or governance files are involved.",
    }
    return {"tier": tier, "summary": labels[tier]}


def _restart_for_impact(impact: dict[str, Any]) -> dict[str, str]:
    buckets = impact["buckets"]
    if buckets["dependencies"]:
        return {"needed": "unknown", "summary": "Dependency changes need an operator-managed install and likely restart."}
    if buckets["protected_or_governance"]:
        return {"needed": "unknown", "summary": "Protected/governance changes need explicit review before restart decisions."}
    if buckets["runtime_code"]:
        return {"needed": "maybe", "summary": "Runtime Python changed; bot restart may be needed after verification."}
    return {"needed": "no", "summary": "No runtime restart expected from the current changed-file set."}


def _next_action(*, divergence: dict[str, Any], dirty: bool, stale: bool) -> str:
    if dirty:
        return "Live working tree is dirty; inspect before any update."
    if stale:
        return "Remote tracking ref is stale; fetch intentionally before apply planning."
    state = divergence["state"]
    if state == "behind":
        return "Run update plan, review impact, then apply manually if approved."
    if state == "ahead":
        return "Live tree has commits not in the base ref; push or reconcile before treating remote as newer."
    if state == "diverged":
        return "Branches diverged; Spirit/operator must reconcile manually."
    if state == "up_to_date":
        return "No update needed."
    return "Resolve source-of-truth comparison before applying updates."


def _reassurance() -> dict[str, list[str]]:
    return {
        "not_touched_by_check_or_plan": [
            "practice state",
            ".env",
            "mage_registry.yaml",
            "native-runtime task/audit state",
            "launchd services",
            "running Discord bot",
        ]
    }


def _split_remote_ref(ref: str) -> tuple[str, str]:
    if "/" not in ref:
        return "", ""
    remote, branch = ref.split("/", 1)
    return remote, branch


def _git(repo: Path, *args: str) -> GitResult:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=15, check=False)
    return GitResult(result.returncode, result.stdout, result.stderr)


def _git_stdout(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise UpdateCheckError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _optional_git_stdout(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_lines(repo: Path, *args: str) -> list[str]:
    output = _optional_git_stdout(repo, *args)
    if not output:
        return []
    return output.splitlines()
