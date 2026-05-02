"""Unit tests for the Certainty enum and overall_certainty logic."""

from __future__ import annotations

from pathlib import Path

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField


class TestCertaintyEnum:

    def test_values(self) -> None:
        assert Certainty.HIGH.value == "High"
        assert Certainty.REVIEW.value == "Review"
        assert Certainty.NOT_FOUND.value == "Not Found"

    def test_is_str_subclass(self) -> None:
        assert isinstance(Certainty.HIGH, str)


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
