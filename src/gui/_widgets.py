"""Shared GUI widgets used across pages."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QLabel, QProgressBar, QWidget

# ── Scaling ───────────────────────────────────────────────────────────────────

_BASE_W: int = 700
_BASE_H: int = 700
_BASE_PT: float = 10.0   # point size that matches the 700×700 base size


def ui_scale(width: int, height: int) -> float:
    """Scale factor relative to the 640×520 base window, capped at 1.5×."""
    return max(1.0, min(width / _BASE_W, height / _BASE_H, 1.5))


# ── Flipped truck ─────────────────────────────────────────────────────────────

class _FlippedTruckLabel(QWidget):
    """Renders the 🚛 emoji mirrored horizontally so it faces right."""

    _SIZE_PX = 28   # fixed square size of the widget

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self._SIZE_PX + 8, self._SIZE_PX + 8)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        font = QFont()
        font.setPixelSize(self._SIZE_PX)
        painter.setFont(font)
        # Translate right then scale x by -1 to mirror the emoji.
        painter.translate(self.width(), 0)
        painter.scale(-1.0, 1.0)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🚛")
        painter.end()


# ── Truck progress widget ─────────────────────────────────────────────────────

class TruckProgressWidget(QWidget):
    """A progress bar with a truck that rolls along above it.

    Use ``setRange`` / ``setValue`` exactly as you would ``QProgressBar``.
    Call ``setRange(0, 0)`` for indeterminate (pulsing) mode.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setVisible(False)

        self._truck = _FlippedTruckLabel(self)

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


# ── Resize-aware corner sparkles ──────────────────────────────────────────────

class _SparkleManager(QObject):
    """Event-filter that keeps two sparkle labels in the top corners of a
    parent widget as it resizes."""

    def __init__(self, labels: list[QLabel], parent: QWidget) -> None:
        super().__init__(parent)
        self._labels = labels
        parent.installEventFilter(self)
        self._reposition(parent.width())

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            self._reposition(event.size().width())  # type: ignore[attr-defined]
        return False

    def _reposition(self, width: int) -> None:
        if not self._labels:
            return
        self._labels[0].move(8, 6)
        if len(self._labels) > 1:
            right_x = width - self._labels[1].width() - 8
            self._labels[1].move(max(8, right_x), 6)


def add_corner_sparkles(widget: QWidget, symbol: str = "✨") -> None:
    """Add two sparkle decorations in the top corners of *widget*.

    The sparkles reposition themselves when the widget is resized and are
    transparent to mouse events.
    """
    labels: list[QLabel] = []
    for _ in range(2):
        lbl = QLabel(symbol, widget)
        lbl.setStyleSheet("font-size: 16px; background: transparent;")
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl.adjustSize()
        lbl.raise_()
        labels.append(lbl)
    _SparkleManager(labels, widget)
