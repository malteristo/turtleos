#!/usr/bin/env python3
"""Aggregate shake verdict JSON + acceptance scenario gates into one CTO dashboard.

Reads test-runs/shake-*-latest.json, maps to acceptance scenario IDs, and prints
Spirit functional status + Mage UX queue for async dogfood.

Usage:
  python scripts/shake_report.py              # human markdown
  python scripts/shake_report.py --json       # machine-readable
  python scripts/shake_report.py --strict     # exit 1 if any Spirit gate failed/missing

See docs/automation/functional-gate-protocol.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
TEST_RUNS = REPO / "test-runs"

# Verdict artifact → acceptance scenarios covered by Spirit offline/live shake
SHAKE_ARTIFACTS: dict[str, dict[str, Any]] = {
    "shake-river-latest.json": {
        "label": "river (offline)",
        "spirit_scenarios": ["R1", "X1"],
        "script": "scripts/shake_river.py",
    },
    "shake-flow-latest.json": {
        "label": "flow navigator",
        "spirit_scenarios": ["J2", "J3"],
        "script": "scripts/shake_flow.py navigator",
    },
    "shake-eddy-bar-latest.json": {
        "label": "eddy bar",
        "spirit_scenarios": ["R1", "R2", "R3"],
        "script": "scripts/shake_eddy_bar.py",
    },
    "shake-link-read-latest.json": {
        "label": "link read",
        "spirit_scenarios": ["H1", "H4", "H5", "X2"],
        "script": "scripts/shake_link_read.py",
    },
    "shake-lifecycle-latest.json": {
        "label": "lifecycle bar",
        "spirit_scenarios": ["R4", "R5"],
        "script": "scripts/shake_lifecycle.py",
    },
    "shake-discord-ref-latest.json": {
        "label": "discord permalink",
        "spirit_scenarios": ["D2", "D2b"],
        "script": "scripts/shake_discord_ref.py",
    },
}

# Mage async dogfood — practice feel; not automated by shake scripts
MAGE_UX_SCENARIOS: dict[str, str] = {
    "H1": "First reply feels informed (not just plumbing)",
    "H2": "Save to library UX (Tier 2)",
    "H3": "Cached library act — no duplicate Save",
    "J1": "Daily loop: new eddy → talk (ChatGPT-style)",
    "D1": "Resume eddy continuity after gap",
    "D3": "Contextual River offer useful vs noise",
    "R3": "Thread rename + Turtle join feels right",
    "S1": "Share eddy sender + Continue UX",
}

# Default post-deploy Spirit suite (offline); live adds --live on Mini
DEFAULT_OFFLINE_SUITE = [
    "scripts/shake_river.py",
    "scripts/shake_flow.py navigator",
    "scripts/shake_eddy_bar.py",
    "scripts/shake_link_read.py",
    "scripts/shake_lifecycle.py",
    "scripts/shake_discord_ref.py",
]


def _parse_verdict(data: dict[str, Any]) -> tuple[str, bool | None]:
    """Return (status_label, live_flag). status: pass | fail | unknown."""
    if "pass" in data and isinstance(data["pass"], bool):
        return ("pass" if data["pass"] else "fail", None)
    status = str(data.get("status", "unknown")).lower()
    if status in ("pass", "ok"):
        return ("pass", data.get("live"))
    if status in ("fail", "error"):
        return ("fail", data.get("live"))
    return ("unknown", data.get("live"))


def _load_artifact(name: str) -> dict[str, Any] | None:
    path = TEST_RUNS / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "fail", "error": "invalid json", "_path": str(path)}


def build_report() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    spirit_by_scenario: dict[str, dict[str, Any]] = {}
    spirit_failed: list[str] = []
    spirit_missing: list[str] = []

    for filename, meta in SHAKE_ARTIFACTS.items():
        raw = _load_artifact(filename)
        if raw is None:
            entry = {
                "file": filename,
                "label": meta["label"],
                "status": "missing",
                "spirit_scenarios": meta["spirit_scenarios"],
                "script": meta["script"],
            }
            artifacts.append(entry)
            for sid in meta["spirit_scenarios"]:
                spirit_by_scenario[sid] = {"status": "missing", "source": filename}
            spirit_missing.append(filename)
            continue

        status, live = _parse_verdict(raw)
        entry = {
            "file": filename,
            "label": meta["label"],
            "status": status,
            "live": live if live is not None else raw.get("live"),
            "capability": raw.get("capability"),
            "spirit_scenarios": meta["spirit_scenarios"],
            "script": meta["script"],
            "checks": raw.get("checks"),
            "timestamp": raw.get("timestamp"),
        }
        artifacts.append(entry)
        for sid in meta["spirit_scenarios"]:
            spirit_by_scenario[sid] = {"status": status, "source": filename}
        if status != "pass":
            spirit_failed.append(filename)

    functional_gate = "pass" if not spirit_failed and not spirit_missing else "fail"
    if spirit_missing and not spirit_failed:
        functional_gate = "incomplete"

    mage_queue = [
        {"id": sid, "prompt": MAGE_UX_SCENARIOS[sid]}
        for sid in sorted(MAGE_UX_SCENARIOS.keys())
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(REPO),
        "functional_gate": functional_gate,
        "spirit_failed_artifacts": spirit_failed,
        "spirit_missing_artifacts": spirit_missing,
        "artifacts": artifacts,
        "spirit_by_scenario": spirit_by_scenario,
        "mage_ux_queue": mage_queue,
        "default_offline_suite": DEFAULT_OFFLINE_SUITE,
        "verdict_dir": str(TEST_RUNS),
    }


def format_markdown(report: dict[str, Any]) -> str:
    gate = report["functional_gate"]
    lines = [
        f"# Shake report — functional gate: **{gate.upper()}**",
        f"_Generated {report['generated_at']}_",
        "",
    ]

    if report["spirit_failed_artifacts"]:
        lines.append("## Spirit failures")
        for f in report["spirit_failed_artifacts"]:
            lines.append(f"- `{f}`")
        lines.append("")

    if report["spirit_missing_artifacts"]:
        lines.append("## Spirit missing verdicts (run offline suite)")
        for f in report["spirit_missing_artifacts"]:
            lines.append(f"- `{f}`")
        lines.append("")

    lines.append("## Artifact status")
    lines.append("| Shake | Status | Live | Scenarios |")
    lines.append("|-------|--------|------|-----------|")
    for a in report["artifacts"]:
        live = "yes" if a.get("live") else "no" if a.get("live") is False else "—"
        sc = ", ".join(a["spirit_scenarios"])
        lines.append(f"| {a['label']} | {a['status']} | {live} | {sc} |")
    lines.append("")

    lines.append("## Mage UX queue (async dogfood)")
    lines.append("_Spirit functional gate closed → your job is practice feel only._")
    lines.append("")
    for item in report["mage_ux_queue"]:
        lines.append(f"- **{item['id']}** — {item['prompt']}")
    lines.append("")
    lines.append("Capture: screenshot + felt-sense in Forge (`cast_shake.md` appendix).")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Shake verdict dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 unless functional_gate is pass",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write test-runs/shake-report-latest.json",
    )
    args = parser.parse_args()

    report = build_report()
    if args.write:
        TEST_RUNS.mkdir(parents=True, exist_ok=True)
        (TEST_RUNS / "shake-report-latest.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_markdown(report))

    if args.strict and report["functional_gate"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
