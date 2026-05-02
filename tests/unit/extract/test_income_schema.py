"""Unit tests for the income document extraction schema."""

from __future__ import annotations

import os
from decimal import Decimal

from hypothesis import given, settings as h_settings, strategies as st

from src.extract.llm.schemas.income import IncomeDocumentSchema, _normalize_pay_value
from src.extract.models import Certainty


def _ensure_defaults() -> None:
    """Set env defaults so load_settings() works without a .env file."""
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

    def test_dollar_sign_and_commas_stripped_from_pay(self) -> None:
        tool_input = {
            "pay": {"value": "$1,500.00", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].value == "1500.00"

    def test_dollar_sign_not_stripped_from_date(self) -> None:
        """Stripping is pay-specific — dates must never be modified."""
        tool_input = {
            "pay": None,
            "date": {"value": "$invalid", "confidence": 0.5},
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].value == "$invalid"

    def test_pay_without_dollar_sign_normalized_to_two_decimals(self) -> None:
        tool_input = {
            "pay": {"value": "820", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].value == "820.00"

    def test_pay_value_description_excludes_currency_symbol(self) -> None:
        defn = self.schema.tool_definition()
        pay_value_desc = defn["input_schema"]["properties"]["pay"]["properties"]["value"]["description"]
        assert "$" not in pay_value_desc

    def test_unparseable_pay_value_caps_certainty_at_review(self) -> None:
        """When the LLM returns a non-numeric pay string, certainty is capped at REVIEW."""
        tool_input = {
            "pay": {"value": "N/A", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert len(fields) == 1
        assert fields[0].certainty == Certainty.REVIEW
        assert fields[0].value == "N/A"

    def test_unparseable_pay_already_at_review_stays_review(self) -> None:
        """Downgrade is idempotent — REVIEW stays REVIEW for unparseable values."""
        tool_input = {
            "pay": {"value": "unknown", "confidence": 0.7},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].certainty == Certainty.REVIEW

    def test_pay_commas_stripped_without_dollar_sign(self) -> None:
        tool_input = {
            "pay": {"value": "1,200.50", "confidence": 0.95},
            "date": None,
        }
        fields = self.schema.parse_tool_result(tool_input, source_document="test.pdf")
        assert fields[0].value == "1200.50"

    def test_pay_prompt_rule_requires_plain_decimal(self) -> None:
        prompt = self.schema.system_prompt()
        assert "no commas" in prompt
        assert "two decimal" in prompt


class TestNormalizePayValue:
    """Unit tests for the _normalize_pay_value helper."""

    def test_plain_decimal_unchanged(self) -> None:
        assert _normalize_pay_value("1234.56") == "1234.56"

    def test_dollar_sign_stripped(self) -> None:
        assert _normalize_pay_value("$1500.00") == "1500.00"

    def test_commas_stripped(self) -> None:
        assert _normalize_pay_value("1,500.00") == "1500.00"

    def test_dollar_and_commas_stripped(self) -> None:
        assert _normalize_pay_value("$1,500.00") == "1500.00"

    def test_integer_gains_two_decimal_places(self) -> None:
        assert _normalize_pay_value("820") == "820.00"

    def test_one_decimal_place_padded(self) -> None:
        assert _normalize_pay_value("0.5") == "0.50"

    def test_zero_is_valid(self) -> None:
        assert _normalize_pay_value("0.00") == "0.00"

    def test_non_numeric_returns_none(self) -> None:
        assert _normalize_pay_value("N/A") is None

    def test_empty_string_returns_none(self) -> None:
        assert _normalize_pay_value("") is None

    def test_negative_value_returns_none(self) -> None:
        assert _normalize_pay_value("-100.00") is None

    def test_whitespace_around_value_stripped(self) -> None:
        assert _normalize_pay_value("  750.00  ") == "750.00"

    def test_alphabetic_with_digits_returns_none(self) -> None:
        assert _normalize_pay_value("abc123") is None


class TestNormalizePayValueProperties:
    """Property-based tests for _normalize_pay_value.

    One good property test replaces dozens of example tests for the
    numeric round-trip and the rejection of negatives.
    """

    @given(
        st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("1000000"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @h_settings(max_examples=500)
    def test_round_trip_for_positive_values(self, d: Decimal) -> None:
        """Any non-negative decimal with 2 d.p. normalizes and round-trips exactly."""
        normalized = _normalize_pay_value(str(d))
        assert normalized is not None, f"Expected non-None for {d}"
        assert Decimal(normalized) == d, (
            f"Round-trip failed: input={d}, normalized={normalized}"
        )

    @given(
        st.decimals(
            max_value=Decimal("-0.01"),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @h_settings(max_examples=200)
    def test_any_negative_returns_none(self, d: Decimal) -> None:
        """Any negative value must return None — never a negative pay string."""
        assert _normalize_pay_value(str(d)) is None, (
            f"Expected None for negative input {d}"
        )
