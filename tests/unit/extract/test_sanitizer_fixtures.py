"""Fixture-based PII sanitization tests.

Each fixture simulates realistic Azure Document Intelligence OCR output
from a trucking income document with known PII values embedded.  After
sanitization, none of the original PII strings should survive — and all
legitimate financial data (dollar amounts, dates, load IDs) must be
preserved intact.
"""

from __future__ import annotations

import pytest

from src.extract.llm.sanitizer import sanitize_text


# ── Known PII values seeded into each fixture ──────────────────────────────

_SEEDED_PII: dict[str, list[str]] = {
    "settlement_with_ssn_and_ein": [
        "453-78-9012",   # dashed SSN
        "87-1234567",    # EIN
    ],
    "pay_summary_multi_pii": [
        "321-54-9876",   # dashed SSN
        "654329871",     # undashed SSN (9 digits, no dashes)
        "91-7654321",    # EIN
    ],
    "multi_page_scattered_pii": [
        "111-22-3333",   # dashed SSN (page 1)
        "222-33-4444",   # dashed SSN (page 2)
        "45-6789012",    # EIN (page 2)
    ],
    "pii_adjacent_to_dollars": [
        "987-65-4321",   # dashed SSN on same line as pay amount
        "12-3456789",    # EIN on same line as pay amount
    ],
    "pii_inside_table_layout": [
        "555-66-7777",   # SSN inside whitespace-aligned table row
        "33-9876543",    # EIN inside whitespace-aligned table row
        "876543210",     # undashed SSN in a dense numeric row
    ],
}

# ── Fixture OCR text blocks (realistic Azure DI output) ───────────────────

_FIXTURES: dict[str, str] = {
    "settlement_with_ssn_and_ein": (
        "SETTLEMENT STATEMENT\n"
        "Broker: National Freight Lines LLC\n"
        "Order #: BSAT-2024-1066\n"
        "\n"
        "Driver: Carlos M. Rivera\n"
        "SSN: 453-78-9012\n"
        "EIN: 87-1234567\n"
        "\n"
        "Origin: Memphis, TN 38118\n"
        "Destination: Louisville, KY 40202\n"
        "Pickup Date: 03/12/2024\n"
        "Delivery Date: 03/13/2024\n"
        "\n"
        "Linehaul:                    $1,250.00\n"
        "Fuel Surcharge:                $187.50\n"
        "Detention (2 hrs @ $75):       $150.00\n"
        "Lumper Fee Advance:           ($125.00)\n"
        "                             ---------\n"
        "Total Payment to Carrier:    $1,462.50\n"
    ),
    "pay_summary_multi_pii": (
        "V2 DISPATCH LOAD SUMMARY\n"
        "Load ID: R-667644\n"
        "Date: 04/15/2024\n"
        "\n"
        "Carrier: Khan Transport Inc.\n"
        "Tax ID: 91-7654321\n"
        "Driver SSN: 321-54-9876\n"
        "Driver SSN (alt): 654329871\n"
        "\n"
        "Agent Pays Carrier\n"
        "Rate Confirmation: $820.00\n"
        "Accessorial Charges:\n"
        "  Stop-off fee:      $50.00\n"
        "  TONU:              $0.00\n"
        "Net Amount:          $870.00\n"
        "\n"
        "Pickup: Chicago, IL 60601\n"
        "Drop:   Indianapolis, IN 46201\n"
        "Pickup Date: April 15, 2024 (Mon)\n"
    ),
    "multi_page_scattered_pii": (
        "CONSOLIDATED EARNINGS REPORT\n"
        "Prepared for: Ahmed Hassan\n"
        "SSN: 111-22-3333\n"
        "Period: Q1 2024\n"
        "\n"
        "--- PAGE 1 OF 2 ---\n"
        "\n"
        "Load Date       Origin              Dest                Gross Pay\n"
        "01/05/2024      Dallas, TX          OKC, OK             $650.00\n"
        "01/18/2024      OKC, OK             Tulsa, OK           $380.00\n"
        "02/02/2024      Tulsa, OK           Little Rock, AR     $720.00\n"
        "02/14/2024      Little Rock, AR     Memphis, TN         $510.00\n"
        "                                                    -----------\n"
        "                                    Subtotal Page 1:  $2,260.00\n"
        "\n\n"
        "--- PAGE 2 OF 2 ---\n"
        "\n"
        "Carrier: Hassan Trucking LLC\n"
        "EIN: 45-6789012\n"
        "Secondary Driver SSN: 222-33-4444\n"
        "\n"
        "Load Date       Origin              Dest                Gross Pay\n"
        "03/01/2024      Memphis, TN         Nashville, TN       $440.00\n"
        "03/15/2024      Nashville, TN       Lexington, KY       $520.00\n"
        "                                                    -----------\n"
        "                                    Subtotal Page 2:    $960.00\n"
        "\n"
        "                                    TOTAL Q1 GROSS:   $3,220.00\n"
        "                                    Deductions:        ($480.00)\n"
        "                                    NET PAY:          $2,740.00\n"
    ),
    "pii_adjacent_to_dollars": (
        "QUICK PAY RECEIPT\n"
        "Driver: Jane Doe   SSN: 987-65-4321   EIN: 12-3456789\n"
        "Pay: $2,500.00 Date: 05/01/2024\n"
        "Check #: 004871\n"
    ),
    "pii_inside_table_layout": (
        "DRIVER PAYMENT REGISTER\n"
        "Week Ending: 03/22/2024\n"
        "\n"
        "Driver Name        SSN              EIN            Gross Pay    Net Pay\n"
        "----------------------------------------------------------------------\n"
        "Williams, T.       555-66-7777      33-9876543     $1,845.00    $1,521.00\n"
        "Ref: 876543210     Load #: 44210    Miles: 1,247\n"
        "\n"
        "Deductions:\n"
        "  Insurance:     $124.00\n"
        "  EFS Advance:   $200.00\n"
        "                 -------\n"
        "  Total:         $324.00\n"
    ),
}


