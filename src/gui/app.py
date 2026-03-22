from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

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
        self.setFixedSize(600, 480)

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


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
