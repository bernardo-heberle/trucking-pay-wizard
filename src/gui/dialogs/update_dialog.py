"""Update-available dialog shown when a newer release is found.

Presents the release notes and offers three actions:
- **Install now** — downloads and silently installs; app exits and Inno Setup
  relaunches it on the new version.
- **Later** — dismisses; the update will be offered again next day.
- **Skip this version** — dismisses and suppresses prompts for this exact
  version; a newer release will still prompt.

Usage::

    from src.gui.dialogs.update_dialog import UpdateDialog
    from src import updater

    info = updater.check_for_update()
    if info:
        dlg = UpdateDialog(info, parent=window)
        dlg.exec()
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src import updater as _updater
from src.updater import UpdateInfo


class _DownloadWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self._info = info

    @Slot()
    def run(self) -> None:
        try:
            _updater.download_and_install(self._info)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class UpdateDialog(QDialog):
    """Modal dialog offering the user three choices when an update is available."""

    def __init__(self, info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._info = info
        self._thread: QThread | None = None
        self._worker: _DownloadWorker | None = None
        self.setWindowTitle(f"Update available — v{info.version}")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        header = QLabel(
            f"<b>Trucking Pay Wizard v{self._info.version} is available.</b>"
        )
        root.addWidget(header)

        if self._info.release_notes:
            notes_browser = QTextBrowser()
            notes_browser.setOpenExternalLinks(True)
            notes_browser.setMaximumHeight(200)
            # QTextBrowser understands a small subset of HTML; markdown is
            # passed through as plain text so it still reads well.
            notes_browser.setMarkdown(self._info.release_notes)
            root.addWidget(notes_browser)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setVisible(False)
        root.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._skip_btn = QPushButton("Skip this version")
        self._skip_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        later_btn = QPushButton("Later")
        later_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        later_btn.clicked.connect(self.reject)
        btn_row.addWidget(later_btn)

        self._install_btn = QPushButton("Install now")
        self._install_btn.setDefault(True)
        self._install_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self._install_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self._install_btn)

        root.addLayout(btn_row)

    def _on_skip(self) -> None:
        _updater.skip_version(self._info.version)
        self.reject()

    def _on_install(self) -> None:
        self._install_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText("Downloading update…")
        self._status.setVisible(True)

        self._worker = _DownloadWorker(self._info)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._on_error)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Download failed: {message}")
        self._install_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
