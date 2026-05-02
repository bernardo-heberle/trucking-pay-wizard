"""Fixtures for extraction unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


@pytest.fixture()
def empty_ocr() -> OcrResult:
    """An OcrResult with no lines — no fields should be extracted."""
    return OcrResult(
        source_path=Path("empty.pdf"),
        content_hash="0" * 64,
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=0)],
        lines=[],
    )
