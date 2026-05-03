from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from src import credentials as _creds
from src import updater as _updater
from src.gui._widgets import _BASE_PT, ui_scale
from src.gui.pages.credentials_page import CredentialsPage
from src.gui.pages.results_page import ResultsPage
from src.gui.pages.setup_page import SetupPage
from src.gui.pages.welcome_page import WelcomePage

_IDX_CREDENTIALS = 0
_IDX_WELCOME = 1
_IDX_SETUP = 2
_IDX_RESULTS = 3


# ---------------------------------------------------------------------------
# Background update checker
# ---------------------------------------------------------------------------


class _UpdateCheckWorker(QObject):
    result = Signal(object)  # UpdateInfo | None

    def __init__(self, force: bool = False) -> None:
        super().__init__()
        self._force = force

    @Slot()
    def run(self) -> None:
        info = _updater.check_for_update(force=self._force)
        self.result.emit(info)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trucking Pay Wizard")
        self.setMinimumSize(640, 620)
        self.resize(700, 700)

        self._stack = QStackedWidget()
        self._credentials = CredentialsPage()
        self._welcome = WelcomePage()
        self._setup = SetupPage()
        self._results = ResultsPage()

        self._stack.addWidget(self._credentials)  # 0
        self._stack.addWidget(self._welcome)       # 1
        self._stack.addWidget(self._setup)         # 2
        self._stack.addWidget(self._results)       # 3

        self._credentials.credentials_saved.connect(self._on_credentials_saved)
        self._welcome.next_requested.connect(lambda: self._stack.setCurrentIndex(_IDX_SETUP))
        self._setup.pipeline_finished.connect(self._show_results)
        self._results.run_another_requested.connect(lambda: self._stack.setCurrentIndex(_IDX_SETUP))

        self.setCentralWidget(self._stack)
        self._build_menu()

        # Route to credentials page if keys are missing; otherwise welcome page.
        if _creds.credentials_present():
            self._stack.setCurrentIndex(_IDX_WELCOME)
            self._start_update_check()
        else:
            self._stack.setCurrentIndex(_IDX_CREDENTIALS)

        self._update_thread: QThread | None = None
        self._update_worker: _UpdateCheckWorker | None = None

    def _build_menu(self) -> None:
        from PySide6.QtGui import QAction

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        keys_action = QAction("Update keys\u2026", self)
        keys_action.setStatusTip("Change your Anthropic and Azure API credentials.")
        keys_action.triggered.connect(self._open_credentials)
        file_menu.addAction(keys_action)

        check_action = QAction("Check for updates\u2026", self)
        check_action.setStatusTip("Check for a newer version of Trucking Pay Wizard.")
        check_action.triggered.connect(self._manual_update_check)
        file_menu.addAction(check_action)

        file_menu.addSeparator()

        report_action = QAction("Report an issue\u2026", self)
        report_action.setStatusTip("Bundle log files and open a bug-report email.")
        report_action.triggered.connect(self._report_issue)
        file_menu.addAction(report_action)

    # ── Navigation helpers ────────────────────────────────────────────────────

    def _on_credentials_saved(self) -> None:
        self._stack.setCurrentIndex(_IDX_WELCOME)
        self._start_update_check()

    def _show_results(self, pdf_path: str, excel_path: str) -> None:
        self._results.set_results(pdf_path, excel_path)
        self._stack.setCurrentIndex(_IDX_RESULTS)

    def _open_credentials(self) -> None:
        self._stack.setCurrentIndex(_IDX_CREDENTIALS)

    # ── Auto-update ───────────────────────────────────────────────────────────

    def _start_update_check(self, force: bool = False) -> None:
        self._update_worker = _UpdateCheckWorker(force=force)
        self._update_thread = QThread(self)
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.result.connect(self._on_update_check_result)
        self._update_worker.result.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_worker.deleteLater)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()

    @Slot(object)
    def _on_update_check_result(self, info: object) -> None:
        if info is None:
            return
        from src.gui.dialogs.update_dialog import UpdateDialog
        dlg = UpdateDialog(info, parent=self)  # type: ignore[arg-type]
        dlg.exec()

    def _manual_update_check(self) -> None:
        from src.gui.dialogs.update_dialog import UpdateDialog

        self._start_update_check(force=True)

        # For the manual check we also want a "you're up to date" toast.
        # We connect a one-shot slot below via a lambda so we don't clobber
        # the auto-check slot.
        def _show_toast(info: object) -> None:
            if info is None:
                QMessageBox.information(
                    self,
                    "No updates available",
                    "You are already running the latest version.",
                )

        if self._update_worker:
            self._update_worker.result.connect(_show_toast)

    # ── Report an issue ───────────────────────────────────────────────────────

    def _report_issue(self) -> None:
        from src.gui._report_issue import bundle_logs, open_mail_with_report

        try:
            zip_path = bundle_logs()
        except Exception as exc:
            QMessageBox.warning(
                self, "Could not bundle logs", str(exc)
            )
            return

        open_mail_with_report(zip_path)
        QMessageBox.information(
            self,
            "Bug report saved",
            f"A log bundle has been saved to your Desktop:\n\n{zip_path.name}\n\n"
            "We've opened your email client — please attach that file before sending.",
        )

    # ── Qt overrides ──────────────────────────────────────────────────────────

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
QGroupBox {
    border: 1px solid #c4b5fd;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
}
"""


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    base_font = QFont()
    base_font.setPointSizeF(_BASE_PT)
    app.setFont(base_font)
    app.setStyleSheet(_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
