"""Unit tests for LlmExtractor with a mocked Anthropic client."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import anthropic
import httpx
import pytest

from src.config import Settings
from src.extract.exceptions import ExtractionError
from src.extract.llm.extractor import LlmExtractor, _MAX_ATTEMPTS
from src.extract.llm.schemas.income import IncomeDocumentSchema
from src.extract.models import Certainty
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


def _make_settings(**overrides) -> Settings:
    defaults = dict(
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

    @patch("src.extract.llm.extractor.time.sleep")
    def test_no_tool_use_block_returns_error_after_retries(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        text_block = SimpleNamespace(type="text", text="I cannot extract fields.")
        response = MagicMock()
        response.content = [text_block]
        client.messages.create.return_value = response

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)
        assert result.fields == []
        assert result.extraction_error is not None
        assert "tool_use" in result.extraction_error
        assert client.messages.create.call_count == _MAX_ATTEMPTS

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
        mock_client = MagicMock()
        mock_build.return_value = mock_client

        extractor = LlmExtractor.from_config()

        assert isinstance(extractor, LlmExtractor)
        mock_build.assert_called_once()
        # The client injected must be the one build_anthropic_client returned.
        assert extractor._client is mock_client


def _make_rate_limit_error() -> anthropic.RateLimitError:
    """Build a realistic RateLimitError with a mock httpx response."""
    mock_response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=mock_response,
        body={"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}},
    )


def _make_auth_error() -> anthropic.AuthenticationError:
    mock_response = httpx.Response(
        status_code=401,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.AuthenticationError(
        message="Invalid API key",
        response=mock_response,
        body={"error": {"type": "authentication_error", "message": "Invalid API key"}},
    )


def _make_overloaded_error() -> anthropic.InternalServerError:
    mock_response = httpx.Response(
        status_code=529,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.InternalServerError(
        message="API is temporarily overloaded",
        response=mock_response,
        body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
    )


def _make_bad_request_error() -> anthropic.BadRequestError:
    mock_response = httpx.Response(
        status_code=400,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.BadRequestError(
        message="Invalid request",
        response=mock_response,
        body={"error": {"type": "invalid_request_error", "message": "Invalid request"}},
    )


@patch("src.extract.llm.extractor.time.sleep")
class TestRetryBehavior:
    """Verify the retry logic in LlmExtractor.extract().

    All tests patch time.sleep so retries complete instantly.
    """

    def test_retryable_error_then_success(self, mock_sleep) -> None:
        """A transient failure followed by success returns a normal result."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error(),
            _mock_tool_response(
                "extract_income_fields",
                {"pay": {"value": "750.00", "confidence": 0.95}, "date": None},
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.fields) == 1
        assert result.fields[0].value == "750.00"
        assert client.messages.create.call_count == 2
        assert mock_sleep.call_count == 1

    def test_retryable_error_exhausts_all_attempts(self, mock_sleep) -> None:
        """Repeated transient failures exhaust retries and return extraction_error."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error() for _ in range(_MAX_ATTEMPTS)
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is not None
        assert "Rate limit" in result.extraction_error
        assert result.fields == []
        assert client.messages.create.call_count == _MAX_ATTEMPTS
        # Backoff sleeps happen between attempts (not after the last).
        assert mock_sleep.call_count == _MAX_ATTEMPTS - 1

    def test_overloaded_error_is_retryable(self, mock_sleep) -> None:
        """529 overloaded errors are retried, not raised immediately."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_overloaded_error(),
            _mock_tool_response(
                "extract_income_fields",
                {"pay": {"value": "500.00", "confidence": 0.90}, "date": None},
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.fields) == 1

    def test_connection_error_is_retryable(self, mock_sleep) -> None:
        """Network failures are retried."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
            _mock_tool_response(
                "extract_income_fields",
                {"pay": {"value": "500.00", "confidence": 0.90}, "date": None},
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert client.messages.create.call_count == 2

    def test_auth_error_raises_immediately(self, mock_sleep) -> None:
        """Authentication errors are not retried — they raise ExtractionError."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = _make_auth_error()

        extractor = LlmExtractor(client=client, settings=settings)
        with pytest.raises(ExtractionError, match="Non-retryable"):
            extractor.extract(_make_ocr_result(), page_count=1)

        assert client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_bad_request_raises_immediately(self, mock_sleep) -> None:
        """400 errors are not retried — they raise ExtractionError."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = _make_bad_request_error()

        extractor = LlmExtractor(client=client, settings=settings)
        with pytest.raises(ExtractionError, match="Non-retryable"):
            extractor.extract(_make_ocr_result(), page_count=1)

        assert client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_no_tool_use_retried_then_succeeds(self, mock_sleep) -> None:
        """A missing tool_use block on the first attempt is retried."""
        settings = _make_settings()
        client = MagicMock()
        text_only = MagicMock()
        text_only.content = [SimpleNamespace(type="text", text="Sorry.")]

        client.messages.create.side_effect = [
            text_only,
            _mock_tool_response(
                "extract_income_fields",
                {"pay": {"value": "750.00", "confidence": 0.95}, "date": None},
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.fields) == 1
        assert client.messages.create.call_count == 2

    def test_backoff_delays_increase(self, mock_sleep) -> None:
        """Verify that sleep durations follow exponential backoff."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error() for _ in range(_MAX_ATTEMPTS)
        ]

        extractor = LlmExtractor(client=client, settings=settings)

        with patch("src.extract.llm.extractor.random.uniform", return_value=0.0):
            extractor.extract(_make_ocr_result(), page_count=1)

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert len(delays) == _MAX_ATTEMPTS - 1
        # With jitter = 0: delay = BASE * 2^(attempt-1) → 2.0, 4.0
        assert delays[0] == pytest.approx(2.0)
        assert delays[1] == pytest.approx(4.0)
        # All delays must be capped at the maximum.
        from src.extract.llm.extractor import _MAX_DELAY_SECONDS
        assert all(d <= _MAX_DELAY_SECONDS for d in delays)

    def test_failed_result_preserves_metadata(self, mock_sleep) -> None:
        """Even when extraction fails, source_path, content_hash, and page_count are set."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error() for _ in range(_MAX_ATTEMPTS)
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=3)

        assert result.source_path == Path("test_doc.pdf")
        assert result.content_hash == "abc123"
        assert result.page_count == 3
        assert result.extraction_error is not None


class TestPayOcrVerification:
    """Verify the post-extraction OCR cross-reference step in LlmExtractor."""

    def test_high_certainty_preserved_when_value_found_in_ocr(self) -> None:
        """When the LLM's pay value matches an amount in OCR text, HIGH is kept."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": {"value": "750.00", "confidence": 0.95}, "date": None},
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay_field = next(f for f in result.fields if f.name == "pay")
        assert pay_field.certainty == Certainty.HIGH
        assert pay_field.value == "750.00"

    def test_high_certainty_downgraded_when_value_not_in_ocr(self) -> None:
        """Transposed/wrong LLM value is downgraded from HIGH to REVIEW."""
        settings = _make_settings()
        client = MagicMock()
        # LLM returns 1234.56 but OCR has $12,345.60 (transposed digits).
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": {"value": "1234.56", "confidence": 0.95}, "date": None},
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $12,345.60")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay_field = next(f for f in result.fields if f.name == "pay")
        assert pay_field.certainty == Certainty.REVIEW
        # Downgrade must not alter the extracted value itself.
        assert pay_field.value == "1234.56"

    def test_review_certainty_not_upgraded_when_value_found_in_ocr(self) -> None:
        """Verification never upgrades certainty — a REVIEW field stays REVIEW."""
        settings = _make_settings()
        client = MagicMock()
        # Low confidence → REVIEW from thresholds.
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": {"value": "750.00", "confidence": 0.7}, "date": None},
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay_field = next(f for f in result.fields if f.name == "pay")
        assert pay_field.certainty == Certainty.REVIEW
        assert pay_field.value == "750.00"

    def test_not_found_certainty_pay_left_unchanged_when_value_absent(self) -> None:
        """NOT_FOUND pay fields are never touched by _verify_pay_fields.

        An off-by-one mutant changing `!= HIGH` to `== REVIEW` in the
        verification guard would leave NOT_FOUND fields unguarded — this
        test catches that.
        """
        settings = _make_settings()
        client = MagicMock()
        # Very low confidence → NOT_FOUND certainty.
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"pay": {"value": "750.00", "confidence": 0.3}, "date": None},
        )
        # OCR text does NOT contain 750.00 — verifier would downgrade if it ran.
        ocr = _make_ocr_result("Total Payment to Carrier: $9,999.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay_field = next(f for f in result.fields if f.name == "pay")
        # Certainty must remain NOT_FOUND — verification must not touch it.
        assert pay_field.certainty == Certainty.NOT_FOUND
        assert pay_field.value == "750.00"

    def test_date_field_not_affected_by_ocr_verification(self) -> None:
        """Verification only targets pay fields; date certainty is never changed."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {
                "pay": {"value": "750.00", "confidence": 0.95},
                "date": {"value": "03/12/2024", "confidence": 0.95},
            },
        )
        ocr = _make_ocr_result("Carrier: $750.00  Date: 03/12/2024")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        date_field = next(f for f in result.fields if f.name == "date")
        assert date_field.certainty == Certainty.HIGH
        assert date_field.value == "03/12/2024"
