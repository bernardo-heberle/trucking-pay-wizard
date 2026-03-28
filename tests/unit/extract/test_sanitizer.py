"""Unit tests for PII sanitizer."""

from __future__ import annotations

from src.extract.llm.sanitizer import (
    DEFAULT_PATTERNS,
    RedactionPattern,
    sanitize_text,
)
import re


class TestSSNRedaction:

    def test_dashed_ssn_is_redacted(self) -> None:
        text = "SSN: 123-45-6789"
        result, report = sanitize_text(text)
        assert "123-45-6789" not in result
        assert "[SSN-REDACTED]" in result
        assert report.total_redactions == 1

    def test_multiple_ssns_are_redacted(self) -> None:
        text = "First: 111-22-3333, Second: 444-55-6666"
        result, report = sanitize_text(text)
        assert "111-22-3333" not in result
        assert "444-55-6666" not in result
        assert report.total_redactions == 2
        assert report.counts_by_pattern["ssn_dashed"] == 2

    def test_nine_digit_ssn_no_dashes(self) -> None:
        text = "SSN 123456789 on file"
        result, report = sanitize_text(text)
        assert "123456789" not in result
        assert "[SSN-REDACTED]" in result

    def test_longer_number_not_redacted_as_ssn(self) -> None:
        text = "Account 1234567890 has balance"
        result, report = sanitize_text(text)
        assert "1234567890" in result
        assert report.counts_by_pattern.get("ssn_no_dash", 0) == 0


class TestEINRedaction:

    def test_ein_is_redacted(self) -> None:
        text = "EIN: 12-3456789"
        result, report = sanitize_text(text)
        assert "12-3456789" not in result
        assert "[EIN-REDACTED]" in result
        assert report.total_redactions == 1


class TestNoRedactionNeeded:

    def test_clean_text_passes_through(self) -> None:
        text = "Total Payment to Carrier: $750.00\nPickup Date: 03/12/2024"
        result, report = sanitize_text(text)
        assert result == text
        assert report.total_redactions == 0

    def test_empty_string(self) -> None:
        result, report = sanitize_text("")
        assert result == ""
        assert report.total_redactions == 0


class TestCustomPatterns:

    def test_custom_pattern_applied(self) -> None:
        custom = [
            RedactionPattern(
                name="phone",
                regex=re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),
                placeholder="[PHONE-REDACTED]",
            )
        ]
        text = "Call 555-123-4567 for info"
        result, report = sanitize_text(text, patterns=custom)
        assert "555-123-4567" not in result
        assert "[PHONE-REDACTED]" in result

    def test_empty_patterns_list_passes_through(self) -> None:
        text = "SSN: 123-45-6789"
        result, report = sanitize_text(text, patterns=[])
        assert result == text
        assert report.total_redactions == 0


class TestRedactionReport:

    def test_report_counts_by_pattern(self) -> None:
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        _, report = sanitize_text(text)
        assert report.total_redactions == 2
        assert report.counts_by_pattern["ssn_dashed"] == 1
        assert report.counts_by_pattern["ein"] == 1
