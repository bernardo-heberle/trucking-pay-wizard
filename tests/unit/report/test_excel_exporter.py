"""Unit tests for src.report.excel_exporter."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest
from openpyxl.utils import get_column_letter

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField
from src.report.excel_exporter import build_excel, _FILL_GREEN, _FILL_YELLOW, _FILL_RED
from tests.unit.report.conftest import make_extraction_result


class TestExcelStructure:

    def test_header_row(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert headers[0] == "Document"
        assert headers[1] == "PDF Page"
        assert headers[2] == "Certainty"
        assert "Pay" in headers
        assert "Date" in headers

    def test_row_count_matches_results(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        results = [
            make_extraction_result(synthetic_source_pdf, content_hash="h1"),
            make_extraction_result(synthetic_source_pdf_b, content_hash="h2", page_count=2),
        ]
        offsets = {synthetic_source_pdf.name: 2, synthetic_source_pdf_b.name: 3}
        out = tmp_path / "out.xlsx"
        build_excel(results, out, offsets)

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        assert ws.max_row == 4  # 1 header + 2 data + 1 totals

    def test_field_values_in_correct_columns(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active

        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        gp_col = header_map["Pay"]
        dd_col = header_map["Date"]

        assert ws.cell(row=2, column=gp_col).value == pytest.approx(750.0)
        assert ws.cell(row=2, column=dd_col).value == "03/12/2024"

    def test_pdf_page_offset(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 5})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        assert ws.cell(row=2, column=2).value == 5


class TestDynamicColumns:

    def test_extra_field_gets_column(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """A field name not in the default set still gets its own column."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="net_pay",
                    value="600.00",
                    source_document=synthetic_source_pdf.name,
                    source_page=1,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Net Pay" in headers

    def test_varying_field_names_across_documents(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        r1 = make_extraction_result(
            synthetic_source_pdf,
            content_hash="h1",
            fields=[
                ExtractedField(name="pay", value="100", source_document="a.pdf", source_page=1),
            ],
        )
        r2 = make_extraction_result(
            synthetic_source_pdf_b,
            content_hash="h2",
            page_count=2,
            fields=[
                ExtractedField(name="date", value="01/01/2024", source_document="b.pdf", source_page=1),
            ],
        )
        offsets = {synthetic_source_pdf.name: 2, synthetic_source_pdf_b.name: 3}
        out = tmp_path / "out.xlsx"
        build_excel([r1, r2], out, offsets)

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        assert "Pay" in headers
        assert "Date" in headers

        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        dd_col = header_map["Date"]
        # r1 has no date field — its Date cell must be empty (None in openpyxl).
        assert ws.cell(row=2, column=dd_col).value is None


class TestDateNormalization:

    def test_month_name_date_normalized_to_mm_dd_yyyy(
        self, synthetic_source_pdf: Path, tmp_path: Path
    ) -> None:
        """'March 20, 2024' is written to Excel as '03/20/2024'."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="date", value="March 20, 2024",
                    source_document=synthetic_source_pdf.name, source_page=1,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        date_col = header_map["Date"]
        assert ws.cell(row=2, column=date_col).value == "03/20/2024"

    def test_abbreviated_month_date_normalized(
        self, synthetic_source_pdf: Path, tmp_path: Path
    ) -> None:
        """'Mar 11, 2024' (abbreviated) is normalized to '03/11/2024'."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="date", value="Mar 11, 2024",
                    source_document=synthetic_source_pdf.name, source_page=1,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        date_col = header_map["Date"]
        assert ws.cell(row=2, column=date_col).value == "03/11/2024"

    def test_already_normalized_date_unchanged(
        self, synthetic_source_pdf: Path, tmp_path: Path
    ) -> None:
        """A date already in MM/DD/YYYY format is written without modification."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="date", value="05/15/2024",
                    source_document=synthetic_source_pdf.name, source_page=1,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        date_col = header_map["Date"]
        assert ws.cell(row=2, column=date_col).value == "05/15/2024"


class TestCertaintyColumn:

    def test_certainty_column_present(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        assert "Certainty" in header_map

    def test_certainty_value_all_high(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Default fixture has both fields HIGH -> overall is 'High'."""
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        cert_col = header_map["Certainty"]
        assert ws.cell(row=2, column=cert_col).value == "High"

    def test_certainty_value_mixed(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="pay", value="100", source_document="t.pdf",
                    source_page=1, certainty=Certainty.HIGH,
                ),
                ExtractedField(
                    name="date", value="01/01/2024", source_document="t.pdf",
                    source_page=1, certainty=Certainty.REVIEW,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        cert_col = header_map["Certainty"]
        assert ws.cell(row=2, column=cert_col).value == "Review"

    def test_certainty_fill_colors(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Data cells and certainty cell should carry the right fill color."""
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}

        cert_cell = ws.cell(row=2, column=header_map["Certainty"])
        assert cert_cell.fill.start_color.rgb == "00C6EFCE"

        pay_cell = ws.cell(row=2, column=header_map["Pay"])
        assert pay_cell.fill.start_color.rgb == "00C6EFCE"

class TestTotalsRow:

    def _build(self, tmp_path: Path, results, offsets=None) -> "openpyxl.Workbook":
        out = tmp_path / "out.xlsx"
        if offsets is None:
            offsets = {r.source_path.name: i + 2 for i, r in enumerate(results)}
        build_excel(results, out, offsets)
        # data_only=False so formula strings are preserved (not evaluated)
        return openpyxl.load_workbook(str(out), data_only=False)

    def test_totals_row_exists(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        """1 header + 2 data rows + 1 totals = 4 rows total."""
        results = [
            make_extraction_result(synthetic_source_pdf, content_hash="h1"),
            make_extraction_result(synthetic_source_pdf_b, content_hash="h2", page_count=2),
        ]
        wb = self._build(tmp_path, results)
        ws = wb.active
        assert ws.max_row == 4

    def test_totals_label(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        totals_row = ws.max_row
        assert ws.cell(row=totals_row, column=1).value == "TOTALS"

    def test_totals_row_is_bold(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        totals_row = ws.max_row
        assert ws.cell(row=totals_row, column=1).font.bold is True

    def test_pay_column_has_sum_formula(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        totals_row = ws.max_row
        pay_col_letter = get_column_letter(header_map["Pay"])
        pay_cell_value = ws.cell(row=totals_row, column=header_map["Pay"]).value
        assert isinstance(pay_cell_value, str)
        assert pay_cell_value.upper().startswith("=SUM(")
        # Pin the exact range — must span exactly the data rows.
        expected_range = f"{pay_col_letter}2:{pay_col_letter}{totals_row - 1}"
        assert expected_range in pay_cell_value

    def test_date_column_has_counta_formula(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        totals_row = ws.max_row
        date_cell_value = ws.cell(row=totals_row, column=header_map["Date"]).value
        assert isinstance(date_cell_value, str)
        assert date_cell_value.upper().startswith("=COUNTA(")

    def test_non_formula_columns_blank_in_totals(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Certainty, PDF Page, and Notes columns should be empty in the totals row."""
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        totals_row = ws.max_row
        for col_name in ("PDF Page", "Certainty", "Notes"):
            val = ws.cell(row=totals_row, column=header_map[col_name]).value
            assert val is None or val == "", f"Expected blank in '{col_name}' totals cell, got {val!r}"

    def test_sum_formula_covers_correct_range_three_docs(
        self,
        synthetic_source_pdf: Path,
        synthetic_source_pdf_b: Path,
        tmp_path: Path,
    ) -> None:
        """SUM range must span exactly the data rows (rows 2 through N)."""
        import fitz as _fitz

        pdf_c = tmp_path / "source_c.pdf"
        doc = _fitz.open()
        doc.new_page(width=612, height=792)
        doc.save(str(pdf_c))
        doc.close()

        results = [
            make_extraction_result(synthetic_source_pdf, content_hash="h1"),
            make_extraction_result(synthetic_source_pdf_b, content_hash="h2", page_count=2),
            make_extraction_result(pdf_c, content_hash="h3"),
        ]
        wb = self._build(tmp_path, results)
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        totals_row = ws.max_row  # should be 5 (1 header + 3 data + 1 totals)
        pay_col_letter = get_column_letter(header_map["Pay"])
        pay_formula = ws.cell(row=totals_row, column=header_map["Pay"]).value
        expected_range = f"{pay_col_letter}2:{pay_col_letter}{totals_row - 1}"
        assert expected_range in pay_formula

    def test_single_document_gets_totals(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """Edge case: 1 document still gets a totals row with valid formulas."""
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        # 1 header + 1 data + 1 totals = 3 rows
        assert ws.max_row == 3
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        pay_col_letter = get_column_letter(header_map["Pay"])
        pay_formula = ws.cell(row=3, column=header_map["Pay"]).value
        assert f"{pay_col_letter}2:{pay_col_letter}2" in pay_formula

    def test_pay_totals_cell_has_currency_format(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        wb = self._build(tmp_path, [result])
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        totals_row = ws.max_row
        fmt = ws.cell(row=totals_row, column=header_map["Pay"]).number_format
        assert "$" in fmt


    def test_missing_field_gets_red_fill(
        self, synthetic_source_pdf: Path, synthetic_source_pdf_b: Path, tmp_path: Path
    ) -> None:
        """When a field is absent for a document, its cell should be red."""
        r1 = make_extraction_result(
            synthetic_source_pdf,
            content_hash="h1",
            fields=[
                ExtractedField(name="pay", value="100", source_document="a.pdf", source_page=1, certainty=Certainty.HIGH),
            ],
        )
        r2 = make_extraction_result(
            synthetic_source_pdf_b,
            content_hash="h2",
            page_count=2,
            fields=[
                ExtractedField(name="pay", value="200", source_document="b.pdf", source_page=1, certainty=Certainty.HIGH),
                ExtractedField(name="date", value="01/01/2024", source_document="b.pdf", source_page=1, certainty=Certainty.HIGH),
            ],
        )
        offsets = {synthetic_source_pdf.name: 2, synthetic_source_pdf_b.name: 3}
        out = tmp_path / "out.xlsx"
        build_excel([r1, r2], out, offsets)

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}

        date_cell_r1 = ws.cell(row=2, column=header_map["Date"])
        assert date_cell_r1.fill.start_color.rgb == "00FFC7CE"


class TestPayNumericCells:
    """Pay cell values must be numeric (float) so Excel SUM formulas work."""

    def test_pay_cell_is_float_not_string(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """A normalised pay string '750.00' must be written as float 750.0."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="pay", value="750.00",
                    source_document=synthetic_source_pdf.name, source_page=1,
                    certainty=Certainty.HIGH,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        pay_cell = ws.cell(row=2, column=header_map["Pay"])

        assert isinstance(pay_cell.value, (int, float)), (
            f"Expected numeric type, got {type(pay_cell.value).__name__!r}: {pay_cell.value!r}"
        )

    def test_pay_cell_value_matches_extracted_amount(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="pay", value="1200.50",
                    source_document=synthetic_source_pdf.name, source_page=1,
                    certainty=Certainty.HIGH,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        pay_val = ws.cell(row=2, column=header_map["Pay"]).value

        assert pay_val == pytest.approx(1200.50)

    def test_unparseable_pay_stays_as_string(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        """When pay cannot be parsed as float it is kept as a string rather than crashing."""
        result = make_extraction_result(
            synthetic_source_pdf,
            fields=[
                ExtractedField(
                    name="pay", value="N/A",
                    source_document=synthetic_source_pdf.name, source_page=1,
                    certainty=Certainty.REVIEW,
                ),
            ],
        )
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        pay_val = ws.cell(row=2, column=header_map["Pay"]).value

        assert pay_val == "N/A"
