"""Silent in-place auto-updater.

Polls the public release-mirror GitHub repo for a newer version once per
day.  When a newer release is found, the caller shows an update dialog;
the user's choice drives whether :func:`download_and_install` is called.

Typical call-site in ``app.py``::

    from src import updater

    info = updater.check_for_update()   # None when up-to-date or on network error
    if info:
        show_update_dialog(info)

The module uses only stdlib (``urllib.request``, ``json``, ``subprocess``)
so it adds no new dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.__version__ import __version__

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_GITHUB_API_URL = (
    "https://api.github.com/repos/{owner}/{repo}/releases/latest"
)

_MIRROR_OWNER = "bernardo-heberle"
_MIRROR_REPO = "trucking-pay-wizard-releases"

_RELEASES_URL = _GITHUB_API_URL.format(owner=_MIRROR_OWNER, repo=_MIRROR_REPO)

_REQUEST_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------


def _state_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    d = Path(local_appdata) / "TruckingPayWizard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file() -> Path:
    return _state_dir() / "update_check.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        _state_file().write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Could not save update-check state: {}", exc)


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a semver-ish string like 'v0.2.1' or '0.2.1' into a tuple."""
    v = v.lstrip("v").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    release_notes: str
    asset_size: int  # bytes; used to verify the download


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_for_update(*, force: bool = False) -> UpdateInfo | None:
    """Check GitHub Releases for a newer version.

    Returns an :class:`UpdateInfo` if a newer release is available, or
    ``None`` when already up-to-date, when the check is debounced, or on
    any network/parse error.

    Args:
        force: Bypass the 24-hour debounce (used by the manual
            "Check for updates…" menu entry).
    """
    state = _load_state()

    if not force:
        last_check = state.get("last_check")
        if last_check:
            try:
                last_dt = datetime.fromisoformat(last_check)
                delta = datetime.now(timezone.utc) - last_dt
                if delta.total_seconds() < 86_400:
                    logger.debug("Update check debounced (last check: {})", last_check)
                    return None
            except ValueError:
                pass

    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "TruckingPayWizard"},
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("Update check failed (network): {}", exc)
        return None

    state["last_check"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)

    remote_version = data.get("tag_name", "")
    if not _is_newer(remote_version, __version__):
        logger.debug(
            "No update available (current={}, latest={})", __version__, remote_version
        )
        return None

    version_str = remote_version.lstrip("v")

    if is_skipped(version_str):
        logger.debug("Update {} is in skipped_versions — not prompting", version_str)
        return None

    exe_asset = next(
        (
            a
            for a in data.get("assets", [])
            if a.get("name", "").endswith(".exe")
        ),
        None,
    )
    if exe_asset is None:
        logger.warning(
            "Release {} has no .exe asset — skipping update prompt", remote_version
        )
        return None

    return UpdateInfo(
        version=version_str,
        download_url=exe_asset["browser_download_url"],
        release_notes=data.get("body") or "",
        asset_size=exe_asset.get("size", 0),
    )


def download_and_install(info: UpdateInfo) -> None:
    """Download the installer and launch it silently, then exit.

    The installer is saved to ``%LOCALAPPDATA%\\TruckingPayWizard\\updates\\``.
    Inno Setup's ``/SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`` flags
    handle replacing the running app and relaunching it on the new version.
    """
    updates_dir = _state_dir() / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)

    installer_path = updates_dir / f"TruckingPayWizardSetup-{info.version}.exe"

    logger.info("Downloading update {} to {}", info.version, installer_path)
    try:
        urllib.request.urlretrieve(info.download_url, installer_path)
    except Exception as exc:
        logger.error("Failed to download installer: {}", exc)
        raise

    if info.asset_size > 0:
        actual_size = installer_path.stat().st_size
        if actual_size != info.asset_size:
            installer_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Download size mismatch: expected {info.asset_size} bytes, "
                f"got {actual_size} bytes.  The file may be corrupt."
            )

    logger.info("Launching installer {}", installer_path)
    subprocess.Popen(
        [
            str(installer_path),
            "/SILENT",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ]
    )
    sys.exit(0)


def skip_version(version: str) -> None:
    """Add *version* to the skipped-versions list."""
    version = version.lstrip("v")
    state = _load_state()
    skipped: list[str] = state.get("skipped_versions", [])
    if version not in skipped:
        skipped.append(version)
    state["skipped_versions"] = skipped
    _save_state(state)


def is_skipped(version: str) -> bool:
    """Return True if *version* was previously dismissed by the user."""
    version = version.lstrip("v")
    return version in _load_state().get("skipped_versions", [])
