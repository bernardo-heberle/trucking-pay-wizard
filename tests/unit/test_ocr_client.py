"""Unit tests for src.ocr.client.build_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ocr.exceptions import OcrError


def test_build_client_raises_when_endpoint_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.credentials as creds

    monkeypatch.setattr(creds, "get_azure_endpoint", lambda: None)
    monkeypatch.setattr(creds, "get_azure_key", lambda: "some-key")

    from src.ocr.client import build_client

    with pytest.raises(OcrError, match="endpoint not found"):
        build_client()


def test_build_client_raises_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.credentials as creds

    monkeypatch.setattr(creds, "get_azure_endpoint", lambda: "https://ep.azure.com/")
    monkeypatch.setattr(creds, "get_azure_key", lambda: None)

    from src.ocr.client import build_client

    with pytest.raises(OcrError, match="key not found"):
        build_client()


def test_build_client_returns_client_when_credentials_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.credentials as creds

    monkeypatch.setattr(creds, "get_azure_endpoint", lambda: "https://ep.azure.com/")
    monkeypatch.setattr(creds, "get_azure_key", lambda: "abc123")

    fake_client = MagicMock()

    with patch("src.ocr.client.DocumentIntelligenceClient", return_value=fake_client) as mock_cls, \
         patch("src.ocr.client.AzureKeyCredential") as mock_cred:
        from src.ocr import client as ocr_client
        import importlib
        importlib.reload(ocr_client)

        result = ocr_client.build_client()

    assert result is not None
