"""Live extraction tests — real Anthropic API calls against known OCR text.

Validates that the prompt + schema + pay verifier produce correct results
when wired to the real Claude model.  Uses fixture data from
``tests/fixtures/`` so expected values are stable.

pay.value carries the raw LLM string as it appeared on the document
(e.g. '$750.00', '$820').  Assertions normalise it with
_normalize_pay_value — the same canonicalisation used by the pay verifier
and the Excel exporter — and compare against a pinned two-decimal string.

Fixture files and their expected extraction values:

    settlement_ocr.json               pay=750.00    date=03/12/2024
    pay_summary_ocr.json              pay=820.00    date contains "March 20, 2024"
    central_dispatch_settlement.json  pay=1850.00   date=04/15/2024
    v2_dispatch_load.json             pay=920.00    date contains "April 8, 2024"
    super_dispatch_backlotcars.json   pay=1350.00   date=04/22/2024
    multi_vehicle_central_dispatch.json pay=4500.00 date=05/06/2024
    summary_with_detail_tables.json   pay=981.92    date contains "Feb. 16, 2025" (single load)
"""

from __future__ import annotations

import pytest

from src.extract.llm.schemas.income import _normalize_pay_value
from src.extract.models import Certainty
from tests.conftest import load_ocr_fixture
from tests.live.conftest import needs_anthropic

pytestmark = needs_anthropic


class TestSettlementExtraction:
    """Minimal settlement fixture (4 lines)."""

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) >= 1
        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "750.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) >= 1
        date = result.loads[0].date
        assert date is not None
        assert "03/12/2024" in date.value

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        """$750.00 appears literally in OCR text — pay verification should pass."""
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) >= 1
        pay = result.loads[0].pay
        assert pay is not None
        assert pay.certainty == Certainty.HIGH


class TestPaySummaryExtraction:
    """Minimal V2 Dispatch fixture (6 lines)."""

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) >= 1
        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "820.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) >= 1
        date = result.loads[0].date
        assert date is not None
        assert "March 20, 2024" in date.value or "03/20/2024" in date.value


# ---------------------------------------------------------------------------
# Realistic multi-line fixtures that mirror actual document formats
# ---------------------------------------------------------------------------


class TestCentralDispatchExtraction:
    """Full CentralDispatch settlement (70 lines, 1 page).

    The pay and date are buried among carrier info, vehicle details,
    dispatch instructions, and contract boilerplate — as they are in
    real documents.
    """

    def test_extracts_at_least_one_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")

        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) >= 1
        assert result.loads[0].pay is not None, "Expected a pay field in load 0"
        assert result.loads[0].date is not None, "Expected a date field in load 0"

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "1850.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = result.loads[0].date
        assert date is not None
        assert "04/15/2024" in date.value

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert pay.certainty == Certainty.HIGH


class TestV2DispatchExtraction:
    """Full V2 Dispatch load summary (88 lines, 2 pages).

    Payment appears on page 2 as a standalone "$920" line.
    Date is "April 8, 2024 (Mon)" under "Pickup Date".
    """

    def test_extracts_at_least_one_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")

        result = anthropic_extractor.extract(ocr, page_count=2)

        assert result.extraction_error is None
        assert len(result.loads) >= 1
        assert result.loads[0].pay is not None
        assert result.loads[0].date is not None

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "920.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        date = result.loads[0].date
        assert date is not None
        assert "April 8, 2024" in date.value or "04/08/2024" in date.value


class TestSuperDispatchExtraction:
    """Super Dispatch / BacklotCars (110 lines, 3 pages).

    Dense contract terms that could confuse extraction. Pay and date
    appear on page 1 among many similar-looking fields.
    """

    def test_extracts_at_least_one_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")

        result = anthropic_extractor.extract(ocr, page_count=3)

        assert result.extraction_error is None
        assert len(result.loads) >= 1
        assert result.loads[0].pay is not None
        assert result.loads[0].date is not None

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")
        result = anthropic_extractor.extract(ocr, page_count=3)

        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "1350.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")
        result = anthropic_extractor.extract(ocr, page_count=3)

        date = result.loads[0].date
        assert date is not None
        assert "04/22/2024" in date.value


