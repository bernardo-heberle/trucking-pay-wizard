"""Unit tests for the income document extraction schema."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.extract.exceptions import MalformedToolResponse
from src.extract.llm.schemas.income import IncomeDocumentSchema, _normalize_pay_value
from src.extract.models import Certainty, ExtractedLoad


def _ensure_defaults() -> None:
    """Set env defaults so load_settings() works without a .env file."""
    os.environ.setdefault("CONFIDENCE_HIGH_THRESHOLD", "0.9")
    os.environ.setdefault("CONFIDENCE_REVIEW_THRESHOLD", "0.6")


def _wrap(pay: object | None = None, date: object | None = None) -> dict:
    """Wrap a single pay/date pair as the new ``{"loads": [{...}]}`` shape."""
    return {"loads": [{"pay": pay, "date": date}]}


class TestToolDefinition:

    def test_has_required_keys(self) -> None:
        schema = IncomeDocumentSchema()
        defn = schema.tool_definition()
        assert "name" in defn
        assert "description" in defn
        assert "input_schema" in defn

    def test_input_schema_requires_loads_array(self) -> None:
        """The new schema returns a top-level ``loads`` array."""
        schema = IncomeDocumentSchema()
        input_schema = schema.tool_definition()["input_schema"]
        assert "loads" in input_schema["properties"]
        assert input_schema["required"] == ["loads"]

    def test_loads_array_items_have_pay_and_date(self) -> None:
        schema = IncomeDocumentSchema()
        item_props = (
            schema.tool_definition()["input_schema"]
            ["properties"]["loads"]["items"]["properties"]
        )
        assert "pay" in item_props
        assert "date" in item_props

    def test_loads_array_requires_at_least_one_entry(self) -> None:
        """``minItems: 1`` keeps the LLM from returning an empty loads list."""
        schema = IncomeDocumentSchema()
        loads_schema = schema.tool_definition()["input_schema"]["properties"]["loads"]
        assert loads_schema.get("minItems") == 1

    def test_name_is_income(self) -> None:
        assert IncomeDocumentSchema().name == "income"


class TestParseToolResult:
    """Single-load tool inputs are parsed into a one-element list of loads."""

    def setup_method(self) -> None:
        _ensure_defaults()
        self.schema = IncomeDocumentSchema()

    def test_returns_list_of_loads(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(
                pay={"value": "750.00", "confidence": 0.95},
                date={"value": "03/12/2024", "confidence": 0.92},
            ),
            source_document="test.pdf",
        )
        assert isinstance(loads, list)
        assert len(loads) == 1
        assert isinstance(loads[0], ExtractedLoad)

    def test_both_fields_populated(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(
                pay={"value": "750.00", "confidence": 0.95},
                date={"value": "03/12/2024", "confidence": 0.92},
            ),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.name == "pay"
        assert loads[0].pay.value == "750.00"
        assert loads[0].date is not None
        assert loads[0].date.name == "date"
        assert loads[0].date.value == "03/12/2024"

    def test_load_index_starts_at_one(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "100", "confidence": 0.99}),
            source_document="test.pdf",
        )
        assert loads[0].index == 1

    def test_high_confidence_maps_to_high_certainty(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "750.00", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.certainty == Certainty.HIGH
        assert loads[0].pay.confidence == 0.95

    def test_medium_confidence_maps_to_review(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "750.00", "confidence": 0.7}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.certainty == Certainty.REVIEW

    def test_low_confidence_maps_to_not_found(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "750.00", "confidence": 0.3}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.certainty == Certainty.NOT_FOUND

    def test_null_fields_produce_load_with_both_none(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay=None, date=None),
            source_document="test.pdf",
        )
        assert len(loads) == 1
        assert loads[0].pay is None
        assert loads[0].date is None

    def test_empty_value_produces_no_field(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is None

    def test_source_document_preserved(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "100", "confidence": 0.99}),
            source_document="settlement.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.source_document == "settlement.pdf"

    def test_source_page_is_none_for_llm(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "100", "confidence": 0.99}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.source_page is None

    def test_raw_pay_value_with_currency_symbol_preserved(self) -> None:
        """The LLM now returns the raw formatted value; the schema must not normalize it."""
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "$1,500.00", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.value == "$1,500.00"

    def test_dollar_sign_not_stripped_from_date(self) -> None:
        """Date values are always returned verbatim \u2014 no modification of any kind."""
        loads = self.schema.parse_tool_result(
            _wrap(date={"value": "$invalid", "confidence": 0.5}),
            source_document="test.pdf",
        )
        assert loads[0].date is not None
        assert loads[0].date.value == "$invalid"

    def test_pay_without_formatting_preserved_as_is(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "820", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.value == "820"

    def test_pay_value_description_includes_currency_symbol(self) -> None:
        defn = self.schema.tool_definition()
        pay_value_desc = (
            defn["input_schema"]["properties"]["loads"]["items"]
            ["properties"]["pay"]["properties"]["value"]["description"]
        )
        assert "$" in pay_value_desc

    def test_unparseable_pay_value_caps_certainty_at_review(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "N/A", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.certainty == Certainty.REVIEW
        assert loads[0].pay.value == "N/A"

    def test_unparseable_pay_already_at_review_stays_review(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "unknown", "confidence": 0.7}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.certainty == Certainty.REVIEW

    def test_pay_commas_preserved_without_dollar_sign(self) -> None:
        loads = self.schema.parse_tool_result(
            _wrap(pay={"value": "1,200.50", "confidence": 0.95}),
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.value == "1,200.50"

    def test_plain_string_pay_accepted_as_review(self) -> None:
        """Haiku quirk: pay returned as a bare string rather than an object.
        Policy: no model confidence score \u2192 confidence=0.0, certainty=REVIEW."""
        loads = self.schema.parse_tool_result(
            {"loads": [{"pay": "1850.00", "date": None}]},
            source_document="test.pdf",
        )
        assert loads[0].pay is not None
        assert loads[0].pay.value == "1850.00"
        assert loads[0].pay.confidence == 0.0
        assert loads[0].pay.certainty == Certainty.REVIEW

    def test_plain_string_date_accepted_as_review(self) -> None:
        loads = self.schema.parse_tool_result(
            {"loads": [{"pay": None, "date": "04/15/2024"}]},
            source_document="test.pdf",
        )
        assert loads[0].date is not None
        assert loads[0].date.value == "04/15/2024"
        assert loads[0].date.confidence == 0.0
        assert loads[0].date.certainty == Certainty.REVIEW

    def test_unexpected_field_type_raises_malformed(self) -> None:
        """A bare number for a field is not recoverable \u2014 must raise."""
        with pytest.raises(MalformedToolResponse):
            self.schema.parse_tool_result(
                {"loads": [{"pay": 1850.0, "date": None}]},
                source_document="test.pdf",
            )

    def test_pay_prompt_rule_requests_raw_text(self) -> None:
        prompt = self.schema.system_prompt()
        assert "exactly as it appears" in prompt

    def test_prompt_explains_multi_load_case(self) -> None:
        """The system prompt must instruct the LLM to return one entry per load."""
        prompt = self.schema.system_prompt().lower()
        assert "load" in prompt
        assert "each load" in prompt or "one entry per" in prompt or "per load" in prompt


class TestParseMultiLoadToolResult:
    """The schema returns one ExtractedLoad per element of the loads array."""

    def setup_method(self) -> None:
        _ensure_defaults()
        self.schema = IncomeDocumentSchema()

    def test_three_load_input_yields_three_loads(self) -> None:
        loads = self.schema.parse_tool_result(
            {
                "loads": [
                    {
                        "pay": {"value": "$1,250.00", "confidence": 0.95},
                        "date": {"value": "03/05/2024", "confidence": 0.95},
                    },
                    {
                        "pay": {"value": "$2,400.00", "confidence": 0.95},
                        "date": {"value": "03/12/2024", "confidence": 0.95},
                    },
                    {
                        "pay": {"value": "$875.50", "confidence": 0.95},
                        "date": {"value": "03/19/2024", "confidence": 0.95},
                    },
                ]
            },
            source_document="settlement.pdf",
        )
        assert [load.index for load in loads] == [1, 2, 3]
        assert [load.pay.value for load in loads] == ["$1,250.00", "$2,400.00", "$875.50"]
        assert [load.date.value for load in loads] == ["03/05/2024", "03/12/2024", "03/19/2024"]

    def test_each_load_carries_its_own_certainty(self) -> None:
        """Per-load confidences must produce per-load certainties."""
        loads = self.schema.parse_tool_result(
            {
                "loads": [
                    {
                        "pay": {"value": "$1,000.00", "confidence": 0.95},  # HIGH
                        "date": {"value": "01/01/2024", "confidence": 0.95},
                    },
                    {
                        "pay": {"value": "$2,000.00", "confidence": 0.7},   # REVIEW
                        "date": {"value": "01/15/2024", "confidence": 0.95},
                    },
                ]
            },
            source_document="settlement.pdf",
        )
        assert loads[0].pay.certainty == Certainty.HIGH
        assert loads[1].pay.certainty == Certainty.REVIEW

    def test_old_flat_shape_wrapped_into_single_load(self) -> None:
        """Backwards compatibility: a top-level pay/date wraps to one load."""
        loads = self.schema.parse_tool_result(
            {
                "pay": {"value": "100.00", "confidence": 0.95},
                "date": {"value": "01/01/2024", "confidence": 0.95},
            },
            source_document="legacy.pdf",
        )
        assert len(loads) == 1
        assert loads[0].pay.value == "100.00"
        assert loads[0].date.value == "01/01/2024"

    def test_missing_loads_key_raises_malformed(self) -> None:
        """No loads key and no flat pay/date \u2014 unrecoverable."""
        with pytest.raises(MalformedToolResponse, match="loads"):
            self.schema.parse_tool_result({}, source_document="test.pdf")

    def test_empty_loads_array_raises_malformed(self) -> None:
        """An empty loads list violates the minItems=1 contract."""
        with pytest.raises(MalformedToolResponse, match="loads"):
            self.schema.parse_tool_result({"loads": []}, source_document="test.pdf")

    def test_loads_as_string_raises_malformed(self) -> None:
        with pytest.raises(MalformedToolResponse, match="loads"):
            self.schema.parse_tool_result({"loads": "not a list"}, source_document="test.pdf")

    def test_load_entry_must_be_dict(self) -> None:
        """A non-dict load entry is not parseable \u2014 must raise."""
        with pytest.raises(MalformedToolResponse, match=r"Load entry"):
            self.schema.parse_tool_result(
                {"loads": [42]},
                source_document="test.pdf",
            )


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
    """Property-based tests for _normalize_pay_value."""

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
        assert _normalize_pay_value(str(d)) is None, (
            f"Expected None for negative input {d}"
        )
