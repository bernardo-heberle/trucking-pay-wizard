"""Unit tests for src.report.pdf_builder."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox
from src.report.pdf_builder import build_pdf
from tests.unit.report.conftest import make_extraction_result


class TestCombinedPdfStructure:

    def test_page_count_single_document(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """1 index page + 1 source page = 2 total."""
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        assert len(doc) == 2
        doc.close()

    def test_page_count_multiple_documents(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        """1 index + 1 (source_a) + 2 (source_b) = 4 total."""
        r1 = make_extraction_result(synthetic_source_pdf, content_hash="h1")
        r2 = make_extraction_result(synthetic_source_pdf_b, content_hash="h2", page_count=2)
        out = tmp_path / "combined.pdf"
        build_pdf([r1, r2], out)

        doc = fitz.open(str(out))
        assert len(doc) == 4
        doc.close()

    def test_returns_page_offsets(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        _, offsets = build_pdf([result], out)

        assert synthetic_source_pdf.name in offsets
        assert offsets[synthetic_source_pdf.name] == 2  # page 1 is index


class TestIndexPage:

    def test_index_contains_document_name(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_text = doc[0].get_text()
        assert synthetic_source_pdf.name in index_text
        doc.close()

    def test_index_contains_extracted_values(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_text = doc[0].get_text()
        assert "750.00" in index_text
        assert "03/12/2024" in index_text
        doc.close()


class TestHighlightAnnotations:

    def test_highlights_exist_on_source_pages(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        # Source page is page index 1 (after index page at 0)
        source_page = doc[1]
        annots = list(source_page.annots() or [])
        assert len(annots) >= 1
        doc.close()

    def test_no_highlights_on_index_page(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_page = doc[0]
        annots = list(index_page.annots() or [])
        assert annots == []
        doc.close()


class TestImageSourceFiles:

    def test_image_file_embedded_as_page(self, tmp_path: Path) -> None:
        from PIL import Image

        img_path = tmp_path / "photo.png"
        Image.new("RGB", (200, 300), color=(128, 128, 128)).save(str(img_path))

        result = make_extraction_result(img_path, fields=[])
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        assert len(doc) == 2  # index + 1 image page
        doc.close()
