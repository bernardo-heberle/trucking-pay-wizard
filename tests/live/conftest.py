"""Fixtures for live API tests.

These tests make real network calls to Azure and Anthropic.  They are excluded
from the default ``pytest`` run by the ``live_api`` marker.

Run them explicitly::

    pytest -m live_api --no-cov -v

``--no-cov`` is recommended because the coverage minimum (85%) is calibrated
for the full unit/integration suite, not this small set of smoke tests.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.live_api

_HAS_ANTHROPIC_KEY = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
_HAS_AZURE_CREDS = bool(
    os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").strip()
    and os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip()
)

needs_anthropic = pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="ANTHROPIC_API_KEY not set — skipping live LLM test",
)
needs_azure = pytest.mark.skipif(
    not _HAS_AZURE_CREDS,
    reason="Azure Document Intelligence credentials not set — skipping live OCR test",
)


@pytest.fixture(scope="session")
def anthropic_extractor():
    """Build a real ``LlmExtractor`` wired to the live Anthropic API."""
    pytest.importorskip("anthropic")
    from src.extract.llm.extractor import LlmExtractor

    return LlmExtractor.from_config()


@pytest.fixture(scope="session")
def azure_client():
    """Build a real ``DocumentIntelligenceClient`` wired to the live Azure API."""
    from src.ocr.client import build_client

    return build_client()
