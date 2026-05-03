"""Credentials setup page — first-run and Settings re-entry.

Users paste a setup code (auto-fills all fields) or enter the three keys
by hand.  Clicking "Save & Continue" runs a live validation test against
both providers on a background thread.  Keys are written to Windows
Credential Manager **only** if both tests pass.
"""

from __future__ import annotations

import concurrent.futures

from loguru import logger
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src import credentials as _creds
from src.gui._widgets import TruckProgressWidget, add_corner_sparkles
from src.setup_code import InvalidSetupCodeError, decode_setup_code


# ---------------------------------------------------------------------------
# Background validation worker
# ---------------------------------------------------------------------------


def _test_anthropic(api_key: str) -> str | None:
    """Return None on success, error description on failure."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
            timeout=10,
        )
        return None
    except anthropic.AuthenticationError:
        return "Invalid API key — check it was copied correctly."
    except anthropic.PermissionDeniedError:
        return "Permission denied — this key does not have access."
    except Exception as exc:
        if "connect" in str(exc).lower() or "timeout" in str(exc).lower():
            return "Could not reach Anthropic — check your internet connection."
        return f"Anthropic error: {exc}"


def _test_azure(endpoint: str, key: str) -> str | None:
    """Return None on success, error description on failure."""
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

        client = DocumentIntelligenceClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )
        # list_operations() is a lightweight read-only call with no billing.
        list(client.list_operations())
        return None
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "authentication" in msg.lower() or "unauthorized" in msg.lower():
            return "Invalid credentials — check the endpoint and key."
        if "403" in msg or "forbidden" in msg.lower():
            return "Permission denied — this key does not have access."
        if "connect" in msg.lower() or "timeout" in msg.lower() or "name" in msg.lower():
            return "Could not reach Azure — check your internet connection and endpoint URL."
        return f"Azure error: {exc}"


class _CredentialsTestWorker(QObject):
    finished = Signal(object, object)  # (anthropic_err | None, azure_err | None)

    def __init__(self, anthropic_key: str, azure_endpoint: str, azure_key: str) -> None:
        super().__init__()
        self._anthropic_key = anthropic_key
        self._azure_endpoint = azure_endpoint
        self._azure_key = azure_key

    @Slot()
    def run(self) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f_anthropic = pool.submit(_test_anthropic, self._anthropic_key)
            f_azure = pool.submit(_test_azure, self._azure_endpoint, self._azure_key)
            anthropic_err = f_anthropic.result()
            azure_err = f_azure.result()
        self.finished.emit(anthropic_err, azure_err)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


class CredentialsPage(QWidget):
    credentials_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _CredentialsTestWorker | None = None
        self._build_ui()
        self._prefill_from_store()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(8)

        title = QLabel("<b>API Credentials Setup</b>")
        root.addWidget(title)

        intro = QLabel(
            "This tool needs API keys for two cloud services. "
            "If you received a setup code from IT, paste it below. "
            "Otherwise enter the keys manually."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addSpacing(8)

        # ── Setup-code section ───────────────────────────────────────────────
        code_group = QGroupBox("Have a setup code?")
        code_layout = QHBoxLayout(code_group)
        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("Paste the setup code here…")
        self._code_edit.textChanged.connect(self._clear_code_error)
        code_layout.addWidget(self._code_edit)
        use_code_btn = QPushButton("Use code")
        use_code_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        use_code_btn.clicked.connect(self._apply_setup_code)
        code_layout.addWidget(use_code_btn)
        root.addWidget(code_group)

        self._code_error = QLabel("")
        self._code_error.setStyleSheet("color: red;")
        self._code_error.setWordWrap(True)
        self._code_error.setVisible(False)
        root.addWidget(self._code_error)

        root.addSpacing(4)

        # ── Manual entry section ─────────────────────────────────────────────
        manual_group = QGroupBox("API keys")
        manual_layout = QVBoxLayout(manual_group)
        manual_layout.setSpacing(6)

        self._anthropic_edit, self._anthropic_err = self._make_key_row(
            manual_layout,
            label="Anthropic API key",
            placeholder="sk-ant-…",
        )
        self._azure_endpoint_edit, self._azure_endpoint_err = self._make_key_row(
            manual_layout,
            label="Azure endpoint",
            placeholder="https://<resource>.cognitiveservices.azure.com/",
            masked=False,
        )
        self._azure_key_edit, self._azure_key_err = self._make_key_row(
            manual_layout,
            label="Azure Document Intelligence key",
            placeholder="32-character hex key",
        )

        howto = QLabel(
            "<small><i>Where do I get these? "
            "Anthropic key: console.anthropic.com \u2192 API keys. "
            "Azure: portal.azure.com \u2192 your Document Intelligence resource \u2192 Keys and Endpoint.</i></small>"
        )
        howto.setWordWrap(True)
        howto.setTextFormat(Qt.TextFormat.RichText)
        manual_layout.addWidget(howto)

        root.addWidget(manual_group)

        root.addStretch()

        # ── Progress / status ─────────────────────────────────────────────────
        self._truck_progress = TruckProgressWidget()
        root.addWidget(self._truck_progress)

        self._status = QLabel("")
        self._status.setStyleSheet("color: gray;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # ── Save button ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("Save \u0026 Continue")
        self._save_btn.setMinimumWidth(140)
        self._save_btn.setMinimumHeight(34)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

        # Enable Save when all three key fields are non-empty
        for edit in (self._anthropic_edit, self._azure_endpoint_edit, self._azure_key_edit):
            edit.textChanged.connect(self._refresh_save_btn)

        add_corner_sparkles(self)

    def _make_key_row(
        self,
        layout: QVBoxLayout,
        label: str,
        placeholder: str,
        masked: bool = True,
    ) -> tuple[QLineEdit, QLabel]:
        layout.addWidget(QLabel(f"<b>{label}</b>"))
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if masked:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(edit)
        err_label = QLabel("")
        err_label.setStyleSheet("color: red; font-size: 11px;")
        err_label.setVisible(False)
        layout.addWidget(err_label)
        return edit, err_label

    def _prefill_from_store(self) -> None:
        """Pre-fill fields if credentials are already stored (Settings re-entry)."""
        if key := _creds.get_anthropic_key():
            self._anthropic_edit.setText(key)
        if endpoint := _creds.get_azure_endpoint():
            self._azure_endpoint_edit.setText(endpoint)
        if key := _creds.get_azure_key():
            self._azure_key_edit.setText(key)

    def _refresh_save_btn(self) -> None:
        all_filled = bool(
            self._anthropic_edit.text().strip()
            and self._azure_endpoint_edit.text().strip()
            and self._azure_key_edit.text().strip()
        )
        self._save_btn.setEnabled(all_filled)

    def _clear_code_error(self) -> None:
        self._code_error.setVisible(False)

    def _apply_setup_code(self) -> None:
        code = self._code_edit.text().strip()
        if not code:
            return
        try:
            payload = decode_setup_code(code)
        except InvalidSetupCodeError as exc:
            self._code_error.setText(str(exc))
            self._code_error.setVisible(True)
            return
        self._anthropic_edit.setText(payload.anthropic_key)
        self._azure_endpoint_edit.setText(payload.azure_endpoint)
        self._azure_key_edit.setText(payload.azure_key)
        self._code_error.setVisible(False)
        self._set_status("Setup code applied — click Save & Continue to verify.", "gray")

    def _on_save(self) -> None:
        # Clear previous per-field errors
        for err in (self._anthropic_err, self._azure_endpoint_err, self._azure_key_err):
            err.setVisible(False)

        anthropic_key = self._anthropic_edit.text().strip()
        azure_endpoint = self._azure_endpoint_edit.text().strip()
        azure_key = self._azure_key_edit.text().strip()

        self._save_btn.setEnabled(False)
        self._truck_progress.setRange(0, 0)
        self._truck_progress.setVisible(True)
        self._set_status("Checking your keys…", "gray")

        self._worker = _CredentialsTestWorker(anthropic_key, azure_endpoint, azure_key)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_test_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot(object, object)
    def _on_test_finished(
        self, anthropic_err: str | None, azure_err: str | None
    ) -> None:
        self._truck_progress.setVisible(False)

        if anthropic_err or azure_err:
            if anthropic_err:
                self._anthropic_err.setText(f"Anthropic: {anthropic_err}")
                self._anthropic_err.setVisible(True)
                logger.warning("Anthropic credential test failed: {}", anthropic_err)
            else:
                self._anthropic_err.setText("Anthropic: \u2713 Connected")
                self._anthropic_err.setStyleSheet("color: green; font-size: 11px;")
                self._anthropic_err.setVisible(True)

            if azure_err:
                self._azure_key_err.setText(f"Azure: {azure_err}")
                self._azure_key_err.setVisible(True)
                logger.warning("Azure credential test failed: {}", azure_err)
            else:
                self._azure_key_err.setText("Azure: \u2713 Connected")
                self._azure_key_err.setStyleSheet("color: green; font-size: 11px;")
                self._azure_key_err.setVisible(True)

            self._set_status(
                "One or more keys could not be verified. Correct them and try again.", "red"
            )
            self._save_btn.setEnabled(True)
            return

        # Both passed — persist to keyring
        _creds.save_all(
            anthropic_key=self._anthropic_edit.text().strip(),
            azure_endpoint=self._azure_endpoint_edit.text().strip(),
            azure_key=self._azure_key_edit.text().strip(),
        )
        logger.info("Credentials saved to Credential Manager.")
        self._set_status("Keys verified and saved.", "green")
        self.credentials_saved.emit()

    def _set_status(self, text: str, color: str) -> None:
        self._status.setStyleSheet(f"color: {color};")
        self._status.setText(text)
