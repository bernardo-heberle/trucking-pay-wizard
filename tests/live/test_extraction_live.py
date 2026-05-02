"""Live extraction tests — real Anthropic API calls against known OCR text.

Validates that the prompt + schema + pay verifier produce correct results
when wired to the real Claude model.  Uses the same fixture data from
``tests/fixtures/`` so expected values are stable.
"""

from __future__ import annotations

from tests.conftest import load_ocr_fixture
from tests.live.conftest import needs_anthropic

pytestmark = needs_anthropic


class TestSettlementExtraction:
    """Extract from the settlement statement fixture.

    Fixture text contains:
      - "Total Payment to Carrier: $750.00"
      - "Pickup Exactly: 03/12/2024"
    """

    def test_extracts_pay_and_date(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")

        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        field_names = {f.name for f in result.fields}
        assert "pay" in field_names, f"Expected 'pay' field, got: {field_names}"
        assert "date" in field_names, f"Expected 'date' field, got: {field_names}"

    def test_pay_value_is_750(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "750.00"

    def test_date_value_is_march_12(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = next(f for f in result.fields if f.name == "date")
        assert "03/12/2024" in date.value or "03/12/2024" == date.value

    def test_pay_certainty_is_high(self, anthropic_extractor) -> None:
        """$750.00 appears literally in OCR text, so pay verification should pass."""
        from src.extract.models import Certainty

        ocr = load_ocr_fixture("settlement_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.certainty == Certainty.HIGH


class TestPaySummaryExtraction:
    """Extract from the pay summary (dispatch load summary) fixture.

    Fixture text contains:
      - "$820" under "Agent Pays Carrier"
      - "March 20, 2024 (Wed)" under "Pickup Date"
    """

    def test_extracts_pay_and_date(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")

        result = anthropic_extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        field_names = {f.name for f in result.fields}
        assert "pay" in field_names
        assert "date" in field_names

    def test_pay_value_is_820(self, anthropic_extractor) -> None:
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        pay = next(f for f in result.fields if f.name == "pay")
        assert pay.value == "820.00"

    def test_date_contains_march_20(self, anthropic_extractor) -> None:
        """The LLM may return the raw string or normalize it; either is fine."""
        ocr = load_ocr_fixture("pay_summary_ocr.json")
        result = anthropic_extractor.extract(ocr, page_count=1)

        date = next(f for f in result.fields if f.name == "date")
        assert "March 20, 2024" in date.value or "03/20/2024" in date.value
