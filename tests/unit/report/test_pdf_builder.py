"""Unit tests for src.report.pdf_builder."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, ExtractedLoad, SourceSpan
from src.ocr.models import BoundingBox
from src.report.pdf_builder import (
    _compute_page_limit,
    _HIGHLIGHT_COLOR,
    build_pdf,
)
from tests.unit.report.conftest import make_extraction_result


class TestCombinedPdfStructure:

    def test_page_count_single_document(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """1 source page = 1 total."""
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        assert len(doc) == 1
        doc.close()

    def test_page_count_multiple_documents(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        """1 (source_a) + 2 (source_b) = 3 total."""
        r1 = make_extraction_result(synthetic_source_pdf, content_hash="h1")
        r2 = make_extraction_result(synthetic_source_pdf_b, content_hash="h2", page_count=2)
        out = tmp_path / "combined.pdf"
        build_pdf([r1, r2], out)

        doc = fitz.open(str(out))
        assert len(doc) == 3
        doc.close()

    def test_returns_page_offsets(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        _, offsets = build_pdf([result], out)

        assert synthetic_source_pdf.name in offsets
        assert offsets[synthetic_source_pdf.name] == 1  # source starts at page 1


class TestHighlightAnnotations:

    def test_highlights_exist_on_source_pages(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        # Source page is now at index 0 (no preceding index page).
        # The default fixture has exactly 2 fields with spans.
        source_page = doc[0]
        annots = list(source_page.annots() or [])
        assert len(annots) == 2
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
        assert len(doc) == 1  # 1 image page, no index
        # The source page must actually contain an embedded image XObject —
        # a mutant omitting the image would still produce a 1-page PDF.
        source_page = doc[0]
        images = source_page.get_images(full=True)
        assert len(images) >= 1, "Source page contains no embedded image XObject"
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
        annots = list(doc[0].annots() or [])
        assert len(annots) == 1
        stroke = tuple(round(c, 2) for c in annots[0].colors["stroke"])
        assert stroke == tuple(round(c, 2) for c in _HIGHLIGHT_COLOR)
        doc.close()

    def test_review_certainty_uses_same_highlight_color(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = self._make_result_with_span(synthetic_source_pdf, Certainty.REVIEW)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[0].annots() or [])
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
        annots = list(doc[0].annots() or [])
        assert len(annots) == 2
        expected = tuple(round(c, 2) for c in _HIGHLIGHT_COLOR)
        for annot in annots:
            stroke = tuple(round(c, 2) for c in annot.colors["stroke"])
            assert stroke == expected
        doc.close()

    def test_highlight_color_is_not_red(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Highlight color must not be red."""
        _COLOR_RED = (0.8, 0.0, 0.0)
        result = self._make_result_with_span(synthetic_source_pdf, Certainty.HIGH)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[0].annots() or [])
        stroke = tuple(round(c, 2) for c in annots[0].colors["stroke"])
        assert stroke != tuple(round(c, 2) for c in _COLOR_RED)
        doc.close()

    def test_failed_extraction_produces_no_highlights(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Failed extractions have no source-page highlights."""
        result = DocumentExtractionResult(
            source_path=synthetic_source_pdf,
            content_hash="err123",
            loads=[],
            page_count=1,
            extraction_error="LLM timeout",
        )
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        annots = list(doc[0].annots() or [])
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
            pay = ExtractedField(
                name="pay", value="500.00",
                source_document=source_path.name, source_page=highlight_page,
                source_spans=[
                    SourceSpan(
                        page_number=highlight_page,
                        bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25),
                    )
                ],
                certainty=Certainty.HIGH,
            )
        else:
            pay = ExtractedField(
                name="pay", value="500.00",
                source_document=source_path.name, source_page=None,
                source_spans=[],
                certainty=Certainty.HIGH,
            )
        return DocumentExtractionResult(
            source_path=source_path,
            content_hash="longhash",
            loads=[ExtractedLoad(index=1, pay=pay, date=None)],
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
        """Combined PDF must contain exactly 5 pages (not 10) for a truncated doc."""
        result = self._make_long_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        # 5 source pages (3 highlight page + 2 more), no index page
        assert len(doc) == 5
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
        # short starts at 1, long starts at 2 (no index page)
        out = tmp_path / "combined.pdf"
        _, offsets = build_pdf([r_short, r_long], out)

        assert offsets[synthetic_source_pdf.name] == 1
        assert offsets[synthetic_source_pdf_long.name] == 2

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
        # Source starts at page offset 0 (0-indexed); highlight is on source page 3
        # → combined index 0 + (3 - 1) = 2
        highlight_page_0indexed = 0 + (3 - 1)
        annots = list(doc[highlight_page_0indexed].annots() or [])
        assert len(annots) >= 1
        doc.close()
