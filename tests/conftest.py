"""Top-level test fixtures shared across all test levels."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult
from tests.fixtures.pdf_builder import (
    build_central_dispatch_pdf,
    build_cod_settlement_pdf,
    build_multi_vehicle_pdf,
    build_revision_history_pdf,
    build_super_dispatch_pdf,
    build_v2_dispatch_pdf,
)


@pytest.fixture(autouse=True, scope="session")
def _seed_random() -> None:
    """Seed the standard-library random module for the entire test session.

    This ensures that any production code or test helper that calls the
    module-level random functions produces deterministic output.  Tests that
    need to exercise specific random behaviour (e.g. LlmExtractor backoff
    jitter) must patch random.uniform directly — this fixture does not prevent
    that.
    """
    random.seed(0)

_FIXTURES = Path(__file__).parent / "fixtures"


def load_ocr_fixture(name: str) -> OcrResult:
    """Load a JSON fixture from tests/fixtures/ into an OcrResult."""
    raw = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    pages = [
        OcrPage(
            page_number=p["page_number"],
            width_inches=p["width_inches"],
            height_inches=p["height_inches"],
            line_count=p["line_count"],
        )
        for p in raw["pages"]
    ]
    lines = [
        OcrLine(
            text=ln["text"],
            page_number=ln["page_number"],
            bounding_box=BoundingBox(**ln["bounding_box"]),
            char_start=ln["char_start"],
            char_end=ln["char_end"],
        )
        for ln in raw["lines"]
    ]
    return OcrResult(
        source_path=Path(raw["source_path"]),
        content_hash=raw["content_hash"],
        pages=pages,
        lines=lines,
    )


@pytest.fixture(scope="session")
def settlement_ocr() -> OcrResult:
    return load_ocr_fixture("settlement_ocr.json")


@pytest.fixture(scope="session")
def pay_summary_ocr() -> OcrResult:
    return load_ocr_fixture("pay_summary_ocr.json")


# ---------------------------------------------------------------------------
# Realistic fixtures matching real document formats (all PII is synthetic)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def central_dispatch_ocr() -> OcrResult:
    """CentralDispatch settlement — 70-line single-page dispatch sheet."""
    return load_ocr_fixture("central_dispatch_settlement.json")


@pytest.fixture(scope="session")
def v2_dispatch_ocr() -> OcrResult:
    """V2 Dispatch load summary — 88-line, 2-page format."""
    return load_ocr_fixture("v2_dispatch_load.json")


@pytest.fixture(scope="session")
def super_dispatch_ocr() -> OcrResult:
    """Super Dispatch / BacklotCars — 110-line, 3-page format."""
    return load_ocr_fixture("super_dispatch_backlotcars.json")


@pytest.fixture(scope="session")
def multi_vehicle_ocr() -> OcrResult:
    """CentralDispatch with 3 vehicles — 88-line, 2-page format."""
    return load_ocr_fixture("multi_vehicle_central_dispatch.json")


# ---------------------------------------------------------------------------
# Edge-case JSON fixtures that stress extraction logic
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cod_settlement_ocr() -> OcrResult:
    """COD scenario — three competing dollar amounts: $1,400 carrier pay, $1,750 COD, $350 net."""
    return load_ocr_fixture("cod_settlement_ocr.json")


@pytest.fixture(scope="session")
def revision_history_ocr() -> OcrResult:
    """Revision table showing Price: $0.00 → $750.00 above the real payment block."""
    return load_ocr_fixture("revision_history_ocr.json")


@pytest.fixture(scope="session")
def noisy_boilerplate_ocr() -> OcrResult:
    """Contract boilerplate with penalty amounts ($100/day, 3%) near the real pay line."""
    return load_ocr_fixture("noisy_boilerplate_ocr.json")


@pytest.fixture(scope="session")
def multi_date_formats_ocr() -> OcrResult:
    """PDF timestamp + dispatch date + pickup date + delivery date — must pick up date."""
    return load_ocr_fixture("multi_date_formats_ocr.json")


@pytest.fixture(scope="session")
def sparse_tms_print_ocr() -> OcrResult:
    """Carrier TMS print with 'No Payment received' status alongside Price $800.00."""
    return load_ocr_fixture("sparse_tms_print_ocr.json")


@pytest.fixture(scope="session")
def multi_load_settlement_ocr() -> OcrResult:
    """Three-load settlement — distinct pay ($1,250/$2,400/$875.50) and dates per load."""
    return load_ocr_fixture("multi_load_settlement.json")


@pytest.fixture(scope="session")
def multi_load_duplicate_pay_ocr() -> OcrResult:
    """Two loads sharing pay $1,200.00 on different dates (04/02 and 04/16)."""
    return load_ocr_fixture("multi_load_duplicate_pay.json")


@pytest.fixture(scope="session")
def multi_load_duplicate_date_ocr() -> OcrResult:
    """Two loads sharing date 04/02/2024 with different pay ($1,100 and $1,300)."""
    return load_ocr_fixture("multi_load_duplicate_date.json")


# ---------------------------------------------------------------------------
# PDF builder fixtures (function-scoped so each test gets its own tmp dir)
# ---------------------------------------------------------------------------


@pytest.fixture()
def central_dispatch_pdf(tmp_path: Path) -> Path:
    """CentralDispatch single-page settlement PDF. Expected: pay=1850.00, date=04/15/2024."""
    return build_central_dispatch_pdf(tmp_path)


@pytest.fixture()
def v2_dispatch_pdf(tmp_path: Path) -> Path:
    """V2 Dispatch 2-page load summary PDF. Expected: pay=920.00, date=April 8, 2024."""
    return build_v2_dispatch_pdf(tmp_path)


@pytest.fixture()
def super_dispatch_pdf(tmp_path: Path) -> Path:
    """Super Dispatch / BacklotCars 3-page PDF. Expected: pay=1350.00, date=04/22/2024."""
    return build_super_dispatch_pdf(tmp_path)


@pytest.fixture()
def cod_settlement_pdf(tmp_path: Path) -> Path:
    """COD settlement PDF with three competing dollar amounts. Expected: pay=1400.00."""
    return build_cod_settlement_pdf(tmp_path)


@pytest.fixture()
def multi_vehicle_pdf(tmp_path: Path) -> Path:
    """3-vehicle 2-page batch PDF. Expected: pay=4500.00, date=05/06/2024."""
    return build_multi_vehicle_pdf(tmp_path)


@pytest.fixture()
def revision_history_pdf(tmp_path: Path) -> Path:
    """2-page PDF with revision table (old price=$0.00). Expected: pay=750.00."""
    return build_revision_history_pdf(tmp_path)
