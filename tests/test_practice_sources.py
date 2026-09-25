"""Immutable source intake, local processing, and corpus retrieval."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from practice_corpus import read_page, rebuild, search
from practice_sources import (
    SOURCE_MAX_BYTES,
    _extract_pdf,
    _native_text_usable,
    _tsv_text_and_confidence,
    intake_attachment,
    intake_file,
    process_source,
)


class FakeAttachment:
    def __init__(self, filename: str, data: bytes, mime: str):
        self.filename = filename
        self.data = data
        self.size = len(data)
        self.content_type = mime

    async def save(self, path):
        with Path(path).open("wb") as handle:
            for start in range(0, len(self.data), 1024 * 1024):
                handle.write(self.data[start : start + 1024 * 1024])


class SourceIntakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_streaming_limit_is_separate_from_twenty_mb_prompt_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = b"x" * (20 * 1024 * 1024 + 450_000)
            attachment = FakeAttachment("charite.pdf", data, "application/pdf")
            result = await intake_attachment(
                tmp, attachment, actor="partner", channel_id=7, message_id=9
            )
            self.assertEqual(result.status, "Saved")
            original = Path(tmp) / result.manifest["original_path"]
            self.assertEqual(original.stat().st_size, len(data))
            self.assertEqual(original.stat().st_mode & 0o777, 0o444)

    async def test_exact_duplicate_reuses_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attachment = FakeAttachment("lab.txt", b"Ferritin 21 ng/mL", "text/plain")
            first = await intake_attachment(
                tmp, attachment, actor="partner", channel_id=7, message_id=1
            )
            second = await intake_attachment(
                tmp, attachment, actor="partner", channel_id=7, message_id=2
            )
            self.assertEqual(first.status, "Saved")
            self.assertEqual(second.status, "Duplicate")
            self.assertEqual(first.source_id, second.source_id)
            self.assertEqual(
                len(list((Path(tmp) / "documents" / "manifests").glob("*.json"))), 1
            )

    async def test_declared_oversize_fails_before_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attachment = FakeAttachment("huge.pdf", b"x", "application/pdf")
            attachment.size = SOURCE_MAX_BYTES + 1
            with patch.object(attachment, "save") as save:
                result = await intake_attachment(
                    tmp, attachment, actor="partner", channel_id=7, message_id=1
                )
            self.assertEqual(result.status, "Needs review")
            save.assert_not_called()

    async def test_unsupported_type_is_still_saved_but_not_processed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attachment = FakeAttachment(
                "specialist.bin", b"\x00\x01private", "application/octet-stream"
            )
            saved = await intake_attachment(
                tmp, attachment, actor="partner", channel_id=7, message_id=1
            )
            self.assertEqual(saved.status, "Saved")
            processed = process_source(tmp, saved.source_id)
            self.assertEqual(processed.status, "Needs review")
            self.assertTrue(
                (Path(tmp) / saved.manifest["original_path"]).is_file()
            )


class ProcessingAndRetrievalTests(unittest.TestCase):
    def test_text_source_processes_and_searches_with_page_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "lab.txt"
            source.write_text("Ferritin measured at 21 ng/mL on 3 May.", encoding="utf-8")
            saved = intake_file(tmp, source, actor="migration")
            processed = process_source(tmp, saved.source_id)
            self.assertEqual(processed.status, "Ready")
            rows = search(tmp, "Ferritin")
            self.assertEqual(len(rows), 1)
            self.assertIn("p. 1", rows[0]["citation"])
            page = read_page(tmp, saved.source_id, 1)
            self.assertIn("21 ng/mL", page["text"])

    def test_unsafe_archive_is_stored_but_processing_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../escape.txt", "no")
            saved = intake_file(tmp, archive, actor="migration")
            processed = process_source(tmp, saved.source_id)
            self.assertEqual(processed.status, "Failed")
            self.assertIn("unsafe path", processed.detail)
            self.assertFalse((Path(tmp).parent / "escape.txt").exists())

    def test_spaced_scan_layer_is_not_usable_native_text(self) -> None:
        garbage = (
            "CFI ARITE\n"
            "C h o r i t d - 1 3 3 5 3 B e r I i n I CVK lnnere Medizin\n"
            "Frou Patient Name Morkstr.2\n"
            "lnstitut f0r medizinische lmmunologie\n"
        )
        self.assertFalse(_native_text_usable(garbage))
        self.assertFalse(_native_text_usable("short"))
        self.assertTrue(
            _native_text_usable(
                "Ferritin measured at 21 ng/mL on 3 May. The clinic letter "
                "names the next appointment and the open questions."
            )
        )

    def test_tesseract_tsv_quote_does_not_swallow_following_rows(self) -> None:
        raw = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num"
            "\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t10\t20\t10\t96.0\tNatrium\n"
            '5\t1\t1\t1\t1\t2\t40\t10\t8\t10\t44.1\t"\n'
            "5\t1\t1\t1\t2\t1\t10\t30\t20\t10\t95.0\tKalium\n"
            "5\t1\t1\t1\t2\t2\t40\t30\t8\t10\t60.5\t3.5\n"
        )
        text, confidence = _tsv_text_and_confidence(raw)
        self.assertEqual(text, 'Natrium "\nKalium 3.5')
        self.assertNotIn("\t", text)
        self.assertAlmostEqual(confidence, 73.9)

    def test_unusable_native_pdf_layer_falls_through_to_ocr(self) -> None:
        try:
            import pymupdf
        except ImportError:
            self.skipTest("PyMuPDF missing")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text(
                (72, 72),
                "C h o r i t d   F r o u   P a t i e n t   l n n e r e",
            )
            doc.save(path)
            doc.close()
            with patch(
                "practice_sources._ocr_image",
                return_value={
                    "page": 1,
                    "text": "Charité Immundefekt-Ambulanz",
                    "method": "tesseract",
                    "confidence": 90.0,
                    "needs_review": False,
                },
            ) as ocr:
                rows, method = _extract_pdf(path)
            ocr.assert_called_once()
            self.assertEqual(method, "native_text+tesseract")
            self.assertEqual(rows[0]["text"], "Charité Immundefekt-Ambulanz")
            self.assertEqual(rows[0]["method"], "tesseract")

    def test_derived_index_can_be_deleted_and_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "note.txt"
            source.write_text("Kopfschmerzen on Tuesday", encoding="utf-8")
            saved = intake_file(tmp, source, actor="migration")
            processed = process_source(tmp, saved.source_id)
            manifest = processed.manifest
            report = rebuild(tmp, [manifest])
            self.assertEqual(report["sources"], 1)
            self.assertTrue(search(tmp, "Kopfschmerzen"))


if __name__ == "__main__":
    unittest.main()
