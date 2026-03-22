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

from src.ingest import collect_source_files


class _PipelineWorker(QObject):
    """Runs all pipeline stages on a background thread.

    Emits ``progress`` for each step, ``finished`` on success, or
    ``error`` with an error message on failure.
    """

    progress: Signal = Signal(str)
    finished: Signal = Signal(str, str)   # pdf_path, excel_path
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
            self.progress.emit(f"Found {n} document(s)…")

            client = None
            results = []

            for i, source_path in enumerate(source_files, 1):
                ingested = ingest_document(source_path)
                extraction = cache_get(self._folder, ingested.content_hash)

                if extraction is not None:
                    self.progress.emit(f"[{i}/{n}] {source_path.name} — cached, skipping OCR")
                else:
                    self.progress.emit(f"[{i}/{n}] Processing {source_path.name}…")
                    if client is None:
                        self.progress.emit(f"[{i}/{n}] Connecting to Azure…")
                        client = build_client()
                    ocr_result = analyze_document(ingested, client)
                    extraction = extract_document(ocr_result, page_count=ingested.page_count)
                    cache_put(self._folder, extraction)

                results.append(extraction)

            self.progress.emit("Assembling report…")
            pdf_path, excel_path = build_report(
                results, self._folder / "results", prefix=self._prefix
            )
            self.finished.emit(str(pdf_path), str(excel_path))

        except Exception as exc:
            self.error.emit(str(exc))


class SetupPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _PipelineWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 24)
        root.setSpacing(8)

        # ── Input section ────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Input folder</b>"))

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText("Select a folder containing income documents…")
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

        # ── Output section ───────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Output</b>"))

        prefix_row = QHBoxLayout()
        prefix_lbl = QLabel("File prefix:")
        prefix_lbl.setFixedWidth(74)
        self._prefix_edit = QLineEdit("report")
        self._prefix_edit.setMaximumWidth(180)
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

        # ── Run button ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._run_btn = QPushButton("Run Pipeline")
        self._run_btn.setEnabled(False)
        self._run_btn.setFixedWidth(130)
        self._run_btn.setFixedHeight(34)
        self._run_btn.clicked.connect(self._start_pipeline)
        btn_row.addWidget(self._run_btn)
        root.addLayout(btn_row)

        root.addSpacing(8)

        self._status_label = QLabel("Ready.")
        self._status_label.setStyleSheet("font-size: 11px; color: gray;")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

    # ── Folder picker ────────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select input folder")
        if not folder:
            return

        path = Path(folder)
        self._folder_edit.setText(str(path))

        try:
            files = collect_source_files(path)
        except Exception as exc:
            self._doc_count_label.setText(f"Error scanning folder: {exc}")
            self._doc_count_label.setStyleSheet("color: red; font-size: 11px;")
            self._run_btn.setEnabled(False)
            return

        if not files:
            self._doc_count_label.setText(
                "No supported documents found (PDF, PNG, JPG, TIFF)."
            )
            self._doc_count_label.setStyleSheet("color: red; font-size: 11px;")
            self._run_btn.setEnabled(False)
        else:
            ext_note = ", ".join(sorted({f.suffix.upper().lstrip(".") for f in files}))
            self._doc_count_label.setText(
                f"{len(files)} document(s) found ({ext_note})."
            )
            self._doc_count_label.setStyleSheet("color: green; font-size: 11px;")
            self._run_btn.setEnabled(True)

    # ── Output label ─────────────────────────────────────────────────────────

    def _refresh_output_label(self) -> None:
        prefix = self._prefix_edit.text().strip() or "report"
        self._output_label.setText(
            f"Both files will be saved into results/:  "
            f"results/{prefix}_combined.pdf  \u00b7  results/{prefix}_extracted.xlsx"
        )

    # ── Pipeline execution ───────────────────────────────────────────────────

    def _start_pipeline(self) -> None:
        folder = Path(self._folder_edit.text())
        prefix = self._prefix_edit.text().strip() or "report"

        self._run_btn.setEnabled(False)
        self._set_status("Starting…", "gray")

        self._worker = _PipelineWorker(folder, prefix)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
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

    @Slot(str, str)
    def _on_finished(self, pdf_path: str, excel_path: str) -> None:
        pdf_name = Path(pdf_path).name
        xlsx_name = Path(excel_path).name
        self._set_status(f"Done.  {pdf_name}  \u00b7  {xlsx_name}", "green")
        self._run_btn.setEnabled(True)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._set_status(f"Error: {message}", "red")
        self._run_btn.setEnabled(True)

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.setStyleSheet(f"font-size: 11px; color: {color};")
        self._status_label.setText(text)
