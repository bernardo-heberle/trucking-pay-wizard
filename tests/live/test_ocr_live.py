"""Live OCR tests — real Azure Document Intelligence calls.

Sends a synthetic PDF with known text through Azure and verifies
the returned OCR lines contain the expected content.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.ingest import ingest_document
from src.ocr.analyzer import analyze_document
from tests.live.conftest import needs_azure

pytestmark = needs_azure

_KNOWN_LINES = [
    "Settlement Statement",
    "Total Payment to Carrier: $1,200.50",
    "Pickup Date: 05/15/2024",
]


@pytest.fixture()
def known_text_pdf(tmp_path: Path) -> Path:
    """A single-page PDF containing ``_KNOWN_LINES`` as rendered text."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 100
    for line in _KNOWN_LINES:
        page.insert_text((72, y), line, fontsize=12)
        y += 40
    path = tmp_path / "known_text.pdf"
    doc.save(str(path))
    doc.close()
    return path


class TestAzureOcrSmoke:
    """Basic round-trip: known PDF → Azure → verify lines come back."""

    def test_returns_ocr_result_with_lines(
        self, azure_client, known_text_pdf: Path
    ) -> None:
        ingested = ingest_document(known_text_pdf)

        result = analyze_document(ingested, azure_client, rate_limit_delay=0)

        assert len(result.lines) >= len(_KNOWN_LINES)

    def test_ocr_text_contains_dollar_amount(
        self, azure_client, known_text_pdf: Path
    ) -> None:
        ingested = ingest_document(known_text_pdf)
        result = analyze_document(ingested, azure_client, rate_limit_delay=0)

        full_text = result.full_text
        assert "1,200.50" in full_text or "1200.50" in full_text

    def test_ocr_text_contains_date(
        self, azure_client, known_text_pdf: Path
    ) -> None:
        ingested = ingest_document(known_text_pdf)
        result = analyze_document(ingested, azure_client, rate_limit_delay=0)

        assert "05/15/2024" in result.full_text

    def test_page_dimensions_are_reasonable(
        self, azure_client, known_text_pdf: Path
    ) -> None:
        ingested = ingest_document(known_text_pdf)
        result = analyze_document(ingested, azure_client, rate_limit_delay=0)

        assert len(result.pages) == 1
        page = result.pages[0]
        assert 7.0 < page.width_inches < 10.0
        assert 9.0 < page.height_inches < 13.0

    def test_content_hash_preserved(
        self, azure_client, known_text_pdf: Path
    ) -> None:
        ingested = ingest_document(known_text_pdf)
        result = analyze_document(ingested, azure_client, rate_limit_delay=0)

        assert result.content_hash == ingested.content_hash
