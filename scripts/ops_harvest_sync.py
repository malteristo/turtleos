#!/usr/bin/env python3
"""Push Spirit Ops Reports from Mini workshop to turtle bare for Forge harvest."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

ALLOWED_PREFIX = "desk/craft/automation-reports/"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _normalize_rel(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def sync_ops_harvest(
    written_paths: dict[str, str],
    *,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Commit and push automation report markdown to workshop origin."""
    result: dict[str, Any] = {"status": "skipped", "reason": "", "paths": []}

    candidates: list[Path] = []
    for key in ("latest_md", "dated_md"):
        raw = written_paths.get(key)
        if raw:
            path = Path(raw)
            if path.is_file():
                candidates.append(path)

    if not candidates:
        result["reason"] = "no report files to sync"
        return result

    top = _git(candidates[0].parent, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        result["reason"] = "reports path is not inside a git repository"
        return result

    repo_root = Path(top.stdout.strip()).resolve()
    rel_paths: list[str] = []
    for path in candidates:
        rel = _normalize_rel(path, repo_root)
        if not rel.startswith(ALLOWED_PREFIX):
            result["status"] = "error"
            result["reason"] = f"refusing path outside automation-reports: {rel}"
            return result
        rel_paths.append(rel)

    result["paths"] = rel_paths
    result["repo"] = str(repo_root)

    status = _git(repo_root, "status", "--porcelain", "--", *rel_paths)
    if status.returncode != 0:
        result["status"] = "error"
        result["reason"] = (status.stderr or status.stdout or "git status failed").strip()
        return result
    if not status.stdout.strip():
        result["status"] = "unchanged"
        result["reason"] = "reports already match HEAD"
        return result

    add = _git(repo_root, "add", "--", *rel_paths)
    if add.returncode != 0:
        result["status"] = "error"
        result["reason"] = (add.stderr or add.stdout or "git add failed").strip()
        return result

    meta = (bundle or {}).get("meta", {})
    job = meta.get("job", "ops-gate")
    ops_overall = (bundle or {}).get("ops_overall", "unknown")
    commit_msg = f"ops harvest: {job} {ops_overall}"

    commit = _git(repo_root, "commit", "-m", commit_msg)
    if commit.returncode != 0:
        result["status"] = "error"
        result["reason"] = (commit.stderr or commit.stdout or "git commit failed").strip()
        return result

    branch_proc = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = (branch_proc.stdout or "main").strip() or "main"
    push = _git(repo_root, "push", "origin", branch)
    if push.returncode != 0:
        result["status"] = "error"
        result["reason"] = (push.stderr or push.stdout or "git push failed").strip()
        result["branch"] = branch
        return result

    sha_proc = _git(repo_root, "rev-parse", "--short", "HEAD")
    result.update(
        {
            "status": "pushed",
            "reason": "",
            "branch": branch,
            "commit": (sha_proc.stdout or "").strip(),
            "message": commit_msg,
        }
    )
    return result
