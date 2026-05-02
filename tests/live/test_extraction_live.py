"""Live extraction tests — real Anthropic API calls against known OCR text.

Validates that the prompt + schema + pay verifier produce correct results
when wired to the real Claude model.  Uses fixture data from
``tests/fixtures/`` so expected values are stable.

Fixture files and their expected extraction values:

    settlement_ocr.json               pay=750.00    date=03/12/2024
    pay_summary_ocr.json              pay=820.00    date contains "March 20, 2024"
    central_dispatch_settlement.json  pay=1850.00   date=04/15/2024
    v2_dispatch_load.json             pay=920.00    date contains "April 8, 2024"
    super_dispatch_backlotcars.json   pay=1350.00   date=04/22/2024
    multi_vehicle_central_dispatch.json pay=4500.00 date=05/06/2024
"""

from __future__ import annotations

import pytest

from src.extract.models import Certainty
from tests.conftest import load_ocr_fixture
from tests.live.conftest import needs_anthropic

pytestmark = needs_anthropic


class TestSettlementExtraction:
    """Minimal settlement fixture (4 lines)."""

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "750.00"

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = next(f for f in result.fields if f.name == "date")
        assert "03/12/2024" in date.value

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        """$750.00 appears literally in OCR text — pay verification should pass."""
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.certainty == Certainty.HIGH


class TestPaySummaryExtraction:
    """Minimal V2 Dispatch fixture (6 lines)."""

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "820.00"

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = next(f for f in result.fields if f.name == "date")
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

    def test_extracts_both_fields(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")

        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        names = {f.name for f in result.fields}
        assert names == {"pay", "date"}, f"Expected pay+date, got: {names}"

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "1850.00"

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = next(f for f in result.fields if f.name == "date")
        assert "04/15/2024" in date.value

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("central_dispatch_settlement.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.certainty == Certainty.HIGH


class TestV2DispatchExtraction:
    """Full V2 Dispatch load summary (88 lines, 2 pages).

    Payment appears on page 2 as a standalone "$920" line.
    Date is "April 8, 2024 (Mon)" under "Pickup Date".
    """

    def test_extracts_both_fields(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")

        result = anthropic_extractor.extract(ocr, page_count=2)

        assert result.extraction_error is None
        names = {f.name for f in result.fields}
        assert names == {"pay", "date"}, f"Expected pay+date, got: {names}"

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "920.00"

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("v2_dispatch_load.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        date = next(f for f in result.fields if f.name == "date")
        assert "April 8, 2024" in date.value or "04/08/2024" in date.value


class TestSuperDispatchExtraction:
    """Super Dispatch / BacklotCars (110 lines, 3 pages).

    Dense contract terms that could confuse extraction. Pay and date
    appear on page 1 among many similar-looking fields.
    """

    def test_extracts_both_fields(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")

        result = anthropic_extractor.extract(ocr, page_count=3)

        assert result.extraction_error is None
        names = {f.name for f in result.fields}
        assert names == {"pay", "date"}, f"Expected pay+date, got: {names}"

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")
        result = anthropic_extractor.extract(ocr, page_count=3)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "1350.00"

    def test_date_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("super_dispatch_backlotcars.json")
        result = anthropic_extractor.extract(ocr, page_count=3)

        date = next(f for f in result.fields if f.name == "date")
        assert "04/22/2024" in date.value


class TestMultiVehicleExtraction:
    """CentralDispatch with 3 vehicles (88 lines, 2 pages).

    Tests that multiple vehicle listings and a high dollar amount
    ($4,500.00) don't confuse the extractor.
    """

    def test_extracts_both_fields(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")

        result = anthropic_extractor.extract(ocr, page_count=2)

        assert result.extraction_error is None
        names = {f.name for f in result.fields}
        assert names == {"pay", "date"}, f"Expected pay+date, got: {names}"

    def test_pay_value(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "4500.00"

    @pytest.mark.parametrize("date_variant", ["05/06/2024"])
    def test_date_value(self, anthropic_extractor, date_variant: str) -> None:
        ocr = load_ocr_fixture("multi_vehicle_central_dispatch.json")
        result = anthropic_extractor.extract(ocr, page_count=2)

        date = next(f for f in result.fields if f.name == "date")
        assert date_variant in date.value
