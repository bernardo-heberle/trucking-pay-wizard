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

pay.value carries the raw LLM string (e.g. "$1,850.00" or "$920").
Assertions normalise it with _normalize_pay_value — the same
canonicalisation used by the pay verifier and the Excel exporter —
and compare against the pinned two-decimal canonical string.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.extract.llm.schemas.income import _normalize_pay_value
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
    """Return the named field from loads[0].

    All pipeline live test documents contain a single load, so loads[0]
    is the whole result.  Fails with a descriptive message when the
    loads list is empty or the requested field is None.
    """
    assert len(result.loads) >= 1, (
        f"Expected at least one load, got 0. extraction_error={result.extraction_error!r}"
    )
    load = result.loads[0]
    field = getattr(load, name, None)
    assert field is not None, (
        f"Field '{name}' is None on loads[0]. "
        f"pay={load.pay!r}  date={load.date!r}"
    )
    return field


def _assert_pay(result, canonical: str) -> None:
    """Assert that loads[0].pay normalises to *canonical* (e.g. '1850.00').

    pay.value carries the raw LLM string as it appeared on the document
    (e.g. '$1,850.00', '$920').  _normalize_pay_value strips currency
    symbols and commas and pads to two decimal places — matching what the
    pay verifier and Excel exporter produce.  The pinned canonical string
    is the same value that appears in the staff-facing spreadsheet.
    """
    pay = _field(result, "pay")
    normalized = _normalize_pay_value(pay.value)
    assert normalized == canonical, (
        f"pay normalised to {normalized!r} (raw: {pay.value!r}), expected {canonical!r}"
    )


# ---------------------------------------------------------------------------
# Baseline: CentralDispatch single-page settlement
# ---------------------------------------------------------------------------


class TestCentralDispatchPipeline:
    """Standard single-page CentralDispatch layout — the baseline happy path."""

    def test_extracts_pay(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_central_dispatch_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        _assert_pay(result, "1850.00")

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
        _assert_pay(result, "920.00")

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
        _assert_pay(result, "1350.00")

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
        normalized = _normalize_pay_value(pay.value)
        assert normalized == "1400.00", (
            f"Expected carrier pay 1400.00, got {normalized!r} (raw: {pay.value!r}). "
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
        _assert_pay(result, "4500.00")

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
        normalized = _normalize_pay_value(pay.value)
        assert normalized == "750.00", (
            f"Expected 750.00, got {normalized!r} (raw: {pay.value!r}). "
            "Extractor may have grabbed the old revision value ($0.00)."
        )

    def test_extracts_date(self, azure_client, anthropic_extractor, tmp_path) -> None:
        pdf = build_revision_history_pdf(tmp_path)
        result = _run_pipeline(pdf, azure_client, anthropic_extractor)
        assert "03/12/2024" in _field(result, "date").value
