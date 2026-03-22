from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class WelcomePage(QWidget):
    next_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 24)
        root.setSpacing(0)

        title = QLabel("Trucking Pay Wizard")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        root.addSpacing(6)

        tagline = QLabel("A batch OCR tool for downtime claims staff.")
        tagline_font = QFont()
        tagline_font.setPointSize(10)
        tagline.setFont(tagline_font)
        root.addWidget(tagline)

        root.addSpacing(18)

        desc = QLabel(
            "Drop your income documents into a folder, tell the tool where they are, "
            "and it will read every page using Azure OCR, pull out the key financial "
            "fields, and write two ready-to-file output files back to the same folder."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        root.addSpacing(16)

        outputs_header = QLabel("<b>What you get</b>")
        root.addWidget(outputs_header)
        root.addSpacing(6)

        for bullet, detail in [
            (
                "&lt;prefix&gt;_combined.pdf",
                "all source pages in one PDF, with gross pay and delivery date "
                "highlighted in yellow",
            ),
            (
                "&lt;prefix&gt;_extracted.xlsx",
                "one row per document — document name, starting page in the PDF, "
                "gross pay, delivery date",
            ),
        ]:
            row = QLabel(f"\u2022  <b>{bullet}</b> &mdash; {detail}")
            row.setWordWrap(True)
            row.setTextFormat(Qt.TextFormat.RichText)
            root.addWidget(row)
            root.addSpacing(4)

        root.addSpacing(16)

        stages_label = QLabel(
            "<b>Pipeline:</b> &nbsp;Ingestion &rarr; OCR &rarr; Extraction &rarr; Report"
        )
        stages_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(stages_label)

        root.addSpacing(10)

        note = QLabel(
            "<i>Requires Azure Document Intelligence credentials in a "
            "<code>.env</code> file in the project folder before running.</i>"
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(note)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        next_btn = QPushButton("Next \u2192")
        next_btn.setFixedWidth(100)
        next_btn.clicked.connect(self.next_requested)
        btn_row.addWidget(next_btn)
        root.addLayout(btn_row)
