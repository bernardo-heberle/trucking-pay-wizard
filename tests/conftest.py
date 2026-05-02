"""Top-level test fixtures shared across all test levels."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


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
