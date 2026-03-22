"""Fixtures for extraction unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


@pytest.fixture()
def empty_ocr() -> OcrResult:
    """An OcrResult with no lines — no rule should match."""
    return OcrResult(
        source_path=Path("empty.pdf"),
        content_hash="0" * 64,
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=0)],
        lines=[],
    )


@pytest.fixture()
def ambiguous_ocr() -> OcrResult:
    """An OcrResult with text that could match multiple gross-pay patterns.

    Contains both "Total Payment to Carrier: $750.00" and "Agent Pays Carrier\\n$820".
    The first-match-wins rule means only "total_payment_to_carrier" should fire.
    """
    lines_data = [
        ("Total Payment to Carrier: $750.00", 1),
        ("Agent Pays Carrier", 1),
        ("$820", 1),
    ]
    lines: list[OcrLine] = []
    offset = 0
    for i, (text, page) in enumerate(lines_data):
        start = offset
        end = offset + len(text)
        lines.append(
            OcrLine(
                text=text,
                page_number=page,
                bounding_box=BoundingBox(x=1.0, y=float(i + 1), width=3.0, height=0.25),
                char_start=start,
                char_end=end,
            )
        )
        offset = end + 1  # \n separator

    return OcrResult(
        source_path=Path("ambiguous.pdf"),
        content_hash="a" * 64,
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=3)],
        lines=lines,
    )
