"""Unit tests for multi-load extraction scenarios.

These tests verify that LlmExtractor correctly handles documents that
contain multiple loads — the primary target of the multi-load feature.
All tests use a mocked Anthropic client and synthetic OCR text.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.extract.llm.extractor import LlmExtractor, _MAX_ATTEMPTS
from src.extract.models import Certainty, ExtractedLoad
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


def _make_settings() -> Settings:
    return Settings(
        anthropic_api_key="sk-test-key",
        llm_model="claude-3-5-haiku-20241022",
        confidence_high_threshold=0.9,
        confidence_review_threshold=0.6,
    )


def _mock_response(tool_input: dict) -> MagicMock:
    block = SimpleNamespace(type="tool_use", name="extract_income_fields", input=tool_input)
    resp = MagicMock()
    resp.content = [block]
    return resp


def _build_ocr(lines: list[str], source: Path = Path("doc.pdf")) -> OcrResult:
    """Build an OcrResult from a list of text lines, all on page 1."""
    ocr_lines: list[OcrLine] = []
    offset = 0
    for i, text in enumerate(lines):
        ocr_lines.append(
            OcrLine(
                text=text,
                page_number=1,
                bounding_box=BoundingBox(x=1.0, y=float(i), width=6.0, height=0.25),
                char_start=offset,
                char_end=offset + len(text),
            )
        )
        offset += len(text) + 1
    return OcrResult(
        source_path=source,
        content_hash="test" + "0" * 60,
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=len(lines))],
        lines=ocr_lines,
    )


# ── Three-load settlement ────────────────────────────────────────────────────

OCR_THREE_LOADS = [
    "SETTLEMENT STATEMENT",
    "Carrier: ACME Trucking LLC",
    "Payee: Joe Doe",
    "",
    "Load 1 of 3",
    "Pickup Date: 03/05/2024",
    "Total Payment to Carrier: $1,250.00",
    "",
    "Load 2 of 3",
    "Pickup Date: 03/12/2024",
    "Total Payment to Carrier: $2,400.00",
    "",
    "Load 3 of 3",
    "Pickup Date: 03/19/2024",
    "Total Payment to Carrier: $875.50",
    "",
    "Gross Pay: $4,525.50",
]

_THREE_LOAD_TOOL_INPUT = {
    "loads": [
        {"pay": {"value": "$1,250.00", "confidence": 0.97}, "date": {"value": "03/05/2024", "confidence": 0.95}},
        {"pay": {"value": "$2,400.00", "confidence": 0.97}, "date": {"value": "03/12/2024", "confidence": 0.95}},
        {"pay": {"value": "$875.50", "confidence": 0.97}, "date": {"value": "03/19/2024", "confidence": 0.95}},
    ]
}


@patch("src.extract.llm.extractor.time.sleep")
class TestThreeLoadExtraction:

    def test_returns_three_loads(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 3

    def test_load_indices_are_sequential(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        assert [load.index for load in result.loads] == [1, 2, 3]

    def test_pay_values_pin_per_load(self, _sleep) -> None:
        """Each load's pay must match the LLM-extracted value — no cross-contamination."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].pay is not None
        assert result.loads[0].pay.value == "$1,250.00"
        assert result.loads[1].pay is not None
        assert result.loads[1].pay.value == "$2,400.00"
        assert result.loads[2].pay is not None
        assert result.loads[2].pay.value == "$875.50"

    def test_date_values_pin_per_load(self, _sleep) -> None:
        """Each load's date must be paired with its own load, not mixed up."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].date is not None
        assert result.loads[0].date.value == "03/05/2024"
        assert result.loads[1].date is not None
        assert result.loads[1].date.value == "03/12/2024"
        assert result.loads[2].date is not None
        assert result.loads[2].date.value == "03/19/2024"

    def test_all_loads_high_certainty_when_found_in_ocr(self, _sleep) -> None:
        """When every pay value appears in the OCR text, all loads should be HIGH."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        for load in result.loads:
            assert load.pay is not None
            assert load.pay.certainty == Certainty.HIGH, (
                f"Load {load.index} pay certainty expected HIGH, got {load.pay.certainty}"
            )

    def test_source_spans_resolved_per_load(self, _sleep) -> None:
        """Each load's pay and date must have source spans from the OCR text."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        result = extractor.extract(ocr, page_count=1)

        for load in result.loads:
            assert load.pay is not None
            assert len(load.pay.source_spans) >= 1, f"Load {load.index} pay has no source spans"
            assert load.date is not None
            assert len(load.date.source_spans) >= 1, f"Load {load.index} date has no source spans"

    def test_api_called_exactly_once_on_success(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_THREE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_THREE_LOADS)

        extractor.extract(ocr, page_count=1)

        assert client.messages.create.call_count == 1


# ── Duplicate-pay two-load document ─────────────────────────────────────────

OCR_DUPLICATE_PAY = [
    "SETTLEMENT STATEMENT",
    "Carrier: ACME Trucking LLC",
    "",
    "Load 1",
    "Pickup Date: 04/02/2024",
    "Total Payment to Carrier: $1,200.00",
    "",
    "Load 2",
    "Pickup Date: 04/16/2024",
    "Total Payment to Carrier: $1,200.00",
    "",
    "Gross Pay: $2,400.00",
]

_DUPLICATE_PAY_TOOL_INPUT = {
    "loads": [
        {"pay": {"value": "$1,200.00", "confidence": 0.95}, "date": {"value": "04/02/2024", "confidence": 0.95}},
        {"pay": {"value": "$1,200.00", "confidence": 0.95}, "date": {"value": "04/16/2024", "confidence": 0.95}},
    ]
}


@patch("src.extract.llm.extractor.time.sleep")
class TestDuplicatePayExtraction:
    """Two loads sharing the same pay amount — load pairing must not confuse dates."""

    def test_returns_two_loads(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_PAY_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_PAY)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 2

    def test_both_pay_values_are_identical_strings(self, _sleep) -> None:
        """Both loads carry $1,200.00 — each must survive serialisation intact."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_PAY_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_PAY)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].pay.value == "$1,200.00"
        assert result.loads[1].pay.value == "$1,200.00"

    def test_dates_differ_between_loads(self, _sleep) -> None:
        """Different dates must not bleed across duplicate-pay loads."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_PAY_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_PAY)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].date.value == "04/02/2024"
        assert result.loads[1].date.value == "04/16/2024"

    def test_both_loads_high_certainty(self, _sleep) -> None:
        """$1,200.00 appears twice in the OCR text — both loads should be HIGH."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_PAY_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_PAY)

        result = extractor.extract(ocr, page_count=1)

        for load in result.loads:
            assert load.pay.certainty == Certainty.HIGH


