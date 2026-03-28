"""Unit tests for the income document extraction schema."""

from __future__ import annotations

import os

from src.extract.llm.schemas.income import IncomeDocumentSchema
from src.extract.models import Certainty


def _ensure_defaults() -> None:
    """Set env defaults so load_settings() works without a .env file."""
    os.environ.setdefault("EXTRACTION_MODE", "rules")
    os.environ.setdefault("CONFIDENCE_HIGH_THRESHOLD", "0.9")
    os.environ.setdefault("CONFIDENCE_REVIEW_THRESHOLD", "0.6")


class TestToolDefinition:

    def test_has_required_keys(self) -> None:
        schema = IncomeDocumentSchema()
        defn = schema.tool_definition()
        assert "name" in defn
        assert "description" in defn
        assert "input_schema" in defn

    def test_input_schema_requires_pay_and_date(self) -> None:
        schema = IncomeDocumentSchema()
        props = schema.tool_definition()["input_schema"]["properties"]
        assert "pay" in props
        assert "date" in props

    def test_name_is_income(self) -> None:
        assert IncomeDocumentSchema().name == "income"


class TestParseToolResult:

    def setup_method(self) -> None:
        _ensure_defaults()
        self.schema = IncomeDocumentSchema()

    def test_both_fields_parsed(self) -> None:
        tool_input = {
            "pay": {"value": "750.00", "confidence": 0.95},
            "date": {"value": "03/12/2024", "confidence": 0.92},
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert len(fields) == 2
        names = {f.name for f in fields}
        assert names == {"pay", "date"}

    def test_high_confidence_maps_to_high_certainty(self) -> None:
        tool_input = {
            "pay": {"value": "750.00", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert len(fields) == 1
        assert fields[0].certainty == Certainty.HIGH
        assert fields[0].confidence == 0.95

    def test_medium_confidence_maps_to_review(self) -> None:
        tool_input = {
            "pay": {"value": "750.00", "confidence": 0.7},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].certainty == Certainty.REVIEW

    def test_low_confidence_maps_to_not_found(self) -> None:
        tool_input = {
            "pay": {"value": "750.00", "confidence": 0.3},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].certainty == Certainty.NOT_FOUND

    def test_null_field_produces_no_entry(self) -> None:
        tool_input = {"pay": None, "date": None}
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields == []

    def test_empty_value_produces_no_entry(self) -> None:
        tool_input = {
            "pay": {"value": "", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields == []

    def test_source_document_preserved(self) -> None:
        tool_input = {
            "pay": {"value": "100", "confidence": 0.99},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="settlement.pdf")
        assert fields[0].source_document == "settlement.pdf"

    def test_source_page_is_none_for_llm(self) -> None:
        tool_input = {
            "pay": {"value": "100", "confidence": 0.99},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].source_page is None
