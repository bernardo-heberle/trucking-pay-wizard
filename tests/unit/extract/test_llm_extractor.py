"""Unit tests for LlmExtractor with a mocked Anthropic client."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.extract.llm.extractor import LlmExtractor
from src.extract.llm.schemas.income import IncomeDocumentSchema
from src.extract.models import Certainty
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        extraction_mode="llm",
        anthropic_api_key="sk-test-key",
        llm_model="claude-3-5-haiku-20241022",
        confidence_high_threshold=0.9,
        confidence_review_threshold=0.6,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_ocr_result(text: str = "Total Payment to Carrier: $750.00") -> OcrResult:
    line = OcrLine(
        text=text,
        page_number=1,
        bounding_box=BoundingBox(x=1.0, y=1.0, width=5.0, height=0.25),
        char_start=0,
        char_end=len(text),
    )
    return OcrResult(
        source_path=Path("test_doc.pdf"),
        content_hash="abc123",
        pages=[OcrPage(page_number=1, width_inches=8.5, height_inches=11.0, line_count=1)],
        lines=[line],
    )


def _mock_tool_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Build a mock Anthropic Messages response with a tool_use block."""
    tool_block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)
    response = MagicMock()
    response.content = [tool_block]
    return response


class TestLlmExtractorExtract:

    def test_returns_document_extraction_result(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": {"value": "750.00", "confidence": 0.95}, "date": None},
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.source_path == Path("test_doc.pdf")
        assert result.content_hash == "abc123"
        assert result.page_count == 1
        assert len(result.fields) == 1
        assert result.fields[0].name == "pay"
        assert result.fields[0].value == "750.00"

    def test_both_fields_extracted(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {
                "pay": {"value": "750.00", "confidence": 0.95},
                "date": {"value": "03/12/2024", "confidence": 0.92},
            },
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=2)
        assert len(result.fields) == 2
        names = {f.name for f in result.fields}
        assert names == {"pay", "date"}

    def test_empty_response_returns_no_fields(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": None, "date": None},
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)
        assert result.fields == []

    def test_no_tool_use_block_returns_no_fields(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        text_block = SimpleNamespace(type="text", text="I cannot extract fields.")
        response = MagicMock()
        response.content = [text_block]
        client.messages.create.return_value = response

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)
        assert result.fields == []

    def test_pii_is_sanitized_before_api_call(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": None, "date": None},
        )
        ocr = _make_ocr_result("SSN: 123-45-6789\nTotal: $500")
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(ocr, page_count=1)

        call_args = client.messages.create.call_args
        user_message = call_args.kwargs["messages"][0]["content"]
        assert "123-45-6789" not in user_message
        assert "[SSN-REDACTED]" in user_message

    def test_tool_definition_sent_in_request(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": None, "date": None},
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        tools = call_args.kwargs["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "extract_income_fields"

    def test_model_from_settings_is_used(self) -> None:
        settings = _make_settings(llm_model="claude-3-opus-20240229")
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": None, "date": None},
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-3-opus-20240229"


class TestLlmExtractorFromConfig:

    @patch("src.extract.llm.extractor.load_settings")
    @patch("src.extract.llm.extractor.build_anthropic_client")
    def test_from_config_creates_instance(self, mock_build, mock_settings) -> None:
        mock_settings.return_value = _make_settings()
        mock_build.return_value = MagicMock()

        extractor = LlmExtractor.from_config()
        assert isinstance(extractor, LlmExtractor)
        mock_build.assert_called_once()
