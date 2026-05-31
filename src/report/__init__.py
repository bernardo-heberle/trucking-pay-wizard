from __future__ import annotations

import datetime
from pathlib import Path

from loguru import logger

from src.extract.models import DocumentExtractionResult
from src.report._date_parsing import parse_extracted_date
from src.report.excel_exporter import build_excel
from src.report.exceptions import ReportAssemblyError
from src.report.pdf_builder import build_pdf

_MAX_DATE = datetime.date.max


def build_report(
    results: list[DocumentExtractionResult],
    output_folder: Path,
    prefix: str = "",
    duplicate_map: dict[str, list[str]] | None = None,
) -> tuple[Path, Path]:
    """Orchestrate report assembly: combined PDF then Excel spreadsheet.

    Results are sorted chronologically by the extracted ``date`` field before
    building both outputs, so the combined PDF and Excel rows appear in date
    order.  Documents with no extracted date sort to the end.

    Only documents classified as payment documents are embedded in the combined
    PDF.  Non-payment documents are excluded from the PDF but still listed in
    the Excel spreadsheet (grayed out).  The Excel exporter owns its own tiered
    row ordering, so the full *results* set is handed to it unfiltered.

    When *prefix* is provided the output files are named
    ``<prefix>_combined.pdf`` and ``<prefix>_extracted.xlsx``.
    When omitted the legacy names ``combined_report.pdf`` /
    ``extracted_data.xlsx`` are used.

    *duplicate_map* maps a kept filename to the list of byte-identical filenames
    that were excluded from processing.  When provided, ``build_excel`` adds a
    note to each affected row so staff can see which files were skipped.

    Returns ``(pdf_path, excel_path)``.

    Raises:
        ReportAssemblyError: Either the PDF or Excel stage fails.
    """
    results = _sort_by_date(results)

    output_folder.mkdir(parents=True, exist_ok=True)

    if prefix:
        pdf_path = output_folder / f"{prefix}_combined.pdf"
        excel_path = output_folder / f"{prefix}_extracted.xlsx"
    else:
        pdf_path = output_folder / "combined_report.pdf"
        excel_path = output_folder / "extracted_data.xlsx"

    pdf_results = [r for r in results if r.is_payment_document]

    logger.info("Building combined PDF report …")
    pdf_path, page_offsets, page_limits = build_pdf(pdf_results, pdf_path)

    logger.info("Building Excel spreadsheet …")
    build_excel(
        results,
        excel_path,
        page_offsets,
        page_limits,
        duplicate_map=duplicate_map,
    )

    logger.info("Report assembly complete.")
    return pdf_path, excel_path


def _sort_by_date(
    results: list[DocumentExtractionResult],
) -> list[DocumentExtractionResult]:
    """Return *results* sorted chronologically by the extracted ``date`` field.

    Documents with no ``date`` field or an unparseable date value sort to the
    end, preserving their original relative order.
    """
    return sorted(results, key=lambda r: _date_sort_key(r))


def _date_sort_key(result: DocumentExtractionResult) -> datetime.date:
    """Extract the earliest comparable date from *result*, or ``date.max`` if absent.

    For multi-load documents the document is sorted by the earliest load date
    so it appears at the correct chronological position in the combined output.
    """
    earliest: datetime.date | None = None
    for load in result.loads:
        if load.date is not None and load.date.value:
            parsed = parse_extracted_date(load.date.value)
            if parsed is not None:
                if earliest is None or parsed < earliest:
                    earliest = parsed
    return earliest if earliest is not None else _MAX_DATE


__all__ = [
    "build_report",
    "build_pdf",
    "build_excel",
    "ReportAssemblyError",
]
