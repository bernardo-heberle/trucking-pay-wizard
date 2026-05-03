"""Launch the Trucking Pay Wizard GUI.

Usage:
    python run_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.logging_config import configure_file_logging  # noqa: E402
from src.gui.app import main  # noqa: E402

if __name__ == "__main__":
    configure_file_logging()
    main()
