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
_PAGE_WIDTH = 612
_PAGE_HEIGHT = 792
_INDEX_BOTTOM_LIMIT = _PAGE_HEIGHT - _INDEX_MARGIN


def build_pdf(
    results: list[DocumentExtractionResult],
    output_path: Path,
) -> tuple[Path, dict[str, int]]:
    """Build a combined PDF with index pages, source pages, and highlight annotations.

    The index may span multiple pages when there are many documents.  Page
    offsets account for however many index pages are needed.

    Returns ``(output_path, page_offsets)`` where *page_offsets* maps each
    ``source_path.name`` to its 1-indexed starting page in the combined PDF.
    This mapping feeds into the Excel exporter so users can cross-reference
    spreadsheet rows with PDF pages.

    Raises:
        ReportAssemblyError: A source document cannot be opened or embedded.
    """
    page_offsets: dict[str, int] = {}

    # Determine how many index pages are needed before computing source offsets.
    n_index_pages = _count_index_pages(results)

    # Source pages start immediately after the last index page (1-indexed).
    current_page = n_index_pages + 1
    for result in results:
        page_offsets[result.source_path.name] = current_page
        current_page += result.page_count

    # Build index pages first, then append source pages.
    combined = fitz.open()
    index_doc = _build_index_pages(results, page_offsets)
    combined.insert_pdf(index_doc)
    index_doc.close()

    for result in results:
        try:
            _append_source_pages(combined, result)
        except Exception as exc:
            raise ReportAssemblyError(
                f"Failed to embed '{result.source_path.name}': {exc}"
            ) from exc

    _add_highlights(combined, results, page_offsets)

    combined.save(str(output_path))
    combined.close()

    logger.info(
        "Combined PDF saved to '{}' — {} document(s), {} page(s) total ({} index page(s))",
        output_path.name,
        len(results),
        current_page - 1,
        n_index_pages,
    )

    return output_path, page_offsets


def _count_index_pages(results: list[DocumentExtractionResult]) -> int:
    """Return the number of index pages required for *results*.

    Mirrors the layout logic in ``_build_index_pages`` without rendering,
    so ``build_pdf`` can compute correct page offsets before building the PDF.
    """
    y = _INDEX_MARGIN + _INDEX_LINE_HEIGHT * 2  # space consumed by heading
    pages = 1

    for result in results:
        # Each document entry: one doc-name line, one line per field, then a gap.
        lines = [_INDEX_LINE_HEIGHT] * (1 + len(result.fields))
        gap = _INDEX_LINE_HEIGHT * 0.5

        for line_h in lines:
            if y + line_h > _INDEX_BOTTOM_LIMIT:
                pages += 1
                y = _INDEX_MARGIN
            y += line_h

        if y + gap <= _INDEX_BOTTOM_LIMIT:
            y += gap

    return pages


def _build_index_pages(
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
) -> fitz.Document:
    """Create a multi-page index document.

    Automatically overflows onto additional pages when content exceeds the
    printable area of a US Letter page.
    """
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
    x = _INDEX_MARGIN
    y = _INDEX_MARGIN

    page.insert_text(
        (x, y),
        "Combined Report — Document Index",
        fontsize=_INDEX_HEADING_FONT_SIZE,
        fontname="helv",
    )
    y += _INDEX_LINE_HEIGHT * 2

    def _ensure_space(needed: float) -> None:
        """Add a new page if *needed* pts of vertical space is unavailable."""
        nonlocal page, y
        if y + needed > _INDEX_BOTTOM_LIMIT:
            page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
            y = _INDEX_MARGIN

    for result in results:
        doc_name = result.source_path.name
        start_page = page_offsets.get(doc_name, 0)

        _ensure_space(_INDEX_LINE_HEIGHT)
        page.insert_text(
            (x, y),
            f"\u2022 {doc_name}  (page {start_page})",
            fontsize=_INDEX_FONT_SIZE,
            fontname="helv",
        )
        y += _INDEX_LINE_HEIGHT

        for field in result.fields:
            _ensure_space(_INDEX_LINE_HEIGHT)
            page.insert_text(
                (x, y),
                f"    {field.name}: {field.value}",
                fontsize=_INDEX_FONT_SIZE - 1,
                fontname="helv",
            )
            y += _INDEX_LINE_HEIGHT

        gap = _INDEX_LINE_HEIGHT * 0.5
        if y + gap <= _INDEX_BOTTOM_LIMIT:
            y += gap

    return doc


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


def _add_highlights(
    combined: fitz.Document,
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
) -> None:
    """Draw semi-transparent yellow highlight annotations on extracted field locations.

    page_offsets values are 1-indexed (page 1+ = index pages, then source pages).
    The combined doc is 0-indexed, so the 0-based index is ``offset - 1``.
    """
    for result in results:
        doc_name = result.source_path.name
        base_page_1indexed = page_offsets.get(doc_name, 2)
        base_page_0indexed = base_page_1indexed - 1

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
