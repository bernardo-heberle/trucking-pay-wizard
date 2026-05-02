"""Live end-to-end test — real Azure OCR + real Anthropic extraction.

Sends a synthetic PDF through the full pipeline (ingest → OCR → extraction)
with real API calls and verifies the extracted financial values.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import Certainty
from src.ingest import ingest_document
from src.ocr.analyzer import analyze_document
from tests.live.conftest import needs_anthropic, needs_azure

pytestmark = [needs_azure, needs_anthropic]


@pytest.fixture()
def settlement_pdf(tmp_path: Path) -> Path:
    """A synthetic settlement statement with realistic field layout."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    lines = [
        ("Settlement Statement", 72, 80, 14),
        ("Order ID: BSAT2099", 72, 140, 11),
        ("Carrier: Khan Transport LLC", 72, 170, 11),
        ("Total Payment to Carrier: $1,450.75", 72, 260, 12),
        ("Pickup Exactly: 07/22/2024", 72, 340, 11),
        ("Delivery: Dallas, TX", 72, 380, 11),
    ]
    for text, x, y, size in lines:
        page.insert_text((x, y), text, fontsize=size)

    path = tmp_path / "settlement_live.pdf"
    doc.save(str(path))
    doc.close()
    return path


class TestEndToEndPipeline:
    """Full pipeline: synthetic PDF → real Azure OCR → real Claude extraction."""

    def test_extracts_correct_pay(
        self, azure_client, anthropic_extractor, settlement_pdf: Path
    ) -> None:
        ingested = ingest_document(settlement_pdf)
        ocr = analyze_document(ingested, azure_client, rate_limit_delay=0)
        result = anthropic_extractor.extract(ocr, page_count=ingested.page_count)

        assert result.extraction_error is None

        pay = next((f for f in result.fields if f.name == "pay"), None)
        assert pay is not None, f"No pay field extracted. Fields: {result.fields}"
        assert pay.value == "1450.75"

    def test_extracts_correct_date(
        self, azure_client, anthropic_extractor, settlement_pdf: Path
    ) -> None:
        ingested = ingest_document(settlement_pdf)
        ocr = analyze_document(ingested, azure_client, rate_limit_delay=0)
        result = anthropic_extractor.extract(ocr, page_count=ingested.page_count)

        date = next((f for f in result.fields if f.name == "date"), None)
        assert date is not None, f"No date field extracted. Fields: {result.fields}"
        assert "07/22/2024" in date.value

    def test_pay_verified_as_high_certainty(
        self, azure_client, anthropic_extractor, settlement_pdf: Path
    ) -> None:
        """The pay value appears literally in the OCR text, so pay verification
        should keep certainty at HIGH rather than downgrading to REVIEW."""
        ingested = ingest_document(settlement_pdf)
        ocr = analyze_document(ingested, azure_client, rate_limit_delay=0)
        result = anthropic_extractor.extract(ocr, page_count=ingested.page_count)

        pay = next((f for f in result.fields if f.name == "pay"), None)
        assert pay is not None
        assert pay.certainty == Certainty.HIGH
