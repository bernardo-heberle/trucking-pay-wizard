"""Unit tests for the pay OCR cross-reference verifier."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.extract.pay_verifier import verify_pay_against_ocr


class TestBasicMatches:

    def test_exact_match_no_formatting(self) -> None:
        matched, reason = verify_pay_against_ocr("750.00", "Total: 750.00")

        assert matched is True
        assert "Matched" in reason
        assert "750.00" in reason

    def test_dollar_sign_in_ocr_matches(self) -> None:
        """LLM canonical form matches a dollar-formatted value in OCR text."""
        matched, reason = verify_pay_against_ocr("1500.00", "Payment: $1,500.00")

        assert matched is True
        assert "Matched" in reason
        assert "1,500.00" in reason

    def test_comma_in_ocr_matches(self) -> None:
        """OCR has thousand separator; normalized form matches."""
        matched, reason = verify_pay_against_ocr("1500.00", "Carrier pay: 1,500.00")

        assert matched is True
        assert "Matched" in reason

    def test_integer_in_ocr_matches(self) -> None:
        """OCR value with no decimal part matches normalized form."""
        matched, reason = verify_pay_against_ocr("820.00", "Amount: $820")

        assert matched is True
        assert "Matched" in reason

    def test_match_among_multiple_amounts(self) -> None:
        """Returns True when the target is one of several dollar amounts."""
        ocr = "Fuel surcharge: $150.00\nTotal payment: $1,200.50\nDeduction: $75.00"
        matched, reason = verify_pay_against_ocr("1200.50", ocr)

        assert matched is True
        assert "Matched" in reason
        assert "1,200.50" in reason

    def test_reason_string_quotes_matched_text(self) -> None:
        _, reason = verify_pay_against_ocr("750.00", "Settlement: $750.00")

        assert reason == "Matched '$750.00' in document text"

    def test_zero_amount_matches(self) -> None:
        """Zero is a valid dollar amount that should match literally."""
        matched, reason = verify_pay_against_ocr("0.00", "Stop-off fee: $0.00")

        assert matched is True
        assert "Matched" in reason

    def test_differs_only_in_cents_not_matched(self) -> None:
        """Amount differing only in the cents digit must not match."""
        matched, reason = verify_pay_against_ocr("1500.00", "Payment: $1,500.01")

        assert matched is False
        assert "1500.00" in reason


class TestNoMatch:

    def test_value_absent_returns_false(self) -> None:
        matched, reason = verify_pay_against_ocr("9999.00", "Payment: $750.00")

        assert matched is False
        assert "9999.00" in reason

    def test_empty_ocr_text_returns_false(self) -> None:
        matched, reason = verify_pay_against_ocr("750.00", "")

        assert matched is False
        assert "750.00" in reason

    def test_ocr_with_no_numbers_returns_false(self) -> None:
        matched, reason = verify_pay_against_ocr("750.00", "No amounts here at all.")

        assert matched is False
        assert "750.00" in reason

    def test_reason_string_describes_mismatch(self) -> None:
        _, reason = verify_pay_against_ocr("9999.00", "Payment: $750.00")

        assert "9999.00" in reason
        assert "Matched" not in reason


class TestLLMNumericErrors:
    """Verify the verifier catches realistic LLM misread scenarios."""

    def test_transposed_digits_not_matched(self) -> None:
        """LLM returns 1234.56 but document says 12345.60 — should not match."""
        ocr = "Total to carrier: $12,345.60"
        matched, reason = verify_pay_against_ocr("1234.56", ocr)
        assert matched is False
        assert "1234.56" in reason

    def test_dropped_digit_not_matched(self) -> None:
        """LLM returns 150.00 but document says 1500.00."""
        ocr = "Carrier payment: $1,500.00"
        matched, _ = verify_pay_against_ocr("150.00", ocr)
        assert matched is False

    def test_off_by_one_decimal_not_matched(self) -> None:
        """LLM returns 1500.00 but document says 15000.00 (misplaced decimal)."""
        ocr = "Settlement amount: $15,000.00"
        matched, _ = verify_pay_against_ocr("1500.00", ocr)
        assert matched is False

    def test_partial_overlap_not_matched(self) -> None:
        """OCR has 2500.00; LLM returns 250.00 — substring of digits not a match."""
        ocr = "Gross pay: $2,500.00"
        matched, _ = verify_pay_against_ocr("250.00", ocr)
        assert matched is False


class TestWrongFieldPresenceLimit:
    """Document the known limitation: verifier confirms presence, not semantic role."""

    def test_wrong_field_present_returns_true(self) -> None:
        """LLM returns a deduction amount that happens to appear in the document.

        The verifier cannot distinguish gross pay from a deduction — it can
        only confirm the number exists somewhere in the text.  This is a
        known limitation; the test documents expected behavior rather than
        a bug.
        """
        ocr = (
            "Gross Pay:      $2,500.00\n"
            "Deductions:      $500.00\n"
            "Net Pay:        $2,000.00"
        )
        # LLM returns the deduction amount instead of gross pay.
        matched, _ = verify_pay_against_ocr("500.00", ocr)
        assert matched is True

    def test_correct_field_also_returns_true(self) -> None:
        """The correct gross-pay value from the same document also matches."""
        ocr = (
            "Gross Pay:      $2,500.00\n"
            "Deductions:      $500.00\n"
            "Net Pay:        $2,000.00"
        )
        matched, _ = verify_pay_against_ocr("2500.00", ocr)
        assert matched is True


class TestVerifyPayProperties:
    """Property-based tests for verify_pay_against_ocr.

    If the normalized value appears literally in the OCR text, the verifier
    must always return True — regardless of surrounding context.  This
    catches regex-narrowing mutants that would exclude certain number formats.
    """

    @given(
        st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("10000"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @h_settings(max_examples=500)
    def test_value_present_in_ocr_always_matches(self, d: Decimal) -> None:
        """If the plain-decimal value appears in OCR text, must return True."""
        normalized = f"{d:.2f}"
        ocr_text = f"Total Payment to Carrier: {normalized}"

        matched, reason = verify_pay_against_ocr(normalized, ocr_text)

        assert matched is True, (
            f"Expected match for {normalized!r} in {ocr_text!r}, got: {reason}"
        )
        assert "Matched" in reason
