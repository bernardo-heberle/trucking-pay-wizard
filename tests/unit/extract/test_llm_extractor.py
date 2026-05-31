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
from src.extract.models import Certainty, ExtractedLoad
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        anthropic_api_key="sk-test-key",
        llm_model="claude-3-5-haiku-20241022",
        llm_temperature=0.0,
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


def _make_multi_line_ocr(lines_data: list[tuple[str, int]]) -> OcrResult:
    """Build an OcrResult with multiple lines, one per (text, page_number) pair."""
    pages_dict: dict[int, list[str]] = {}
    for text, pg in lines_data:
        pages_dict.setdefault(pg, []).append(text)
    page_texts = ["\n".join(pages_dict[pn]) for pn in sorted(pages_dict)]
    full_text = "\n\n".join(page_texts)

    ocr_lines: list[OcrLine] = []
    offset = 0
    page_order = sorted(pages_dict)
    for pg_idx, pg in enumerate(page_order):
        for line_text in pages_dict[pg]:
            ocr_lines.append(
                OcrLine(
                    text=line_text,
                    page_number=pg,
                    bounding_box=BoundingBox(x=1.0, y=float(len(ocr_lines)), width=5.0, height=0.25),
                    char_start=offset,
                    char_end=offset + len(line_text),
                )
            )
            offset += len(line_text) + 1  # +1 for the '\n' separator
        if pg_idx < len(page_order) - 1:
            offset += 1  # extra '\n' for the page separator '\n\n'

    return OcrResult(
        source_path=Path("multi_doc.pdf"),
        content_hash="multi123",
        pages=[
            OcrPage(page_number=pg, width_inches=8.5, height_inches=11.0, line_count=len(pages_dict[pg]))
            for pg in page_order
        ],
        lines=ocr_lines,
    )


def _mock_tool_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Build a mock Anthropic Messages response with a tool_use block."""
    tool_block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)
    response = MagicMock()
    response.content = [tool_block]
    return response


# Helper: build tool input in the new loads shape.
def _loads_input(pay=None, date=None) -> dict:
    """Return a ``{"loads": [{...}]}`` tool input dict."""
    return {"loads": [{"pay": pay, "date": date}]}


class TestResolveSourceLocations:
    """Unit tests for LlmExtractor._resolve_source_locations.

    Tested via a real LlmExtractor with a mocked client so the full
    extract() pipeline exercises the resolver.
    """

    def _extractor_with_response(self, tool_input: dict) -> tuple[LlmExtractor, MagicMock]:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields", tool_input
        )
        return LlmExtractor(client=client, settings=settings), client

    def test_source_spans_populated_when_value_found(self) -> None:
        """When the raw LLM value appears in OCR text, source_spans must be non-empty."""
        extractor, _ = self._extractor_with_response(
            _loads_input(pay={"value": "$750.00", "confidence": 0.95})
        )
        ocr = _make_ocr_result("Carrier payment: $750.00")
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert len(pay.source_spans) == 1
        assert pay.source_spans[0].page_number == 1
        assert pay.source_page == 1

    def test_source_spans_empty_when_value_not_found(self) -> None:
        """When the raw value is absent from OCR text, source_spans stays empty."""
        extractor, _ = self._extractor_with_response(
            _loads_input(pay={"value": "$999.99", "confidence": 0.95})
        )
        ocr = _make_ocr_result("Carrier payment: $750.00")
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert pay.source_spans == []
        assert pay.source_page is None

    def test_source_spans_case_insensitive_match(self) -> None:
        """Matching is case-insensitive — useful for date strings."""
        extractor, _ = self._extractor_with_response(
            _loads_input(date={"value": "march 13, 2024", "confidence": 0.92})
        )
        ocr = _make_ocr_result("Pickup: March 13, 2024")
        result = extractor.extract(ocr, page_count=1)

        date = result.loads[0].date
        assert date is not None
        assert len(date.source_spans) == 1
        assert date.source_page == 1

    def test_source_page_set_to_page_of_first_matching_line(self) -> None:
        """source_page must reflect which page the value was found on."""
        ocr = _make_multi_line_ocr([
            ("Header line only", 1),
            ("Carrier payment: $750.00", 2),
        ])
        extractor, _ = self._extractor_with_response(
            _loads_input(pay={"value": "$750.00", "confidence": 0.95})
        )
        result = extractor.extract(ocr, page_count=2)

        pay = result.loads[0].pay
        assert pay is not None
        assert pay.source_page == 2
        assert pay.source_spans[0].page_number == 2

    def test_bounding_box_coordinates_preserved_from_ocr_line(self) -> None:
        """The SourceSpan bounding box must match the OcrLine's exact coordinates."""
        extractor, _ = self._extractor_with_response(
            _loads_input(pay={"value": "$750.00", "confidence": 0.95})
        )
        ocr = _make_ocr_result("Carrier: $750.00")
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert len(pay.source_spans) == 1
        bbox = pay.source_spans[0].bounding_box
        assert bbox.x == pytest.approx(1.0)
        assert bbox.y == pytest.approx(1.0)
        assert bbox.width == pytest.approx(5.0)
        assert bbox.height == pytest.approx(0.25)


