from __future__ import annotations

import dataclasses
import random
import re
import time

import anthropic
from loguru import logger

from src.config import Settings, load_settings
from src.extract.exceptions import ExtractionError, MalformedToolResponse
from src.extract.llm.client import build_anthropic_client
from src.extract.llm.sanitizer import sanitize_text
from src.extract.llm.schemas.base import ExtractionSchema
from src.extract.llm.schemas.income import IncomeDocumentSchema, _normalize_pay_value
from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan
from src.extract.pay_verifier import verify_pay_against_ocr
from src.ocr.models import OcrResult

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 2.0
_MAX_DELAY_SECONDS = 30.0

# HTTP status codes that indicate a configuration or code problem.
# Retrying the same request will not help.
_NON_RETRYABLE_STATUSES = {400, 401, 403}


class _NoToolUseBlock(Exception):
    """Raised internally when Claude returns a response with no tool_use block."""


# Alias so the retry loop can treat both soft failures the same way.
_RetryableSoftFailure = (_NoToolUseBlock, MalformedToolResponse)


def _is_retryable(exc: Exception) -> bool:
    """Return True if *exc* is a transient API failure worth retrying."""
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APITimeoutError):
        return True
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code not in _NON_RETRYABLE_STATUSES
    return False


class LlmExtractor:
    """Schema-driven field extraction using the Anthropic API (Claude).

    The extractor sanitises OCR text (PII scrubbing), sends it to the
    configured model with a ``tool_use`` call matching the active schema,
    and parses the structured response into ``ExtractedField`` objects.

    Failure handling
    ----------------
    Transient API failures (rate limits, network errors, server overload) are
    retried up to ``_MAX_ATTEMPTS`` times with exponential backoff.  A missing
    ``tool_use`` block in the response is treated as a soft transient failure
    and is also retried.

    If all attempts are exhausted, ``extract()`` returns a
    ``DocumentExtractionResult`` with an empty ``fields`` list and
    ``extraction_error`` set to a description of the last failure.  The failed
    result is intentionally not cached so the document is retried on the next
    pipeline run.

    Non-retryable errors (bad API key, malformed request) raise
    ``ExtractionError`` immediately so the caller can abort and report a
    configuration problem rather than silently skipping documents.
    """

    def __init__(
        self,
        client: anthropic.Anthropic,
        settings: Settings,
        schema: ExtractionSchema | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._schema = schema or IncomeDocumentSchema()

    @classmethod
    def from_config(cls) -> LlmExtractor:
        """Construct an ``LlmExtractor`` from current environment settings."""
        settings = load_settings()
        client = build_anthropic_client(settings)
        return cls(client=client, settings=settings)

    def extract(self, ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult:
        source_name = ocr_result.source_path.name
        logger.info("LLM extraction starting for '{}'", source_name)

        sanitized_text, _report = sanitize_text(ocr_result.full_text)

        last_error: str | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                fields = self._call_llm(sanitized_text, source_name)

            except ExtractionError:
                # Non-retryable configuration error — propagate immediately.
                raise

            except _RetryableSoftFailure as exc:
                last_error = str(exc) if str(exc) else "LLM response contained no tool_use block"
                logger.warning(
                    "Attempt {}/{}: malformed LLM response for '{}': {} — {}",
                    attempt,
                    _MAX_ATTEMPTS,
                    source_name,
                    last_error,
                    "retrying" if attempt < _MAX_ATTEMPTS else "giving up",
                )

            except Exception as exc:
                if not _is_retryable(exc):
                    raise ExtractionError(
                        f"Non-retryable API error for '{source_name}': {exc}"
                    ) from exc

                last_error = str(exc)
                logger.warning(
                    "Attempt {}/{}: API error for '{}': {} — {}",
                    attempt,
                    _MAX_ATTEMPTS,
                    source_name,
                    exc,
                    "retrying" if attempt < _MAX_ATTEMPTS else "giving up",
                )

            else:
                fields = self._resolve_source_locations(fields, ocr_result)
                fields = self._verify_pay_fields(fields, sanitized_text, source_name)
                logger.info(
                    "LLM extraction complete for '{}' — {} field(s) found",
                    source_name,
                    len(fields),
                )
                return DocumentExtractionResult(
                    source_path=ocr_result.source_path,
                    content_hash=ocr_result.content_hash,
                    fields=fields,
                    page_count=page_count,
                )

            if attempt < _MAX_ATTEMPTS:
                delay = min(
                    _BASE_DELAY_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 1),
                    _MAX_DELAY_SECONDS,
                )
                logger.info(
                    "Waiting {:.1f}s before attempt {}/{} for '{}'",
                    delay,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    source_name,
                )
                time.sleep(delay)

        logger.error(
            "LLM extraction failed for '{}' after {} attempt(s): {}",
            source_name,
            _MAX_ATTEMPTS,
            last_error,
        )
        return DocumentExtractionResult(
            source_path=ocr_result.source_path,
            content_hash=ocr_result.content_hash,
            fields=[],
            page_count=page_count,
            extraction_error=last_error,
        )

    def _resolve_source_locations(
        self,
        fields: list[ExtractedField],
        ocr_result: OcrResult,
    ) -> list[ExtractedField]:
        """Populate source_spans and source_page for each field by searching OCR text.

        Searches ``ocr_result.full_text`` for the exact raw value the LLM
        returned, resolves the match position to bounding-box spans via
        ``OcrResult.find_lines_for_span``, and attaches the resulting
        ``SourceSpan`` objects to the field.  Fields whose value is not
        found in the OCR text are returned unchanged (no spans) — staff
        will need to locate and mark them manually in the PDF.
        """
        resolved: list[ExtractedField] = []
        full_text = ocr_result.full_text

        for field in fields:
            if not field.value:
                resolved.append(field)
                continue

            pattern = re.compile(re.escape(field.value), re.IGNORECASE)
            match = pattern.search(full_text)

            if match is None:
                logger.debug(
                    "Source location not found in OCR text for field '{}' value {!r}",
                    field.name,
                    field.value,
                )
                resolved.append(field)
                continue

            lines = ocr_result.find_lines_for_span(match.start(), match.end())
            spans = [
                SourceSpan(page_number=line.page_number, bounding_box=line.bounding_box)
                for line in lines
            ]
            first_page = lines[0].page_number if lines else None
            resolved.append(
                dataclasses.replace(field, source_page=first_page, source_spans=spans)
            )
            logger.debug(
                "Resolved source location for field '{}': page {}, {} span(s)",
                field.name,
                first_page,
                len(spans),
            )

        return resolved

    def _verify_pay_fields(
        self,
        fields: list[ExtractedField],
        sanitized_text: str,
        source_name: str,
    ) -> list[ExtractedField]:
        """Cross-reference HIGH-certainty pay fields against OCR text.

        For each pay field the LLM reported with HIGH certainty, confirm
        that the numeric value appears somewhere in the sanitized OCR text.
        The raw LLM value is normalized to a plain decimal before comparison
        so that formatted strings like ``'$1,500.00'`` match correctly.
        When no match is found the field is downgraded to REVIEW so staff
        know to check it manually.  Fields already at REVIEW or NOT_FOUND
        are left unchanged.
        """
        verified: list[ExtractedField] = []
        for field in fields:
            if field.name != "pay" or field.certainty != Certainty.HIGH:
                verified.append(field)
                continue

            normalized = _normalize_pay_value(field.value)
            if normalized is None:
                # Unparseable value — already capped at REVIEW by the schema,
                # but guard here too for safety.
                verified.append(field)
                continue

            matched, reason = verify_pay_against_ocr(normalized, sanitized_text)
            if matched:
                logger.debug(
                    "Pay verification passed for '{}': {}",
                    source_name,
                    reason,
                )
                verified.append(field)
            else:
                logger.warning(
                    "Pay verification failed for '{}': {} — downgrading to REVIEW",
                    source_name,
                    reason,
                )
                verified.append(
                    dataclasses.replace(field, certainty=Certainty.REVIEW)
                )
        return verified

    def _call_llm(self, text: str, source_document: str) -> list[ExtractedField]:
        """Send *text* to Claude and parse the structured tool response.

        Raises ``_NoToolUseBlock`` if the response contains no ``tool_use``
        block.  All other exceptions propagate to the retry loop in
        ``extract()``.
        """
        tool_def = self._schema.tool_definition()
        tool_name = tool_def["name"]

        response = self._client.messages.create(
            model=self._settings.llm_model,
            max_tokens=1024,
            system=self._schema.system_prompt(),
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract the requested fields from the following "
                        "document text.\n\n"
                        "--- DOCUMENT START ---\n"
                        f"{text}\n"
                        "--- DOCUMENT END ---"
                    ),
                }
            ],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return self._schema.parse_tool_result(
                    block.input,
                    source_document=source_document,
                )

        raise _NoToolUseBlock()
