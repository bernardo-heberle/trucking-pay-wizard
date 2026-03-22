from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ResultsPage(QWidget):
    """Displayed after a successful pipeline run with links to output files."""

    run_another_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_path: Path | None = None
        self._excel_path: Path | None = None
        self._build_ui()

    def set_results(self, pdf_path: str, excel_path: str) -> None:
        """Populate the page with output file paths."""
        self._pdf_path = Path(pdf_path)
        self._excel_path = Path(excel_path)

        self._pdf_name_label.setText(self._pdf_path.name)
        self._excel_name_label.setText(self._excel_path.name)
        self._folder_label.setText(
            f"Saved to:  {self._pdf_path.parent}"
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 24)
        root.setSpacing(0)

        # ── Heading ──────────────────────────────────────────────────────────
        heading = QLabel("Processing complete")
        heading_font = QFont()
        heading_font.setPointSize(18)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        root.addWidget(heading)

        root.addSpacing(6)

        subtitle = QLabel("Your reports are ready.")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: green;")
        root.addWidget(subtitle)

        root.addSpacing(28)

        # ── PDF output ───────────────────────────────────────────────────────
        pdf_row = QHBoxLayout()
        pdf_info = QVBoxLayout()
        pdf_info.setSpacing(2)

        pdf_heading = QLabel("Combined PDF")
        pdf_heading_font = QFont()
        pdf_heading_font.setBold(True)
        pdf_heading.setFont(pdf_heading_font)
        pdf_info.addWidget(pdf_heading)

        self._pdf_name_label = QLabel()
        self._pdf_name_label.setStyleSheet("color: gray; font-size: 11px;")
        pdf_info.addWidget(self._pdf_name_label)

        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.setFixedWidth(100)
        open_pdf_btn.setFixedHeight(30)
        open_pdf_btn.clicked.connect(self._open_pdf)

        pdf_row.addLayout(pdf_info)
        pdf_row.addStretch()
        pdf_row.addWidget(open_pdf_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(pdf_row)

        root.addSpacing(18)

        # ── Excel output ─────────────────────────────────────────────────────
        excel_row = QHBoxLayout()
        excel_info = QVBoxLayout()
        excel_info.setSpacing(2)

        excel_heading = QLabel("Excel Spreadsheet")
        excel_heading_font = QFont()
        excel_heading_font.setBold(True)
        excel_heading.setFont(excel_heading_font)
        excel_info.addWidget(excel_heading)

        self._excel_name_label = QLabel()
        self._excel_name_label.setStyleSheet("color: gray; font-size: 11px;")
        excel_info.addWidget(self._excel_name_label)

        open_excel_btn = QPushButton("Open Spreadsheet")
        open_excel_btn.setFixedWidth(130)
        open_excel_btn.setFixedHeight(30)
        open_excel_btn.clicked.connect(self._open_excel)

        excel_row.addLayout(excel_info)
        excel_row.addStretch()
        excel_row.addWidget(open_excel_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(excel_row)

        root.addSpacing(14)

        self._folder_label = QLabel()
        self._folder_label.setWordWrap(True)
        self._folder_label.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(self._folder_label)

        root.addStretch()

        # ── Bottom actions ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setFixedWidth(120)
        open_folder_btn.setFixedHeight(34)
        open_folder_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(open_folder_btn)

        btn_row.addSpacing(10)

        again_btn = QPushButton("Process Another Folder")
        again_btn.setFixedWidth(170)
        again_btn.setFixedHeight(34)
        again_btn.clicked.connect(self.run_another_requested)
        btn_row.addWidget(again_btn)

        root.addLayout(btn_row)

    def _open_pdf(self) -> None:
        if self._pdf_path is not None:
            os.startfile(str(self._pdf_path))

    def _open_excel(self) -> None:
        if self._excel_path is not None:
            os.startfile(str(self._excel_path))

    def _open_output_folder(self) -> None:
        if self._pdf_path is not None:
            os.startfile(str(self._pdf_path.parent))
