from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from src.gui._widgets import _BASE_PT, ui_scale
from src.gui.pages.results_page import ResultsPage
from src.gui.pages.setup_page import SetupPage
from src.gui.pages.welcome_page import WelcomePage

_IDX_WELCOME = 0
_IDX_SETUP = 1
_IDX_RESULTS = 2


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trucking Pay Wizard")
        self.setMinimumSize(640, 620)
        self.resize(700, 700)

        self._stack = QStackedWidget()
        self._welcome = WelcomePage()
        self._setup = SetupPage()
        self._results = ResultsPage()

        self._stack.addWidget(self._welcome)   # 0
        self._stack.addWidget(self._setup)     # 1
        self._stack.addWidget(self._results)   # 2

        self._welcome.next_requested.connect(lambda: self._stack.setCurrentIndex(_IDX_SETUP))
        self._setup.pipeline_finished.connect(self._show_results)
        self._results.run_another_requested.connect(lambda: self._stack.setCurrentIndex(_IDX_SETUP))

        self.setCentralWidget(self._stack)

    def _show_results(self, pdf_path: str, excel_path: str) -> None:
        self._results.set_results(pdf_path, excel_path)
        self._stack.setCurrentIndex(_IDX_RESULTS)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        scale = ui_scale(event.size().width(), event.size().height())
        font = QFont()
        font.setPointSizeF(_BASE_PT * scale)
        app = QApplication.instance()
        if app is not None:
            app.setFont(font)


_STYLESHEET = """
QWidget {
    background-color: #f3eeff;
    color: #2d1b69;
}
QLabel {
    background: transparent;
}
QPushButton {
    background-color: #8b5cf6;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: bold;
    min-width: 70px;
}
QPushButton:hover  { background-color: #7c3aed; }
QPushButton:pressed { background-color: #6d28d9; }
QPushButton:disabled {
    background-color: #c4b5fd;
    color: #ede9fe;
}
QLineEdit {
    background-color: white;
    border: 1.5px solid #c4b5fd;
    border-radius: 4px;
    padding: 3px 6px;
    color: #2d1b69;
}
QLineEdit:focus { border-color: #8b5cf6; }
QProgressBar {
    background-color: #e9d5ff;
    border-radius: 4px;
    border: none;
}
QProgressBar::chunk {
    background-color: #8b5cf6;
    border-radius: 4px;
}
"""


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    # Set the baseline font — MainWindow.resizeEvent scales this dynamically.
    base_font = QFont()
    base_font.setPointSizeF(_BASE_PT)
    app.setFont(base_font)
    app.setStyleSheet(_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