class TestSourceLineDisambiguation:
    """Unit tests for source_line context-first disambiguation in _resolve_source_locations."""

    def _extractor_with_response(self, tool_input: dict) -> LlmExtractor:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields", tool_input
        )
        return LlmExtractor(client=client, settings=settings)

    def test_source_line_picks_second_occurrence_of_duplicate_value(self) -> None:
        """When a value appears twice and source_line identifies the second line,
        the highlight must target the second occurrence, not the first."""
        ocr = _make_multi_line_ocr([
            ("Total Payment to Carrier: $1,200.00", 1),
            ("Load 2 of 2", 1),
            ("Total Payment to Carrier: $1,200.00", 1),
        ])
        tool_input = {
            "loads": [
                {
                    "pay": {
                        "value": "$1,200.00",
                        "confidence": 0.95,
                        "source_line": "Total Payment to Carrier: $1,200.00",
                    },
                    "date": None,
                },
                {
                    "pay": {
                        "value": "$1,200.00",
                        "confidence": 0.95,
                        "source_line": "Total Payment to Carrier: $1,200.00",
                    },
                    "date": None,
                },
            ]
        }
        extractor = self._extractor_with_response(tool_input)
        result = extractor.extract(ocr, page_count=1)

        load1_pay = result.loads[0].pay
        load2_pay = result.loads[1].pay
        assert load1_pay is not None
        assert load2_pay is not None
        assert len(load1_pay.source_spans) == 1
        assert len(load2_pay.source_spans) == 1
        # The two loads must resolve to different bounding boxes (different y positions).
        assert load1_pay.source_spans[0].bounding_box.y != load2_pay.source_spans[0].bounding_box.y

    def test_source_line_match_finds_correct_page(self) -> None:
        """When the source_line is unique (appears only on page 2), source_page must be 2,
        even though the value alone also appears on page 1."""
        ocr = _make_multi_line_ocr([
            ("Summary Pay: $750.00", 1),
            ("Pickup Date: 03/01/2024 Load Detail Pay: $750.00", 2),
        ])
        tool_input = {
            "loads": [
                {
                    "pay": {
                        "value": "$750.00",
                        "confidence": 0.95,
                        "source_line": "Pickup Date: 03/01/2024 Load Detail Pay: $750.00",
                    },
                    "date": {
                        "value": "03/01/2024",
                        "confidence": 0.95,
                        "source_line": "Pickup Date: 03/01/2024 Load Detail Pay: $750.00",
                    },
                }
            ]
        }
        extractor = self._extractor_with_response(tool_input)
        result = extractor.extract(ocr, page_count=2)

        pay = result.loads[0].pay
        assert pay is not None
        # source_line appears only on page 2, so the resolver must pick page 2.
        assert pay.source_page == 2

    def test_fallback_to_sequential_when_source_line_absent(self) -> None:
        """Without source_line, sequential offset prevents load 2 from
        claiming the same occurrence as load 1."""
        ocr = _make_multi_line_ocr([
            ("Pickup: 04/02/2024", 1),
            ("Pay: $1,200.00", 1),
            ("Pickup: 04/16/2024", 1),
            ("Pay: $1,200.00", 1),
        ])
        tool_input = {
            "loads": [
                {
                    "pay": {"value": "$1,200.00", "confidence": 0.95},
                    "date": {"value": "04/02/2024", "confidence": 0.95},
                },
                {
                    "pay": {"value": "$1,200.00", "confidence": 0.95},
                    "date": {"value": "04/16/2024", "confidence": 0.95},
                },
            ]
        }
        extractor = self._extractor_with_response(tool_input)
        result = extractor.extract(ocr, page_count=1)

        load1_pay = result.loads[0].pay
        load2_pay = result.loads[1].pay
        assert load1_pay is not None and load2_pay is not None
        assert len(load1_pay.source_spans) == 1
        assert len(load2_pay.source_spans) == 1
        # The two loads must point to different lines (different y coordinates).
        assert load1_pay.source_spans[0].bounding_box.y != load2_pay.source_spans[0].bounding_box.y

    def test_fallback_to_sequential_for_duplicate_dates(self) -> None:
        """Two loads sharing the same date string must each get their own occurrence
        via sequential offset consumption (no source_line)."""
        ocr = _make_multi_line_ocr([
            ("Pickup: 04/02/2024", 1),
            ("Pay: $1,100.00", 1),
            ("Pickup: 04/02/2024", 1),
            ("Pay: $1,300.00", 1),
        ])
        tool_input = {
            "loads": [
                {
                    "pay": {"value": "$1,100.00", "confidence": 0.95},
                    "date": {"value": "04/02/2024", "confidence": 0.95},
                },
                {
                    "pay": {"value": "$1,300.00", "confidence": 0.95},
                    "date": {"value": "04/02/2024", "confidence": 0.95},
                },
            ]
        }
        extractor = self._extractor_with_response(tool_input)
        result = extractor.extract(ocr, page_count=1)

        load1_date = result.loads[0].date
        load2_date = result.loads[1].date
        assert load1_date is not None and load2_date is not None
        assert len(load1_date.source_spans) == 1
        assert len(load2_date.source_spans) == 1
        assert load1_date.source_spans[0].bounding_box.y != load2_date.source_spans[0].bounding_box.y

    def test_source_line_not_found_falls_back_gracefully(self) -> None:
        """When source_line does not match any OCR text, the resolver must fall back
        to regex matching and still return spans rather than raising."""
        ocr = _make_multi_line_ocr([
            ("Pay: $750.00", 1),
        ])
        tool_input = {
            "loads": [
                {
                    "pay": {
                        "value": "$750.00",
                        "confidence": 0.95,
                        "source_line": "Completely different text that is not in the OCR",
                    },
                    "date": None,
                }
            ]
        }
        extractor = self._extractor_with_response(tool_input)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        # Fallback must still find $750.00 in the OCR text.
        assert len(pay.source_spans) == 1

    def test_source_line_stored_on_field_after_extraction(self) -> None:
        """The source_line from the LLM must be preserved on ExtractedField
        even after resolution (it is diagnostic context, not consumed away)."""
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        tool_input = _loads_input(
            pay={"value": "$750.00", "confidence": 0.95, "source_line": "Total Payment to Carrier: $750.00"}
        )
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response("extract_income_fields", tool_input)
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay is not None
        assert pay.source_line == "Total Payment to Carrier: $750.00"


