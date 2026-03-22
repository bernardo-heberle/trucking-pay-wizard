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
) -> tuple[Path, Path]:
    """Orchestrate report assembly: combined PDF then Excel spreadsheet.

    Returns ``(pdf_path, excel_path)``.

    Raises:
        ReportAssemblyError: Either the PDF or Excel stage fails.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

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
