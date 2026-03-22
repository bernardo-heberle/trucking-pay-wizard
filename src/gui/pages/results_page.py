from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ResultsPage(QWidget):
    """Displayed after a successful pipeline run with links to output files."""

    run_another_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_path: Path | None = None
        self._excel_path: Path | None = None
        self._build_ui()

    def set_results(self, pdf_path: str, excel_path: str) -> None:
        """Populate the page with output file information."""
        self._pdf_path = Path(pdf_path)
        self._excel_path = Path(excel_path)

        self._pdf_label.setText(f"\u2022  <b>{self._pdf_path.name}</b>")
        self._excel_label.setText(f"\u2022  <b>{self._excel_path.name}</b>")
        self._folder_label.setText(
            f"Saved to:  <code>{self._pdf_path.parent}</code>"
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 24)
        root.setSpacing(0)

        # ── Heading ──────────────────────────────────────────────────────────
        heading = QLabel("Pipeline Complete")
        heading_font = QFont()
        heading_font.setPointSize(18)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        root.addWidget(heading)

        root.addSpacing(6)

        subtitle = QLabel("All documents processed successfully.")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: green;")
        root.addWidget(subtitle)

        root.addSpacing(24)

        # ── Output files ─────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Output files</b>"))
        root.addSpacing(8)

        self._pdf_label = QLabel()
        self._pdf_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self._pdf_label)
        root.addSpacing(4)

        self._excel_label = QLabel()
        self._excel_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self._excel_label)

        root.addSpacing(12)

        self._folder_label = QLabel()
        self._folder_label.setTextFormat(Qt.TextFormat.RichText)
        self._folder_label.setWordWrap(True)
        self._folder_label.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(self._folder_label)

        root.addStretch()

        # ── Action buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        open_btn = QPushButton("Open Folder")
        open_btn.setFixedWidth(120)
        open_btn.setFixedHeight(34)
        open_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(open_btn)

        btn_row.addSpacing(10)

        again_btn = QPushButton("Run Another")
        again_btn.setFixedWidth(120)
        again_btn.setFixedHeight(34)
        again_btn.clicked.connect(self.run_another_requested)
        btn_row.addWidget(again_btn)

        root.addLayout(btn_row)

    def _open_output_folder(self) -> None:
        if self._pdf_path is None:
            return
        folder = str(self._pdf_path.parent)
        os.startfile(folder)