# ── Single-load document (new schema handles N=1) ────────────────────────────

_SINGLE_LOAD_TOOL_INPUT = {
    "loads": [
        {"pay": {"value": "$985.00", "confidence": 0.95}, "date": {"value": "05/10/2024", "confidence": 0.95}},
    ]
}

OCR_SINGLE_LOAD = [
    "Settlement Statement",
    "Carrier: ACME Trucking LLC",
    "Pickup Date: 05/10/2024",
    "Total Payment to Carrier: $985.00",
    "Payment terms: Net 30",
]


@patch("src.extract.llm.extractor.time.sleep")
class TestSingleLoadNewSchema:
    """Single-load document via the new loads array schema (1-element list)."""

    def test_returns_exactly_one_load(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_SINGLE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1

    def test_load_has_correct_pay_and_date(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_SINGLE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].pay is not None
        assert result.loads[0].pay.value == "$985.00"
        assert result.loads[0].date is not None
        assert result.loads[0].date.value == "05/10/2024"

    def test_load_index_is_one(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_SINGLE_LOAD_TOOL_INPUT)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].index == 1


# ── Malformed / edge-case LLM responses ─────────────────────────────────────

# ── Duplicate-date two-load document ─────────────────────────────────────────

OCR_DUPLICATE_DATE = [
    "SETTLEMENT STATEMENT",
    "Carrier: ACME Trucking LLC",
    "",
    "Load 1",
    "Pickup Date: 04/02/2024",
    "Total Payment to Carrier: $1,100.00",
    "",
    "Load 2",
    "Pickup Date: 04/02/2024",
    "Total Payment to Carrier: $1,300.00",
    "",
    "Gross Pay: $2,400.00",
]

_DUPLICATE_DATE_WITH_SOURCE_LINE = {
    "loads": [
        {
            "pay": {
                "value": "$1,100.00",
                "confidence": 0.95,
                "source_line": "Total Payment to Carrier: $1,100.00",
            },
            "date": {
                "value": "04/02/2024",
                "confidence": 0.95,
                "source_line": "Pickup Date: 04/02/2024",
            },
        },
        {
            "pay": {
                "value": "$1,300.00",
                "confidence": 0.95,
                "source_line": "Total Payment to Carrier: $1,300.00",
            },
            "date": {
                "value": "04/02/2024",
                "confidence": 0.95,
                "source_line": "Pickup Date: 04/02/2024",
            },
        },
    ]
}

_DUPLICATE_DATE_NO_SOURCE_LINE = {
    "loads": [
        {
            "pay": {"value": "$1,100.00", "confidence": 0.95},
            "date": {"value": "04/02/2024", "confidence": 0.95},
        },
        {
            "pay": {"value": "$1,300.00", "confidence": 0.95},
            "date": {"value": "04/02/2024", "confidence": 0.95},
        },
    ]
}


