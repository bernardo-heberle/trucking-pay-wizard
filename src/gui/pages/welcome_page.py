from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui._widgets import add_corner_sparkles, ui_scale

_TITLE_PT = 18.0
_LOGO_BASE_PX = 100   # logo height/width at the 640×520 base window size

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


class WelcomePage(QWidget):
    next_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logo_pixmap = QPixmap(str(_LOGO_PATH))
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 24)
        root.setSpacing(0)

        # ── Header: title/tagline left, logo right ────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)

        self._title = QLabel("Trucking Pay Wizard")
        title_font = QFont()
        title_font.setPointSizeF(_TITLE_PT)
        title_font.setBold(True)
        self._title.setFont(title_font)
        text_col.addWidget(self._title)

        text_col.addSpacing(6)

        # Tagline inherits the dynamic app font — no explicit setFont needed.
        tagline = QLabel("Income document processing for downtime claims")
        text_col.addWidget(tagline)

        header_row.addLayout(text_col)
        header_row.addStretch()

        self._logo_label = QLabel()
        self._logo_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self._logo_label.setStyleSheet("background: transparent;")
        self._update_logo(_LOGO_BASE_PX)
        header_row.addWidget(self._logo_label)

        root.addLayout(header_row)

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
        next_btn.setMinimumWidth(120)
        next_btn.setMinimumHeight(34)
        next_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        next_btn.clicked.connect(self.next_requested)
        btn_row.addWidget(next_btn)
        root.addLayout(btn_row)

        add_corner_sparkles(self)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_logo(self, px: int) -> None:
        if self._logo_pixmap.isNull():
            return
        self._logo_label.setPixmap(
            self._logo_pixmap.scaled(
                px,
                px,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        scale = ui_scale(self.width(), self.height())

        font = self._title.font()
        font.setPointSizeF(_TITLE_PT * scale)
        self._title.setFont(font)

        self._update_logo(int(_LOGO_BASE_PX * scale))