class TestMultiVehicleExtraction:
    """CentralDispatch with 3 vehicles (88 lines, 2 pages).

    Tests that multiple vehicle listings and a high dollar amount
    ($4,500.00) don't confuse the extractor.
    """

    def test_extracts_at_least_one_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")

        result = anthropic_extractor.extract(ocr, page_count=2)

        assert result.extraction_error is None
        assert len(result.loads) >= 1
        assert result.loads[0].pay is not None
        assert result.loads[0].date is not None

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "4500.00", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    @pytest.mark.parametrize("date_variant", ["05/06/2024"])
    def test_date_value(self, anthropic_extractor, date_variant: str) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        date = result.loads[0].date
        assert date is not None
        assert date_variant in date.value


# ---------------------------------------------------------------------------
# Multi-load fixtures — test that the LLM returns multiple loads and that
# source_line context correctly disambiguates duplicate values
# ---------------------------------------------------------------------------


class TestMultiLoadSettlementExtraction:
    """Three-load settlement — distinct pay and date per load.

    Validates that the model returns all three loads, pins financial values,
    and that source_line is populated and source_spans are resolved for each
    load (confirming the highlighting pipeline has enough data to work).
    """

    def test_returns_three_loads(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 3, (
            f"Expected 3 loads, got {len(result.loads)}: "
            f"{[l.pay.value if l.pay else None for l in result.loads]}"
        )

    def test_pay_values_pinned_per_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 3
        assert _normalize_pay_value(result.loads[0].pay.value) == "1250.00", (
            f"Load 1 raw pay: {result.loads[0].pay.value!r}"
        )
        assert _normalize_pay_value(result.loads[1].pay.value) == "2400.00", (
            f"Load 2 raw pay: {result.loads[1].pay.value!r}"
        )
        assert _normalize_pay_value(result.loads[2].pay.value) == "875.50", (
            f"Load 3 raw pay: {result.loads[2].pay.value!r}"
        )

    def test_date_values_pinned_per_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 3
        assert "03/05/2024" in result.loads[0].date.value
        assert "03/12/2024" in result.loads[1].date.value
        assert "03/19/2024" in result.loads[2].date.value

    def test_all_loads_high_certainty(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 3
        for load in result.loads:
            assert load.pay is not None
            assert load.pay.certainty == Certainty.HIGH, (
                f"Load {load.index} pay certainty: {load.pay.certainty}"
            )

    def test_source_spans_resolved_for_all_loads(self, anthropic_extractor) -> None:
        """Each load's pay and date must have source_spans — the PDF highlighter needs them."""
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 3
        for load in result.loads:
            assert load.pay is not None
            assert len(load.pay.source_spans) >= 1, (
                f"Load {load.index} pay has no source_spans"
            )
            assert load.date is not None
            assert len(load.date.source_spans) >= 1, (
                f"Load {load.index} date has no source_spans"
            )

    def test_source_line_populated_by_llm(self, anthropic_extractor) -> None:
        """The LLM must return source_line for each field so disambiguation can work."""
        ocr = load_ocr_fixture("multi_load_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 3
        for load in result.loads:
            assert load.pay is not None
            assert load.pay.source_line is not None, (
                f"Load {load.index} pay.source_line is None — LLM did not return it"
            )
            assert load.date is not None
            assert load.date.source_line is not None, (
                f"Load {load.index} date.source_line is None — LLM did not return it"
            )


class TestDuplicatePayLiveExtraction:
    """Two loads sharing pay $1,200.00 on different dates.

    The critical property: each load's pay must resolve to a *different*
    bounding box in the OCR text — not both pointing at the first occurrence.
    This validates the full disambiguation pipeline end-to-end with real LLM
    source_line output.
    """

    def test_returns_two_loads(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_pay.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 2

    def test_both_pay_values_normalize_to_1200(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_pay.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        assert _normalize_pay_value(result.loads[0].pay.value) == "1200.00"
        assert _normalize_pay_value(result.loads[1].pay.value) == "1200.00"

    def test_dates_differ_between_loads(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_pay.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        assert "04/02/2024" in result.loads[0].date.value
        assert "04/16/2024" in result.loads[1].date.value

    def test_pay_spans_resolve_to_different_locations(self, anthropic_extractor) -> None:
        """The two identical pay values must each resolve to a distinct OCR line.

        If both loads point to the same bounding box, disambiguation failed —
        one load's highlight would cover the wrong line in the PDF report.
        """
        ocr = load_ocr_fixture("multi_load_duplicate_pay.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        load1_pay = result.loads[0].pay
        load2_pay = result.loads[1].pay
        assert load1_pay is not None and len(load1_pay.source_spans) >= 1, (
            "Load 1 pay has no source_spans"
        )
        assert load2_pay is not None and len(load2_pay.source_spans) >= 1, (
            "Load 2 pay has no source_spans"
        )
        assert load1_pay.source_spans[0].bounding_box.y != load2_pay.source_spans[0].bounding_box.y, (
            f"Both pay loads resolved to the same y={load1_pay.source_spans[0].bounding_box.y} — "
            "disambiguation failed"
        )


class TestDuplicateDateLiveExtraction:
    """Two loads sharing the same pickup date (04/02/2024) with different pays.

    The critical property: each load's date must resolve to a *different*
    bounding box — not both pinned to the first occurrence of 04/02/2024.
    This is the hardest disambiguation case: the anchor field itself is
    duplicated, so source_line or sequential offset must carry the load.
    """

    def test_returns_two_loads(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_date.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 2

    def test_pay_values_differ_between_loads(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_date.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        assert _normalize_pay_value(result.loads[0].pay.value) == "1100.00", (
            f"Load 1 raw pay: {result.loads[0].pay.value!r}"
        )
        assert _normalize_pay_value(result.loads[1].pay.value) == "1300.00", (
            f"Load 2 raw pay: {result.loads[1].pay.value!r}"
        )

    def test_both_dates_are_the_duplicate_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_load_duplicate_date.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        assert "04/02/2024" in result.loads[0].date.value
        assert "04/02/2024" in result.loads[1].date.value

    def test_date_spans_resolve_to_different_locations(self, anthropic_extractor) -> None:
        """The duplicate date string must resolve to two distinct OCR lines.

        If both loads point to the same bounding box, the second load's date
        highlight would cover the first load's date line — a clear error that
        staff would notice in the PDF report.
        """
        ocr = load_ocr_fixture("multi_load_duplicate_date.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        assert len(result.loads) == 2
        load1_date = result.loads[0].date
        load2_date = result.loads[1].date
        assert load1_date is not None and len(load1_date.source_spans) >= 1, (
            "Load 1 date has no source_spans"
        )
        assert load2_date is not None and len(load2_date.source_spans) >= 1, (
            "Load 2 date has no source_spans"
        )
        assert load1_date.source_spans[0].bounding_box.y != load2_date.source_spans[0].bounding_box.y, (
            f"Both date loads resolved to the same y={load1_date.source_spans[0].bounding_box.y} — "
            "duplicate-date disambiguation failed"
        )


class TestSummaryWithDetailExtraction:
    """Settlement remittance with a summary page + item-by-item detail tables.

    Page 1 is a "Settlement at a glance" summary stating the net pay-out
    ($981.92) and the period-ending date. Pages 2-4 are detail tables (per-trip
    earnings, deductions, per-truck subtotals) full of competing dollar amounts.

    The correct extraction is the single net pay-out from the summary — not the
    gross earnings ($3,543.07), not a per-trip linehaul/total amount, not a
    detail subtotal — and the document is one settlement, so exactly one load.
    """

    def test_returns_single_load(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("summary_with_detail_tables.json")
        result = anthropic_extractor.extract(ocr, page_count=4)

        assert result.extraction_error is None
        assert len(result.loads) == 1, (
            f"Expected 1 load (summary settlement), got {len(result.loads)}: "
            f"{[l.pay.value if l.pay else None for l in result.loads]}"
        )

    def test_pay_is_period_payout(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("summary_with_detail_tables.json")
        result = anthropic_extractor.extract(ocr, page_count=4)

        assert len(result.loads) == 1
        pay = result.loads[0].pay
        assert pay is not None
        assert _normalize_pay_value(pay.value) == "981.92", (
            f"Raw pay value from LLM: {pay.value!r}"
        )

    def test_date_is_period_ending(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("summary_with_detail_tables.json")
        result = anthropic_extractor.extract(ocr, page_count=4)

        assert len(result.loads) == 1
        date = result.loads[0].date
        assert date is not None
        assert "Feb. 16, 2025" in date.value or "02/16/2025" in date.value, (
            f"Raw date value from LLM: {date.value!r}"
        )

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("summary_with_detail_tables.json")
        result = anthropic_extractor.extract(ocr, page_count=4)

        assert len(result.loads) == 1
        pay = result.loads[0].pay
        assert pay is not None
        assert pay.certainty == Certainty.HIGH
