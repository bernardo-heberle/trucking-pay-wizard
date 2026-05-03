"""Unit tests for src.gui._errors.friendly_message.

Every branch must pin the exact returned string — per the testing rules,
weak oracles like ``assert 'permission' in result.lower()`` are not
acceptable here.
"""

from __future__ import annotations

import errno

import pytest

from src.gui._errors import friendly_message


# ---------------------------------------------------------------------------
# PermissionError
# ---------------------------------------------------------------------------


def test_permission_error_returns_permission_message() -> None:
    result = friendly_message(PermissionError("access denied"))
    assert result == (
        "Permission denied — this folder or file cannot be written to. "
        "Try selecting a different folder, or ask IT to check your permissions."
    )


# ---------------------------------------------------------------------------
# FileNotFoundError
# ---------------------------------------------------------------------------


def test_file_not_found_returns_not_found_message() -> None:
    result = friendly_message(FileNotFoundError("no such file"))
    assert result == (
        "A required file or folder was not found. "
        "Make sure the documents folder still exists and has not been renamed."
    )


# ---------------------------------------------------------------------------
# OSError with WinError 32 (file in use)
# ---------------------------------------------------------------------------


def test_os_error_winerror_32_returns_file_in_use_message() -> None:
    exc = OSError()
    exc.winerror = 32
    result = friendly_message(exc)
    assert result == (
        "A file is open in another program — close it and try again. "
        "(Tip: close the PDF in Acrobat / Edge and the spreadsheet in Excel.)"
    )


# ---------------------------------------------------------------------------
# OSError with errno EACCES is a PermissionError in Python — handled above
# ---------------------------------------------------------------------------


def test_os_error_eacces_is_caught_as_permission_error() -> None:
    # Python promotes OSError(EACCES) to PermissionError, so it hits the
    # PermissionError branch rather than the OSError/WinError branch.
    exc = OSError(errno.EACCES, "permission denied")
    assert isinstance(exc, PermissionError)  # contract assertion
    result = friendly_message(exc)
    assert result == (
        "Permission denied — this folder or file cannot be written to. "
        "Try selecting a different folder, or ask IT to check your permissions."
    )


# ---------------------------------------------------------------------------
# OSError with WinError 5 (access denied)
# ---------------------------------------------------------------------------


def test_os_error_winerror_5_returns_access_denied_message() -> None:
    exc = OSError()
    exc.winerror = 5
    result = friendly_message(exc)
    assert result == (
        "Access denied — Windows blocked a write operation. "
        "Try running the tool from a folder in your Documents or Desktop."
    )


# ---------------------------------------------------------------------------
# OSError with WinError 112 (disk full)
# ---------------------------------------------------------------------------


def test_os_error_winerror_112_returns_disk_full_message() -> None:
    exc = OSError()
    exc.winerror = 112
    result = friendly_message(exc)
    assert result == "Disk full — free up space and try again."


# ---------------------------------------------------------------------------
# OSError with errno ENOSPC (disk full on non-Windows)
# ---------------------------------------------------------------------------


def test_os_error_enospc_returns_disk_full_message() -> None:
    exc = OSError(errno.ENOSPC, "no space left on device")
    result = friendly_message(exc)
    assert result == "Disk full — free up space and try again."


# ---------------------------------------------------------------------------
# ConnectionError
# ---------------------------------------------------------------------------


def test_connection_error_returns_network_message() -> None:
    result = friendly_message(ConnectionError("connection refused"))
    assert result == (
        "Could not reach one of the cloud services. "
        "Check your internet connection and try again."
    )


# ---------------------------------------------------------------------------
# TimeoutError
# ---------------------------------------------------------------------------


def test_timeout_error_returns_network_message() -> None:
    result = friendly_message(TimeoutError("timed out"))
    assert result == (
        "Could not reach one of the cloud services. "
        "Check your internet connection and try again."
    )


# ---------------------------------------------------------------------------
# OcrError with credential keywords
# ---------------------------------------------------------------------------


def test_ocr_error_with_endpoint_keyword_returns_credential_message() -> None:
    from src.ocr.exceptions import OcrError

    exc = OcrError("Azure endpoint not found.")
    result = friendly_message(exc)
    assert result == (
        "Azure credentials are invalid or missing. "
        "Go to File \u2192 Settings\u2026 to update them."
    )


def test_ocr_error_with_key_keyword_returns_credential_message() -> None:
    from src.ocr.exceptions import OcrError

    exc = OcrError("Azure key not found.")
    result = friendly_message(exc)
    assert result == (
        "Azure credentials are invalid or missing. "
        "Go to File \u2192 Settings\u2026 to update them."
    )


def test_ocr_error_without_credential_keyword_returns_ocr_prefix() -> None:
    from src.ocr.exceptions import OcrError

    exc = OcrError("Something unexpected happened during OCR.")
    result = friendly_message(exc)
    assert result == "OCR error: Something unexpected happened during OCR."


# ---------------------------------------------------------------------------
# ValueError with ANTHROPIC_API_KEY in message
# ---------------------------------------------------------------------------


def test_value_error_anthropic_key_returns_credential_message() -> None:
    exc = ValueError("ANTHROPIC_API_KEY is required but was not found.")
    result = friendly_message(exc)
    assert result == (
        "Anthropic API key is missing. "
        "Go to File \u2192 Settings\u2026 to enter your credentials."
    )


# ---------------------------------------------------------------------------
# Catch-all
# ---------------------------------------------------------------------------


def test_unknown_exception_returns_str_representation() -> None:
    exc = RuntimeError("some unexpected internal error")
    result = friendly_message(exc)
    assert result == "some unexpected internal error"


def test_unknown_exception_does_not_hide_message() -> None:
    exc = Exception("specific detail that must not be lost")
    result = friendly_message(exc)
    assert "specific detail that must not be lost" in result