@patch("src.extract.llm.extractor.time.sleep")
class TestDuplicateDateExtraction:
    """Two loads sharing the same date string — correct disambiguation required."""

    def test_both_loads_returned(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_DATE_WITH_SOURCE_LINE)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_DATE)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 2

    def test_pay_values_differ_between_loads_with_source_line(self, _sleep) -> None:
        """source_line disambiguates the two pay lines even though dates are identical."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_DATE_WITH_SOURCE_LINE)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_DATE)

        result = extractor.extract(ocr, page_count=1)

        assert result.loads[0].pay.value == "$1,100.00"
        assert result.loads[1].pay.value == "$1,300.00"

    def test_date_spans_differ_between_loads_with_source_line(self, _sleep) -> None:
        """When source_line is provided for the duplicate date string, each load must
        highlight a different occurrence of the date in the OCR text."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_DATE_WITH_SOURCE_LINE)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_DATE)

        result = extractor.extract(ocr, page_count=1)

        load1_date = result.loads[0].date
        load2_date = result.loads[1].date
        assert load1_date is not None and load2_date is not None
        assert len(load1_date.source_spans) == 1
        assert len(load2_date.source_spans) == 1
        assert (
            load1_date.source_spans[0].bounding_box.y
            != load2_date.source_spans[0].bounding_box.y
        ), "Both date loads resolved to the same bounding box — disambiguation failed"

    def test_date_spans_differ_between_loads_without_source_line(self, _sleep) -> None:
        """Sequential offset fallback must also disambiguate duplicate dates when
        source_line is absent."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_DATE_NO_SOURCE_LINE)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_DATE)

        result = extractor.extract(ocr, page_count=1)

        load1_date = result.loads[0].date
        load2_date = result.loads[1].date
        assert load1_date is not None and load2_date is not None
        assert len(load1_date.source_spans) == 1
        assert len(load2_date.source_spans) == 1
        assert (
            load1_date.source_spans[0].bounding_box.y
            != load2_date.source_spans[0].bounding_box.y
        ), "Sequential fallback did not disambiguate duplicate date occurrences"

    def test_all_loads_high_certainty_with_duplicate_dates(self, _sleep) -> None:
        client = MagicMock()
        client.messages.create.return_value = _mock_response(_DUPLICATE_DATE_WITH_SOURCE_LINE)
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_DUPLICATE_DATE)

        result = extractor.extract(ocr, page_count=1)

        for load in result.loads:
            assert load.pay is not None
            assert load.pay.certainty == Certainty.HIGH, (
                f"Load {load.index} pay certainty expected HIGH, got {load.pay.certainty}"
            )


@patch("src.extract.llm.extractor.time.sleep")
class TestMalformedLoadsResponses:
    """Verify graceful handling of malformed loads arrays from the LLM."""

    def test_empty_loads_array_retried(self, _sleep) -> None:
        """An empty loads array is invalid (minItems=1) — must be retried."""
        bad = _mock_response({"loads": []})
        good = _mock_response(_SINGLE_LOAD_TOOL_INPUT)
        client = MagicMock()
        client.messages.create.side_effect = [bad, good]
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
        assert client.messages.create.call_count == 2

    def test_empty_loads_exhausts_retries_when_always_bad(self, _sleep) -> None:
        """Persistent empty loads array → extraction_error after all retries."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response({"loads": []})
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is not None
        assert result.loads == []
        assert client.messages.create.call_count == _MAX_ATTEMPTS

    def test_load_with_null_pay_and_date_returns_not_found(self, _sleep) -> None:
        """A load where both pay and date are null is NOT_FOUND certainty."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            {"loads": [{"pay": None, "date": None}]}
        )
        extractor = LlmExtractor(client=client, settings=_make_settings())
        ocr = _build_ocr(OCR_SINGLE_LOAD)

        result = extractor.extract(ocr, page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
        load = result.loads[0]
        assert load.pay is None
        assert load.date is None
        assert load.certainty() == Certainty.NOT_FOUND

    def test_flat_old_format_loads_fallback(self, _sleep) -> None:
        """Old flat format {pay: ..., date: ...} (no 'loads' key) is accepted via fallback."""
        client = MagicMock()
        client.messages.create.return_value = _mock_response({
            "pay": {"value": "$500.00", "confidence": 0.90},
            "date": {"value": "01/01/2024", "confidence": 0.92},
        })
        ocr = _build_ocr(["Payment: $500.00", "Pickup: 01/01/2024"])
        extractor = LlmExtractor(client=client, settings=_make_settings())

        result = extractor.extract(ocr, page_count=1)

        # Fallback wraps the flat response into a 1-element loads list.
        assert result.extraction_error is None
        assert len(result.loads) == 1
        assert result.loads[0].pay is not None
        assert result.loads[0].pay.value == "$500.00"
        assert result.loads[0].date is not None
        assert result.loads[0].date.value == "01/01/2024"
