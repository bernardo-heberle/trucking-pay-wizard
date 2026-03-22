"""Fixtures for report unit tests."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox


@pytest.fixture()
def synthetic_source_pdf(tmp_path: Path) -> Path:
    """A single-page PDF with known text, for the PDF builder to embed."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Settlement Statement — synthetic source")
    path = tmp_path / "source_a.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def synthetic_source_pdf_b(tmp_path: Path) -> Path:
    """A 2-page PDF to test multi-page embedding."""
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"Source B — page {i + 1}")
    path = tmp_path / "source_b.pdf"
    doc.save(str(path))
    doc.close()
    return path


def make_extraction_result(
    source_path: Path,
    *,
    page_count: int = 1,
    content_hash: str = "abc123",
    fields: list[ExtractedField] | None = None,
) -> DocumentExtractionResult:
    """Helper to build a DocumentExtractionResult with sensible defaults."""
    if fields is None:
        fields = [
            ExtractedField(
                name="gross_pay",
                value="750.00",
                source_document=source_path.name,
                source_page=1,
                source_spans=[
                    SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25)),
                ],
            ),
            ExtractedField(
                name="delivery_date",
                value="03/12/2024",
                source_document=source_path.name,
                source_page=1,
                source_spans=[
                    SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25)),
                ],
            ),
        ]
    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        fields=fields,
        page_count=page_count,
    )
