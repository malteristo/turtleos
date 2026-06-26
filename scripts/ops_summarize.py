#!/usr/bin/env python3
"""Layer 2: local qwen narrative on ops FAIL only.

Scripts own pass/fail; this model only summarizes structured failures for Forge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from models import RIVER_MODEL
from state import OLLAMA_URL

OPS_SUMMARY_SYSTEM = """You are the turtleOS ops reporter on a sovereign Mac Mini.
Spirit on Forge will read your bullets. Use ONLY facts from the JSON payload.
Write 3-5 bullet points: what failed, observable evidence, suggested next steps on Forge.
Do not claim anything passed. Do not invent root causes beyond the evidence.
Plain markdown bullets only. No preamble."""


def _failure_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    shake = bundle.get("shake_report", {})
    canary = bundle.get("canary", {})
    return {
        "ops_overall": bundle.get("ops_overall"),
        "functional_gate": shake.get("functional_gate"),
        "spirit_failed_artifacts": shake.get("spirit_failed_artifacts"),
        "spirit_missing_artifacts": shake.get("spirit_missing_artifacts"),
        "failed_suite_steps": [
            {
                "name": s.get("name"),
                "exit_code": s.get("exit_code"),
                "stderr_tail": (s.get("stderr") or "")[-500:],
            }
            for s in bundle.get("suite_steps", [])
            if s.get("exit_code") != 0
        ],
        "canary_non_green": [
            c for c in canary.get("checks", []) if c.get("status") != "green"
        ],
        "updates": bundle.get("updates"),
    }


def needs_summary(bundle: dict[str, Any]) -> bool:
    if bundle.get("ops_overall") != "pass":
        return True
    shake = bundle.get("shake_report", {})
    canary = bundle.get("canary", {})
    if shake.get("functional_gate") != "pass":
        return True
    if canary.get("overall") not in ("green", None):
        return True
    return any(s.get("exit_code") != 0 for s in bundle.get("suite_steps", []))


def summarize_failures(bundle: dict[str, Any], timeout_s: float = 90.0) -> str | None:
    if not needs_summary(bundle):
        return None

    payload = _failure_payload(bundle)
    user_content = "Failure payload JSON:\n" + json.dumps(payload, indent=2)

    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=timeout_s, write=10.0, pool=10.0)
        ) as client:
            response = client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": RIVER_MODEL,
                    "messages": [
                        {"role": "system", "content": OPS_SUMMARY_SYSTEM},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"num_ctx": 8192},
                    "keep_alive": "5m",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return f"_Local summary unavailable ({type(exc).__name__}: {exc})_"

    text = (data.get("message", {}).get("content") or "").strip()
    return text or None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Summarize ops failures with local qwen")
    parser.add_argument("bundle_file", type=Path)
    args = parser.parse_args()

    bundle = json.loads(args.bundle_file.read_text(encoding="utf-8"))
    summary = summarize_failures(bundle)
    if summary:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
