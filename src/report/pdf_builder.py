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

_HIGHLIGHT_COLOR = (0.0, 0.75, 0.85)  # cyan — neutral "extracted" marker
_COLOR_RED = (0.8, 0.0, 0.0)  # reserved for error notices on index page


def build_pdf(
    results: list[DocumentExtractionResult],
    output_path: Path,
) -> tuple[Path, dict[str, int]]:
    """Build a combined PDF with index pages, source pages, and highlight annotations.

    Long documents (more than 3 pages) are truncated to the last page that
    carries a highlighted field plus two additional pages.  Documents with no
    field location information are never truncated so staff can find and mark
    the relevant pages manually.

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

    # Pre-compute the effective (possibly truncated) page count for each document.
    page_limits: dict[str, int] = {
        result.source_path.name: _compute_page_limit(result)
        for result in results
    }

    # Determine how many index pages are needed before computing source offsets.
    n_index_pages = _count_index_pages(results, page_limits)

    # Source pages start immediately after the last index page (1-indexed).
    current_page = n_index_pages + 1
    for result in results:
        page_offsets[result.source_path.name] = current_page
        current_page += page_limits[result.source_path.name]

    # Build index pages first, then append source pages.
    combined = fitz.open()
    index_doc = _build_index_pages(results, page_offsets, page_limits)
    combined.insert_pdf(index_doc)
    index_doc.close()

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
        "Combined PDF saved to '{}' — {} document(s), {} page(s) total ({} index page(s))",
        output_path.name,
        len(results),
        current_page - 1,
        n_index_pages,
    )

    return output_path, page_offsets


_TRUNCATION_THRESHOLD = 3  # documents with more pages than this may be truncated


def _compute_page_limit(result: DocumentExtractionResult) -> int:
    """Return the number of pages to include for *result* in the combined PDF.

    If the document has more than ``_TRUNCATION_THRESHOLD`` pages AND at
    least one field carries page-location information, the limit is the last
    highlighted page plus two more (capped at the total page count).

    When no field location data is available the document is never truncated
    — staff need all pages to locate and highlight fields manually.
    """
    total = result.page_count
    if total <= _TRUNCATION_THRESHOLD:
        return total

    # Collect the highest page number mentioned in any field's spans or source_page.
    last_highlighted: int | None = None
    for field in result.fields:
        for span in field.source_spans:
            if last_highlighted is None or span.page_number > last_highlighted:
                last_highlighted = span.page_number
        if field.source_page is not None:
            if last_highlighted is None or field.source_page > last_highlighted:
                last_highlighted = field.source_page

    if last_highlighted is None:
        # No location data — keep all pages so staff can find fields manually.
        return total

    return min(last_highlighted + 2, total)


def _count_index_pages(
    results: list[DocumentExtractionResult],
    page_limits: dict[str, int],
) -> int:
    """Return the number of index pages required for *results*.

    Mirrors the layout logic in ``_build_index_pages`` without rendering,
    so ``build_pdf`` can compute correct page offsets before building the PDF.
    Each document entry is treated as an atomic block — it is never split
    across a page boundary.

    A truncation notice line is added for documents whose page limit is less
    than their total page count (matching ``_build_index_pages`` layout).
    """
    y = _INDEX_MARGIN + _INDEX_LINE_HEIGHT * 2  # space consumed by heading
    pages = 1

    for result in results:
        doc_name = result.source_path.name
        effective_pages = page_limits.get(doc_name, result.page_count)
        is_truncated = effective_pages < result.page_count

        # Failed extractions: name line + error line.
        # Successful: name line + one line per field + optional truncation notice.
        if result.extraction_error:
            entry_height = _INDEX_LINE_HEIGHT * 2
        else:
            extra = 1 if is_truncated else 0
            entry_height = _INDEX_LINE_HEIGHT * (1 + len(result.fields) + extra)
        gap = _INDEX_LINE_HEIGHT * 0.5

        # Move to a new page only when we are not already at the top of one
        # (guards against an entry taller than a full page).
        if y > _INDEX_MARGIN and y + entry_height > _INDEX_BOTTOM_LIMIT:
            pages += 1
            y = _INDEX_MARGIN

        y += entry_height

        if y + gap <= _INDEX_BOTTOM_LIMIT:
            y += gap

    return pages


def _build_index_pages(
    results: list[DocumentExtractionResult],
    page_offsets: dict[str, int],
    page_limits: dict[str, int],
) -> fitz.Document:
    """Create a multi-page index document.

    Document names and field lines use ``_HIGHLIGHT_COLOR``; error entries
    use ``_COLOR_RED``.  A truncation notice is added for documents whose
    page limit is less than their total page count.  Automatically overflows
    onto additional pages when content exceeds the printable area of a US
    Letter page.
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

    for result in results:
        doc_name = result.source_path.name
        start_page = page_offsets.get(doc_name, 0)
        effective_pages = page_limits.get(doc_name, result.page_count)
        is_truncated = effective_pages < result.page_count

        if result.extraction_error:
            entry_height = _INDEX_LINE_HEIGHT * 2
        else:
            extra = 1 if is_truncated else 0
            entry_height = _INDEX_LINE_HEIGHT * (1 + len(result.fields) + extra)

        if y > _INDEX_MARGIN and y + entry_height > _INDEX_BOTTOM_LIMIT:
            page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
            y = _INDEX_MARGIN

        doc_color = _COLOR_RED if result.extraction_error else _HIGHLIGHT_COLOR
        page.insert_text(
            (x, y),
            f"\u2022 {doc_name}  (page {start_page})",
            fontsize=_INDEX_FONT_SIZE,
            fontname="helv",
            color=doc_color,
        )
        y += _INDEX_LINE_HEIGHT

        if result.extraction_error:
            page.insert_text(
                (x, y),
                f"    \u26a0 Extraction failed — review manually",
                fontsize=_INDEX_FONT_SIZE - 1,
                fontname="helv",
                color=_COLOR_RED,
            )
            y += _INDEX_LINE_HEIGHT
        else:
            for field in result.fields:
                page.insert_text(
                    (x, y),
                    f"    {field.name}: {field.value}",
                    fontsize=_INDEX_FONT_SIZE - 1,
                    fontname="helv",
                    color=_HIGHLIGHT_COLOR,
                )
                y += _INDEX_LINE_HEIGHT

            if is_truncated:
                page.insert_text(
                    (x, y),
                    f"    \u2026 showing {effective_pages} of {result.page_count} pages",
                    fontsize=_INDEX_FONT_SIZE - 1,
                    fontname="helv",
                    color=_HIGHLIGHT_COLOR,
                )
                y += _INDEX_LINE_HEIGHT

        gap = _INDEX_LINE_HEIGHT * 0.5
        if y + gap <= _INDEX_BOTTOM_LIMIT:
            y += gap

    return doc


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

    All fields use a single uniform highlight color regardless of certainty.
    page_offsets values are 1-indexed; the combined doc is 0-indexed, so the
    0-based index is ``offset - 1``.
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
        annot = page.add_highlight_annot(rect)
        if annot:
            annot.set_colors(stroke=_HIGHLIGHT_COLOR)
            annot.update()
