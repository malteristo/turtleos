#!/usr/bin/env python3
"""B-calibration instrument — can the judge tell present-tense stale from aged carry?

This is not a live-turn continuity eval. It scores two banked synthetic fixtures
(transcript + what the root held). No model. No live practice root. No real
person's words.

Suite PASS iff the judge classifies both fixtures correctly:
  b-stale-present — present-tense stale fact → must flag B
  b-aged-carry    — same fact with age attached → must clear B

Planted false carry that the judge *detects* is expected. The gate goes red only
when the judge is wrong.

    python3 scripts/shake_continuity.py           # score the bank; write verdict
    python3 scripts/shake_continuity.py --self-test
"""
from __future__ import annotations

# Declared for scripts/shake_report.py: mutates nothing a practitioner can see.
OFFLINE_SAFE = True

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO / "scripts" / "fixtures" / "continuity"
TEST_RUNS = REPO / "test-runs"
VERDICT_PATH = TEST_RUNS / "shake-continuity-latest.json"

# CE: carried context with its age attached is not a false carry.
_AGE_CUE = re.compile(
    r"\b("
    r"ago|since|"
    r"last\s+(?:noted|mentioned|checkpoint|raised|true)|"
    r"\d{4}-\d{2}-\d{2}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}"
    r"|\d{1,2}\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r")\b",
    re.I,
)

WINDOW = 80


def load_fixtures(directory: Path = FIXTURE_DIR) -> list[dict]:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no continuity fixtures in {directory}")
    out = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        out.append(data)
    return out


def _window(transcript: str, phrase: str) -> str | None:
    i = transcript.lower().find(phrase.lower())
    if i < 0:
        return None
    return transcript[max(0, i - WINDOW) : i + len(phrase) + WINDOW]


def flags_b(held: list[dict], transcript: str) -> bool:
    """True when a no-longer-true fact is asserted without age."""
    for item in held:
        if item.get("current", True):
            continue
        phrase = str(item.get("fact") or "").strip()
        if not phrase:
            continue
        around = _window(transcript, phrase)
        if around is None:
            continue
        last_true = str(item.get("last_true") or "")
        if last_true and last_true in around:
            continue
        if _AGE_CUE.search(around):
            continue
        return True
    return False


def classify(fixture: dict, invert: bool = False) -> bool:
    flagged = flags_b(fixture.get("held") or [], fixture.get("transcript") or "")
    return (not flagged) if invert else flagged


def score_pair(fixtures: list[dict], invert: bool = False) -> dict:
    rows = []
    errors: list[str] = []
    for fx in fixtures:
        got = classify(fx, invert=invert)
        expect = bool(fx.get("expect_b"))
        ok = got == expect
        rows.append(
            {
                "id": fx.get("id"),
                "expect_b": expect,
                "got_b": got,
                "ok": ok,
            }
        )
        if not ok:
            errors.append(
                f"{fx.get('id')}: expected B={expect}, judge said B={got}"
            )
    return {
        "rows": rows,
        "errors": errors,
        "ok": not errors,
    }


def trivial_baselines(fixtures: list[dict]) -> dict:
    """What a mindless scorer would do to this pair — printed beside the score."""
    always_pass = []
    always_flag = []
    for fx in fixtures:
        expect = bool(fx.get("expect_b"))
        always_pass.append(
            {"id": fx.get("id"), "ok": expect is False}
        )
        always_flag.append(
            {"id": fx.get("id"), "ok": expect is True}
        )
    return {
        "always_pass": {
            "ok": all(r["ok"] for r in always_pass),
            "rows": always_pass,
        },
        "always_flag_b": {
            "ok": all(r["ok"] for r in always_flag),
            "rows": always_flag,
        },
    }


def build_report(fixtures: list[dict], invert: bool = False) -> dict:
    scored = score_pair(fixtures, invert=invert)
    baselines = trivial_baselines(fixtures)
    return {
        "shake": "continuity",
        "instrument": "B-calibration",
        "not": "live-turn continuity eval",
        "status": "pass" if scored["ok"] else "fail",
        "live": False,
        "invert": invert,
        "checks": scored["rows"],
        "errors": scored["errors"],
        "baselines": baselines,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def write_verdict(report: dict) -> None:
    TEST_RUNS.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def format_human(report: dict) -> str:
    lines = [
        f"# Continuity judge — B-calibration: **{report['status'].upper()}**",
        "",
        "Instrument, not a live-turn eval. Red only when the judge is wrong.",
        "",
        "| Fixture | Expect B | Got B | |",
        "|---------|----------|-------|---|",
    ]
    for row in report["checks"]:
        mark = "ok" if row["ok"] else "MISCLASSIFIED"
        lines.append(
            f"| {row['id']} | {row['expect_b']} | {row['got_b']} | {mark} |"
        )
    lines.append("")
    lines.append("Trivial baselines (must not both pass if the pair is real):")
    for name, body in report["baselines"].items():
        lines.append(f"- {name}: {'would pass the pair' if body['ok'] else 'fails a fixture (expected)'}")
    if report["errors"]:
        lines.append("")
        lines.append("Errors:")
        for e in report["errors"]:
            lines.append(f"- {e}")
    return "\n".join(lines)


def self_test() -> int:
    fixtures = load_fixtures()
    real = build_report(fixtures, invert=False)
    if real["status"] != "pass":
        print("SELF-TEST FAIL: banked pair is not classified correctly")
        print(format_human(real))
        return 1
    planted = build_report(fixtures, invert=True)
    if planted["status"] != "fail":
        print("SELF-TEST FAIL: inverted judge was not caught — the gate cannot fail")
        return 1
    always_pass = real["baselines"]["always_pass"]["ok"]
    always_flag = real["baselines"]["always_flag_b"]["ok"]
    if always_pass or always_flag:
        print("SELF-TEST FAIL: a trivial baseline would pass the pair — fixtures are not a pair")
        return 1
    print(
        "shake_continuity self-test: ok "
        "(pair classified; inverted judge fails the gate; trivial baselines lose)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="positive control: inverted judge must fail the gate",
    )
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    fixtures = load_fixtures()
    report = build_report(fixtures, invert=False)
    write_verdict(report)
    print(format_human(report))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
