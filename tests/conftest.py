"""Top-level test fixtures shared across all test levels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult

_DATA_RAW = Path(__file__).parent.parent / "data" / "raw" / "khan_trans"
_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    """Return the path to a real settlement PDF from data/raw/.

    Tests that depend on this fixture are smoke-tested against an actual
    document. They are skipped automatically when data/raw/ is empty so the
    suite still passes in CI environments that don't carry the raw files.
    """
    pdfs = sorted(_DATA_RAW.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No PDF files found in data/raw/ — skipping real-document tests.")
    return pdfs[0]


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
