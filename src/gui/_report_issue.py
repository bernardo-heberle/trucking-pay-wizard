"""Bug-report bundler for the Settings → "Report an issue…" menu entry.

``bundle_logs()`` zips the rotating log files to the user's Desktop.
``open_mail_with_report(zip_path)`` opens the system mail client with a
prefilled subject and body so the user only needs to attach the zip.
"""

from __future__ import annotations

import os
import platform
import urllib.parse
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.__version__ import __version__

_SUPPORT_EMAIL = "bernardo.aguzzoli@gmail.com"


def _log_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local_appdata) / "TruckingPayWizard" / "logs"


def _desktop_dir() -> Path:
    return Path.home() / "Desktop"


def bundle_logs() -> Path:
    """Zip the log folder to the Desktop and return the zip path.

    Returns:
        Path to the created ``trucking-pay-wizard-bug-report-<timestamp>.zip``.

    Raises:
        FileNotFoundError: The log directory does not exist (no logs yet).
        RuntimeError: No log files were found to bundle.
    """
    log_dir = _log_dir()
    if not log_dir.exists():
        raise FileNotFoundError(
            f"No log folder found at {log_dir}. "
            "Run the tool at least once before reporting an issue."
        )

    log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.log.zip"))
    if not log_files:
        raise RuntimeError(
            f"No log files found in {log_dir}. "
            "Run the tool at least once before reporting an issue."
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_name = f"trucking-pay-wizard-bug-report-{timestamp}.zip"
    zip_path = _desktop_dir() / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for log_file in log_files:
            zf.write(log_file, arcname=log_file.name)

    logger.info("Bug report bundle created: {}", zip_path)
    return zip_path


def open_mail_with_report(zip_path: Path) -> None:
    """Open the system mail client with a prefilled bug-report email.

    The zip path is included in the body with a request to attach it.
    ``mailto:`` links cannot attach files reliably across mail clients, so
    we rely on the user dragging the file in.
    """
    subject = f"Trucking Pay Wizard bug report — v{__version__}"
    body = (
        "Please describe what you were doing when the issue occurred:\n\n"
        "[Describe the issue here]\n\n"
        "--- App information ---\n"
        f"Version: {__version__}\n"
        f"OS: {platform.system()} {platform.version()}\n\n"
        "--- Attachment instructions ---\n"
        f"Please attach the file below before sending:\n{zip_path}\n"
        f"\n(It was saved to your Desktop as: {zip_path.name})"
    )

    mailto_url = (
        f"mailto:{urllib.parse.quote(_SUPPORT_EMAIL)}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )

    logger.info("Opening mail client for bug report")
    webbrowser.open(mailto_url)
