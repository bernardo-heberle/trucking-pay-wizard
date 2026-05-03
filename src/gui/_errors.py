"""Human-readable error messages for common pipeline failures.

``friendly_message(exc)`` is called in the GUI wherever raw exception text
would otherwise be shown to non-technical staff.  The raw message is still
written to the log file so developers keep full information.

The function is exhaustively unit-tested in ``tests/unit/gui/test_errors.py``.
"""

from __future__ import annotations

import errno
import os


def friendly_message(exc: BaseException) -> str:
    """Return a staff-facing description of *exc*.

    Falls through to ``str(exc)`` for any exception type not explicitly
    handled so we never silently hide information.
    """
    # ── Credential / auth errors ─────────────────────────────────────────────
    if isinstance(exc, ValueError) and "ANTHROPIC_API_KEY" in str(exc):
        return (
            "Anthropic API key is missing. "
            "Go to File \u2192 Settings\u2026 to enter your credentials."
        )

    # ── OS / file-system errors ──────────────────────────────────────────────
    if isinstance(exc, PermissionError):
        return (
            "Permission denied — this folder or file cannot be written to. "
            "Try selecting a different folder, or ask IT to check your permissions."
        )

    if isinstance(exc, FileNotFoundError):
        return (
            "A required file or folder was not found. "
            "Make sure the documents folder still exists and has not been renamed."
        )

    if isinstance(exc, OSError):
        # WinError 32 — file in use by another process (ERROR_SHARING_VIOLATION)
        if getattr(exc, "winerror", None) == 32:
            return (
                "A file is open in another program — close it and try again. "
                "(Tip: close the PDF in Acrobat / Edge and the spreadsheet in Excel.)"
            )
        # WinError 5 — access denied
        if getattr(exc, "winerror", None) == 5:
            return (
                "Access denied — Windows blocked a write operation. "
                "Try running the tool from a folder in your Documents or Desktop."
            )
        # WinError 112 — disk full
        if getattr(exc, "winerror", None) == 112:
            return "Disk full — free up space and try again."

        if getattr(exc, "errno", None) == errno.ENOSPC:
            return "Disk full — free up space and try again."

    # ── Network errors ───────────────────────────────────────────────────────
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return (
            "Could not reach one of the cloud services. "
            "Check your internet connection and try again."
        )

    # ── OcrError ─────────────────────────────────────────────────────────────
    try:
        from src.ocr.exceptions import OcrError  # lazy import — avoids circular deps at test time

        if isinstance(exc, OcrError):
            msg = str(exc)
            if "endpoint" in msg.lower() or "key" in msg.lower():
                return (
                    "Azure credentials are invalid or missing. "
                    "Go to File \u2192 Settings\u2026 to update them."
                )
            return f"OCR error: {msg}"
    except ImportError:
        pass

    # ── Extraction errors ────────────────────────────────────────────────────
    try:
        from src.extract.exceptions import ExtractionError  # lazy import

        if isinstance(exc, ExtractionError):
            return f"Extraction error: {exc}"
    except ImportError:
        pass

    # ── Catch-all ────────────────────────────────────────────────────────────
    return str(exc)
