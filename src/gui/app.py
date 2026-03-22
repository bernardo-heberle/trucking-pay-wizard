from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from src.gui.pages.setup_page import SetupPage
from src.gui.pages.welcome_page import WelcomePage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trucking Pay Wizard")
        self.setFixedSize(600, 460)

        self._stack = QStackedWidget()
        self._welcome = WelcomePage()
        self._setup = SetupPage()

        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._setup)

        self._welcome.next_requested.connect(lambda: self._stack.setCurrentIndex(1))
        self.setCentralWidget(self._stack)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
