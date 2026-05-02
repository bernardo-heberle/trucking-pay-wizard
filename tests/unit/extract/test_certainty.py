"""Unit tests for the Certainty enum and overall_certainty logic."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField


def _ensure_thresholds(high: float = 0.9, review: float = 0.6) -> None:
    """Set threshold env vars so load_settings() works without a .env file."""
    os.environ["CONFIDENCE_HIGH_THRESHOLD"] = str(high)
    os.environ["CONFIDENCE_REVIEW_THRESHOLD"] = str(review)


class TestCertaintyEnum:

    def test_values(self) -> None:
        assert Certainty.HIGH.value == "High"
        assert Certainty.REVIEW.value == "Review"
        assert Certainty.NOT_FOUND.value == "Not Found"


class TestConfidenceToCertaintyBoundaries:
    """Pin the exact threshold comparisons — >= not >."""

    def setup_method(self) -> None:
        _ensure_thresholds(high=0.9, review=0.6)

    @pytest.mark.parametrize(
        "confidence, expected",
        [
            (0.9,    Certainty.HIGH),       # at high threshold — must be HIGH
            (0.8999, Certainty.REVIEW),     # one ULP below high threshold
            (1.0,    Certainty.HIGH),       # maximum confidence
            (0.6,    Certainty.REVIEW),     # at review threshold — must be REVIEW
            (0.5999, Certainty.NOT_FOUND),  # one ULP below review threshold
            (0.0,    Certainty.NOT_FOUND),  # minimum confidence
        ],
        ids=[
            "high_at_threshold",
            "just_below_high",
            "max_confidence",
            "review_at_threshold",
            "just_below_review",
            "zero_confidence",
        ],
    )
    def test_confidence_to_certainty_boundary(
        self, confidence: float, expected: Certainty
    ) -> None:
        from src.extract.llm.schemas.income import _confidence_to_certainty

        assert _confidence_to_certainty(confidence) == expected


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
