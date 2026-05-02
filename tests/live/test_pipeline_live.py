"""Live end-to-end tests — real Azure OCR + real Anthropic extraction.

Sends realistic synthetic PDFs through the full pipeline
(ingest → OCR → extraction) with real API calls and verifies extracted
financial values against pinned expected values.

Each document format exercises different layout challenges:
  - CentralDispatch: standard single-page, baseline
  - V2 Dispatch: pay on page 2, word-form date on page 1
  - Super Dispatch: 3-page dense boilerplate
  - COD settlement: three competing dollar amounts
  - Multi-vehicle: 3 vehicles, high total, 2 pages
  - Revision history: old price=$0.00 in revision table
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.extract.models import Certainty
from src.ingest import ingest_document
from src.ocr.analyzer import analyze_document
from tests.fixtures.pdf_builder import (
    build_central_dispatch_pdf,
    build_cod_settlement_pdf,
    build_multi_vehicle_pdf,
    build_revision_history_pdf,
    build_super_dispatch_pdf,
    build_v2_dispatch_pdf,
)
from tests.live.conftest import needs_anthropic, needs_azure

pytestmark = [needs_azure, needs_anthropic]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_pipeline(pdf: Path, azure_client, anthropic_extractor):
    ingested = ingest_document(pdf)
    ocr = analyze_document(ingested, azure_client, rate_limit_delay=0)
    result = anthropic_extractor.extract(ocr, page_count=ingested.page_count)
    assert result.extraction_error is None, f"Extraction error: {result.extraction_error}"
    return result


def _field(result, name: str):
    f = next((f for f in result.fields if f.name == name), None)
    assert f is not None, f"Field '{name}' not found. Fields: {result.fields}"
    return f


# ---------------------------------------------------------------------------
# Baseline: CentralDispatch single-page settlement
# ---------------------------------------------------------------------------


class TestCentralDispatchPipeline:
    """Standard single-page CentralDispatch layout — the baseline happy path."""

    def test_extracts_pay(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_central_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert _field(result, "pay").value == "1850.00"

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_central_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "04/15/2024" in _field(result, "date").value

    def test_pay_certainty_is_high(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_central_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert _field(result, "pay").certainty == Certainty.HIGH


# ---------------------------------------------------------------------------
# V2 Dispatch: pay on page 2, word-form date on page 1
# ---------------------------------------------------------------------------


class TestV2DispatchPipeline:
    """Pay is on page 2; date is written as 'April 8, 2024 (Mon)' on page 1."""

    def test_extracts_pay(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_v2_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert _field(result, "pay").value == "920.00"

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_v2_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        date_val = _field(result, "date").value
        assert "April 8, 2024" in date_val or "04/08/2024" in date_val, (
            f"Expected pickup date in date field, got: {date_val!r}"
        )


# ---------------------------------------------------------------------------
# Super Dispatch / BacklotCars: 3-page dense boilerplate
# ---------------------------------------------------------------------------


class TestSuperDispatchPipeline:
    """Three-page document with dense legal boilerplate — pay on page 1."""

    def test_extracts_pay(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_super_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert _field(result, "pay").value == "1350.00"

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_super_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "04/22/2024" in _field(result, "date").value


# ---------------------------------------------------------------------------
# COD settlement: must pick carrier pay ($1,400), not COD ($1,750) or net ($350)
# ---------------------------------------------------------------------------


class TestCodSettlementPipeline:
    """Three competing dollar amounts — extractor must pick the carrier pay."""

    def test_extracts_carrier_pay_not_cod_amount(
        self, azure_client, anthropic_extractor, tmp_path
    ) -> None:
        pdf = build_cod_settlement_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        pay = _field(result, "pay")
        assert pay.value == "1400.00", (
            f"Expected carrier pay 1400.00, got {pay.value!r}. "
            "Extractor may have grabbed the COD amount ($1,750) or the net ($350)."
        )

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_cod_settlement_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "03/12/2024" in _field(result, "date").value


# ---------------------------------------------------------------------------
# Multi-vehicle batch: 3 vehicles, high aggregate total
# ---------------------------------------------------------------------------


class TestMultiVehiclePipeline:
    """Three vehicles in one order — total pay is $4,500 across all vehicles."""

    def test_extracts_total_pay(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_multi_vehicle_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert _field(result, "pay").value == "4500.00"

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_multi_vehicle_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "05/06/2024" in _field(result, "date").value


# ---------------------------------------------------------------------------
# Revision history: must ignore old price ($0.00) in revision table
# ---------------------------------------------------------------------------


class TestRevisionHistoryPipeline:
    """Revision table shows old price=$0.00 before the real $750.00 payment block."""

    def test_extracts_current_pay_not_old_value(
        self, azure_client, anthropic_extractor, tmp_path
    ) -> None:
        pdf = build_revision_history_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        pay = _field(result, "pay")
        assert pay.value == "750.00", (
            f"Expected 750.00, got {pay.value!r}. "
            "Extractor may have grabbed the old revision value ($0.00)."
        )

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_revision_history_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "03/12/2024" in _field(result, "date").value
