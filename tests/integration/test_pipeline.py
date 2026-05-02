"""Integration test: Ingest -> mocked OCR -> mocked LLM Extract -> Report.

Exercises the full pipeline with synthetic PDF documents and a mocked Azure
client and mocked Anthropic client, verifying that extracted values flow
correctly through all stages and appear in the final Excel and combined PDF
outputs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz
import openpyxl
import pytest

from src.extract.llm.extractor import LlmExtractor
from src.extract.models import Certainty, ExtractedField
from src.ingest import ingest_document
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult
from src.report import build_report


def _make_synthetic_pdf(path: Path, text_lines: list[tuple[str, float]]) -> None:
    """Create a single-page PDF with *text_lines* at specified y positions."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for text, y in text_lines:
        page.insert_text((72, y), text)
    doc.save(str(path))
    doc.close()


def _build_mock_ocr_result(source_path: Path, content_hash: str) -> OcrResult:
    """Build a canned OcrResult for use with the mocked extractor."""
    lines_text = [
        "Settlement Statement",
        "Order ID: BSAT1066",
        "Total Payment to Carrier: $1,200.50",
        "Pickup Exactly: 05/15/2024",
    ]
    lines: list[OcrLine] = []
    offset = 0
    for i, text in enumerate(lines_text):
        start = offset
        end = offset + len(text)
        lines.append(
            OcrLine(
                text=text,
                page_number=1,
                bounding_box=BoundingBox(x=1.0, y=0.5 + i * 1.5, width=4.0, height=0.25),
                char_start=start,
                char_end=end,
            )
        )
        offset = end + (1 if i < len(lines_text) - 1 else 0)

    return OcrResult(
        source_path=source_path,
        content_hash=content_hash,
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=len(lines))],
        lines=lines,
    )


def _make_extraction_result(source_path: Path, content_hash: str, page_count: int):
    """Build a canned DocumentExtractionResult as if returned by LlmExtractor."""
    from src.extract.models import DocumentExtractionResult, SourceSpan
    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        page_count=page_count,
        fields=[
            ExtractedField(
                name="pay",
                value="1,200.50",
                source_document=source_path.name,
                source_page=1,
                source_spans=[SourceSpan(
                    page_number=1,
                    bounding_box=BoundingBox(x=1.0, y=2.0, width=4.0, height=0.25),
                )],
                certainty=Certainty.HIGH,
                confidence=0.97,
            ),
            ExtractedField(
                name="date",
                value="05/15/2024",
                source_document=source_path.name,
                source_page=1,
                source_spans=[SourceSpan(
                    page_number=1,
                    bounding_box=BoundingBox(x=1.0, y=3.5, width=3.5, height=0.25),
                )],
                certainty=Certainty.HIGH,
                confidence=0.95,
            ),
        ],
    )


class TestFullPipeline:

    def test_end_to_end(self, tmp_path: Path) -> None:
        # 1. Create a synthetic source PDF
        source = tmp_path / "test_settlement.pdf"
        _make_synthetic_pdf(source, [
            ("Settlement Statement", 72),
            ("Total Payment to Carrier: $1,200.50", 200),
            ("Pickup Exactly: 05/15/2024", 320),
        ])

        # 2. Ingest
        ingested = ingest_document(source)
        assert ingested.page_count >= 1

        # 3. Build a mock OCR result (bypassing Azure)
        ocr_result = _build_mock_ocr_result(source, ingested.content_hash)

        # 4. Extract using a mocked LlmExtractor
        canned = _make_extraction_result(source, ingested.content_hash, ingested.page_count)
        mock_extractor = MagicMock(spec=LlmExtractor)
        mock_extractor.extract.return_value = canned

        extraction = mock_extractor.extract(ocr_result, page_count=ingested.page_count)
        field_names = {f.name for f in extraction.fields}
        assert "pay" in field_names
        assert "date" in field_names

        pay = next(f for f in extraction.fields if f.name == "pay")
        assert pay.value == "1,200.50"
        assert pay.certainty == Certainty.HIGH

        date = next(f for f in extraction.fields if f.name == "date")
        assert date.value == "05/15/2024"
        assert date.certainty == Certainty.HIGH

        # 5. Report assembly
        output_dir = tmp_path / "output"
        pdf_path, excel_path = build_report([extraction], output_dir)

        assert pdf_path.exists()
        assert excel_path.exists()

        # Verify PDF page count: 1 index + 1 source page
        combined = fitz.open(str(pdf_path))
        assert len(combined) == 1 + ingested.page_count

        # Verify highlight annotations on source page(s)
        source_page = combined[1]
        annots = list(source_page.annots() or [])
        assert len(annots) >= 1
        combined.close()

        # Verify Excel values
        wb = openpyxl.load_workbook(str(excel_path))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        assert ws.cell(row=2, column=header_map["Pay"]).value == "1,200.50"
        assert ws.cell(row=2, column=header_map["Date"]).value == "05/15/2024"
        assert ws.cell(row=2, column=header_map["PDF Page"]).value == 2

        assert "Certainty" in header_map
        assert ws.cell(row=2, column=header_map["Certainty"]).value == "High"

    def test_multiple_documents(self, tmp_path: Path) -> None:
        """Verify the pipeline handles multiple documents correctly."""
        from src.extract.models import DocumentExtractionResult, SourceSpan

        extractions = []

        for idx, (pay, date) in enumerate([("500.00", "01/01/2024"), ("900.00", "06/30/2024")]):
            src = tmp_path / f"doc_{idx}.pdf"
            _make_synthetic_pdf(src, [
                ("Settlement", 72),
                (f"Total Payment to Carrier: ${pay}", 200),
                (f"Pickup Exactly: {date}", 320),
            ])

            ingested = ingest_document(src)
            canned = DocumentExtractionResult(
                source_path=src,
                content_hash=ingested.content_hash,
                page_count=1,
                fields=[
                    ExtractedField(
                        name="pay",
                        value=pay,
                        source_document=src.name,
                        source_page=1,
                        source_spans=[SourceSpan(
                            page_number=1,
                            bounding_box=BoundingBox(x=1.0, y=2.0, width=4.0, height=0.25),
                        )],
                        certainty=Certainty.HIGH,
                        confidence=0.95,
                    ),
                    ExtractedField(
                        name="date",
                        value=date,
                        source_document=src.name,
                        source_page=1,
                        source_spans=[SourceSpan(
                            page_number=1,
                            bounding_box=BoundingBox(x=1.0, y=3.5, width=3.5, height=0.25),
                        )],
                        certainty=Certainty.HIGH,
                        confidence=0.95,
                    ),
                ],
            )
            extractions.append(canned)

        output_dir = tmp_path / "output"
        pdf_path, excel_path = build_report(extractions, output_dir)

        combined = fitz.open(str(pdf_path))
        assert len(combined) == 3  # 1 index + 2 source pages
        combined.close()

        wb = openpyxl.load_workbook(str(excel_path))
        ws = wb.active
        assert ws.max_row == 3  # header + 2 data rows
