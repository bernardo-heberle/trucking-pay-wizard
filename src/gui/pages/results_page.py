from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui._widgets import add_corner_sparkles, ui_scale

_HEADING_PT = 18.0


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
        self._folder_label.setText(f"Saved to:  {self._pdf_path.parent}")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 24)
        root.setSpacing(0)

        # ── Celebration header ────────────────────────────────────────────────
        self._heading = QLabel("All done!")
        heading_font = QFont()
        heading_font.setPointSizeF(_HEADING_PT)
        heading_font.setBold(True)
        self._heading.setFont(heading_font)
        root.addWidget(self._heading)

        root.addSpacing(4)

        # Subtitle inherits the dynamic app font — no explicit setFont needed.
        subtitle = QLabel("Your reports are ready — time to file that claim!")
        subtitle.setStyleSheet("color: #7c3aed;")
        root.addWidget(subtitle)

        root.addSpacing(24)

        # ── PDF output ────────────────────────────────────────────────────────
        pdf_row = QHBoxLayout()
        pdf_info = QVBoxLayout()
        pdf_info.setSpacing(2)

        pdf_heading = QLabel("Combined PDF")
        pdf_heading_font = QFont()
        pdf_heading_font.setBold(True)
        pdf_heading.setFont(pdf_heading_font)
        pdf_info.addWidget(pdf_heading)

        self._pdf_name_label = QLabel()
        self._pdf_name_label.setStyleSheet("color: gray;")
        pdf_info.addWidget(self._pdf_name_label)

        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.setMinimumWidth(100)
        open_pdf_btn.setMinimumHeight(30)
        open_pdf_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        open_pdf_btn.clicked.connect(self._open_pdf)

        pdf_row.addLayout(pdf_info)
        pdf_row.addStretch()
        pdf_row.addWidget(open_pdf_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(pdf_row)

        root.addSpacing(16)

        # ── Excel output ──────────────────────────────────────────────────────
        excel_row = QHBoxLayout()
        excel_info = QVBoxLayout()
        excel_info.setSpacing(2)

        excel_heading = QLabel("Excel Spreadsheet")
        excel_heading_font = QFont()
        excel_heading_font.setBold(True)
        excel_heading.setFont(excel_heading_font)
        excel_info.addWidget(excel_heading)

        self._excel_name_label = QLabel()
        self._excel_name_label.setStyleSheet("color: gray;")
        excel_info.addWidget(self._excel_name_label)

        open_excel_btn = QPushButton("Open Spreadsheet")
        open_excel_btn.setMinimumWidth(160)
        open_excel_btn.setMinimumHeight(30)
        open_excel_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        open_excel_btn.clicked.connect(self._open_excel)

        excel_row.addLayout(excel_info)
        excel_row.addStretch()
        excel_row.addWidget(open_excel_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(excel_row)

        root.addSpacing(12)

        self._folder_label = QLabel()
        self._folder_label.setWordWrap(True)
        self._folder_label.setStyleSheet("color: gray;")
        root.addWidget(self._folder_label)

        root.addStretch()

        # ── Bottom actions ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        open_folder_btn = QPushButton("Open Results Folder")
        open_folder_btn.setMinimumWidth(160)
        open_folder_btn.setMinimumHeight(34)
        open_folder_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        open_folder_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(open_folder_btn)

        btn_row.addSpacing(10)

        again_btn = QPushButton("Process Another Folder")
        again_btn.setMinimumWidth(170)
        again_btn.setMinimumHeight(34)
        again_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        again_btn.clicked.connect(self.run_another_requested)
        btn_row.addWidget(again_btn)

        root.addLayout(btn_row)

        add_corner_sparkles(self, symbol="✨")

    def _open_pdf(self) -> None:
        if self._pdf_path is not None:
            os.startfile(str(self._pdf_path))

    def _open_excel(self) -> None:
        if self._excel_path is not None:
            os.startfile(str(self._excel_path))

    def _open_output_folder(self) -> None:
        if self._pdf_path is not None:
            os.startfile(str(self._pdf_path.parent))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        scale = ui_scale(self.width(), self.height())
        font = self._heading.font()
        font.setPointSizeF(_HEADING_PT * scale)
        self._heading.setFont(font)
