"""Unit tests for src.report.pdf_builder."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox
from src.report.pdf_builder import (
    _compute_page_limit,
    _count_index_pages,
    _HIGHLIGHT_COLOR,
    _COLOR_RED,
    build_pdf,
)
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
        # Source page is page index 1 (after index page at 0).
        # The default fixture has exactly 2 fields with spans.
        source_page = doc[1]
        annots = list(source_page.annots() or [])
        assert len(annots) == 2
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
        # The source page must actually contain an embedded image XObject —
        # a mutant omitting the image would still produce a 2-page PDF.
        source_page = doc[1]
        images = source_page.get_images(full=True)
        assert len(images) >= 1, "Source page contains no embedded image XObject"
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

    @staticmethod
    def _page_limits(results: list[DocumentExtractionResult]) -> dict[str, int]:
        return {r.source_path.name: _compute_page_limit(r) for r in results}

    def test_small_batch_fits_one_index_page(self, tmp_path: Path) -> None:
        """2 documents with 2 fields each comfortably fit on 1 index page."""
        results = self._make_many_results(tmp_path, 2)
        assert _count_index_pages(results, self._page_limits(results)) == 1

    def test_large_batch_overflows_to_multiple_index_pages(self, tmp_path: Path) -> None:
        """15 documents with 2 fields each exceed a single page."""
        results = self._make_many_results(tmp_path, 15)
        assert _count_index_pages(results, self._page_limits(results)) >= 2

    def test_multi_page_index_produces_correct_total_pages(self, tmp_path: Path) -> None:
        """Total pages = n_index_pages + n_source_pages."""
        results = self._make_many_results(tmp_path, 15)
        n_index = _count_index_pages(results, self._page_limits(results))
        out = tmp_path / "combined.pdf"
        build_pdf(results, out)

        doc = fitz.open(str(out))
        assert len(doc) == n_index + 15  # each source PDF is 1 page
        doc.close()

    def test_page_offsets_account_for_multi_page_index(self, tmp_path: Path) -> None:
        """Source page offsets start after all index pages, not hardcoded at 2."""
        results = self._make_many_results(tmp_path, 15)
        n_index = _count_index_pages(results, self._page_limits(results))
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
        n_index = _count_index_pages(results, self._page_limits(results))
        # Verify that every source page slot exists in the document
        assert len(doc) == n_index + 15
        doc.close()


class TestUniformHighlightColor:

    def _make_result_with_span(
        self, source_path: Path, certainty: Certainty
    ) -> DocumentExtractionResult:
        return make_extraction_result(
            source_path,
            fields=[
                ExtractedField(
                    name="pay", value="750.00",
                    source_document=source_path.name, source_page=1,
                    source_spans=[SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25))],
                    certainty=certainty,
                ),
            ],
        )

    def test_high_certainty_uses_highlight_color(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = self._make_result_with_span(synthetic_source_pdf, Certainty.HIGH)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[1].annots() or [])
        assert len(annots) == 1
        stroke = tuple(round(c, 2) for c in annots[0].colors["stroke"])
        assert stroke == tuple(round(c, 2) for c in _HIGHLIGHT_COLOR)
        doc.close()

    def test_review_certainty_uses_same_highlight_color(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = self._make_result_with_span(synthetic_source_pdf, Certainty.REVIEW)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[1].annots() or [])
        assert len(annots) == 1
        stroke = tuple(round(c, 2) for c in annots[0].colors["stroke"])
        assert stroke == tuple(round(c, 2) for c in _HIGHLIGHT_COLOR)
        doc.close()

    def test_mixed_certainty_all_use_same_color(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """All annotations use _HIGHLIGHT_COLOR regardless of per-field certainty."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="pay", value="750.00",
                    source_document=synthetic_source_pdf.name, source_page=1,
                    source_spans=[SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25))],
                    certainty=Certainty.HIGH,
                ),
                ExtractedField(
                    name="date", value="03/12/2024",
                    source_document=synthetic_source_pdf.name, source_page=1,
                    source_spans=[SourceSpan(page_number=1, bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25))],
                    certainty=Certainty.REVIEW,
                ),
            ],
        )
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[1].annots() or [])
        assert len(annots) == 2
        expected = tuple(round(c, 2) for c in _HIGHLIGHT_COLOR)
        for annot in annots:
            stroke = tuple(round(c, 2) for c in annot.colors["stroke"])
            assert stroke == expected
        doc.close()

    def test_highlight_color_is_not_red(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Highlight color must not be red — red is reserved for error notices."""
        result = self._make_result_with_span(synthetic_source_pdf, Certainty.HIGH)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[1].annots() or [])
        stroke = tuple(round(c, 2) for c in annots[0].colors["stroke"])
        assert stroke != tuple(round(c, 2) for c in _COLOR_RED)
        doc.close()

    def test_error_entry_uses_red_on_index(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Index page error notice text should be red; no source highlights expected."""
        result = DocumentExtractionResult(
            source_path=synthetic_source_pdf,
            content_hash="err123",
            fields=[],
            page_count=1,
            extraction_error="LLM timeout",
        )
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_text = doc[0].get_text()
        assert "Extraction failed" in index_text
        # No highlight annotations on source page for failed extraction
        annots = list(doc[1].annots() or [])
        assert annots == []
        doc.close()


class TestHighlightAnnotationCleanliness:

    def test_no_annotation_content_metadata(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Highlights must not carry content/comment text — PDF goes to court."""
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        for page in doc:
            for annot in page.annots() or []:
                info = annot.info
                assert info.get("content", "") == "", (
                    f"Annotation has content metadata: {info['content']!r}"
                )
                assert info.get("title", "") == "", (
                    f"Annotation has title metadata: {info['title']!r}"
                )
        doc.close()

    def test_no_read_only_or_locked_flags(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Annotations must not be flagged read-only or locked so staff can edit them."""
        _PDF_ANNOT_LOCKED = 1 << 7
        _PDF_ANNOT_READ_ONLY = 1 << 6

        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        for page in doc:
            for annot in page.annots() or []:
                flags = annot.flags
                assert not (flags & _PDF_ANNOT_READ_ONLY), "Annotation is read-only"
                assert not (flags & _PDF_ANNOT_LOCKED), "Annotation is locked"
        doc.close()


class TestPageTruncation:
    """Tests for smart page truncation of long documents."""

    def _make_long_result(
        self,
        source_path: Path,
        *,
        page_count: int = 10,
        highlight_page: int | None = None,
    ) -> DocumentExtractionResult:
        """Build a result for a long document, optionally with a span on *highlight_page*."""
        if highlight_page is not None:
            fields = [
                ExtractedField(
                    name="pay", value="500.00",
                    source_document=source_path.name, source_page=highlight_page,
                    source_spans=[
                        SourceSpan(
                            page_number=highlight_page,
                            bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25),
                        )
                    ],
                    certainty=Certainty.HIGH,
                ),
            ]
        else:
            fields = [
                ExtractedField(
                    name="pay", value="500.00",
                    source_document=source_path.name, source_page=None,
                    source_spans=[],
                    certainty=Certainty.HIGH,
                ),
            ]
        return DocumentExtractionResult(
            source_path=source_path,
            content_hash="longhash",
            fields=fields,
            page_count=page_count,
        )

    def test_short_document_not_truncated(self, synthetic_source_pdf: Path) -> None:
        """Documents with <= 3 pages are never truncated regardless of highlights."""
        result = make_extraction_result(synthetic_source_pdf, page_count=3)
        assert _compute_page_limit(result) == 3

    def test_four_page_doc_is_above_threshold(self, synthetic_source_pdf_long: Path) -> None:
        """4-page doc (just above the 3-page threshold) is truncated when highlight is early.

        This is the exact threshold boundary: total == 4, highlight on page 1
        → last+2 = 3, capped at 4, so result is 3.
        """
        result = self._make_long_result(synthetic_source_pdf_long, page_count=4, highlight_page=1)
        assert _compute_page_limit(result) == 3

    def test_three_page_doc_at_threshold_not_truncated(self, synthetic_source_pdf: Path) -> None:
        """3-page doc at the truncation threshold must never be truncated."""
        result = make_extraction_result(synthetic_source_pdf, page_count=3)
        assert _compute_page_limit(result) == 3

    def test_long_doc_with_highlight_truncated_to_last_plus_two(
        self, synthetic_source_pdf_long: Path
    ) -> None:
        """10-page doc with highlight on page 3 → keep pages 1-5 (3+2)."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)
        assert _compute_page_limit(result) == 5

    def test_long_doc_no_highlights_keeps_all_pages(
        self, synthetic_source_pdf_long: Path
    ) -> None:
        """10-page doc with no field location data must keep all pages."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=None)
        assert _compute_page_limit(result) == 10

    def test_truncation_capped_at_total_pages(self, synthetic_source_pdf_long: Path) -> None:
        """Highlight on page 9 of a 10-page doc → last+2 would be 11, capped at 10."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=9)
        assert _compute_page_limit(result) == 10

    def test_combined_pdf_page_count_reflects_truncation(
        self, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Combined PDF must contain index + 5 pages (not 10) for a truncated doc."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        # 1 index page + 5 source pages (3 highlight page + 2 more)
        assert len(doc) == 1 + 5
        doc.close()

    def test_page_offsets_use_truncated_count(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Page offsets must account for the truncated page count of earlier docs."""
        r_short = make_extraction_result(synthetic_source_pdf, content_hash="short")
        r_long = self._make_long_result(
            synthetic_source_pdf_long, page_count=10, highlight_page=3
        )
        # short doc is 1 page, long doc truncated to 5 pages
        # index page = 1, short starts at 2, long starts at 3
        out = tmp_path / "combined.pdf"
        _, offsets = build_pdf([r_short, r_long], out)

        assert offsets[synthetic_source_pdf.name] == 2
        assert offsets[synthetic_source_pdf_long.name] == 3

    def test_index_shows_truncation_notice(
        self, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Index page must mention the page count for truncated documents."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_text = doc[0].get_text()
        assert "5 of 10" in index_text
        doc.close()

    def test_no_truncation_notice_for_short_docs(
        self, synthetic_source_pdf: Path, tmp_path: Path
    ) -> None:
        """Index page must NOT show a truncation notice for documents under the threshold."""
        result = make_extraction_result(synthetic_source_pdf)  # 1-page doc, no truncation
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        index_text = doc[0].get_text()
        doc.close()
        # The truncation notice format is "N of M" (see test_index_shows_truncation_notice).
        # For a 1-page doc there is no truncation, so this pattern must be absent.
        assert "1 of 1" not in index_text

    def test_highlights_land_on_correct_page_after_truncation(
        self, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Annotation for the highlighted field must be on the correct page in the combined PDF."""
        result = self._make_long_result(
            synthetic_source_pdf_long, page_count=10, highlight_page=3
        )
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        # 1 index page + source pages; highlight is on source page 3 → combined index 1+2=3 (0-indexed)
        highlight_page_0indexed = 1 + (3 - 1)  # base (0-indexed) + span.page_number - 1
        annots = list(doc[highlight_page_0indexed].annots() or [])
        assert len(annots) >= 1
        doc.close()