class TestOcrFixtureSanitization:
    """Sanitize realistic OCR fixtures and verify every seeded PII string
    is removed while legitimate financial content survives."""

    @pytest.mark.parametrize(
        "fixture_name",
        list(_FIXTURES.keys()),
        ids=list(_FIXTURES.keys()),
    )
    def test_no_seeded_pii_survives(self, fixture_name: str) -> None:
        raw_text = _FIXTURES[fixture_name]
        pii_values = _SEEDED_PII[fixture_name]

        for pii in pii_values:
            assert pii in raw_text, f"Fixture setup bug: {pii!r} missing from raw text"

        sanitized, report = sanitize_text(raw_text)

        for pii in pii_values:
            assert pii not in sanitized, (
                f"PII {pii!r} survived sanitization in {fixture_name!r}"
            )

        assert report.total_redactions == len(pii_values)

    def test_dollar_amounts_preserved(self) -> None:
        sanitized, _ = sanitize_text(_FIXTURES["settlement_with_ssn_and_ein"])

        for amount in ["$1,250.00", "$187.50", "$150.00", "$125.00", "$1,462.50"]:
            assert amount in sanitized, f"{amount} was incorrectly removed"

    def test_dates_preserved(self) -> None:
        sanitized, _ = sanitize_text(_FIXTURES["settlement_with_ssn_and_ein"])

        assert "03/12/2024" in sanitized
        assert "03/13/2024" in sanitized

    def test_load_ids_preserved(self) -> None:
        sanitized_settlement, _ = sanitize_text(
            _FIXTURES["settlement_with_ssn_and_ein"]
        )
        sanitized_summary, _ = sanitize_text(_FIXTURES["pay_summary_multi_pii"])

        assert "BSAT-2024-1066" in sanitized_settlement
        assert "R-667644" in sanitized_summary

    def test_redaction_placeholders_present(self) -> None:
        sanitized, _ = sanitize_text(_FIXTURES["pay_summary_multi_pii"])

        assert sanitized.count("[SSN-REDACTED]") == 2   # dashed + undashed
        assert sanitized.count("[EIN-REDACTED]") == 1

    def test_multi_page_redaction_counts(self) -> None:
        _, report = sanitize_text(_FIXTURES["multi_page_scattered_pii"])

        assert report.counts_by_pattern["ssn_dashed"] == 2
        assert report.counts_by_pattern["ein"] == 1

    def test_table_layout_pii_redacted(self) -> None:
        """PII embedded in whitespace-aligned table rows must still be caught."""
        sanitized, report = sanitize_text(_FIXTURES["pii_inside_table_layout"])

        assert "555-66-7777" not in sanitized
        assert "33-9876543" not in sanitized
        assert "876543210" not in sanitized
        assert report.total_redactions == 3

    def test_fixture_and_pii_lists_stay_in_sync(self) -> None:
        """Guard against adding a fixture without a PII list or vice versa."""
        assert set(_FIXTURES.keys()) == set(_SEEDED_PII.keys())
