#!/usr/bin/env python3
"""Format and write Spirit Ops Reports from structured ops bundles.

Layer 1: template-only markdown from JSON facts (no LLM).
See docs/automation/registry.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ops_paths import REPO, TEST_RUNS, resolve_automation_reports_dir
except ImportError:
    from scripts.ops_paths import REPO, TEST_RUNS, resolve_automation_reports_dir


def _gate_emoji(gate: str) -> str:
    if gate == "pass":
        return "PASS"
    if gate == "incomplete":
        return "INCOMPLETE"
    return "FAIL"


def _canary_emoji(overall: str) -> str:
    return overall.upper()


def format_ops_markdown(bundle: dict[str, Any]) -> str:
    meta = bundle.get("meta", {})
    shake = bundle.get("shake_report", {})
    canary = bundle.get("canary", {})
    updates = bundle.get("updates", {})
    steps = bundle.get("suite_steps", [])

    functional_gate = shake.get("functional_gate", "unknown")
    canary_overall = canary.get("overall", "unknown")
    ops_overall = bundle.get("ops_overall", "unknown")

    lines = [
        "# Spirit Ops Report",
        "",
        f"**Job:** {meta.get('job', 'ops-gate')}",
        f"**Generated:** {meta.get('generated_at', '')}",
        f"**Host:** {meta.get('hostname', '')}",
        f"**Overall:** {_gate_emoji(ops_overall)}",
        "",
        "## Summary",
        f"- Functional gate: **{functional_gate}**",
        f"- Canary: **{canary_overall}**",
        f"- turtleOS: {updates.get('turtleos_summary', '—')}",
        f"- Workshop: {updates.get('workshop_summary', '—')}",
        "",
    ]

    failed_steps = [s for s in steps if s.get("exit_code") != 0]
    if failed_steps:
        lines.append("## Suite step failures")
        for step in failed_steps:
            lines.append(f"- `{step.get('name')}` — exit {step.get('exit_code')}")
            stderr = (step.get("stderr") or "").strip()
            if stderr:
                lines.append(f"  - stderr: {stderr[:200]}")
        lines.append("")

    if shake.get("spirit_failed_artifacts"):
        lines.append("## Spirit gate failures")
        for name in shake["spirit_failed_artifacts"]:
            lines.append(f"- `{name}`")
        lines.append("")

    if shake.get("spirit_missing_artifacts"):
        lines.append("## Spirit missing verdicts")
        for name in shake["spirit_missing_artifacts"]:
            lines.append(f"- `{name}`")
        lines.append("")

    artifacts = shake.get("artifacts") or []
    if artifacts:
        lines.append("## Artifact status")
        lines.append("| Shake | Status | Live | Scenarios |")
        lines.append("|-------|--------|------|-----------|")
        for artifact in artifacts:
            live = artifact.get("live")
            live_cell = "yes" if live else "no" if live is False else "—"
            scenarios = ", ".join(artifact.get("spirit_scenarios", []))
            lines.append(
                f"| {artifact.get('label', '')} | {artifact.get('status', '')} | "
                f"{live_cell} | {scenarios} |"
            )
        lines.append("")

    canary_checks = canary.get("checks") or []
    non_green = [c for c in canary_checks if c.get("status") != "green"]
    if non_green:
        lines.append("## Canary (non-green)")
        for check in non_green:
            lines.append(
                f"- **{check.get('status')}** `{check.get('layer')}/{check.get('name')}` — "
                f"{check.get('detail', '')}"
            )
        lines.append("")

    if updates.get("turtleos"):
        lines.append("## turtleOS drift")
        lines.append(f"```json\n{json.dumps(updates['turtleos'], indent=2)}\n```")
        lines.append("")

    if updates.get("workshop"):
        lines.append("## Workshop drift")
        lines.append(f"```json\n{json.dumps(updates['workshop'], indent=2)}\n```")
        lines.append("")

    lines.append("## Spirit action (Forge)")
    if functional_gate == "pass" and canary_overall == "green":
        lines.append(
            "- Gate closed — Mage UX dogfood only when a chapter ships; harvest this report at `. craft`."
        )
    else:
        lines.append("- Fix failing suite steps / shake artifacts on Forge.")
        lines.append("- Re-run `scripts/ops_runner.py` on Mini (or `shake_after_deploy.sh`).")
        lines.append("- Do not ask Mage to verify plumbing.")
    lines.append("")

    diagnosis = bundle.get("local_diagnosis")
    if diagnosis:
        lines.append("## Local diagnosis (qwen)")
        lines.append(diagnosis.strip())
        lines.append("")
        lines.append("_Scripts set pass/fail; this section is narrative only._")
        lines.append("")

    lines.append("---")
    lines.append(f"_turtleOS ops Layer 1+2 · repo {REPO}_")
    return "\n".join(lines)


def write_ops_artifacts(bundle: dict[str, Any], reports_dir: Path | None = None) -> dict[str, str]:
    out_dir = reports_dir or resolve_automation_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    job = bundle.get("meta", {}).get("job", "ops-gate")
    dated_name = f"{stamp}-{job}.md"

    markdown = format_ops_markdown(bundle)
    json_text = json.dumps(bundle, indent=2) + "\n"

    paths = {
        "dated_md": str(out_dir / dated_name),
        "latest_md": str(out_dir / "latest.md"),
        "latest_json": str(TEST_RUNS / "ops-report-latest.json"),
    }

    (out_dir / dated_name).write_text(markdown, encoding="utf-8")
    (out_dir / "latest.md").write_text(markdown, encoding="utf-8")
    TEST_RUNS.mkdir(parents=True, exist_ok=True)
    (TEST_RUNS / "ops-report-latest.json").write_text(json_text, encoding="utf-8")

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Spirit Ops Report from ops bundle JSON")
    parser.add_argument("bundle_file", type=Path, help="JSON bundle from ops_runner")
    parser.add_argument("--reports-dir", type=Path, default=None)
    args = parser.parse_args()

    bundle = json.loads(args.bundle_file.read_text(encoding="utf-8"))
    paths = write_ops_artifacts(bundle, args.reports_dir)
    print(json.dumps(paths, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