class TestLlmExtractorExtract:

    def test_returns_document_extraction_result(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.source_path == Path("test_doc.pdf")
        assert result.content_hash == "abc123"
        assert result.page_count == 1
        assert len(result.loads) == 1
        assert result.loads[0].pay is not None
        assert result.loads[0].pay.value == "750.00"

    def test_both_fields_extracted(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(
                pay={"value": "750.00", "confidence": 0.95},
                date={"value": "03/12/2024", "confidence": 0.92},
            ),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=2)

        assert len(result.loads) == 1
        assert result.loads[0].pay is not None
        assert result.loads[0].pay.value == "750.00"
        assert result.loads[0].date is not None
        assert result.loads[0].date.value == "03/12/2024"

    def test_empty_response_returns_load_with_no_fields(self) -> None:
        """A null-only response yields one load with both fields None."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay=None, date=None),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert len(result.loads) == 1
        assert result.loads[0].pay is None
        assert result.loads[0].date is None

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

        assert result.loads == []
        assert result.extraction_error is not None
        assert "tool_use" in result.extraction_error
        assert client.messages.create.call_count == _MAX_ATTEMPTS

    def test_pii_is_sanitized_before_api_call(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay=None, date=None),
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
            _loads_input(),
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
            _loads_input(),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-3-opus-20240229"

    def test_temperature_zero_is_passed_to_api(self) -> None:
        settings = _make_settings(llm_temperature=0.0)
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        assert call_args.kwargs["temperature"] == 0.0

    def test_cache_breakpoint_on_system_prompt_not_top_level(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        # Automatic top-level caching would place the breakpoint on the
        # document; we must use an explicit breakpoint on the static prefix.
        assert "cache_control" not in call_args.kwargs

        system = call_args.kwargs["system"]
        assert system == [
            {
                "type": "text",
                "text": IncomeDocumentSchema().system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def test_document_message_is_not_cached(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        document_message = call_args.kwargs["messages"][0]
        assert "cache_control" not in document_message

    def test_max_tokens_is_4096(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        extractor = LlmExtractor(client=client, settings=settings)
        extractor.extract(_make_ocr_result(), page_count=1)

        call_args = client.messages.create.call_args
        assert call_args.kwargs["max_tokens"] == 4096


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
        assert extractor._client is mock_client


def _make_rate_limit_error() -> anthropic.RateLimitError:
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
    """Verify the retry logic in LlmExtractor.extract()."""

    def test_retryable_error_then_success(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error(),
            _mock_tool_response(
                "extract_income_fields",
                _loads_input(pay={"value": "750.00", "confidence": 0.95}),
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
        assert result.loads[0].pay.value == "750.00"
        assert client.messages.create.call_count == 2
        assert mock_sleep.call_count == 1

    def test_retryable_error_exhausts_all_attempts(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_rate_limit_error() for _ in range(_MAX_ATTEMPTS)
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is not None
        assert "Rate limit" in result.extraction_error
        assert result.loads == []
        assert client.messages.create.call_count == _MAX_ATTEMPTS
        assert mock_sleep.call_count == _MAX_ATTEMPTS - 1

    def test_overloaded_error_is_retryable(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            _make_overloaded_error(),
            _mock_tool_response(
                "extract_income_fields",
                _loads_input(pay={"value": "500.00", "confidence": 0.90}),
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1

    def test_connection_error_is_retryable(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = [
            anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
            _mock_tool_response(
                "extract_income_fields",
                _loads_input(pay={"value": "500.00", "confidence": 0.90}),
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert client.messages.create.call_count == 2

    def test_auth_error_raises_immediately(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = _make_auth_error()

        extractor = LlmExtractor(client=client, settings=settings)
        with pytest.raises(ExtractionError, match="Non-retryable"):
            extractor.extract(_make_ocr_result(), page_count=1)

        assert client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_bad_request_raises_immediately(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.side_effect = _make_bad_request_error()

        extractor = LlmExtractor(client=client, settings=settings)
        with pytest.raises(ExtractionError, match="Non-retryable"):
            extractor.extract(_make_ocr_result(), page_count=1)

        assert client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_malformed_field_type_retried_then_fails(self, mock_sleep) -> None:
        """A bare number for a field is unrecoverable — retried then fails."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"loads": [{"pay": 1850.0, "date": None}]},  # bare float triggers retry
        )

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.loads == []
        assert result.extraction_error is not None
        assert client.messages.create.call_count == _MAX_ATTEMPTS

    def test_malformed_field_type_retried_then_succeeds(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        malformed = _mock_tool_response(
            "extract_income_fields",
            {"loads": [{"pay": 1850.0, "date": None}]},
        )
        good = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "1850.00", "confidence": 0.95}),
        )
        client.messages.create.side_effect = [malformed, good]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
        assert result.loads[0].pay.value == "1850.00"
        assert client.messages.create.call_count == 2

    def test_plain_string_field_accepted_without_retry(self, mock_sleep) -> None:
        """A plain string for pay is accepted leniently as REVIEW — no retry."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            {"loads": [{"pay": "1850.00", "date": None}]},
        )

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
        assert result.loads[0].pay.value == "1850.00"
        assert client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_no_tool_use_retried_then_succeeds(self, mock_sleep) -> None:
        settings = _make_settings()
        client = MagicMock()
        text_only = MagicMock()
        text_only.content = [SimpleNamespace(type="text", text="Sorry.")]

        client.messages.create.side_effect = [
            text_only,
            _mock_tool_response(
                "extract_income_fields",
                _loads_input(pay={"value": "750.00", "confidence": 0.95}),
            ),
        ]

        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(_make_ocr_result(), page_count=1)

        assert result.extraction_error is None
        assert len(result.loads) == 1
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
        assert delays[0] == pytest.approx(2.0)
        assert delays[1] == pytest.approx(4.0)
        from src.extract.llm.extractor import _MAX_DELAY_SECONDS
        assert all(d <= _MAX_DELAY_SECONDS for d in delays)

    def test_failed_result_preserves_metadata(self, mock_sleep) -> None:
        """Even when extraction fails, source_path, content_hash, page_count are set."""
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
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.95}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.HIGH
        assert pay.value == "750.00"

    def test_high_certainty_downgraded_when_value_not_in_ocr(self) -> None:
        """Transposed/wrong LLM value is downgraded from HIGH to REVIEW."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "1234.56", "confidence": 0.95}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $12,345.60")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.REVIEW
        assert pay.value == "1234.56"

    def test_review_certainty_not_upgraded_when_value_found_in_ocr(self) -> None:
        """Verification never upgrades certainty — a REVIEW field stays REVIEW."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.7}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.REVIEW
        assert pay.value == "750.00"

    def test_not_found_certainty_pay_left_unchanged_when_value_absent(self) -> None:
        """NOT_FOUND pay fields are never touched by _verify_pay_fields."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "750.00", "confidence": 0.3}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $9,999.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.NOT_FOUND
        assert pay.value == "750.00"

    def test_date_field_not_affected_by_ocr_verification(self) -> None:
        """Verification only targets pay fields; date certainty is never changed."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(
                pay={"value": "750.00", "confidence": 0.95},
                date={"value": "03/12/2024", "confidence": 0.95},
            ),
        )
        ocr = _make_ocr_result("Carrier: $750.00  Date: 03/12/2024")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        date = result.loads[0].date
        assert date.certainty == Certainty.HIGH
        assert date.value == "03/12/2024"

    def test_raw_formatted_pay_stays_high_when_found_in_ocr(self) -> None:
        """When LLM returns '$750.00', normalization before verification keeps HIGH."""
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "$750.00", "confidence": 0.95}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $750.00")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.HIGH
        assert pay.value == "$750.00"

    def test_raw_formatted_pay_downgraded_when_not_found_in_ocr(self) -> None:
        settings = _make_settings()
        client = MagicMock()
        client.messages.create.return_value = _mock_tool_response(
            "extract_income_fields",
            _loads_input(pay={"value": "$1,234.56", "confidence": 0.95}),
        )
        ocr = _make_ocr_result("Total Payment to Carrier: $12,345.60")
        extractor = LlmExtractor(client=client, settings=settings)
        result = extractor.extract(ocr, page_count=1)

        pay = result.loads[0].pay
        assert pay.certainty == Certainty.REVIEW
        assert pay.value == "$1,234.56"
