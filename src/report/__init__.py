from __future__ import annotations

import datetime
from pathlib import Path

from loguru import logger

from src.extract.models import DocumentExtractionResult
from src.report.excel_exporter import build_excel
from src.report.exceptions import ReportAssemblyError
from src.report.pdf_builder import build_pdf

_MAX_DATE = datetime.date.max


def build_report(
    results: list[DocumentExtractionResult],
    output_folder: Path,
    prefix: str = "",
) -> tuple[Path, Path]:
    """Orchestrate report assembly: combined PDF then Excel spreadsheet.

    Results are sorted chronologically by the extracted ``date`` field before
    building both outputs, so the combined PDF and Excel rows appear in date
    order.  Documents with no extracted date sort to the end.

    When *prefix* is provided the output files are named
    ``<prefix>_combined.pdf`` and ``<prefix>_extracted.xlsx``.
    When omitted the legacy names ``combined_report.pdf`` /
    ``extracted_data.xlsx`` are used.

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

    logger.info("Building combined PDF report …")
    pdf_path, page_offsets = build_pdf(results, pdf_path)

    logger.info("Building Excel spreadsheet …")
    build_excel(results, excel_path, page_offsets)

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
    """Extract a comparable date from *result*, or ``date.max`` if absent."""
    for field in result.fields:
        if field.name == "date":
            parsed = _parse_date(field.value)
            if parsed is not None:
                return parsed
    return _MAX_DATE


def _parse_date(value: str) -> datetime.date | None:
    """Parse the raw date string produced by the extraction rules.

    Handles:
      - ``M/D/YYYY`` and ``MM/DD/YYYY`` (numeric, slash-separated)
      - ``Month D, YYYY`` (e.g. ``March 13, 2024`` or ``Mar 11, 2024``)
    """
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


__all__ = [
    "build_report",
    "build_pdf",
    "build_excel",
    "ReportAssemblyError",
]
