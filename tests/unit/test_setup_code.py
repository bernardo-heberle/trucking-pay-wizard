"""Unit tests for src.setup_code."""

from __future__ import annotations

import base64
import json

import pytest

from src.setup_code import (
    InvalidSetupCodeError,
    SetupCodePayload,
    decode_setup_code,
    encode_setup_code,
)

# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_encode_decode_roundtrip() -> None:
    code = encode_setup_code(
        anthropic_key="sk-ant-abc123",
        azure_endpoint="https://myresource.cognitiveservices.azure.com/",
        azure_key="deadbeef0123456789abcdef01234567",
    )
    payload = decode_setup_code(code)

    assert payload.anthropic_key == "sk-ant-abc123"
    assert payload.azure_endpoint == "https://myresource.cognitiveservices.azure.com/"
    assert payload.azure_key == "deadbeef0123456789abcdef01234567"


def test_encode_returns_str() -> None:
    code = encode_setup_code("k", "e", "y")
    assert isinstance(code, str)


def test_decode_returns_dataclass() -> None:
    code = encode_setup_code("a", "b", "c")
    result = decode_setup_code(code)
    assert isinstance(result, SetupCodePayload)


# ---------------------------------------------------------------------------
# Whitespace tolerance
# ---------------------------------------------------------------------------


def test_decode_strips_surrounding_whitespace() -> None:
    code = encode_setup_code("k", "e", "y")
    padded = f"  {code}  \n"
    payload = decode_setup_code(padded)
    assert payload.anthropic_key == "k"


# ---------------------------------------------------------------------------
# Version gate
# ---------------------------------------------------------------------------


def test_decode_rejects_wrong_version() -> None:
    raw = json.dumps({"v": 99, "anthropic": "k", "azure_endpoint": "e", "azure_key": "y"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="format version"):
        decode_setup_code(code)


def test_decode_rejects_missing_version_field() -> None:
    raw = json.dumps({"anthropic": "k", "azure_endpoint": "e", "azure_key": "y"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="format version"):
        decode_setup_code(code)


# ---------------------------------------------------------------------------
# Invalid input
# ---------------------------------------------------------------------------


def test_decode_rejects_garbage_string() -> None:
    with pytest.raises(InvalidSetupCodeError, match="copied in full"):
        decode_setup_code("not-valid-base64!!!")


def test_decode_rejects_non_object_json() -> None:
    raw = json.dumps([1, 2, 3])
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="copied in full"):
        decode_setup_code(code)


def test_decode_rejects_missing_anthropic_field() -> None:
    raw = json.dumps({"v": 1, "azure_endpoint": "e", "azure_key": "y"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="anthropic"):
        decode_setup_code(code)


def test_decode_rejects_missing_azure_endpoint() -> None:
    raw = json.dumps({"v": 1, "anthropic": "k", "azure_key": "y"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="azure_endpoint"):
        decode_setup_code(code)


def test_decode_rejects_missing_azure_key() -> None:
    raw = json.dumps({"v": 1, "anthropic": "k", "azure_endpoint": "e"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="azure_key"):
        decode_setup_code(code)


def test_decode_rejects_empty_field_values() -> None:
    raw = json.dumps({"v": 1, "anthropic": "", "azure_endpoint": "e", "azure_key": "y"})
    code = base64.urlsafe_b64encode(raw.encode()).decode()
    with pytest.raises(InvalidSetupCodeError, match="anthropic"):
        decode_setup_code(code)


def test_decode_rejects_empty_string() -> None:
    with pytest.raises(InvalidSetupCodeError):
        decode_setup_code("")


# ---------------------------------------------------------------------------
# Encode preserves values verbatim (no normalisation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "anthropic,azure_endpoint,azure_key",
    [
        ("sk-ant-abc123", "https://x.cognitiveservices.azure.com/", "abc" * 11),
        ("a", "b", "c"),
        ("key with spaces", "endpoint/with/path", "key==with==equals"),
    ],
    ids=["typical", "minimal", "special_chars"],
)
def test_roundtrip_values_preserved(
    anthropic: str, azure_endpoint: str, azure_key: str
) -> None:
    payload = decode_setup_code(encode_setup_code(anthropic, azure_endpoint, azure_key))
    assert payload.anthropic_key == anthropic
    assert payload.azure_endpoint == azure_endpoint
    assert payload.azure_key == azure_key
