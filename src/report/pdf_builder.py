from __future__ import annotations

from pathlib import Path

import fitz
from loguru import logger

from src.extract.models import DocumentExtractionResult, ExtractedField
from src.report.exceptions import ReportAssemblyError

_INDEX_FONT_SIZE = 11
_INDEX_HEADING_FONT_SIZE = 16
_INDEX_LINE_HEIGHT = 16
_INDEX_MARGIN = 54  # 0.75 inch


def build_pdf(
    results: list[DocumentExtractionResult],
    output_path: Path,
) -> tuple[Path, dict[str, int]]:
    """Build a combined PDF with an index page, source pages, and highlight annotations.

    Returns ``(output_path, page_offsets)`` where *page_offsets* maps each
    ``source_path.name`` to its 1-indexed starting page in the combined PDF
    (after the index page).  This mapping feeds into the Excel exporter so
    users can cross-reference spreadsheet rows with PDF pages.

    Raises:
        ReportAssemblyError: A source document cannot be opened or embedded.
    """
    page_offsets: dict[str, int] = {}

    # Pre-compute page offsets (index page = page 1, source pages start at 2).
    current_page = 2
    for result in results:
        page_offsets[result.source_path.name] = current_page
        current_page += result.page_count

    # Build the index page first so it is page 0 in the combined doc.
    combined = fitz.open()
    index_doc = _build_index_page(results, page_offsets)
    combined.insert_pdf(index_doc)
    index_doc.close()

    # Append source pages (page 0 = index, so source pages start at index 1).
    for result in results:
        try:
            _append_source_pages(combined, result)
        except Exception as exc:
            raise ReportAssemblyError(
                f"Failed to embed '{result.source_path.name}': {exc}"
            ) from exc

    # Highlights go on source pages which now start at 0-based index 1.
    _add_highlights(combined, results, page_offsets)

    combined.save(str(output_path))
    combined.close()

    logger.info(
        "Combined PDF saved to '{}' — {} document(s), {} page(s) total",
        output_path.name,
        len(results),
        current_page - 1,
    )

    return output_path, page_offsets


def _append_source_pages(combined: fitz.Document, result: DocumentExtractionResult) -> None:
    """Append all pages from a source document into *combined*."""
    src_path = result.source_path
    suffix = src_path.suffix.lower()

    if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        img = fitz.open(str(src_path))
        pdfbytes = img.convert_to_pdf()
        img.close()
        img_doc = fitz.open("pdf", pdfbytes)
        combined.insert_pdf(img_doc)
        img_doc.close()
    else:
        src_doc = fitz.open(str(src_path))
        combined.insert_pdf(src_doc)
        src_doc.close()


def _build_index_page(
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
) -> fitz.Document:
    """Create a single-page document containing the report index."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter

    y = _INDEX_MARGIN
    x = _INDEX_MARGIN

    page.insert_text(
        (x, y),
        "Combined Report — Document Index",
        fontsize=_INDEX_HEADING_FONT_SIZE,
        fontname="helv",
    )
    y += _INDEX_LINE_HEIGHT * 2

    for result in results:
        doc_name = result.source_path.name
        start_page = page_offsets.get(doc_name, 0)

        line = f"• {doc_name}  (page {start_page})"
        page.insert_text((x, y), line, fontsize=_INDEX_FONT_SIZE, fontname="helv")
        y += _INDEX_LINE_HEIGHT

        for field in result.fields:
            summary = f"    {field.name}: {field.value}"
            page.insert_text((x, y), summary, fontsize=_INDEX_FONT_SIZE - 1, fontname="helv")
            y += _INDEX_LINE_HEIGHT

        y += _INDEX_LINE_HEIGHT * 0.5

    return doc


def _add_highlights(
    combined: fitz.Document,
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
) -> None:
    """Draw semi-transparent yellow highlight annotations on extracted field locations.

    page_offsets values are 1-indexed (page 1 = index, page 2+ = source pages).
    The combined doc is 0-indexed, so the 0-based index is ``offset - 1``.
    """
    for result in results:
        doc_name = result.source_path.name
        base_page_1indexed = page_offsets.get(doc_name, 2)
        base_page_0indexed = base_page_1indexed - 1  # 0-based index into combined

        for field in result.fields:
            _highlight_field(combined, field, base_page_0indexed)


def _highlight_field(
    combined: fitz.Document,
    field: ExtractedField,
    base_page_0indexed: int,
) -> None:
    """Add highlight annotations for a single extracted field."""
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
        annot = page.add_highlight_annot(rect)
        if annot:
            annot.update()
