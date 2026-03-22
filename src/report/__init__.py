from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.extract.models import DocumentExtractionResult
from src.report.excel_exporter import build_excel
from src.report.exceptions import ReportAssemblyError
from src.report.pdf_builder import build_pdf


def build_report(
    results: list[DocumentExtractionResult],
    output_folder: Path,
    prefix: str = "",
) -> tuple[Path, Path]:
    """Orchestrate report assembly: combined PDF then Excel spreadsheet.

    When *prefix* is provided the output files are named
    ``<prefix>_combined.pdf`` and ``<prefix>_extracted.xlsx``.
    When omitted the legacy names ``combined_report.pdf`` /
    ``extracted_data.xlsx`` are used.

    Returns ``(pdf_path, excel_path)``.

    Raises:
        ReportAssemblyError: Either the PDF or Excel stage fails.
    """
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


__all__ = [
    "build_report",
    "build_pdf",
    "build_excel",
    "ReportAssemblyError",
]
