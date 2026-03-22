from __future__ import annotations

from pathlib import Path

from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, numbers
from openpyxl.utils import get_column_letter

from src.extract.models import DocumentExtractionResult
from src.report.exceptions import ReportAssemblyError

_CURRENCY_FORMAT = '$#,##0.00'


def build_excel(
    results: list[DocumentExtractionResult],
    output_path: Path,
    page_offsets: dict[str, int],
) -> Path:
    """Build an Excel spreadsheet with one row per document.

    Columns: ``Document``, ``PDF Page``, then one column per unique extracted
    field name (derived dynamically so new extraction rules automatically
    get columns).

    Returns *output_path* on success.

    Raises:
        ReportAssemblyError: The workbook cannot be saved.
    """
    field_names = _collect_field_names(results)

    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Data"

    headers = ["Document", "PDF Page"] + field_names
    _write_header_row(ws, headers)

    for row_idx, result in enumerate(results, start=2):
        doc_name = result.source_path.name
        pdf_page = page_offsets.get(doc_name, "")

        field_map = {f.name: f.value for f in result.fields}

        ws.cell(row=row_idx, column=1, value=doc_name)
        ws.cell(row=row_idx, column=2, value=pdf_page)

        for col_offset, field_name in enumerate(field_names):
            cell = ws.cell(row=row_idx, column=3 + col_offset, value=field_map.get(field_name, ""))
            if "pay" in field_name.lower():
                cell.number_format = _CURRENCY_FORMAT

    _auto_width(ws, len(headers))

    try:
        wb.save(str(output_path))
    except Exception as exc:
        raise ReportAssemblyError(
            f"Failed to save Excel file '{output_path}': {exc}"
        ) from exc

    logger.info(
        "Excel report saved to '{}' — {} document row(s), {} field column(s)",
        output_path.name,
        len(results),
        len(field_names),
    )
    return output_path


def _collect_field_names(results: list[DocumentExtractionResult]) -> list[str]:
    """Return a stable-ordered list of unique field names across all results."""
    seen: dict[str, None] = {}
    for result in results:
        for field in result.fields:
            seen.setdefault(field.name, None)
    return list(seen)


def _write_header_row(ws, headers: list[str]) -> None:
    bold = Font(bold=True)
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = bold
        cell.alignment = Alignment(horizontal="center")


def _auto_width(ws, num_columns: int) -> None:
    """Set column widths based on the longest value in each column."""
    for col in range(1, num_columns + 1):
        max_len = 0
        col_letter = get_column_letter(col)
        for cell in ws[col_letter]:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)
