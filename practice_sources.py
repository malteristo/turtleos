"""Immutable source intake and bounded local extraction for channel primitives."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.atomic_io import atomic_write_json, atomic_write_text, file_lock


SOURCE_MAX_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_IMAGE_PIXELS = 40_000_000
MAX_ARCHIVE_MEMBERS = 1000
MAX_ARCHIVE_EXPANDED_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_RATIO = 100
OCR_LANGUAGES = "deu+eng"
PROCESS_TIMEOUT_SECONDS = 60
ALLOWED_MIME_PREFIXES = ("image/", "text/")
ALLOWED_MIMES = {
    "application/pdf",
    "application/json",
    "application/zip",
    "application/x-zip-compressed",
    "text/csv",
}


@dataclass(frozen=True)
class IntakeResult:
    status: str
    source_id: str | None
    filename: str
    detail: str
    manifest: dict | None = None


def processor_readiness() -> dict[str, Any]:
    try:
        import pymupdf  # noqa: F401

        pymupdf = True
    except ImportError:
        pymupdf = False
    binary = _tesseract_path()
    languages: set[str] = set()
    if binary:
        try:
            out = subprocess.run(
                [binary, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            languages = {line.strip() for line in out.splitlines()[1:] if line.strip()}
        except (OSError, subprocess.TimeoutExpired):
            pass
    needed = set(OCR_LANGUAGES.split("+"))
    return {
        "pymupdf": pymupdf,
        "tesseract": bool(binary),
        "ocr_languages": sorted(languages),
        "health_ocr": bool(pymupdf and binary and needed <= languages),
        "missing": sorted(
            ({"PyMuPDF"} if not pymupdf else set())
            | ({"tesseract"} if not binary else set())
            | ({f"tesseract:{lang}" for lang in needed - languages} if binary else set())
        ),
    }


async def intake_attachment(
    practice_dir: str | Path,
    attachment,
    *,
    actor: str,
    channel_id: int | str,
    message_id: int | str,
    status: Callable[[str], Any] | None = None,
) -> IntakeResult:
    """Stream one Discord attachment to local intake, then register by hash."""
    filename = _safe_filename(getattr(attachment, "filename", "attachment"))
    declared_size = int(getattr(attachment, "size", 0) or 0)
    mime = _normalise_mime(getattr(attachment, "content_type", ""), filename)
    if declared_size > SOURCE_MAX_BYTES:
        return IntakeResult("Needs review", None, filename, "file exceeds 100 MB intake limit")

    incoming = Path(practice_dir) / "documents" / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=incoming, suffix=".part")
    os.close(fd)
    temp = Path(temp_name)
    try:
        if status:
            status("Saving")
        save = getattr(attachment, "save", None)
        if callable(save):
            await save(temp)
        else:
            data = await attachment.read()
            temp.write_bytes(data)
        actual_size = temp.stat().st_size
        if actual_size > SOURCE_MAX_BYTES:
            return IntakeResult("Needs review", None, filename, "file exceeds 100 MB intake limit")
        return _register_temp(
            practice_dir,
            temp,
            filename=filename,
            mime=mime,
            actor=actor,
            channel_id=channel_id,
            message_id=message_id,
        )
    except Exception as exc:
        return IntakeResult("Failed", None, filename, f"{type(exc).__name__}: {exc}")
    finally:
        temp.unlink(missing_ok=True)


def intake_file(
    practice_dir: str | Path,
    path: str | Path,
    *,
    actor: str,
    channel_id: int | str = "migration",
    message_id: int | str = "migration",
) -> IntakeResult:
    """Register a local file without moving or rewriting it (migration path)."""
    source = Path(path)
    if not source.is_file():
        return IntakeResult("Failed", None, source.name, "file not found")
    size = source.stat().st_size
    if size > SOURCE_MAX_BYTES:
        return IntakeResult("Needs review", None, source.name, "file exceeds 100 MB intake limit")
    sha = _sha256(source)
    return _register_external(
        practice_dir,
        source,
        sha=sha,
        filename=_safe_filename(source.name),
        mime=_normalise_mime("", source.name),
        actor=actor,
        channel_id=channel_id,
        message_id=message_id,
    )


def process_source(
    practice_dir: str | Path,
    source_id: str,
    *,
    force_ocr: bool = False,
) -> IntakeResult:
    """Extract locally, write page-aware text, and replace derived index rows."""
    root = Path(practice_dir)
    manifest_path = root / "documents" / "manifests" / f"{source_id}.json"
    if not manifest_path.is_file():
        return IntakeResult("Failed", source_id, source_id, "manifest not found")
    with file_lock(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "Ready" and not force_ocr:
            return IntakeResult("Ready", source_id, manifest["filename"], "already processed", manifest)
        manifest["status"] = "Reading"
        atomic_write_json(manifest_path, manifest, indent=2)
        try:
            original = _resolve_original(root, manifest)
            mime = manifest["mime"]
            if mime in {"application/zip", "application/x-zip-compressed"}:
                inventory = _inspect_archive(original)
                manifest["archive_inventory"] = inventory
                manifest["status"] = "Stored"
                manifest["detail"] = "archive stored and inventoried; specialist review required"
                atomic_write_json(manifest_path, manifest, indent=2)
                return IntakeResult("Stored", source_id, manifest["filename"], manifest["detail"], manifest)
            if not _allowed_mime(mime):
                manifest["status"] = "Needs review"
                manifest["detail"] = f"stored safely; no local processor for {mime}"
                atomic_write_json(manifest_path, manifest, indent=2)
                return IntakeResult(
                    "Needs review",
                    source_id,
                    manifest["filename"],
                    manifest["detail"],
                    manifest,
                )

            pages, method = _extract_pages(
                original,
                mime,
                force_ocr=force_ocr or bool(manifest.get("force_ocr")),
            )
            extracts = []
            extract_root = root / "documents" / "extracts" / source_id
            for page in pages:
                relative = (
                    Path("documents")
                    / "extracts"
                    / source_id
                    / f"page-{page['page']:04d}.txt"
                )
                atomic_write_text(root / relative, page["text"])
                extracts.append(
                    {
                        "page": page["page"],
                        "path": str(relative),
                        "method": page["method"],
                        "confidence": page.get("confidence"),
                        "needs_review": page.get("needs_review", False),
                    }
                )
            manifest["extracts"] = extracts
            manifest["processor"] = method
            fingerprint = _content_fingerprint(
                "\n".join(page["text"] for page in pages)
            )
            manifest["content_fingerprint"] = fingerprint
            likely = next(
                (
                    row["source_id"]
                    for row in load_manifests(root)
                    if row.get("source_id") != source_id
                    and fingerprint
                    and row.get("content_fingerprint") == fingerprint
                ),
                None,
            )
            if likely:
                manifest["likely_duplicate_of"] = likely
            manifest["status"] = (
                "Needs review"
                if likely or any(item["needs_review"] for item in extracts)
                else "Ready"
            )
            manifest["detail"] = f"{len(extracts)} page(s) extracted locally"
            if likely:
                manifest["detail"] += f"; likely duplicate of source:{likely}"
            atomic_write_json(manifest_path, manifest, indent=2)
            from practice_corpus import replace_source

            indexed = replace_source(
                root,
                {**manifest, "manifest_path": str(manifest_path.relative_to(root))},
                [(page["page"], page["text"]) for page in pages if page["text"].strip()],
            )
            manifest["indexed_chunks"] = indexed
            atomic_write_json(manifest_path, manifest, indent=2)
            return IntakeResult(
                manifest["status"], source_id, manifest["filename"], manifest["detail"], manifest
            )
        except Exception as exc:
            manifest["status"] = "Failed"
            manifest["detail"] = f"{type(exc).__name__}: {exc}"
            atomic_write_json(manifest_path, manifest, indent=2)
            return IntakeResult("Failed", source_id, manifest["filename"], manifest["detail"], manifest)


def load_manifests(practice_dir: str | Path) -> list[dict]:
    root = Path(practice_dir)
    rows = []
    for path in sorted((root / "documents" / "manifests").glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            row["manifest_path"] = str(path.relative_to(root))
            rows.append(row)
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def _register_temp(
    practice_dir: str | Path,
    temp: Path,
    *,
    filename: str,
    mime: str,
    actor: str,
    channel_id: int | str,
    message_id: int | str,
) -> IntakeResult:
    sha = _sha256(temp)
    root = Path(practice_dir)
    manifest_path = root / "documents" / "manifests" / f"{sha[:16]}.json"
    with file_lock(manifest_path):
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return IntakeResult("Duplicate", manifest["source_id"], filename, "exact SHA-256 duplicate", manifest)
        original = root / "documents" / "sources" / sha / "original" / filename
        original.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp, original)
        original.chmod(0o444)
        return _write_manifest(
            root,
            sha,
            filename,
            mime,
            actor,
            channel_id,
            message_id,
            original_path=str(original.relative_to(root)),
            immutable_copy=True,
        )


def _register_external(
    practice_dir: str | Path,
    source: Path,
    *,
    sha: str,
    filename: str,
    mime: str,
    actor: str,
    channel_id: int | str,
    message_id: int | str,
) -> IntakeResult:
    root = Path(practice_dir)
    manifest_path = root / "documents" / "manifests" / f"{sha[:16]}.json"
    with file_lock(manifest_path):
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return IntakeResult("Duplicate", manifest["source_id"], filename, "exact SHA-256 duplicate", manifest)
        return _write_manifest(
            root,
            sha,
            filename,
            mime,
            actor,
            channel_id,
            message_id,
            original_path=str(source.resolve()),
            immutable_copy=False,
        )


def _write_manifest(
    root: Path,
    sha: str,
    filename: str,
    mime: str,
    actor: str,
    channel_id: int | str,
    message_id: int | str,
    *,
    original_path: str,
    immutable_copy: bool,
) -> IntakeResult:
    source_id = sha[:16]
    manifest_path = root / "documents" / "manifests" / f"{source_id}.json"
    manifest = {
        "schema": 1,
        "source_id": source_id,
        "sha256": sha,
        "filename": filename,
        "mime": mime,
        "size": Path(original_path).stat().st_size if os.path.isabs(original_path) else (root / original_path).stat().st_size,
        "original_path": original_path,
        "immutable_copy": immutable_copy,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "channel_id": str(channel_id),
        "message_id": str(message_id),
        "status": "Saved",
        "detail": "immutable original saved" if immutable_copy else "existing original registered in place",
        "extracts": [],
    }
    atomic_write_json(manifest_path, manifest, indent=2)
    manifest["manifest_path"] = str(manifest_path.relative_to(root))
    return IntakeResult("Saved", source_id, filename, manifest["detail"], manifest)


def _extract_pages(
    path: Path, mime: str, *, force_ocr: bool = False
) -> tuple[list[dict], str]:
    if mime.startswith("text/") or mime == "application/json":
        text = path.read_text(encoding="utf-8", errors="replace")
        return [{"page": 1, "text": text, "method": "native_text", "confidence": 1.0}], "native_text"
    if mime == "application/pdf":
        return _extract_pdf(path, force_ocr=force_ocr)
    if mime.startswith("image/"):
        return [_ocr_image(path.read_bytes(), page=1)], "tesseract"
    raise ValueError(f"no local processor for {mime}")


def _native_text_usable(text: str) -> bool:
    """False when a scan left a spaced-out or empty text layer.

    Length alone is not enough: phone-scan PDFs often carry 40+ characters
    of broken OCR that would otherwise skip Tesseract.
    """
    body = (text or "").strip()
    if len(body) < 40:
        return False
    tokens = re.findall(r"\S+", body)
    if not tokens:
        return False
    letters = sum(1 for char in body if char.isalpha())
    if letters < 24:
        return False
    singles = 0
    for token in tokens:
        core = re.sub(r"[^\w]", "", token, flags=re.UNICODE)
        if len(core) <= 1:
            singles += 1
    return (singles / len(tokens)) <= 0.35


def _extract_pdf(path: Path, *, force_ocr: bool = False) -> tuple[list[dict], str]:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is unavailable") from exc
    document = fitz.open(path)
    if document.page_count > MAX_PDF_PAGES:
        raise ValueError(f"PDF has {document.page_count} pages; limit is {MAX_PDF_PAGES}")
    rows = []
    used_ocr = False
    for number, page in enumerate(document, start=1):
        native = page.get_text("text").strip()
        if not force_ocr and _native_text_usable(native):
            rows.append(
                {
                    "page": number,
                    "text": native,
                    "method": "native_text",
                    "confidence": 1.0,
                    "needs_review": False,
                }
            )
            continue
        matrix = fitz.Matrix(2, 2)
        pixels = int(page.rect.width * 2) * int(page.rect.height * 2)
        if pixels > MAX_IMAGE_PIXELS:
            raise ValueError(f"rendered page {number} exceeds pixel limit")
        image = page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")
        rows.append(_ocr_image(image, page=number))
        used_ocr = True
    document.close()
    return rows, "native_text+tesseract" if used_ocr else "native_text"


def _ocr_image(data: bytes, *, page: int) -> dict:
    ready = processor_readiness()
    if not ready["health_ocr"]:
        raise RuntimeError("local OCR unavailable: " + ", ".join(ready["missing"]))
    try:
        import pymupdf

        pixmap = pymupdf.Pixmap(data)
        if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
            raise ValueError(f"image page {page} exceeds pixel limit")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"image page {page} is unreadable") from exc
    binary = _tesseract_path()
    result = subprocess.run(
        [binary, "stdin", "stdout", "-l", OCR_LANGUAGES, "tsv"],
        input=data,
        capture_output=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[:500])
    text, confidence = _tsv_text_and_confidence(
        result.stdout.decode("utf-8", errors="replace")
    )
    return {
        "page": page,
        "text": text,
        "method": "tesseract",
        "confidence": confidence,
        "needs_review": confidence is None or confidence < 80.0,
    }


def _tsv_text_and_confidence(raw: str) -> tuple[str, float | None]:
    words = []
    scores = []
    # Tesseract TSV is not a quoted CSV. A " from a lab-sheet graphic
    # must stay a character; default csv quoting swallows the next rows.
    reader = csv.DictReader(
        io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    current_line = None
    for row in reader:
        word = (row.get("text") or "").strip()
        if not word:
            continue
        line_key = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
        if words and line_key != current_line:
            words.append("\n")
        words.append(word)
        current_line = line_key
        try:
            score = float(row.get("conf") or -1)
            if score >= 0:
                scores.append(score)
        except ValueError:
            pass
    text = " ".join(words).replace(" \n ", "\n").strip()
    return text, (round(sum(scores) / len(scores), 2) if scores else None)


def _inspect_archive(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("archive member limit exceeded")
        expanded = sum(item.file_size for item in members)
        compressed = max(1, sum(item.compress_size for item in members))
        if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
            raise ValueError("archive expanded-size limit exceeded")
        if expanded / compressed > MAX_ARCHIVE_RATIO:
            raise ValueError("archive compression-ratio limit exceeded")
        for item in members:
            candidate = Path(item.filename)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError("archive contains an unsafe path")
        return {
            "members": len(members),
            "expanded_bytes": expanded,
            "compressed_bytes": compressed,
            "filenames": [item.filename for item in members[:100]],
        }


def _resolve_original(root: Path, manifest: dict) -> Path:
    raw = Path(manifest["original_path"])
    return raw if raw.is_absolute() else root / raw


def _allowed_mime(mime: str) -> bool:
    return mime in ALLOWED_MIMES or mime.startswith(ALLOWED_MIME_PREFIXES)


def _normalise_mime(content_type: str | None, filename: str) -> str:
    supplied = str(content_type or "").split(";", 1)[0].strip().lower()
    if supplied and supplied != "application/octet-stream":
        return supplied
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _safe_filename(filename: str) -> str:
    name = Path(filename or "attachment").name
    name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name).strip(" .")
    return name[:180] or "attachment"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_fingerprint(text: str) -> str | None:
    normalized = " ".join(
        re.findall(r"[\wÀ-ÖØ-öø-ÿ.,/%+-]+", (text or "").casefold())
    )
    if len(normalized) < 40:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _tesseract_path() -> str | None:
    """Find Homebrew OCR even under launchd's intentionally small PATH."""
    discovered = shutil.which("tesseract")
    if discovered:
        return discovered
    for candidate in (
        Path("/opt/homebrew/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
