"""Unit tests for src.credentials."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

import src.credentials as creds

_SERVICE = "TruckingPayWizard"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_keyring(store: dict | None = None):
    """Return a mock keyring module with an in-memory backing store."""
    if store is None:
        store = {}

    m = MagicMock()
    m.get_password.side_effect = lambda svc, name: store.get(name)
    m.set_password.side_effect = lambda svc, name, val: store.update({name: val})
    m.delete_password.side_effect = lambda svc, name: store.pop(name, None)
    m.errors = MagicMock()
    m.errors.PasswordDeleteError = KeyError
    return m


# ---------------------------------------------------------------------------
# get_* reads keyring first
# ---------------------------------------------------------------------------


def test_get_anthropic_key_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"anthropic_api_key": "sk-ant-keyring"})
    monkeypatch.setattr(creds, "keyring", kr)

    result = creds.get_anthropic_key()

    assert result == "sk-ant-keyring"
    kr.get_password.assert_called_once_with(_SERVICE, "anthropic_api_key")


def test_get_azure_endpoint_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"azure_endpoint": "https://ep.azure.com/"})
    monkeypatch.setattr(creds, "keyring", kr)

    assert creds.get_azure_endpoint() == "https://ep.azure.com/"


def test_get_azure_key_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"azure_key": "abc123"})
    monkeypatch.setattr(creds, "keyring", kr)

    assert creds.get_azure_key() == "abc123"


# ---------------------------------------------------------------------------
# get_* falls back to env vars when keyring is empty
# ---------------------------------------------------------------------------


def test_get_anthropic_key_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")

    result = creds.get_anthropic_key()

    assert result == "sk-ant-env"


def test_get_azure_endpoint_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://env.azure.com/")

    assert creds.get_azure_endpoint() == "https://env.azure.com/"


def test_get_azure_key_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "envkey123")

    assert creds.get_azure_key() == "envkey123"


# ---------------------------------------------------------------------------
# get_* returns None when both keyring and env are empty
# ---------------------------------------------------------------------------


def test_get_anthropic_key_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert creds.get_anthropic_key() is None


def test_get_azure_endpoint_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)

    assert creds.get_azure_endpoint() is None


def test_get_azure_key_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    assert creds.get_azure_key() is None


# ---------------------------------------------------------------------------
# set_* always writes to keyring
# ---------------------------------------------------------------------------


def test_set_anthropic_key_writes_to_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict = {}
    kr = _make_keyring(store)
    monkeypatch.setattr(creds, "keyring", kr)

    creds.set_anthropic_key("sk-ant-new")

    kr.set_password.assert_called_once_with(_SERVICE, "anthropic_api_key", "sk-ant-new")
    assert store["anthropic_api_key"] == "sk-ant-new"


def test_set_azure_endpoint_writes_to_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict = {}
    kr = _make_keyring(store)
    monkeypatch.setattr(creds, "keyring", kr)

    creds.set_azure_endpoint("https://new.azure.com/")

    assert store["azure_endpoint"] == "https://new.azure.com/"


def test_set_azure_key_writes_to_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict = {}
    kr = _make_keyring(store)
    monkeypatch.setattr(creds, "keyring", kr)

    creds.set_azure_key("newkey456")

    assert store["azure_key"] == "newkey456"


# ---------------------------------------------------------------------------
# credentials_present
# ---------------------------------------------------------------------------


def test_credentials_present_true_when_all_set(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({
        "anthropic_api_key": "k",
        "azure_endpoint": "e",
        "azure_key": "y",
    })
    monkeypatch.setattr(creds, "keyring", kr)

    assert creds.credentials_present() is True


def test_credentials_present_false_when_anthropic_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"azure_endpoint": "e", "azure_key": "y"})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert creds.credentials_present() is False


def test_credentials_present_false_when_azure_endpoint_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"anthropic_api_key": "k", "azure_key": "y"})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)

    assert creds.credentials_present() is False


def test_credentials_present_false_when_azure_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"anthropic_api_key": "k", "azure_endpoint": "e"})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)

    assert creds.credentials_present() is False


# ---------------------------------------------------------------------------
# save_all
# ---------------------------------------------------------------------------


def test_save_all_writes_all_three(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict = {}
    kr = _make_keyring(store)
    monkeypatch.setattr(creds, "keyring", kr)

    creds.save_all("sk-ant-x", "https://ep.azure.com/", "azkey123")

    assert store["anthropic_api_key"] == "sk-ant-x"
    assert store["azure_endpoint"] == "https://ep.azure.com/"
    assert store["azure_key"] == "azkey123"


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------


def test_clear_all_removes_all_three(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {
        "anthropic_api_key": "k",
        "azure_endpoint": "e",
        "azure_key": "y",
    }
    kr = _make_keyring(store)
    monkeypatch.setattr(creds, "keyring", kr)

    creds.clear_all()

    assert store == {}


def test_clear_all_tolerates_missing_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({})
    # delete_password raises PasswordDeleteError (which is KeyError in our mock)
    # clear_all must not propagate it
    monkeypatch.setattr(creds, "keyring", kr)

    creds.clear_all()  # should not raise


# ---------------------------------------------------------------------------
# keyring takes priority over env var
# ---------------------------------------------------------------------------


def test_keyring_value_shadows_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    kr = _make_keyring({"anthropic_api_key": "sk-ant-keyring-wins"})
    monkeypatch.setattr(creds, "keyring", kr)
    monkeypatch.setattr(creds, "load_dotenv", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-should-not-win")

    assert creds.get_anthropic_key() == "sk-ant-keyring-wins"
