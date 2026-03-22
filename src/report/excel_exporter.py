from __future__ import annotations

import datetime
from pathlib import Path

from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, numbers
from openpyxl.utils import get_column_letter

from src.extract.models import Certainty, DocumentExtractionResult
from src.extract.rules import EXPECTED_FIELDS
from src.report.exceptions import ReportAssemblyError

_CURRENCY_FORMAT = '$#,##0.00'
_DATE_FORMATS = ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y")

_FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
_FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
_FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

_CERTAINTY_FILLS: dict[Certainty, PatternFill] = {
    Certainty.HIGH: _FILL_GREEN,
    Certainty.REVIEW: _FILL_YELLOW,
    Certainty.NOT_FOUND: _FILL_RED,
}


def _fill_for_certainty(certainty: Certainty | None) -> PatternFill:
    if certainty is None:
        return _FILL_YELLOW
    return _CERTAINTY_FILLS.get(certainty, _FILL_YELLOW)


def build_excel(
    results: list[DocumentExtractionResult],
    output_path: Path,
    page_offsets: dict[str, int],
) -> Path:
    """Build an Excel spreadsheet with one row per document.

    Columns: ``Document``, ``PDF Page``, ``Certainty``, then one column per
    unique extracted field name (derived dynamically so new extraction rules
    automatically get columns).  Data cells are color-filled by their
    individual field certainty; the ``Certainty`` column shows the worst
    certainty across all expected fields for the document.

    Returns *output_path* on success.

    Raises:
        ReportAssemblyError: The workbook cannot be saved.
    """
    field_names = _collect_field_names(results)

    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Data"

    display_names = [name.replace("_", " ").title() for name in field_names]
    headers = ["Document", "PDF Page", "Certainty"] + display_names
    _write_header_row(ws, headers)

    for row_idx, result in enumerate(results, start=2):
        doc_name = result.source_path.name
        pdf_page = page_offsets.get(doc_name, "")

        field_map = {f.name: f for f in result.fields}

        ws.cell(row=row_idx, column=1, value=doc_name)
        ws.cell(row=row_idx, column=2, value=pdf_page)

        doc_certainty = result.overall_certainty(EXPECTED_FIELDS)
        cert_cell = ws.cell(row=row_idx, column=3, value=doc_certainty.value)
        cert_cell.fill = _fill_for_certainty(doc_certainty)

        for col_offset, field_name in enumerate(field_names):
            extracted = field_map.get(field_name)
            raw_value = extracted.value if extracted else ""
            if field_name == "date" and raw_value:
                raw_value = _normalize_date(raw_value)
            cell = ws.cell(row=row_idx, column=4 + col_offset, value=raw_value)
            if "pay" in field_name.lower():
                cell.number_format = _CURRENCY_FORMAT

            if extracted:
                cell.fill = _fill_for_certainty(extracted.certainty)
            else:
                cell.fill = _fill_for_certainty(Certainty.NOT_FOUND)

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


def _normalize_date(value: str) -> str:
    """Return *value* formatted as ``MM/DD/YYYY``.

    Handles the raw date formats produced by the extraction rules:
    ``MM/DD/YYYY``, ``Month D, YYYY``, and abbreviated ``Mon D, YYYY``.
    Returns the original string unchanged if none of the formats match.
    """
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(value.strip(), fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return value


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
