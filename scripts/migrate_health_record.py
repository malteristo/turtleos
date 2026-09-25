#!/usr/bin/env python3
"""Backfill an existing private health store without moving originals."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.atomic_io import atomic_write_json
from practice_corpus import remove_source, search
from practice_sources import intake_file, load_manifests, process_source


EXCLUDED_PARTS = frozenset({"manifests", "sources", ".derived", ".incoming"})
EXCLUDED_NAMES = frozenset(
    {
        "health_model.md",
        "README.md",
        "index.md",
        "intake-2026-09-07.md",
    }
)
SUPPORTED = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md", ".csv", ".json", ".zip"}
)
SOURCE_ROOTS = frozenset({"labs", "visits", "notes", "genetics"})


def candidate_files(practice_dir: Path) -> list[Path]:
    candidates = []
    for path in practice_dir.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(practice_dir)
        in_source_root = (
            relative.parts
            and relative.parts[0] in SOURCE_ROOTS
        ) or (
            len(relative.parts) > 1
            and relative.parts[0] == "documents"
            and relative.parts[1] in SOURCE_ROOTS
        )
        if not in_source_root:
            continue
        if set(relative.parts) & EXCLUDED_PARTS:
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() not in SUPPORTED:
            continue
        candidates.append(path)
    return sorted(candidates)


def migrate(practice_dir: Path, *, apply: bool) -> dict:
    if not practice_dir.is_dir():
        raise RuntimeError(f"health root does not exist: {practice_dir}")
    files = candidate_files(practice_dir)
    report = {
        "mode": "apply" if apply else "dry-run",
        "practice_dir": str(practice_dir),
        "candidates": len(files),
        "saved": 0,
        "duplicates": 0,
        "ready": 0,
        "stored": 0,
        "needs_review": 0,
        "failed": [],
    }
    if not apply:
        report["paths"] = [str(path.relative_to(practice_dir)) for path in files]
        return report

    practice_dir.chmod(0o700)
    report["pruned_derived_extracts"] = prune_derived_extract_manifests(practice_dir)
    for path in files:
        result = intake_file(practice_dir, path, actor="private-migration")
        if result.status == "Saved":
            report["saved"] += 1
            processed = process_source(practice_dir, result.source_id)
            if processed.status == "Failed":
                report["failed"].append(
                    {"path": str(path.relative_to(practice_dir)), "detail": processed.detail}
                )
            elif processed.status == "Needs review":
                report["needs_review"] += 1
            else:
                report[processed.status.lower()] = report.get(processed.status.lower(), 0) + 1
        elif result.status == "Duplicate":
            report["duplicates"] += 1
        elif result.status == "Failed":
            report["failed"].append(
                {"path": str(path.relative_to(practice_dir)), "detail": result.detail}
            )

    report["claim_map"] = source_map_model(practice_dir)
    report["manifests"] = len(load_manifests(practice_dir))
    return report


def prune_derived_extract_manifests(practice_dir: Path) -> int:
    """Undo registrations of legacy extracts as originals; never touch extracts."""
    count = 0
    extract_root = (practice_dir / "documents" / "extracts").resolve()
    for manifest_path in (practice_dir / "documents" / "manifests").glob("*.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            original = Path(str(manifest.get("original_path") or "")).resolve()
            original.relative_to(extract_root)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        remove_source(practice_dir, str(manifest.get("source_id") or ""))
        manifest_path.unlink()
        count += 1
    return count


def source_map_model(practice_dir: Path) -> dict:
    """Retrieval-map existing board lines; do not reinterpret or rewrite them."""
    model_path = practice_dir / "health_model.md"
    claims = {}
    if model_path.is_file():
        for line_no, raw in enumerate(model_path.read_text(encoding="utf-8").splitlines(), 1):
            text = re.sub(r"^[|*\-\s]+|[|\s]+$", "", raw).strip()
            if not text or text.startswith("#") or len(text) < 20:
                continue
            terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", text, flags=re.UNICODE)[:10]
            hits = search(practice_dir, " ".join(terms), limit=3) if terms else []
            claim_id = hashlib.sha256(f"{line_no}:{text}".encode()).hexdigest()[:16]
            claims[claim_id] = {
                "claim_id": claim_id,
                "model_line": line_no,
                "text": text,
                "evidence": [hit["citation"] for hit in hits],
                "status": "retrieval_mapped" if hits else "unmapped",
                "method": "lexical retrieval only; no clinical reinterpretation",
            }
    path = practice_dir / "record" / "model_claim_map.json"
    atomic_write_json(path, claims, indent=2, lock=True)
    return {
        "claims": len(claims),
        "mapped": sum(1 for row in claims.values() if row["evidence"]),
        "unmapped": sum(1 for row in claims.values() if not row["evidence"]),
        "path": str(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--practice-dir",
        type=Path,
        default=Path("~/workshops/health").expanduser(),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = migrate(args.practice_dir.expanduser().resolve(), apply=args.apply)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
