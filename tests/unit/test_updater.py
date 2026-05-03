"""Unit tests for src.updater."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.updater as updater
from src.__version__ import __version__


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_github_response(
    tag: str,
    exe_name: str = "TruckingPayWizardSetup.exe",
    exe_size: int = 1000,
    body: str = "Release notes here.",
) -> dict:
    return {
        "tag_name": tag,
        "body": body,
        "assets": [
            {
                "name": exe_name,
                "browser_download_url": f"https://github.com/example/releases/download/{tag}/{exe_name}",
                "size": exe_size,
            }
        ],
    }


def _write_state(state_dir: Path, data: dict) -> None:
    (state_dir / "update_check.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0.1.0", (0, 1, 0)),
        ("v0.2.3", (0, 2, 3)),
        ("1.0.0", (1, 0, 0)),
        ("v10.20.30", (10, 20, 30)),
    ],
    ids=["no_prefix", "v_prefix", "major_one", "large_numbers"],
)
def test_parse_version(raw: str, expected: tuple) -> None:
    assert updater._parse_version(raw) == expected


def test_parse_version_invalid_returns_zero_tuple() -> None:
    assert updater._parse_version("not-semver") == (0,)


# ---------------------------------------------------------------------------
# _is_newer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "remote, local, expected",
    [
        ("0.2.0", "0.1.0", True),
        ("0.1.0", "0.1.0", False),
        ("0.1.0", "0.2.0", False),
        ("v1.0.0", "0.9.9", True),
        ("0.1.1", "0.1.0", True),
    ],
    ids=["newer_minor", "same", "older", "v_prefix_newer", "newer_patch"],
)
def test_is_newer(remote: str, local: str, expected: bool) -> None:
    assert updater._is_newer(remote, local) is expected


# ---------------------------------------------------------------------------
# skip_version / is_skipped
# ---------------------------------------------------------------------------


def test_skip_and_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    updater.skip_version("0.2.0")

    assert updater.is_skipped("0.2.0") is True
    assert updater.is_skipped("0.3.0") is False


def test_skip_strips_v_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    updater.skip_version("v0.2.0")

    assert updater.is_skipped("0.2.0") is True


def test_skip_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    updater.skip_version("0.2.0")
    updater.skip_version("0.2.0")

    state = json.loads((tmp_path / "update_check.json").read_text())
    assert state["skipped_versions"].count("0.2.0") == 1


def test_is_skipped_false_when_no_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    assert updater.is_skipped("0.2.0") is False


# ---------------------------------------------------------------------------
# check_for_update — debounce
# ---------------------------------------------------------------------------


def test_check_debounced_within_24h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _write_state(tmp_path, {"last_check": recent})

    result = updater.check_for_update()

    assert result is None


def test_check_not_debounced_after_24h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _write_state(tmp_path, {"last_check": old})

    response_data = _make_github_response("v99.0.0")

    with patch("src.updater.urllib.request.Request") as mock_req, \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update()

    assert result is not None
    assert result.version == "99.0.0"


def test_check_force_bypasses_debounce(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _write_state(tmp_path, {"last_check": recent})

    response_data = _make_github_response("v99.0.0")

    with patch("src.updater.urllib.request.Request"), \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update(force=True)

    assert result is not None


# ---------------------------------------------------------------------------
# check_for_update — network failure is silent
# ---------------------------------------------------------------------------


def test_check_returns_none_on_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    with patch("src.updater.urllib.request.urlopen", side_effect=OSError("network down")):
        result = updater.check_for_update(force=True)

    assert result is None


# ---------------------------------------------------------------------------
# check_for_update — up-to-date
# ---------------------------------------------------------------------------


def test_check_returns_none_when_up_to_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    response_data = _make_github_response(f"v{__version__}")

    with patch("src.updater.urllib.request.Request"), \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update(force=True)

    assert result is None


# ---------------------------------------------------------------------------
# check_for_update — returns UpdateInfo when newer
# ---------------------------------------------------------------------------


def test_check_returns_update_info_when_newer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    response_data = _make_github_response("v99.0.0", body="Big release!")

    with patch("src.updater.urllib.request.Request"), \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update(force=True)

    assert result is not None
    assert result.version == "99.0.0"
    assert result.release_notes == "Big release!"
    assert result.download_url.endswith(".exe")
    assert result.asset_size == 1000


def test_check_returns_none_for_skipped_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    _write_state(tmp_path, {"skipped_versions": ["99.0.0"]})
    response_data = _make_github_response("v99.0.0")

    with patch("src.updater.urllib.request.Request"), \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update(force=True)

    assert result is None


def test_check_returns_none_when_no_exe_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)
    response_data = {"tag_name": "v99.0.0", "body": "", "assets": []}

    with patch("src.updater.urllib.request.Request"), \
         patch("src.updater.urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_resp

        result = updater.check_for_update(force=True)

    assert result is None


# ---------------------------------------------------------------------------
# download_and_install
# ---------------------------------------------------------------------------


def test_download_and_install_raises_on_size_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    installer_path = tmp_path / "updates" / "TruckingPayWizardSetup-1.0.0.exe"
    installer_path.parent.mkdir(parents=True)
    installer_path.write_bytes(b"x" * 50)  # 50 bytes

    info = updater.UpdateInfo(
        version="1.0.0",
        download_url="https://example.com/installer.exe",
        release_notes="",
        asset_size=100,  # expected 100, got 50 — mismatch
    )

    with patch("src.updater.urllib.request.urlretrieve") as mock_dl:
        mock_dl.side_effect = lambda url, path: installer_path.write_bytes(b"x" * 50)

        with pytest.raises(RuntimeError, match="size mismatch"):
            updater.download_and_install(info)


def test_download_and_install_launches_installer_and_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updater, "_state_dir", lambda: tmp_path)

    installer_content = b"x" * 200
    info = updater.UpdateInfo(
        version="1.0.0",
        download_url="https://example.com/installer.exe",
        release_notes="",
        asset_size=200,
    )

    launched: list[list] = []

    def _fake_urlretrieve(url: str, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(installer_content)

    def _fake_popen(cmd: list, **kwargs) -> None:
        launched.append(cmd)

    with patch("src.updater.urllib.request.urlretrieve", side_effect=_fake_urlretrieve), \
         patch("src.updater.subprocess.Popen", side_effect=_fake_popen), \
         patch("src.updater.sys.exit") as mock_exit:
        updater.download_and_install(info)

    assert len(launched) == 1
    assert "/SILENT" in launched[0]
    assert "/CLOSEAPPLICATIONS" in launched[0]
    assert "/RESTARTAPPLICATIONS" in launched[0]
    mock_exit.assert_called_once_with(0)
