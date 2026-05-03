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


class TestAnchorOffset:
    """Tests for the anchor_offset parameter that restricts search to a local window."""

    def _build_ocr(self, lines: list[str]) -> str:
        """Join lines with newlines to simulate multi-line OCR text."""
        return "\n".join(lines)

    def test_no_anchor_finds_value_anywhere(self) -> None:
        """Without anchor_offset, the verifier searches the full text."""
        ocr = self._build_ocr([
            "Pickup Date: 03/05/2024",
            "Load 1 pay: $1,250.00",
            "Pickup Date: 03/12/2024",
            "Load 2 pay: $2,400.00",
        ])
        matched, reason = verify_pay_against_ocr("2400.00", ocr)
        assert matched is True
        assert "Matched" in reason

    def test_anchor_restricts_search_to_local_line(self) -> None:
        """With anchor_offset on the '03/05/2024' line, only that line is searched first.

        The first load's date '03/05/2024' sits at offset 13 in the text.
        The first load's pay is '$1,250.00' on the next line.
        The second load's pay '$2,400.00' is several lines away.
        With an anchor pinned to line 1, '$1,250.00' (nearby) should match first.
        """
        line0 = "Pickup Date: 03/05/2024"
        line1 = "Load 1 pay: $1,250.00"
        ocr = self._build_ocr([line0, line1, "Pickup Date: 03/12/2024", "Load 2 pay: $2,400.00"])

        # Anchor at offset within line0 — the verifier should find $1,250.00 nearby.
        anchor = 5  # inside "Pickup Date: 03/05/2024"
        matched_local, reason_local = verify_pay_against_ocr("1250.00", ocr, anchor_offset=anchor)
        assert matched_local is True
        assert "Matched" in reason_local

    def test_anchor_falls_back_to_global_when_value_not_local(self) -> None:
        """When the value is not on the anchor's line, the global search finds it."""
        line0 = "Pickup Date: 03/05/2024"
        line1 = "Load 1 pay: $999.00"
        line2 = "Pickup Date: 03/12/2024"
        line3 = "Load 2 pay: $2,400.00"
        ocr = self._build_ocr([line0, line1, line2, line3])

        # Anchor on line2 (03/12/2024 date), searching for $2,400.00 which is on line3.
        anchor = len(line0) + 1 + len(line1) + 1 + 5  # within line2
        matched, reason = verify_pay_against_ocr("2400.00", ocr, anchor_offset=anchor)
        assert matched is True
        assert "Matched" in reason

    def test_anchor_none_same_as_no_anchor(self) -> None:
        """Passing anchor_offset=None is identical to omitting the argument."""
        ocr = "Total: $500.00"
        result_explicit_none = verify_pay_against_ocr("500.00", ocr, anchor_offset=None)
        result_no_arg = verify_pay_against_ocr("500.00", ocr)
        assert result_explicit_none == result_no_arg

    def test_anchor_beyond_text_length_falls_back_to_global(self) -> None:
        """An anchor_offset past the end of the text falls back gracefully."""
        ocr = "Payment: $750.00"
        matched, reason = verify_pay_against_ocr("750.00", ocr, anchor_offset=9999)
        assert matched is True
        assert "Matched" in reason

    def test_wrong_pay_near_anchor_not_matched(self) -> None:
        """A value not in the text at all should still return False with anchor_offset set."""
        ocr = "Pickup Date: 03/05/2024\nLoad pay: $1,250.00"
        anchor = 5
        matched, _ = verify_pay_against_ocr("9999.00", ocr, anchor_offset=anchor)
        assert matched is False


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
