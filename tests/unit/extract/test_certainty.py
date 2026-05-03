"""Unit tests for the Certainty enum and overall_certainty logic."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.extract.models import (
    Certainty,
    DocumentExtractionResult,
    ExtractedField,
    ExtractedLoad,
)


def _ensure_thresholds(high: float = 0.9, review: float = 0.6) -> None:
    """Set threshold env vars so load_settings() works without a .env file."""
    os.environ["CONFIDENCE_HIGH_THRESHOLD"] = str(high)
    os.environ["CONFIDENCE_REVIEW_THRESHOLD"] = str(review)


def _field(name: str, certainty: Certainty | None) -> ExtractedField:
    value = "100" if name == "pay" else "01/01/2024"
    return ExtractedField(
        name=name,
        value=value,
        source_document="t.pdf",
        source_page=1,
        certainty=certainty,
    )


def _load(
    pay_certainty: Certainty | None = Certainty.HIGH,
    date_certainty: Certainty | None = Certainty.HIGH,
    *,
    omit_pay: bool = False,
    omit_date: bool = False,
    index: int = 1,
) -> ExtractedLoad:
    pay = None if omit_pay else _field("pay", pay_certainty)
    date = None if omit_date else _field("date", date_certainty)
    return ExtractedLoad(index=index, pay=pay, date=date)


def _result(loads: list[ExtractedLoad]) -> DocumentExtractionResult:
    return DocumentExtractionResult(
        source_path=Path("test.pdf"),
        content_hash="0" * 64,
        loads=loads,
        page_count=1,
    )


class TestCertaintyEnum:

    def test_values(self) -> None:
        assert Certainty.HIGH.value == "High"
        assert Certainty.REVIEW.value == "Review"
        assert Certainty.NOT_FOUND.value == "Not Found"


class TestConfidenceToCertaintyBoundaries:
    """Pin the exact threshold comparisons \u2014 >= not >."""

    def setup_method(self) -> None:
        _ensure_thresholds(high=0.9, review=0.6)

    @pytest.mark.parametrize(
        "confidence, expected",
        [
            (0.9,    Certainty.HIGH),       # at high threshold \u2014 must be HIGH
            (0.8999, Certainty.REVIEW),     # one ULP below high threshold
            (1.0,    Certainty.HIGH),       # maximum confidence
            (0.6,    Certainty.REVIEW),     # at review threshold \u2014 must be REVIEW
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


class TestLoadCertainty:
    """ExtractedLoad.certainty() returns the worst of pay/date."""

    def test_both_high(self) -> None:
        load = _load(Certainty.HIGH, Certainty.HIGH)
        assert load.certainty() == Certainty.HIGH

    def test_pay_review_date_high_returns_review(self) -> None:
        load = _load(Certainty.REVIEW, Certainty.HIGH)
        assert load.certainty() == Certainty.REVIEW

    def test_pay_high_date_review_returns_review(self) -> None:
        load = _load(Certainty.HIGH, Certainty.REVIEW)
        assert load.certainty() == Certainty.REVIEW

    def test_pay_not_found_returns_not_found(self) -> None:
        load = _load(Certainty.NOT_FOUND, Certainty.HIGH)
        assert load.certainty() == Certainty.NOT_FOUND

    def test_missing_pay_returns_not_found(self) -> None:
        load = _load(date_certainty=Certainty.HIGH, omit_pay=True)
        assert load.certainty() == Certainty.NOT_FOUND

    def test_missing_date_returns_not_found(self) -> None:
        load = _load(pay_certainty=Certainty.HIGH, omit_date=True)
        assert load.certainty() == Certainty.NOT_FOUND

    def test_pay_certainty_none_returns_not_found(self) -> None:
        """A field with ``certainty=None`` is treated as NOT_FOUND."""
        load = _load(pay_certainty=None, date_certainty=Certainty.HIGH)
        assert load.certainty() == Certainty.NOT_FOUND


class TestOverallCertainty:
    """DocumentExtractionResult.overall_certainty() returns worst across loads."""

    def test_no_loads_returns_not_found(self) -> None:
        assert _result([]).overall_certainty() == Certainty.NOT_FOUND

    def test_single_high_load(self) -> None:
        assert _result([_load(Certainty.HIGH, Certainty.HIGH)]).overall_certainty() == Certainty.HIGH

    def test_single_review_load(self) -> None:
        assert _result([_load(Certainty.REVIEW, Certainty.HIGH)]).overall_certainty() == Certainty.REVIEW

    def test_all_loads_high_returns_high(self) -> None:
        loads = [
            _load(Certainty.HIGH, Certainty.HIGH, index=1),
            _load(Certainty.HIGH, Certainty.HIGH, index=2),
        ]
        assert _result(loads).overall_certainty() == Certainty.HIGH

    def test_one_review_load_demotes_overall_to_review(self) -> None:
        """A single REVIEW load drags an otherwise-HIGH document to REVIEW."""
        loads = [
            _load(Certainty.HIGH, Certainty.HIGH, index=1),
            _load(Certainty.REVIEW, Certainty.HIGH, index=2),
            _load(Certainty.HIGH, Certainty.HIGH, index=3),
        ]
        assert _result(loads).overall_certainty() == Certainty.REVIEW

    def test_one_not_found_load_demotes_overall_to_not_found(self) -> None:
        """A single NOT_FOUND load demotes the whole document, even with REVIEW peers."""
        loads = [
            _load(Certainty.HIGH, Certainty.HIGH, index=1),
            _load(Certainty.REVIEW, Certainty.HIGH, index=2),
            _load(omit_pay=True, date_certainty=Certainty.HIGH, index=3),
        ]
        assert _result(loads).overall_certainty() == Certainty.NOT_FOUND
