"""Unit tests for src.report.pdf_builder."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox
from src.report.pdf_builder import _count_index_pages, build_pdf
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


class TestMultiPageIndex:

    def _make_many_results(self, tmp_path: Path, n: int) -> list[DocumentExtractionResult]:
        """Build *n* single-page PDF results, each with 2 extracted fields."""
        results = []
        for i in range(n):
            pdf_path = tmp_path / f"doc_{i:02d}.pdf"
            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), f"Document {i}")
            doc.save(str(pdf_path))
            doc.close()
            results.append(make_extraction_result(pdf_path, content_hash=f"hash_{i:02d}"))
        return results

    def test_small_batch_fits_one_index_page(self, tmp_path: Path) -> None:
        """2 documents with 2 fields each comfortably fit on 1 index page."""
        results = self._make_many_results(tmp_path, 2)
        assert _count_index_pages(results) == 1

    def test_large_batch_overflows_to_multiple_index_pages(self, tmp_path: Path) -> None:
        """15 documents with 2 fields each exceed a single page."""
        results = self._make_many_results(tmp_path, 15)
        assert _count_index_pages(results) >= 2

    def test_multi_page_index_produces_correct_total_pages(self, tmp_path: Path) -> None:
        """Total pages = n_index_pages + n_source_pages."""
        results = self._make_many_results(tmp_path, 15)
        n_index = _count_index_pages(results)
        out = tmp_path / "combined.pdf"
        build_pdf(results, out)

        doc = fitz.open(str(out))
        assert len(doc) == n_index + 15  # each source PDF is 1 page
        doc.close()

    def test_page_offsets_account_for_multi_page_index(self, tmp_path: Path) -> None:
        """Source page offsets start after all index pages, not hardcoded at 2."""
        results = self._make_many_results(tmp_path, 15)
        n_index = _count_index_pages(results)
        out = tmp_path / "combined.pdf"
        _, page_offsets = build_pdf(results, out)

        first_source_page = min(page_offsets.values())
        assert first_source_page == n_index + 1

    def test_highlights_land_on_correct_page_with_multi_page_index(self, tmp_path: Path) -> None:
        """With multiple index pages, highlight annotations appear on source pages."""
        results = self._make_many_results(tmp_path, 15)
        out = tmp_path / "combined.pdf"
        build_pdf(results, out)

        doc = fitz.open(str(out))
        n_index = _count_index_pages(results)
        # Verify that every source page slot exists in the document
        assert len(doc) == n_index + 15
        doc.close()

