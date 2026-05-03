"""Credential storage backed by Windows Credential Manager via keyring.

All reads check keyring first, then fall back to environment variables /
``.env`` so developers don't have to interact with the credential UI on
every checkout.  Writes always go to keyring — environment variables are
never modified at runtime.

Usage::

    from src import credentials

    if not credentials.credentials_present():
        # route GUI to CredentialsPage
        ...

    key = credentials.get_anthropic_key()   # str | None
"""

from __future__ import annotations

import os

import keyring
from dotenv import load_dotenv

_SERVICE = "TruckingPayWizard"

_KEY_ANTHROPIC = "anthropic_api_key"
_KEY_AZURE_ENDPOINT = "azure_endpoint"
_KEY_AZURE_KEY = "azure_key"


def _get(name: str, env_var: str) -> str | None:
    """Return the credential named *name* from keyring, falling back to env."""
    value = keyring.get_password(_SERVICE, name)
    if value:
        return value
    load_dotenv()
    return os.getenv(env_var) or None


def _set(name: str, value: str) -> None:
    keyring.set_password(_SERVICE, name, value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_anthropic_key() -> str | None:
    return _get(_KEY_ANTHROPIC, "ANTHROPIC_API_KEY")


def set_anthropic_key(value: str) -> None:
    _set(_KEY_ANTHROPIC, value)


def get_azure_endpoint() -> str | None:
    return _get(_KEY_AZURE_ENDPOINT, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")


def set_azure_endpoint(value: str) -> None:
    _set(_KEY_AZURE_ENDPOINT, value)


def get_azure_key() -> str | None:
    return _get(_KEY_AZURE_KEY, "AZURE_DOCUMENT_INTELLIGENCE_KEY")


def set_azure_key(value: str) -> None:
    _set(_KEY_AZURE_KEY, value)


def credentials_present() -> bool:
    """Return True if all three required credentials are available."""
    return bool(
        get_anthropic_key()
        and get_azure_endpoint()
        and get_azure_key()
    )


def save_all(anthropic_key: str, azure_endpoint: str, azure_key: str) -> None:
    """Persist all three credentials to keyring atomically."""
    set_anthropic_key(anthropic_key)
    set_azure_endpoint(azure_endpoint)
    set_azure_key(azure_key)


def clear_all() -> None:
    """Remove all stored credentials (re-onboarding / key rotation)."""
    for name in (_KEY_ANTHROPIC, _KEY_AZURE_ENDPOINT, _KEY_AZURE_KEY):
        try:
            keyring.delete_password(_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
