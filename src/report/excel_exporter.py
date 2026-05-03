from __future__ import annotations

import datetime
import re
from pathlib import Path

from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedLoad
from src.report.exceptions import ReportAssemblyError

_CURRENCY_FORMAT = '$#,##0.00'
_DATE_FORMAT = 'MM/DD/YYYY'
_DATE_FORMATS = ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y")

_FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
_FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
_FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

_CERTAINTY_FILLS: dict[Certainty, PatternFill] = {
    Certainty.HIGH: _FILL_GREEN,
    Certainty.REVIEW: _FILL_YELLOW,
    Certainty.NOT_FOUND: _FILL_RED,
}

# Fixed column indices (1-based).
_COL_DOCUMENT = 1
_COL_PDF_PAGE = 2
_COL_CERTAINTY = 3
_COL_DATE = 4
_COL_PAY = 5
_COL_NOTES = 6
_N_FIXED_COLS = 6

_HEADERS = ["Document", "PDF Page", "Certainty", "Date", "Pay", "Notes"]


def _fill_for_certainty(certainty: Certainty | None) -> PatternFill:
    if certainty is None:
        return _FILL_YELLOW
    return _CERTAINTY_FILLS.get(certainty, _FILL_YELLOW)


def build_excel(
    results: list[DocumentExtractionResult],
    output_path: Path,
    page_offsets: dict[str, int],
) -> Path:
    """Build an Excel spreadsheet with one row per load.

    Column layout: ``Document | PDF Page | Certainty | Date | Pay | Notes``.

    Documents with multiple loads produce multiple consecutive rows with the
    same document name repeated.  The TOTALS row uses ``=SUM(…)`` on the Pay
    column and ``=MAX(…)-MIN(…)+1`` on the Date column so that Excel
    auto-recalculates if staff correct any cell.

    *page_offsets* maps ``source_path.name`` to the 1-indexed starting page
    of that document in the combined PDF.  Per-load PDF Page is computed from
    that base plus the load's own source page offset.

    Returns *output_path* on success.

    Raises:
        ReportAssemblyError: The workbook cannot be saved.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Data"

    _write_header_row(ws, _HEADERS)

    data_row = 2
    for result in results:
        doc_name = result.source_path.name
        doc_base_page = page_offsets.get(doc_name, "")

        if result.extraction_error:
            # Failed extractions get a single row with the error in Notes.
            ws.cell(row=data_row, column=_COL_DOCUMENT, value=doc_name)
            ws.cell(row=data_row, column=_COL_PDF_PAGE, value=doc_base_page or "")
            cert_cell = ws.cell(row=data_row, column=_COL_CERTAINTY, value=Certainty.NOT_FOUND.value)
            cert_cell.fill = _FILL_RED
            notes_cell = ws.cell(row=data_row, column=_COL_NOTES, value=result.extraction_error)
            notes_cell.fill = _FILL_RED
            data_row += 1
            continue

        for load in result.loads:
            ws.cell(row=data_row, column=_COL_DOCUMENT, value=doc_name)

            # Per-load PDF page: base offset + (load's source_page - 1).
            load_source_page = _load_source_page(load)
            if isinstance(doc_base_page, int) and load_source_page is not None:
                pdf_page = doc_base_page + (load_source_page - 1)
            else:
                pdf_page = doc_base_page or ""
            ws.cell(row=data_row, column=_COL_PDF_PAGE, value=pdf_page)

            load_cert = load.certainty()
            cert_cell = ws.cell(row=data_row, column=_COL_CERTAINTY, value=load_cert.value)
            cert_cell.fill = _fill_for_certainty(load_cert)

            # Date cell
            date_value: str | datetime.datetime | None = None
            date_certainty: Certainty | None = None
            if load.date is not None:
                date_raw = load.date.value
                date_certainty = load.date.certainty
                parsed_dt = _parse_date_to_datetime(date_raw)
                date_value = parsed_dt if parsed_dt is not None else date_raw
            date_cell = ws.cell(row=data_row, column=_COL_DATE, value=date_value)
            date_cell.number_format = _DATE_FORMAT
            date_cell.fill = _fill_for_certainty(date_certainty) if date_value is not None else _FILL_RED

            # Pay cell
            pay_value: float | str | None = None
            pay_certainty: Certainty | None = None
            if load.pay is not None:
                pay_certainty = load.pay.certainty
                pay_value = _parse_pay_float(load.pay.value)
            pay_cell = ws.cell(row=data_row, column=_COL_PAY, value=pay_value)
            pay_cell.number_format = _CURRENCY_FORMAT
            pay_cell.fill = _fill_for_certainty(pay_certainty) if pay_value is not None else _FILL_RED

            data_row += 1

    totals_row = data_row
    data_end_row = data_row - 1
    _write_totals_row(ws, data_start_row=2, data_end_row=data_end_row, totals_row=totals_row)

    _auto_width(ws, _N_FIXED_COLS)

    try:
        wb.save(str(output_path))
    except Exception as exc:
        raise ReportAssemblyError(
            f"Failed to save Excel file '{output_path}': {exc}"
        ) from exc

    n_load_rows = data_end_row - 1  # excludes header
    logger.info(
        "Excel report saved to '{}' — {} load row(s) across {} document(s)",
        output_path.name,
        n_load_rows,
        len(results),
    )
    return output_path


def _load_source_page(load: ExtractedLoad) -> int | None:
    """Return the source page for *load*, preferring pay's page over date's."""
    if load.pay is not None and load.pay.source_page is not None:
        return load.pay.source_page
    if load.date is not None and load.date.source_page is not None:
        return load.date.source_page
    return None


def _write_totals_row(
    ws,
    data_start_row: int,
    data_end_row: int,
    totals_row: int,
) -> None:
    """Write a summary Totals row using Excel formulas.

    The Pay column gets a SUM formula and the Date column gets a MAX-MIN+1
    formula so staff can see the calendar span of all loads.  All cells in the
    totals row are bold.
    """
    bold = Font(bold=True)

    label_cell = ws.cell(row=totals_row, column=_COL_DOCUMENT, value="TOTALS")
    label_cell.font = bold

    pay_col_letter = get_column_letter(_COL_PAY)
    pay_range = f"{pay_col_letter}{data_start_row}:{pay_col_letter}{data_end_row}"
    pay_cell = ws.cell(row=totals_row, column=_COL_PAY, value=f"=SUM({pay_range})")
    pay_cell.font = bold
    pay_cell.number_format = _CURRENCY_FORMAT

    date_col_letter = get_column_letter(_COL_DATE)
    date_range = f"{date_col_letter}{data_start_row}:{date_col_letter}{data_end_row}"
    date_cell = ws.cell(
        row=totals_row, column=_COL_DATE,
        value=f"=MAX({date_range})-MIN({date_range})+1",
    )
    date_cell.font = bold
    date_cell.number_format = "0"


def _parse_pay_float(value: str) -> float | str:
    """Convert a pay string to float for proper Excel numeric handling.

    Strips currency symbols, commas, and surrounding whitespace so that raw
    LLM values like ``'$1,500.00'`` parse correctly.  Returns the float on
    success so Excel treats the cell as a number and SUM() formulas work.
    Returns the original string unchanged when parsing fails so the cell
    still shows something reviewable.
    """
    try:
        return float(re.sub(r"[$,\s]", "", value))
    except (ValueError, AttributeError):
        return value


def _parse_date_to_datetime(value: str) -> datetime.datetime | None:
    """Parse a raw date string to a ``datetime.datetime`` for Excel.

    Writing a ``datetime`` object instead of a string lets Excel treat the
    cell as a native date serial, which is required for MAX/MIN formulas in
    the totals row.  Returns ``None`` when none of the known formats match.
    """
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


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
