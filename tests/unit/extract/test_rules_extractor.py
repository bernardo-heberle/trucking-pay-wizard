"""Unit tests for RulesExtractor (the class, not the wrapper function)."""

from __future__ import annotations

from src.extract.extractor import RulesExtractor
from src.extract.models import Certainty
from src.ocr.models import OcrResult


class TestRulesExtractorDirect:
    """Verify RulesExtractor works identically to the old extract_document."""

    def test_settlement_extraction(self, settlement_ocr: OcrResult) -> None:
        extractor = RulesExtractor()
        result = extractor.extract(settlement_ocr, page_count=1)
        pay = next((f for f in result.fields if f.name == "pay"), None)
        date = next((f for f in result.fields if f.name == "date"), None)
        assert pay is not None
        assert pay.value == "750.00"
        assert date is not None
        assert date.value == "03/12/2024"

    def test_empty_ocr(self, empty_ocr: OcrResult) -> None:
        extractor = RulesExtractor()
        result = extractor.extract(empty_ocr, page_count=1)
        assert result.fields == []

    def test_provenance_fields_set(self, settlement_ocr: OcrResult) -> None:
        extractor = RulesExtractor()
        result = extractor.extract(settlement_ocr, page_count=1)
        assert result.content_hash == settlement_ocr.content_hash
        assert result.source_path == settlement_ocr.source_path
        for field in result.fields:
            assert field.source_document == settlement_ocr.source_path.name
