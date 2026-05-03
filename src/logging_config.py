"""Configure loguru to write rotating file logs.

Call ``configure_file_logging()`` once from ``run_gui.py`` so that
PyInstaller ``--noconsole`` builds still capture output.

Log location: ``%LOCALAPPDATA%\\TruckingPayWizard\\logs\\app.log``
Rotation:     5 MB per file, keep 5 files, compress older files.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger


def _log_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    log_dir = Path(local_appdata) / "TruckingPayWizard" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_file_logging() -> None:
    """Add a rotating file sink to loguru.

    Safe to call multiple times — the default stderr sink already added by
    loguru remains; this adds a *second* sink to the rotating log file.
    In a ``--noconsole`` PyInstaller build there is no stderr, so the file
    sink is the only way to capture output.
    """
    log_path = _log_dir() / "app.log"

    logger.add(
        str(log_path),
        rotation="5 MB",
        retention=5,
        compression="zip",
        level="DEBUG",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
    )

    logger.info(
        "Trucking Pay Wizard starting — log file: {path}",
        path=log_path,
    )
