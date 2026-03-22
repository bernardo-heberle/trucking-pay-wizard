"""Shared GUI widgets used across pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QWidget


class TruckProgressWidget(QWidget):
    """A progress bar with a truck emoji that rolls along above it.

    Use ``setRange`` / ``setValue`` exactly as you would ``QProgressBar``.
    Call ``setRange(0, 0)`` for indeterminate (pulsing) mode.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setVisible(False)

        self._truck = QLabel("🚛", self)
        self._truck.setStyleSheet("font-size: 22px; background: transparent;")
        self._truck.adjustSize()

        self._bar = QProgressBar(self)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setRange(0, 0)

    # ── Public interface (mirrors QProgressBar) ───────────────────────────

    def setRange(self, minimum: int, maximum: int) -> None:
        self._bar.setRange(minimum, maximum)
        self._reposition()

    def setValue(self, value: int) -> None:
        self._bar.setValue(value)
        self._reposition()

    def value(self) -> int:
        return self._bar.value()

    def minimum(self) -> int:
        return self._bar.minimum()

    def maximum(self) -> int:
        return self._bar.maximum()

    # ── Layout ───────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition()

    def _reposition(self) -> None:
        w = self.width()
        if w == 0:
            return

        bar_h = self._bar.height()
        bar_y = self.height() - bar_h
        self._bar.setGeometry(0, bar_y, w, bar_h)

        # Re-measure the truck label in case the font hasn't been laid out yet.
        self._truck.adjustSize()
        truck_w = self._truck.width()
        truck_h = self._truck.height()

        mn = self._bar.minimum()
        mx = self._bar.maximum()
        val = self._bar.value()

        if mx > mn and w > truck_w:
            ratio = (val - mn) / (mx - mn)
            truck_x = int(ratio * (w - truck_w))
        else:
            # Indeterminate or zero-range — park at the far left.
            truck_x = 0

        truck_y = max(0, bar_y - truck_h - 2)
        self._truck.move(max(0, truck_x), truck_y)


def add_corner_sparkles(widget: QWidget, symbol: str = "✨") -> None:
    """Add two small sparkle decorations in the top corners of *widget*.

    The sparkles are sized to sit inside the top margin (≈28 px) without
    overlapping content. They are transparent to mouse events.
    """
    for x in (8, 555):
        lbl = QLabel(symbol, widget)
        lbl.setStyleSheet("font-size: 16px; background: transparent;")
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl.adjustSize()
        lbl.move(x, 6)
        lbl.raise_()
