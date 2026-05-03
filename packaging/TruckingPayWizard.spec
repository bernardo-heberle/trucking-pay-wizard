# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Trucking Pay Wizard.
#
# Build with:
#   pyinstaller packaging/TruckingPayWizard.spec --clean --noconfirm
#
# The output is a one-folder bundle at dist/TruckingPayWizard/.
# Inno Setup then wraps that folder into a single-file installer.

import sys
from pathlib import Path
import importlib.util

# ---------------------------------------------------------------------------
# Read __version__ without importing the whole package
# ---------------------------------------------------------------------------
_spec_path = Path("src/__version__.py")
_spec = importlib.util.spec_from_file_location("__version__", _spec_path)
_ver_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ver_mod)
APP_VERSION = _ver_mod.__version__

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(".").resolve()
ENTRY_POINT = str(PROJECT_ROOT / "run_gui.py")
ICON_PATH = str(PROJECT_ROOT / "packaging" / "icon.ico")
ASSETS_SRC = str(PROJECT_ROOT / "src" / "gui" / "assets")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [ENTRY_POINT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (ASSETS_SRC, "src/gui/assets"),
    ],
    hiddenimports=[
        # PyMuPDF registers its backend lazily
        "fitz",
        "fitz.utils",
        # keyring Windows backend
        "keyring.backends.Windows",
        "keyring.backends.fail",
        # Azure SDK internals
        "azure.ai.documentintelligence",
        "azure.ai.documentintelligence.models",
        "azure.core.pipeline.transport._requests_basic",
        "azure.core.pipeline.transport._requests_asyncio",
        # Anthropic SDK
        "anthropic",
        "anthropic._models",
        # PySide6 extras sometimes missed
        "PySide6.QtSvg",
        "PySide6.QtXml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "IPython",
        "notebook",
        "pytest",
        "hypothesis",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TruckingPayWizard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window
    windowed=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TruckingPayWizard",
)
