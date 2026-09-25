#!/usr/bin/env python3
"""Fail if sensitive health sources cross the local/private boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SENSITIVE_REPO_PARTS = {
    "documents/manifests/",
    "documents/sources/",
    "documents/extracts/",
    "record/claims.json",
    "record/observations.jsonl",
    "record/questions.jsonl",
    "record/dates.jsonl",
    "record/medications.jsonl",
}


def scan_repo() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    findings = []
    for path in proc.stdout.splitlines():
        normalized = path.replace("\\", "/")
        if any(part in normalized for part in SENSITIVE_REPO_PARTS):
            findings.append(f"tracked sensitive record path: {normalized}")
    return findings


def scan_private_root(practice_dir: Path) -> list[str]:
    findings = []
    if not practice_dir.is_dir():
        return ["private health root missing"]
    mode = practice_dir.stat().st_mode & 0o777
    if mode & 0o077:
        findings.append(f"health root permissions are {oct(mode)}, expected 0o700")
    root = practice_dir.resolve()
    for path in (
        practice_dir / "documents" / "manifests",
        practice_dir / "documents" / "extracts",
        practice_dir / "documents" / ".derived",
        practice_dir / "record",
    ):
        if path.is_symlink():
            findings.append(f"sensitive path is symlinked: {path.name}")
        if path.exists():
            try:
                path.resolve().relative_to(root)
            except ValueError:
                findings.append(f"sensitive path escapes private root: {path.name}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--practice-dir", type=Path)
    parser.add_argument("--skip-repo", action="store_true")
    args = parser.parse_args()
    findings = [] if args.skip_repo else scan_repo()
    if args.practice_dir:
        findings.extend(scan_private_root(args.practice_dir.expanduser()))
    report = {"status": "pass" if not findings else "fail", "findings": findings}
    print(json.dumps(report, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
