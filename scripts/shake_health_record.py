#!/usr/bin/env python3
"""Offline functional gate for the complete health channel primitive."""

from __future__ import annotations

OFFLINE_SAFE = True

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEST_RUNS = REPO / "test-runs"
PYTHON = REPO / "venv" / "bin" / "python3"
sys.path.insert(0, str(REPO))


def main() -> int:
    checks = {}
    proc = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "unittest",
            "tests.test_channel_primitives",
            "tests.test_practice_sources",
            "tests.test_governed_record",
            "tests.test_health_record",
            "tests.test_health_checkin",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    checks["acceptance_units"] = {
        "ok": proc.returncode == 0,
        "detail": (proc.stderr or proc.stdout)[-1200:],
    }

    from practice_sources import processor_readiness

    readiness = processor_readiness()
    checks["processor_reporting"] = {
        "ok": all(key in readiness for key in ("pymupdf", "tesseract", "health_ocr", "missing")),
        "detail": readiness,
    }
    from scripts.check_health_privacy import scan_repo

    privacy_findings = scan_repo()
    checks["privacy_boundary"] = {
        "ok": not privacy_findings,
        "detail": privacy_findings or "no private record paths tracked",
    }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "labs").mkdir()
        (root / "labs" / "fixture.txt").write_text(
            "Ferritin: 21 ng/mL\n", encoding="utf-8"
        )
        (root / "health_model.md").write_text(
            "# Health model\n\n- Ferritin measured 21 ng/mL.\n", encoding="utf-8"
        )
        dry = subprocess.run(
            [
                str(PYTHON),
                str(REPO / "scripts" / "migrate_health_record.py"),
                "--practice-dir",
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(dry.stdout) if dry.returncode == 0 else {}
        checks["migration_dry_run"] = {
            "ok": payload.get("mode") == "dry-run"
            and payload.get("candidates") == 1
            and not (root / "documents" / "manifests").exists(),
            "detail": payload or dry.stderr,
        }

    # Positive control: unknown primitives must lose all capabilities.
    from channel_primitives import resolve_primitive

    checks["fail_closed_control"] = {
        "ok": resolve_primitive(
            {"channels": {"7": {"primitive": "not-real"}}}, 7
        )
        is None,
        "detail": "unknown primitive resolved to no contract",
    }

    status = "pass" if all(row["ok"] for row in checks.values()) else "fail"
    report = {
        "capability": "health-record",
        "status": status,
        "live": False,
        "checks": checks,
    }
    TEST_RUNS.mkdir(exist_ok=True)
    (TEST_RUNS / "shake-health-record-latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
