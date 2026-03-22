"""Unit tests for src.report.excel_exporter."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from src.extract.models import DocumentExtractionResult, ExtractedField
from src.report.excel_exporter import build_excel
from tests.unit.report.conftest import make_extraction_result


class TestExcelStructure:

    def test_header_row(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active
        headers = [ws.cell(row=1, column=c).value for c in range(1, 5)]
        assert headers[0] == "Document"
        assert headers[1] == "PDF Page"
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
        assert ws.max_row == 3  # 1 header + 2 data

    def test_field_values_in_correct_columns(self, synthetic_source_pdf: Path, tmp_path: Path) -> None:
        result = make_extraction_result(synthetic_source_pdf)
        out = tmp_path / "out.xlsx"
        build_excel([result], out, {synthetic_source_pdf.name: 2})

        wb = openpyxl.load_workbook(str(out))
        ws = wb.active

        header_map = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        gp_col = header_map["Pay"]
        dd_col = header_map["Date"]

        assert ws.cell(row=2, column=gp_col).value == "750.00"
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
        # r1 has pay but not date — that cell should be empty
        dd_col = header_map["Date"]
        assert ws.cell(row=2, column=dd_col).value in (None, "")
