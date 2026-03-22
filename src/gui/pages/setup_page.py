from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui._widgets import TruckProgressWidget, add_corner_sparkles
from src.ingest import collect_source_files


class _PipelineWorker(QObject):
    """Runs all pipeline stages on a background thread.

    Emits ``progress`` with a status string, ``progress_step`` with
    (current, total) for the progress bar, ``finished`` on success,
    or ``error`` with a message on failure.
    """

    progress: Signal = Signal(str)
    progress_step: Signal = Signal(int, int)   # current, total
    finished: Signal = Signal(str, str)        # pdf_path, excel_path
    error: Signal = Signal(str)

    def __init__(self, folder: Path, prefix: str) -> None:
        super().__init__()
        self._folder = folder
        self._prefix = prefix

    @Slot()
    def run(self) -> None:
        try:
            from src.cache import cache_get, cache_put
            from src.extract import extract_document
            from src.ingest import ingest_document
            from src.ocr import analyze_document, build_client
            from src.report import build_report

            source_files = collect_source_files(self._folder)
            n = len(source_files)
            # total steps = one per document + one for report assembly
            total = n + 1
            self.progress.emit(
                f"Found {n} document{'s' if n != 1 else ''} — starting…"
            )
            self.progress_step.emit(0, total)

            client = None
            results = []

            for i, source_path in enumerate(source_files, 1):
                ingested = ingest_document(source_path)
                extraction = cache_get(self._folder, ingested.content_hash)

                if extraction is not None:
                    self.progress.emit(
                        f"Document {i} of {n}: {source_path.name} — already processed"
                    )
                else:
                    self.progress.emit(
                        f"Document {i} of {n}: reading {source_path.name}…"
                    )
                    if client is None:
                        client = build_client()
                    ocr_result = analyze_document(ingested, client)
                    extraction = extract_document(ocr_result, page_count=ingested.page_count)
                    cache_put(self._folder, extraction)

                results.append(extraction)
                self.progress_step.emit(i, total)

            self.progress.emit("Building your report…")
            pdf_path, excel_path = build_report(
                results, self._folder / "results", prefix=self._prefix
            )
            self.progress_step.emit(total, total)
            self.finished.emit(str(pdf_path), str(excel_path))

        except Exception as exc:
            self.error.emit(str(exc))


class SetupPage(QWidget):
    pipeline_finished = Signal(str, str)  # pdf_path, excel_path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _PipelineWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 24)
        root.setSpacing(8)

        # ── Folder section ───────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Documents folder</b>"))

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText(
            "Select the folder containing the income documents…"
        )
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        self._doc_count_label = QLabel("No folder selected.")
        self._doc_count_label.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(self._doc_count_label)

        root.addSpacing(12)

        # ── Report naming ────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Choose a file name for your report</b>"))

        prefix_row = QHBoxLayout()
        prefix_lbl = QLabel("File name:")
        prefix_lbl.setFixedWidth(48)
        self._prefix_edit = QLineEdit("report")
        self._prefix_edit.setMaximumWidth(180)
        self._prefix_edit.setToolTip(
            "Used as the filename base for the PDF and spreadsheet (e.g. "
            "\u201cclaim_123\u201d produces claim_123_combined.pdf and "
            "claim_123_data.xlsx)"
        )
        self._prefix_edit.textChanged.connect(self._refresh_output_label)
        prefix_row.addWidget(prefix_lbl)
        prefix_row.addWidget(self._prefix_edit)
        prefix_row.addStretch()
        root.addLayout(prefix_row)

        self._output_label = QLabel()
        self._output_label.setStyleSheet("color: gray; font-size: 11px;")
        self._output_label.setWordWrap(True)
        root.addWidget(self._output_label)
        self._refresh_output_label()

        root.addStretch()

        # ── Progress bar with truck ──────────────────────────────────────────
        self._truck_progress = TruckProgressWidget()
        root.addWidget(self._truck_progress)

        root.addSpacing(4)

        # ── Run button ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._run_btn = QPushButton("Generate Report")
        self._run_btn.setEnabled(False)
        self._run_btn.setFixedWidth(160)
        self._run_btn.setFixedHeight(34)
        self._run_btn.clicked.connect(self._start_pipeline)
        btn_row.addWidget(self._run_btn)
        root.addLayout(btn_row)

        root.addSpacing(8)

        self._status_label = QLabel("Ready.")
        self._status_label.setStyleSheet("font-size: 11px; color: gray;")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        add_corner_sparkles(self)

    # ── Folder picker ────────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select documents folder")
        if not folder:
            return

        path = Path(folder)
        self._folder_edit.setText(str(path))

        try:
            files = collect_source_files(path)
        except Exception as exc:
            self._doc_count_label.setText(f"Could not read folder: {exc}")
            self._doc_count_label.setStyleSheet("color: red; font-size: 11px;")
            self._run_btn.setEnabled(False)
            return

        if not files:
            self._doc_count_label.setText(
                "No documents found in this folder (PDF, PNG, JPG, TIFF are supported)."
            )
            self._doc_count_label.setStyleSheet("color: red; font-size: 11px;")
            self._run_btn.setEnabled(False)
        else:
            n = len(files)
            self._doc_count_label.setText(
                f"{n} document{'s' if n != 1 else ''} ready to process."
            )
            self._doc_count_label.setStyleSheet("color: green; font-size: 11px;")
            self._run_btn.setEnabled(True)

    # ── Output label ─────────────────────────────────────────────────────────

    def _refresh_output_label(self) -> None:
        prefix = self._prefix_edit.text().strip() or "report"
        self._output_label.setText(
            f"Saved to results/:  "
            f"{prefix}_combined.pdf  \u00b7  {prefix}_data.xlsx"
        )

    # ── Pipeline execution ───────────────────────────────────────────────────

    def _start_pipeline(self) -> None:
        folder = Path(self._folder_edit.text())
        prefix = self._prefix_edit.text().strip() or "report"

        self._run_btn.setEnabled(False)
        self._truck_progress.setRange(0, 0)   # indeterminate until we know the count
        self._truck_progress.setVisible(True)
        self._set_status("Starting…", "gray")

        self._worker = _PipelineWorker(folder, prefix)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.progress_step.connect(self._on_progress_step)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(str)
    def _on_progress(self, message: str) -> None:
        self._set_status(message, "gray")

    @Slot(int, int)
    def _on_progress_step(self, current: int, total: int) -> None:
        self._truck_progress.setRange(0, total)
        self._truck_progress.setValue(current)

    @Slot(str, str)
    def _on_finished(self, pdf_path: str, excel_path: str) -> None:
        self._truck_progress.setVisible(False)
        self._set_status("Ready.", "gray")
        self._run_btn.setEnabled(True)
        self.pipeline_finished.emit(pdf_path, excel_path)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._truck_progress.setVisible(False)
        self._set_status(f"Something went wrong: {message}", "red")
        self._run_btn.setEnabled(True)

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.setStyleSheet(f"font-size: 11px; color: {color};")
        self._status_label.setText(text)
