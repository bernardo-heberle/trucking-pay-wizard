"""Unit tests for src.extract.extractor."""

from __future__ import annotations

from src.extract.extractor import extract_document
from src.ocr.models import OcrResult


class TestSettlementExtraction:
    """Extraction against settlement_ocr.json fixture."""

    def test_gross_pay_extracted(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=1)
        field = _field_by_name(result.fields, "gross_pay")
        assert field is not None
        assert field.value == "750.00"

    def test_delivery_date_extracted(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=1)
        field = _field_by_name(result.fields, "delivery_date")
        assert field is not None
        assert field.value == "03/12/2024"

    def test_source_document_populated(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=1)
        for field in result.fields:
            assert field.source_document == "settlement.pdf"

    def test_bounding_boxes_resolved(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=1)
        for field in result.fields:
            assert len(field.source_spans) >= 1
            for span in field.source_spans:
                assert span.bounding_box.width > 0
                assert span.bounding_box.height > 0


class TestPaySummaryExtraction:
    """Extraction against pay_summary_ocr.json fixture (V2Dispatch-style)."""

    def test_gross_pay_extracted(self, pay_summary_ocr: OcrResult) -> None:
        result = extract_document(pay_summary_ocr, page_count=1)
        field = _field_by_name(result.fields, "gross_pay")
        assert field is not None
        assert field.value == "820"

    def test_delivery_date_extracted(self, pay_summary_ocr: OcrResult) -> None:
        result = extract_document(pay_summary_ocr, page_count=1)
        field = _field_by_name(result.fields, "delivery_date")
        assert field is not None
        assert field.value == "March 20, 2024"

    def test_multiline_spans_resolved(self, pay_summary_ocr: OcrResult) -> None:
        """The gross-pay pattern spans two lines; both should be in source_spans."""
        result = extract_document(pay_summary_ocr, page_count=1)
        field = _field_by_name(result.fields, "gross_pay")
        assert field is not None
        assert len(field.source_spans) == 2


class TestEdgeCases:

    def test_empty_ocr_produces_no_fields(self, empty_ocr: OcrResult) -> None:
        result = extract_document(empty_ocr, page_count=1)
        assert result.fields == []

    def test_first_match_wins(self, ambiguous_ocr: OcrResult) -> None:
        """When multiple gross-pay patterns could match, the first one wins."""
        result = extract_document(ambiguous_ocr, page_count=1)
        field = _field_by_name(result.fields, "gross_pay")
        assert field is not None
        assert field.value == "750.00"

    def test_content_hash_preserved(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=1)
        assert result.content_hash == settlement_ocr.content_hash

    def test_page_count_preserved(self, settlement_ocr: OcrResult) -> None:
        result = extract_document(settlement_ocr, page_count=3)
        assert result.page_count == 3


def _field_by_name(fields, name: str):
    return next((f for f in fields if f.name == name), None)
