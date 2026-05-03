"""Fixtures for report unit tests."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import (
    Certainty,
    DocumentExtractionResult,
    ExtractedField,
    ExtractedLoad,
    SourceSpan,
)
from src.ocr.models import BoundingBox


@pytest.fixture()
def synthetic_source_pdf(tmp_path: Path) -> Path:
    """A single-page PDF with known text, for the PDF builder to embed."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Settlement Statement \u2014 synthetic source")
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
        page.insert_text((72, 72), f"Source B \u2014 page {i + 1}")
    path = tmp_path / "source_b.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def synthetic_source_pdf_long(tmp_path: Path) -> Path:
    """A 10-page PDF for page-truncation tests."""
    doc = fitz.open()
    for i in range(10):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"Long doc \u2014 page {i + 1}")
    path = tmp_path / "source_long.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _default_pay(source_path: Path) -> ExtractedField:
    return ExtractedField(
        name="pay",
        value="750.00",
        source_document=source_path.name,
        source_page=1,
        source_spans=[
            SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25)),
        ],
        certainty=Certainty.HIGH,
    )


def _default_date(source_path: Path) -> ExtractedField:
    return ExtractedField(
        name="date",
        value="03/12/2024",
        source_document=source_path.name,
        source_page=1,
        source_spans=[
            SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25)),
        ],
        certainty=Certainty.HIGH,
    )


def make_extraction_result(
    source_path: Path,
    *,
    page_count: int = 1,
    content_hash: str = "abc123",
    fields: list[ExtractedField] | None = None,
    loads: list[ExtractedLoad] | None = None,
) -> DocumentExtractionResult:
    """Build a ``DocumentExtractionResult`` with the new loads-based shape.

    Tests may pass either:

    * ``loads=`` — a fully-formed list of ``ExtractedLoad`` objects, used
      directly.  This is the primary way to build multi-load results.
    * ``fields=`` — a backwards-compatibility convenience that picks the
      ``pay`` and ``date`` fields by name and packages them as a single load.
      Any other named fields in the list are ignored (the new schema only
      models pay and date per load).
    * Neither — a default single load with HIGH-certainty pay=$750.00 and
      date=03/12/2024 is created.
    """
    if loads is None:
        if fields is None:
            fields = [_default_pay(source_path), _default_date(source_path)]
        pay = next((f for f in fields if f.name == "pay"), None)
        date = next((f for f in fields if f.name == "date"), None)
        loads = [ExtractedLoad(index=1, pay=pay, date=date)]

    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        loads=loads,
        page_count=page_count,
    )


def make_load(
    source_path: Path,
    *,
    index: int = 1,
    pay_value: str | None = "750.00",
    pay_certainty: Certainty = Certainty.HIGH,
    pay_page: int = 1,
    date_value: str | None = "03/12/2024",
    date_certainty: Certainty = Certainty.HIGH,
    date_page: int = 1,
) -> ExtractedLoad:
    """Build a single ``ExtractedLoad`` with sensible defaults.

    Pass ``pay_value=None`` or ``date_value=None`` to omit a field.  ``*_page``
    controls the ``source_page`` and ``source_spans[0].page_number`` for the
    field — useful for testing per-load page resolution in reports.
    """
    pay = (
        ExtractedField(
            name="pay",
            value=pay_value,
            source_document=source_path.name,
            source_page=pay_page,
            source_spans=[
                SourceSpan(
                    page_number=pay_page,
                    bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25),
                ),
            ],
            certainty=pay_certainty,
        )
        if pay_value is not None
        else None
    )
    date = (
        ExtractedField(
            name="date",
            value=date_value,
            source_document=source_path.name,
            source_page=date_page,
            source_spans=[
                SourceSpan(
                    page_number=date_page,
                    bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25),
                ),
            ],
            certainty=date_certainty,
        )
        if date_value is not None
        else None
    )
    return ExtractedLoad(index=index, pay=pay, date=date)
