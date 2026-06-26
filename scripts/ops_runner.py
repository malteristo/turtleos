#!/usr/bin/env python3
"""Mini-hosted ops gate — Layer 1 scripts + Layer 2 qwen summary on FAIL.

Runs offline functional suite, canary checks, update drift, writes Spirit Ops Report
to practice desk/craft/automation-reports/ for Forge harvest.

Usage:
  python scripts/ops_runner.py              # full offline gate (default)
  python scripts/ops_runner.py --quick      # canary + shake_report only
  python scripts/ops_runner.py --no-summarize # template report only
  python scripts/ops_runner.py --job post-merge

See docs/automation/registry.md
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

try:
    from ops_paths import REPO as _REPO, TEST_RUNS, venv_python, workshop_root, resolve_automation_reports_dir
    from write_ops_report import write_ops_artifacts
except ImportError:
    from scripts.ops_paths import REPO as _REPO, TEST_RUNS, venv_python, workshop_root, resolve_automation_reports_dir
    from scripts.write_ops_report import write_ops_artifacts

REPO = _REPO  # re-export for consistency

from runtime.update import check_update


SUITE_STEPS: list[tuple[str, list[str]]] = [
    ("unittest", ["-m", "unittest", "discover", "-s", "tests", "-q"]),
    ("shake_river", ["scripts/shake_river.py"]),
    ("shake_flow_navigator", ["scripts/shake_flow.py", "navigator"]),
    ("shake_eddy_bar", ["scripts/shake_eddy_bar.py"]),
    ("shake_link_read", ["scripts/shake_link_read.py"]),
    ("shake_lifecycle", ["scripts/shake_lifecycle.py"]),
    ("shake_discord_ref", ["scripts/shake_discord_ref.py"]),
]


def _run_step(name: str, args: list[str], py: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(py), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "name": name,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:] if proc.stdout else "",
        "stderr": proc.stderr[-4000:] if proc.stderr else "",
    }


def _run_canary(py: Path) -> dict[str, Any]:
    import canary as canary_mod

    results: list[dict[str, Any]] = []
    has_red = False
    has_yellow = False
    for layer, name, fn, weight in canary_mod.CHECKS:
        try:
            status, detail = fn()
        except Exception as exc:
            status, detail = "red", f"check raised: {exc}"
        results.append(
            {
                "layer": layer,
                "name": name,
                "status": status,
                "detail": detail,
                "weight": weight,
            }
        )
        if status == "red" and weight == "high":
            has_red = True
        elif status == "red":
            has_yellow = True
        elif status == "yellow":
            has_yellow = True

    overall = "red" if has_red else ("yellow" if has_yellow else "green")
    timestamp = datetime.now(timezone.utc).isoformat()
    return {"timestamp": timestamp, "overall": overall, "checks": results}


def _update_summary(check: dict[str, Any]) -> str:
    div = check.get("divergence", {})
    state = div.get("state", "unknown")
    dirty = check.get("current", {}).get("dirty", False)
    branch = check.get("current", {}).get("branch", "?")
    sha = check.get("current", {}).get("sha", "?")
    behind = div.get("behind", 0)
    ahead = div.get("ahead", 0)
    parts = [f"{branch} @ {sha[:8]}", f"divergence={state}"]
    if behind:
        parts.append(f"behind={behind}")
    if ahead:
        parts.append(f"ahead={ahead}")
    if dirty:
        parts.append("dirty")
    return ", ".join(parts)


def _collect_updates() -> dict[str, Any]:
    turtle_check = check_update(repo=REPO)
    workshop_path = workshop_root()
    workshop_check = None
    if (workshop_path / ".git").is_dir():
        workshop_check = check_update(repo=workshop_path)

    return {
        "turtleos": turtle_check,
        "workshop": workshop_check,
        "turtleos_summary": _update_summary(turtle_check),
        "workshop_summary": _update_summary(workshop_check) if workshop_check else "no git clone",
    }


def _build_shake_report(py: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(py), "scripts/shake_report.py", "--write", "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        path = TEST_RUNS / "shake-report-latest.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        raise RuntimeError(
            f"shake_report failed (exit {proc.returncode}): {proc.stderr[-500:]}"
        )
    return json.loads(proc.stdout)


def _compute_ops_overall(
    shake: dict[str, Any],
    canary: dict[str, Any],
    suite_steps: list[dict[str, Any]],
) -> str:
    if shake.get("functional_gate") != "pass":
        return "fail"
    if any(s.get("exit_code") != 0 for s in suite_steps):
        return "fail"
    if canary.get("overall") == "red":
        return "fail"
    if canary.get("overall") == "yellow" or shake.get("functional_gate") == "incomplete":
        return "warn"
    return "pass"


def run_ops(
    *,
    mode: str,
    job: str,
    summarize: bool,
) -> dict[str, Any]:
    py = venv_python()
    suite_steps: list[dict[str, Any]] = []

    if mode == "quick":
        suite_steps.append(_run_step("shake_report_refresh", ["scripts/shake_report.py", "--write"], py))
    else:
        for name, args in SUITE_STEPS:
            suite_steps.append(_run_step(name, args, py))

    canary = _run_canary(py)
    shake_report = _build_shake_report(py)
    updates = _collect_updates()

    bundle: dict[str, Any] = {
        "meta": {
            "job": job,
            "mode": mode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "repo": str(REPO),
            "reports_dir": str(resolve_automation_reports_dir()),
        },
        "suite_steps": suite_steps,
        "canary": canary,
        "shake_report": shake_report,
        "updates": updates,
    }
    bundle["ops_overall"] = _compute_ops_overall(shake_report, canary, suite_steps)

    if summarize and bundle["ops_overall"] != "pass":
        try:
            from ops_summarize import summarize_failures
        except ImportError:
            from scripts.ops_summarize import summarize_failures

        diagnosis = summarize_failures(bundle)
        if diagnosis:
            bundle["local_diagnosis"] = diagnosis

    paths = write_ops_artifacts(bundle)
    bundle["written_paths"] = paths
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Mini-hosted ops gate runner")
    parser.add_argument(
        "--mode",
        choices=("gate", "quick"),
        default="gate",
        help="gate=full offline suite; quick=refresh report from existing shake artifacts",
    )
    parser.add_argument("--job", default="ops-gate", help="job label for report filename")
    parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="skip Layer 2 qwen summary even on FAIL",
    )
    parser.add_argument("--json", action="store_true", help="print bundle JSON to stdout")
    args = parser.parse_args()

    # Load dotenv for mage registry / OLLAMA when present
    dotenv = REPO / ".env"
    if dotenv.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv)
        except ImportError:
            pass

    bundle = run_ops(
        mode=args.mode,
        job=args.job,
        summarize=not args.no_summarize,
    )

    if args.json:
        print(json.dumps(bundle, indent=2))
    else:
        paths = bundle.get("written_paths", {})
        print(f"ops_overall={bundle['ops_overall']}")
        print(f"latest_md={paths.get('latest_md')}")
        print(f"latest_json={paths.get('latest_json')}")

    if bundle["ops_overall"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
