from __future__ import annotations

import datetime
import re
from pathlib import Path

from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedLoad
from src.report._date_parsing import parse_extracted_date
from src.report.exceptions import ReportAssemblyError

_CURRENCY_FORMAT = '$#,##0.00'
_DATE_FORMAT = 'MM/DD/YYYY'
_DAYS_FORMAT = '[=1]0" day";0" days"'

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
    duplicate_map: dict[str, list[str]] | None = None,
) -> Path:
    """Build an Excel spreadsheet with one row per load.

    Column layout: ``Document | PDF Page | Certainty | Date | Pay | Notes``.

    Documents with multiple loads produce multiple consecutive rows with the
    same document name repeated.  The TOTALS row uses ``=SUM(…)`` on the Pay
    column and ``=MAX(…)-MIN(…)+1`` on the Date column so that Excel
    auto-recalculates if staff correct any cell.

    When a date string cannot be parsed it is not written to the Date cell;
    instead the raw value appears in the Notes cell as
    ``Unparseable date: "<value>"`` and the Date cell is coloured red.  This
    keeps the Date column purely numeric so the MAX/MIN totals formula is
    reliable.

    *page_offsets* maps ``source_path.name`` to the 1-indexed starting page
    of that document in the combined PDF.  Per-load PDF Page is computed from
    that base plus the load's own source page offset.

    *duplicate_map* maps a kept filename to the list of byte-identical filenames
    that were excluded from the pipeline.  When a document has duplicates, every
    one of its load rows receives an additional note:
    ``Exact duplicates excluded from analysis: <name1>, <name2>``.

    Returns *output_path* on success.

    Raises:
        ReportAssemblyError: The workbook cannot be saved.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Data"

    _write_header_row(ws, _HEADERS)

    _dup_map: dict[str, list[str]] = duplicate_map or {}

    data_row = 2
    parseable_date_count = 0
    for result in results:
        doc_name = result.source_path.name
        doc_base_page = page_offsets.get(doc_name, "")

        duplicate_names = _dup_map.get(doc_name, [])
        duplicate_note = (
            f"Exact duplicates excluded from analysis: {', '.join(duplicate_names)}"
            if duplicate_names
            else ""
        )

        if result.extraction_error:
            # Failed extractions get a single row with the error in Notes.
            ws.cell(row=data_row, column=_COL_DOCUMENT, value=doc_name)
            ws.cell(row=data_row, column=_COL_PDF_PAGE, value=doc_base_page or "")
            cert_cell = ws.cell(row=data_row, column=_COL_CERTAINTY, value=Certainty.NOT_FOUND.value)
            cert_cell.fill = _FILL_RED
            error_notes = "; ".join(filter(None, [duplicate_note, result.extraction_error]))
            notes_cell = ws.cell(row=data_row, column=_COL_NOTES, value=error_notes)
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

            # Date cell — write datetime on success; blank + red fill + Notes on failure.
            date_certainty: Certainty | None = None
            notes_parts: list[str] = [duplicate_note] if duplicate_note else []
            if load.date is not None:
                date_raw = load.date.value
                date_certainty = load.date.certainty
                parsed_date = parse_extracted_date(date_raw)
                if parsed_date is not None:
                    date_value: datetime.datetime | None = datetime.datetime(
                        parsed_date.year, parsed_date.month, parsed_date.day
                    )
                    parseable_date_count += 1
                else:
                    date_value = None
                    notes_parts.append(f'Unparseable date: "{date_raw}"')
            else:
                date_value = None

            date_cell = ws.cell(row=data_row, column=_COL_DATE, value=date_value)
            date_cell.number_format = _DATE_FORMAT
            if date_value is not None:
                date_cell.fill = _fill_for_certainty(date_certainty)
            else:
                date_cell.fill = _FILL_RED

            # Pay cell
            pay_value: float | str | None = None
            pay_certainty: Certainty | None = None
            if load.pay is not None:
                pay_certainty = load.pay.certainty
                pay_value = _parse_pay_float(load.pay.value)
            pay_cell = ws.cell(row=data_row, column=_COL_PAY, value=pay_value)
            pay_cell.number_format = _CURRENCY_FORMAT
            pay_cell.fill = _fill_for_certainty(pay_certainty) if pay_value is not None else _FILL_RED

            # Notes cell — join any note fragments.
            if notes_parts:
                notes_cell = ws.cell(row=data_row, column=_COL_NOTES, value="; ".join(notes_parts))
                notes_cell.fill = _FILL_RED

            data_row += 1

    totals_row = data_row
    data_end_row = data_row - 1
    _write_totals_row(
        ws,
        data_start_row=2,
        data_end_row=data_end_row,
        totals_row=totals_row,
        has_parseable_dates=parseable_date_count > 0,
    )

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
    has_parseable_dates: bool = True,
) -> None:
    """Write a summary Totals row using Excel formulas.

    The Pay column gets a SUM formula.  The Date column gets a MAX-MIN+1
    formula when at least one data row has a parseable date; otherwise the
    Date cell is left blank to avoid a misleading ``1 day`` from an all-empty
    date range.  All cells in the totals row are bold.
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
    if has_parseable_dates:
        date_range = f"{date_col_letter}{data_start_row}:{date_col_letter}{data_end_row}"
        date_cell = ws.cell(
            row=totals_row, column=_COL_DATE,
            value=f"=MAX({date_range})-MIN({date_range})+1",
        )
        date_cell.font = bold
        date_cell.number_format = _DAYS_FORMAT
    else:
        date_cell = ws.cell(row=totals_row, column=_COL_DATE, value=None)
        date_cell.font = bold


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
