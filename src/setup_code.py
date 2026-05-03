"""Setup-code encoder/decoder for one-paste credential onboarding.

A setup code is a URL-safe base64 string that encodes all three API
credentials as a small JSON blob::

    {"v": 1, "anthropic": "sk-ant-...", "azure_endpoint": "https://...", "azure_key": "..."}

The ``v`` field is a schema version.  Future changes to the payload
structure must bump this number so that older app versions can surface a
friendly "please reinstall or ask IT for a new code" message instead of a
confusing parse error.

This module has **no GUI dependency** and can be unit-tested directly.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass


class InvalidSetupCodeError(ValueError):
    """Raised when a setup code cannot be decoded or is structurally invalid."""


_CURRENT_VERSION = 1
_REQUIRED_FIELDS = ("anthropic", "azure_endpoint", "azure_key")


@dataclass(frozen=True)
class SetupCodePayload:
    anthropic_key: str
    azure_endpoint: str
    azure_key: str


def encode_setup_code(
    anthropic_key: str,
    azure_endpoint: str,
    azure_key: str,
) -> str:
    """Encode three credential values into a single URL-safe base64 string."""
    payload = {
        "v": _CURRENT_VERSION,
        "anthropic": anthropic_key,
        "azure_endpoint": azure_endpoint,
        "azure_key": azure_key,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_setup_code(code: str) -> SetupCodePayload:
    """Decode a setup code string into a :class:`SetupCodePayload`.

    Raises:
        InvalidSetupCodeError: The string is not valid base64, not valid JSON,
            is missing required fields, or uses an unsupported version.
    """
    code = code.strip()
    try:
        raw = base64.urlsafe_b64decode(code + "==")  # pad to avoid errors
        payload = json.loads(raw)
    except Exception as exc:
        raise InvalidSetupCodeError(
            "Setup code could not be read — check it was copied in full."
        ) from exc

    if not isinstance(payload, dict):
        raise InvalidSetupCodeError(
            "Setup code could not be read — check it was copied in full."
        )

    version = payload.get("v")
    if version != _CURRENT_VERSION:
        raise InvalidSetupCodeError(
            f"This setup code uses format version {version!r}, "
            f"but this version of the app expects version {_CURRENT_VERSION}. "
            "Please ask IT for a new setup code."
        )

    missing = [f for f in _REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise InvalidSetupCodeError(
            "Setup code is incomplete — the following fields are missing: "
            + ", ".join(missing)
            + ". Check it was copied in full."
        )

    return SetupCodePayload(
        anthropic_key=payload["anthropic"],
        azure_endpoint=payload["azure_endpoint"],
        azure_key=payload["azure_key"],
    )
