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
from tests.unit.report.conftest import make_extraction_result, make_load


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
        """1 (source_a) + 2 (source_b) = 3 total.

        r2's highlights are on page 2 so the HIGH-confidence limit is 2 (all pages included).
        """
        r1 = make_extraction_result(synthetic_source_pdf, content_hash="h1")
        r2 = make_extraction_result(
            synthetic_source_pdf_b,
            content_hash="h2",
            page_count=2,
            loads=[make_load(synthetic_source_pdf_b, pay_page=2, date_page=2)],
        )
        out = tmp_path / "combined.pdf"
        build_pdf([r1, r2], out)

        doc = fitz.open(str(out))
        assert len(doc) == 3
        doc.close()

    def test_returns_page_offsets(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "combined.pdf"
        _, offsets, limits = build_pdf([result], out)

        assert synthetic_source_pdf.name in offsets
        assert offsets[synthetic_source_pdf.name] == 1  # source starts at page 1
        assert limits[synthetic_source_pdf.name] == 1  # single-page document


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
    """Tests for confidence-based page selection."""

    def _make_result(
        self,
        source_path: Path,
        *,
        page_count: int = 10,
        highlight_page: int | None = None,
        high_confidence: bool = True,
    ) -> DocumentExtractionResult:
        """Build an extraction result for page-limit tests.

        When *high_confidence* is True both pay and date carry HIGH certainty
        so ``overall_certainty()`` returns HIGH and truncation applies.
        When False, date is omitted so ``overall_certainty()`` returns
        NOT_FOUND and all pages are kept.
        When *highlight_page* is None both fields have no location data
        (empty spans and source_page=None) — used to test the fallback path.
        """
        pay_certainty = Certainty.HIGH if high_confidence else Certainty.REVIEW
        if highlight_page is not None:
            pay = ExtractedField(
                name="pay",
                value="500.00",
                source_document=source_path.name,
                source_page=highlight_page,
                source_spans=[
                    SourceSpan(
                        page_number=highlight_page,
                        bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25),
                    )
                ],
                certainty=pay_certainty,
            )
            date: ExtractedField | None = (
                ExtractedField(
                    name="date",
                    value="01/01/2024",
                    source_document=source_path.name,
                    source_page=highlight_page,
                    source_spans=[
                        SourceSpan(
                            page_number=highlight_page,
                            bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25),
                        )
                    ],
                    certainty=Certainty.HIGH,
                )
                if high_confidence
                else None
            )
        else:
            pay = ExtractedField(
                name="pay",
                value="500.00",
                source_document=source_path.name,
                source_page=None,
                source_spans=[],
                certainty=pay_certainty,
            )
            date = (
                ExtractedField(
                    name="date",
                    value="01/01/2024",
                    source_document=source_path.name,
                    source_page=None,
                    source_spans=[],
                    certainty=Certainty.HIGH,
                )
                if high_confidence
                else None
            )

        return DocumentExtractionResult(
            source_path=source_path,
            content_hash="testhash",
            loads=[ExtractedLoad(index=1, pay=pay, date=date)],
            page_count=page_count,
        )

    def test_high_confidence_doc_truncated_to_last_highlight(
        self, synthetic_source_pdf_long: Path
    ) -> None:
        """High-confidence 10-page doc with highlight on page 3 → limit is 3 (no +2 buffer)."""
        result = self._make_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)

        assert _compute_page_limit(result) == 3

    def test_high_confidence_short_doc_truncated(self, synthetic_source_pdf: Path) -> None:
        """High-confidence 3-page doc is truncated even at short lengths — no length threshold."""
        result = self._make_result(synthetic_source_pdf, page_count=3, highlight_page=1)

        assert _compute_page_limit(result) == 1

    def test_not_high_confidence_keeps_all_pages(self, synthetic_source_pdf_long: Path) -> None:
        """Non-high-confidence doc keeps all pages regardless of where highlights are."""
        result = self._make_result(
            synthetic_source_pdf_long, page_count=10, highlight_page=3, high_confidence=False
        )

        assert _compute_page_limit(result) == 10

    def test_high_confidence_no_location_data_keeps_all_pages(
        self, synthetic_source_pdf_long: Path
    ) -> None:
        """High-confidence doc with no field location data falls back to all pages."""
        result = self._make_result(synthetic_source_pdf_long, page_count=10, highlight_page=None)

        assert _compute_page_limit(result) == 10

    def test_truncation_capped_at_total_pages(self, synthetic_source_pdf_long: Path) -> None:
        """High-confidence doc with highlight on page 9 of 10 → limit is 9, not beyond total."""
        result = self._make_result(synthetic_source_pdf_long, page_count=10, highlight_page=9)

        assert _compute_page_limit(result) == 9

    def test_combined_pdf_page_count_reflects_truncation(
        self, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Combined PDF must contain exactly 3 pages for a high-confidence doc with highlight on page 3."""
        result = self._make_result(synthetic_source_pdf_long, page_count=10, highlight_page=3)
        out = tmp_path / "combined.pdf"
        build_pdf([result], out)

        doc = fitz.open(str(out))
        assert len(doc) == 3
        doc.close()

    def test_page_offsets_use_truncated_count(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Page offsets must account for the truncated page count of earlier docs."""
        r_short = make_extraction_result(synthetic_source_pdf, content_hash="short")
        r_long = self._make_result(
            synthetic_source_pdf_long, page_count=10, highlight_page=3
        )
        # r_short: HIGH certainty, pay+date on page 1 → limit 1
        # r_long: HIGH certainty, highlight page 3 → limit 3
        # short starts at 1, long starts at 2
        out = tmp_path / "combined.pdf"
        _, offsets, _limits = build_pdf([r_short, r_long], out)

        assert offsets[synthetic_source_pdf.name] == 1
        assert offsets[synthetic_source_pdf_long.name] == 2

    def test_highlights_land_on_correct_page_after_truncation(
        self, synthetic_source_pdf_long: Path, tmp_path: Path
    ) -> None:
        """Annotation for the highlighted field must be on the correct page in the combined PDF."""
        result = self._make_result(
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


class TestRotatedPageHighlights:
    """Highlights must land on the marked text even on rotated source pages.

    OCR runs on the rendered (visual) image, so its bounding boxes are in the
    page's visual frame.  Annotations are stored in the page's unrotated frame,
    so the builder must map the box through the page's derotation matrix.  These
    tests build a source page, place real text, feed the visual-frame box that
    OCR would have produced, and assert the resulting highlight actually covers
    that text.
    """

    _MARKER = "PAYVALUE12345"

    def _build_source(self, tmp_path: Path, rotation: int) -> Path:
        doc = fitz.open()
        # Portrait media box; rotation 90 displays it as a landscape page,
        # mirroring the real ArcBest table pages (mediabox 612x792, /Rotate 90).
        page = doc.new_page(width=612, height=792)
        page.set_rotation(rotation)
        page.insert_text((120, 200), self._MARKER, fontsize=12)
        path = tmp_path / f"rotated_{rotation}.pdf"
        doc.save(str(path))
        doc.close()
        return path

    def _visual_box_for_marker(self, source_path: Path) -> tuple[BoundingBox, fitz.Rect]:
        """Return (OCR-style visual-frame box in inches, unrotated text rect in pts)."""
        doc = fitz.open(str(source_path))
        page = doc[0]
        text_rect = page.search_for(self._MARKER)[0]  # unrotated (mediabox) coords
        # OCR sees the rendered/visual frame, so convert via the rotation matrix.
        visual = (text_rect * page.rotation_matrix).normalize()
        doc.close()
        bbox = BoundingBox(
            x=visual.x0 / 72,
            y=visual.y0 / 72,
            width=visual.width / 72,
            height=visual.height / 72,
        )
        return bbox, text_rect

    def _result_marking_text(self, source_path: Path, bbox: BoundingBox) -> DocumentExtractionResult:
        return make_extraction_result(
            source_path,
            fields=[
                ExtractedField(
                    name="pay",
                    value=self._MARKER,
                    source_document=source_path.name,
                    source_page=1,
                    source_spans=[SourceSpan(page_number=1, bounding_box=bbox)],
                    certainty=Certainty.HIGH,
                ),
            ],
        )

    @pytest.mark.parametrize("rotation", [0, 90], ids=["unrotated", "rotated_90"])
    def test_highlight_covers_marked_text(self, rotation: int, tmp_path: Path) -> None:
        source = self._build_source(tmp_path, rotation)
        bbox, _ = self._visual_box_for_marker(source)
        result = self._result_marking_text(source, bbox)
        out = tmp_path / f"combined_{rotation}.pdf"

        build_pdf([result], out)

        doc = fitz.open(str(out))
        page = doc[0]
        annots = list(page.annots() or [])
        assert len(annots) == 1
        annot_rect = annots[0].rect
        text_rect = page.search_for(self._MARKER)[0]
        overlap = (annot_rect & text_rect).get_area()
        # The highlight must cover the bulk of the text it marks.  Without the
        # derotation fix the rotated box would land elsewhere on the page and
        # overlap would be zero.
        assert overlap > 0.5 * text_rect.get_area()
        doc.close()
