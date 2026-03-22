from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.gui._widgets import add_corner_sparkles


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

        tagline = QLabel("Income document processing for downtime claims")
        tagline_font = QFont()
        tagline_font.setPointSize(10)
        tagline.setFont(tagline_font)
        root.addWidget(tagline)

        root.addSpacing(18)

        desc = QLabel(
            "Collect the income documents for a claim into a folder, point this tool "
            "at that folder, and it will read every page, pull out the key payment "
            "figures, and create two ready-to-use files."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        root.addSpacing(16)

        outputs_header = QLabel("<b>What you get</b>")
        root.addWidget(outputs_header)
        root.addSpacing(6)

        for bullet, detail in [
            (
                "Combined PDF",
                "all your documents in one file, easy to attach to a claim or share "
                "with co-counsel",
            ),
            (
                "Excel spreadsheet",
                "one row per document — gross pay, net pay, and payment dates — "
                "with a page reference back to the PDF",
            ),
        ]:
            row = QLabel(f"\u2022  <b>{bullet}</b> &mdash; {detail}")
            row.setWordWrap(True)
            row.setTextFormat(Qt.TextFormat.RichText)
            root.addWidget(row)
            root.addSpacing(4)

        root.addSpacing(16)

        note = QLabel(
            "<i>First time using this tool? Ask your IT contact to confirm the "
            "configuration file is in place on your machine before you run.</i>"
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setStyleSheet("color: gray;")
        root.addWidget(note)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        next_btn = QPushButton("Get Started \u2192")
        next_btn.setFixedWidth(120)
        next_btn.setFixedHeight(34)
        next_btn.clicked.connect(self.next_requested)
        btn_row.addWidget(next_btn)
        root.addLayout(btn_row)

        add_corner_sparkles(self)
