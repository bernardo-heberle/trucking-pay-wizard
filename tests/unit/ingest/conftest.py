"""Fixtures for ingest unit tests.

All fixtures here produce synthetic files via PyMuPDF or Pillow so the tests
run without needing any external documents on disk.
"""

from pathlib import Path

import fitz
import pytest
from PIL import Image


@pytest.fixture()
def synthetic_pdf(tmp_path: Path) -> Path:
    """A minimal single-page A4 PDF created in memory."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Synthetic test page")
    path = tmp_path / "synthetic.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def synthetic_multipage_pdf(tmp_path: Path) -> Path:
    """A 3-page PDF for ordering and page-count tests."""
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1} content")
    path = tmp_path / "multipage.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def png_file(tmp_path: Path) -> Path:
    """A small valid PNG image (100×100 white pixels)."""
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    path = tmp_path / "image.png"
    img.save(str(path))
    return path


@pytest.fixture()
def corrupt_pdf(tmp_path: Path) -> Path:
    """A .pdf file whose contents are not valid PDF data."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is definitely not a pdf \x00\x01\x02\x03")
    return path
