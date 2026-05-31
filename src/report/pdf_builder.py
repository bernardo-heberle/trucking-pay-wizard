from __future__ import annotations

from pathlib import Path

import fitz
from loguru import logger

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, ExtractedLoad
from src.report.exceptions import ReportAssemblyError

_HIGHLIGHT_COLOR = (0.0, 0.75, 0.85)  # cyan — neutral "extracted" marker


def build_pdf(
    results: list[DocumentExtractionResult],
    output_path: Path,
) -> tuple[Path, dict[str, int], dict[str, int]]:
    """Build a combined PDF with source pages and highlight annotations.

    High-confidence documents are truncated to the last page that carries a
    highlighted field.  All other documents are included in full so staff can
    find and mark the relevant pages manually.

    Callers are expected to pass only the documents that belong in the combined
    PDF (e.g. payment documents); any document in *results* is embedded.

    Returns ``(output_path, page_offsets, page_limits)`` where *page_offsets*
    maps each ``source_path.name`` to its 1-indexed starting page in the
    combined PDF and *page_limits* maps each name to the number of pages it
    occupies (after any high-confidence truncation).  Together they let the
    Excel exporter show the page range a document spans.

    Raises:
        ReportAssemblyError: A source document cannot be opened or embedded.
    """
    page_offsets: dict[str, int] = {}

    # Pre-compute the effective (possibly truncated) page count for each document.
    page_limits: dict[str, int] = {
        result.source_path.name: _compute_page_limit(result)
        for result in results
    }

    # Source pages start at page 1 (1-indexed).
    current_page = 1
    for result in results:
        page_offsets[result.source_path.name] = current_page
        current_page += page_limits[result.source_path.name]

    combined = fitz.open()

    for result in results:
        try:
            max_pages = page_limits[result.source_path.name]
            _append_source_pages(combined, result, max_pages=max_pages)
        except Exception as exc:
            raise ReportAssemblyError(
                f"Failed to embed '{result.source_path.name}': {exc}"
            ) from exc

    _add_highlights(combined, results, page_offsets)

    combined.save(str(output_path))
    combined.close()

    logger.info(
        "Combined PDF saved to '{}' — {} document(s), {} page(s) total",
        output_path.name,
        len(results),
        current_page - 1,
    )

    return output_path, page_offsets, page_limits


def _all_fields(result: DocumentExtractionResult) -> list[ExtractedField]:
    """Return every pay and date field across all loads in *result*."""
    fields: list[ExtractedField] = []
    for load in result.loads:
        if load.pay is not None:
            fields.append(load.pay)
        if load.date is not None:
            fields.append(load.date)
    return fields


def _compute_page_limit(result: DocumentExtractionResult) -> int:
    """Return the number of pages to include for *result* in the combined PDF.

    High-confidence documents are truncated to the last highlighted page so
    the combined report stays concise.  All other documents (REVIEW or
    NOT_FOUND certainty) are included in full so staff can locate and verify
    the relevant fields manually.

    When a high-confidence document has no field location data the full page
    count is returned as a safe fallback.
    """
    total = result.page_count

    if result.overall_certainty() != Certainty.HIGH:
        return total

    # High-confidence: trim to the last page that carries a highlighted field.
    last_highlighted: int | None = None
    for field in _all_fields(result):
        for span in field.source_spans:
            if last_highlighted is None or span.page_number > last_highlighted:
                last_highlighted = span.page_number
        if field.source_page is not None:
            if last_highlighted is None or field.source_page > last_highlighted:
                last_highlighted = field.source_page

    if last_highlighted is None:
        return total

    return min(last_highlighted, total)


def _append_source_pages(
    combined: fitz.Document,
    result: DocumentExtractionResult,
    max_pages: int | None = None,
) -> None:
    """Append pages from a source document into *combined*.

    When *max_pages* is given only the first *max_pages* pages are inserted.
    Pass ``None`` (or omit) to include all pages.
    """
    src_path = result.source_path
    suffix = src_path.suffix.lower()

    if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        img = fitz.open(str(src_path))
        pdfbytes = img.convert_to_pdf()
        img.close()
        img_doc = fitz.open("pdf", pdfbytes)
        to_page = (max_pages - 1) if max_pages is not None else -1
        combined.insert_pdf(img_doc, to_page=to_page)
        img_doc.close()
    else:
        src_doc = fitz.open(str(src_path))
        to_page = (max_pages - 1) if max_pages is not None else -1
        combined.insert_pdf(src_doc, to_page=to_page)
        src_doc.close()


def _add_highlights(
    combined: fitz.Document,
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
) -> None:
    """Draw highlight annotations on extracted field locations.

    All fields across all loads use a single uniform highlight color
    regardless of certainty.  page_offsets values are 1-indexed; the
    combined doc is 0-indexed, so the 0-based index is ``offset - 1``.
    """
    for result in results:
        doc_name = result.source_path.name
        base_page_1indexed = page_offsets.get(doc_name, 1)
        base_page_0indexed = base_page_1indexed - 1

        for field in _all_fields(result):
            _highlight_field(combined, field, base_page_0indexed)


def _highlight_field(
    combined: fitz.Document,
    field: ExtractedField,
    base_page_0indexed: int,
) -> None:
    """Add highlight annotations for a single extracted field.

    All highlights use ``_HIGHLIGHT_COLOR`` — no metadata or comments are
    attached so the annotations look like plain human highlights in Adobe.
    """
    for span in field.source_spans:
        page_idx = base_page_0indexed + (span.page_number - 1)
        if page_idx < 0 or page_idx >= len(combined):
            logger.warning(
                "Highlight page index {} out of range for field '{}' — skipping",
                page_idx,
                field.name,
            )
            continue

        x, y, w, h = span.bounding_box.as_pts()
        rect = fitz.Rect(x, y, x + w, y + h)
        page = combined[page_idx]
        # OCR boxes are in the page's visual (rendered) frame, but annotations
        # are placed in the page's unrotated coordinate space.  For rotated
        # pages (e.g. landscape tables saved with /Rotate 90) the raw rect would
        # be drawn sideways, so map it back through the page's derotation matrix.
        if page.rotation:
            rect = rect * page.derotation_matrix
        annot = page.add_highlight_annot(rect)
        if annot:
            annot.set_colors(stroke=_HIGHLIGHT_COLOR)
            annot.update()
