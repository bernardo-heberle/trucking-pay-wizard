"""Unit tests for the Certainty enum and per-pattern certainty tagging."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField
from src.extract.rules import EXPECTED_FIELDS
from src.extract.rules import date as date_rules
from src.extract.rules import pay as pay_rules

_VALID_CERTAINTIES = {"high", "review"}


class TestPatternCertaintyKeys:
    """Every pattern dict must include a valid ``certainty`` key."""

    @pytest.mark.parametrize("pattern", pay_rules.PATTERNS, ids=lambda p: p["name"])
    def test_pay_pattern_has_certainty(self, pattern: dict) -> None:
        assert "certainty" in pattern
        assert pattern["certainty"] in _VALID_CERTAINTIES

    @pytest.mark.parametrize("pattern", date_rules.PATTERNS, ids=lambda p: p["name"])
    def test_date_pattern_has_certainty(self, pattern: dict) -> None:
        assert "certainty" in pattern
        assert pattern["certainty"] in _VALID_CERTAINTIES


class TestCertaintyEnum:

    def test_values(self) -> None:
        assert Certainty.HIGH.value == "High"
        assert Certainty.REVIEW.value == "Review"
        assert Certainty.NOT_FOUND.value == "Not Found"

    def test_is_str_subclass(self) -> None:
        assert isinstance(Certainty.HIGH, str)


class TestExpectedFields:

    def test_expected_fields_contains_pay_and_date(self) -> None:
        assert "pay" in EXPECTED_FIELDS
        assert "date" in EXPECTED_FIELDS


class TestOverallCertainty:

    def _make_result(self, fields: list[ExtractedField]) -> DocumentExtractionResult:
        return DocumentExtractionResult(
            source_path=Path("test.pdf"),
            content_hash="0" * 64,
            fields=fields,
            page_count=1,
        )

    def test_all_high(self) -> None:
        fields = [
            ExtractedField(name="pay", value="100", source_document="t.pdf", source_page=1, certainty=Certainty.HIGH),
            ExtractedField(name="date", value="01/01/2024", source_document="t.pdf", source_page=1, certainty=Certainty.HIGH),
        ]
        result = self._make_result(fields)
        assert result.overall_certainty(["pay", "date"]) == Certainty.HIGH

    def test_mixed_returns_review(self) -> None:
        fields = [
            ExtractedField(name="pay", value="100", source_document="t.pdf", source_page=1, certainty=Certainty.HIGH),
            ExtractedField(name="date", value="01/01/2024", source_document="t.pdf", source_page=1, certainty=Certainty.REVIEW),
        ]
        result = self._make_result(fields)
        assert result.overall_certainty(["pay", "date"]) == Certainty.REVIEW

    def test_missing_field_returns_not_found(self) -> None:
        fields = [
            ExtractedField(name="pay", value="100", source_document="t.pdf", source_page=1, certainty=Certainty.HIGH),
        ]
        result = self._make_result(fields)
        assert result.overall_certainty(["pay", "date"]) == Certainty.NOT_FOUND

    def test_no_fields_returns_not_found(self) -> None:
        result = self._make_result([])
        assert result.overall_certainty(["pay", "date"]) == Certainty.NOT_FOUND

    def test_none_certainty_treated_as_not_found(self) -> None:
        fields = [
            ExtractedField(name="pay", value="100", source_document="t.pdf", source_page=1, certainty=None),
            ExtractedField(name="date", value="01/01/2024", source_document="t.pdf", source_page=1, certainty=Certainty.HIGH),
        ]
        result = self._make_result(fields)
        assert result.overall_certainty(["pay", "date"]) == Certainty.NOT_FOUND
