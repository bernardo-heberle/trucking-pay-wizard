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
from src.extract.models import (
    Certainty,
    Classification,
    DocumentExtractionResult,
    ExtractedField,
    ExtractedLoad,
    SourceSpan,
)
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
    and parses the structured response into ``ExtractedLoad`` objects.

    Failure handling
    ----------------
    Transient API failures (rate limits, network errors, server overload) are
    retried up to ``_MAX_ATTEMPTS`` times with exponential backoff.  A missing
    ``tool_use`` block in the response is treated as a soft transient failure
    and is also retried.

    If all attempts are exhausted, ``extract()`` returns a
    ``DocumentExtractionResult`` with an empty ``loads`` list and
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
                loads, classification = self._call_llm(sanitized_text, source_name)

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
                loads = self._resolve_source_locations(loads, ocr_result)
                loads = self._verify_pay_fields(loads, sanitized_text, source_name)
                logger.info(
                    "LLM extraction complete for '{}' — {} load(s) found, "
                    "is_payment_document={}",
                    source_name,
                    len(loads),
                    classification.is_payment_document,
                )
                return DocumentExtractionResult(
                    source_path=ocr_result.source_path,
                    content_hash=ocr_result.content_hash,
                    loads=loads,
                    page_count=page_count,
                    is_payment_document=classification.is_payment_document,
                    classification_confidence=classification.confidence,
                    classification_reason=classification.reason,
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
            loads=[],
            page_count=page_count,
            extraction_error=last_error,
        )

    def _resolve_source_locations(
        self,
        loads: list[ExtractedLoad],
        ocr_result: OcrResult,
    ) -> list[ExtractedLoad]:
        """Populate source_spans and source_page for each field in every load.

        Disambiguation uses three layers in priority order:

        1. **source_line context match** — if the LLM returned a source_line
           for the field, search for that line in OCR text first.  A full line
           is almost always unique even when the bare value repeats, so this is
           the most reliable anchor.

        2. **Sequential offset consumption** — loads are processed in order;
           each load starts its search at or after the end of the previous
           load's resolved region.  This prevents load N+1 from claiming an
           occurrence already assigned to load N when source_line matching
           fails.

        3. **Closest-to-date-anchor fallback** — within a single load, pay is
           resolved closest to the date's offset when multiple matches remain
           after the earlier layers narrow the candidates.

        Fields whose value is not found in the OCR text are returned unchanged
        (no spans) — staff will need to locate and mark them manually in the
        PDF.
        """
        full_text = ocr_result.full_text
        resolved_loads: list[ExtractedLoad] = []

        # min_offset advances as each load is resolved so that later loads
        # cannot claim occurrences already consumed by earlier ones.
        min_offset: int = 0

        for load in loads:
            # Step 1: resolve the date field and record its character offset.
            date_offset: int | None = None
            resolved_date: ExtractedField | None = load.date
            if load.date is not None and load.date.value:
                resolved_date, date_offset = self._resolve_field_with_offset(
                    load.date,
                    full_text,
                    ocr_result,
                    anchor_offset=None,
                    min_offset=min_offset,
                )

            # Step 2: resolve the pay field, anchored to the date's offset.
            pay_offset: int | None = None
            resolved_pay: ExtractedField | None = load.pay
            if load.pay is not None and load.pay.value:
                resolved_pay, pay_offset = self._resolve_field_with_offset(
                    load.pay,
                    full_text,
                    ocr_result,
                    anchor_offset=date_offset,
                    min_offset=min_offset,
                )

            resolved_loads.append(
                dataclasses.replace(load, pay=resolved_pay, date=resolved_date)
            )

            # Advance the sequential cursor past the furthest resolved offset
            # so the next load's search starts beyond this load's region.
            offsets = [o for o in (date_offset, pay_offset) if o is not None]
            if offsets:
                min_offset = max(offsets) + 1

        return resolved_loads

    def _find_offset_via_source_line(
        self,
        field: ExtractedField,
        full_text: str,
        min_offset: int,
    ) -> int | None:
        """Return the character offset of *field.value* within its source line.

        Searches for *field.source_line* in *full_text* (case-insensitive).
        When found, locates *field.value* within that line match and returns
        its absolute offset in *full_text*.  Returns ``None`` when either the
        source line or the value within it cannot be found.

        The search starts at *min_offset* to respect sequential ordering across
        loads.
        """
        if not field.source_line:
            return None

        line_pattern = re.compile(re.escape(field.source_line), re.IGNORECASE)
        line_match = line_pattern.search(full_text, min_offset)
        if line_match is None:
            logger.debug(
                "source_line not found in OCR text for field '{}'; will fall back",
                field.name,
            )
            return None

        value_pattern = re.compile(re.escape(field.value), re.IGNORECASE)
        value_match = value_pattern.search(full_text, line_match.start(), line_match.end())
        if value_match is None:
            logger.debug(
                "Field '{}' value {!r} not found within matched source_line; will fall back",
                field.name,
                field.value,
            )
            return None

        return value_match.start()

    def _resolve_field_with_offset(
        self,
        field: ExtractedField,
        full_text: str,
        ocr_result: OcrResult,
        anchor_offset: int | None,
        min_offset: int = 0,
    ) -> tuple[ExtractedField, int | None]:
        """Find *field.value* in *full_text* and attach OCR provenance.

        Resolution priority:
        1. source_line context match — if the LLM provided a source_line, use
           it to pin the exact occurrence (most reliable for duplicates).
        2. Sequential floor — candidates before *min_offset* are excluded so
           later loads cannot steal occurrences from earlier ones.
        3. Closest-to-anchor — among remaining candidates, prefer the match
           nearest *anchor_offset* (within-load pay-vs-date pairing).
        4. First remaining match — when no anchor is set.

        Returns ``(resolved_field, match_char_offset)`` where
        *match_char_offset* is the start of the chosen match in *full_text*,
        or ``None`` when no match is found.
        """
        # Layer 1: try to resolve via the LLM-provided source line.
        context_offset = self._find_offset_via_source_line(field, full_text, min_offset)
        if context_offset is not None:
            return self._build_resolved_field(field, full_text, ocr_result, context_offset)

        # Layer 2 + 3 + 4: fall back to regex over all occurrences.
        pattern = re.compile(re.escape(field.value), re.IGNORECASE)
        all_matches = list(pattern.finditer(full_text))

        if not all_matches:
            logger.debug(
                "Source location not found in OCR text for field '{}' value {!r}",
                field.name,
                field.value,
            )
            return field, None

        # Apply the sequential floor (Layer 2).
        candidates = [m for m in all_matches if m.start() >= min_offset]
        if not candidates:
            # All occurrences are before the cursor — fall back to the closest
            # overall match rather than returning nothing.
            logger.debug(
                "All occurrences of field '{}' value {!r} are before min_offset {}; "
                "using closest overall match",
                field.name,
                field.value,
                min_offset,
            )
            candidates = all_matches

        # Layer 3: prefer match closest to anchor_offset within candidates.
        if anchor_offset is not None:
            best_match = min(candidates, key=lambda m: abs(m.start() - anchor_offset))
        else:
            # Layer 4: first remaining candidate.
            best_match = candidates[0]

        return self._build_resolved_field(field, full_text, ocr_result, best_match.start())

    def _build_resolved_field(
        self,
        field: ExtractedField,
        full_text: str,
        ocr_result: OcrResult,
        match_start: int,
    ) -> tuple[ExtractedField, int]:
        """Attach OCR provenance to *field* at *match_start* in *full_text*.

        Finds the end of the match for *field.value* beginning at *match_start*,
        maps the span to OCR lines, and returns the resolved field together
        with the match start offset.
        """
        match_end = match_start + len(field.value)
        lines = ocr_result.find_lines_for_span(match_start, match_end)
        spans = [
            SourceSpan(page_number=line.page_number, bounding_box=line.bounding_box)
            for line in lines
        ]
        first_page = lines[0].page_number if lines else None
        resolved = dataclasses.replace(field, source_page=first_page, source_spans=spans)

        logger.debug(
            "Resolved source location for field '{}': page {}, {} span(s), offset {}",
            field.name,
            first_page,
            len(spans),
            match_start,
        )
        return resolved, match_start

    def _verify_pay_fields(
        self,
        loads: list[ExtractedLoad],
        sanitized_text: str,
        source_name: str,
    ) -> list[ExtractedLoad]:
        """Cross-reference HIGH-certainty pay fields against OCR text per load.

        For each load's pay field reported with HIGH certainty, confirm that
        the numeric value appears in the sanitized OCR text.  When the load's
        date has been resolved to a character offset, the verifier restricts
        its search to that line first, then falls back to a global search.
        The raw LLM value is normalized to a plain decimal before comparison.
        When no match is found the field is downgraded to REVIEW so staff know
        to check it manually.
        """
        verified_loads: list[ExtractedLoad] = []
        for load in loads:
            pay = load.pay
            if pay is None or pay.certainty != Certainty.HIGH:
                verified_loads.append(load)
                continue

            normalized = _normalize_pay_value(pay.value)
            if normalized is None:
                verified_loads.append(load)
                continue

            # Use the date's resolved position as the locality anchor.
            anchor_offset: int | None = None
            if load.date is not None and load.date.source_spans:
                # Approximate the char offset from the date's first span page.
                # The verifier uses a line-level window via the text, not spans,
                # so we need the character offset — re-locate the date text.
                if load.date.value:
                    date_match = re.search(
                        re.escape(load.date.value), sanitized_text, re.IGNORECASE
                    )
                    if date_match:
                        anchor_offset = date_match.start()

            matched, reason = verify_pay_against_ocr(normalized, sanitized_text, anchor_offset)
            if matched:
                logger.debug("Pay verification passed for '{}': {}", source_name, reason)
                verified_loads.append(load)
            else:
                logger.warning(
                    "Pay verification failed for '{}': {} — downgrading to REVIEW",
                    source_name,
                    reason,
                )
                downgraded_pay = dataclasses.replace(pay, certainty=Certainty.REVIEW)
                verified_loads.append(dataclasses.replace(load, pay=downgraded_pay))

        return verified_loads

    def _call_llm(
        self, text: str, source_document: str
    ) -> tuple[list[ExtractedLoad], Classification]:
        """Send *text* to Claude and parse the structured tool response.

        Returns the extracted loads together with the document-level
        ``Classification``.  Raises ``_NoToolUseBlock`` if the response
        contains no ``tool_use`` block.  All other exceptions propagate to the
        retry loop in ``extract()``.
        """
        tool_def = self._schema.tool_definition()
        tool_name = tool_def["name"]

        response = self._client.messages.create(
            model=self._settings.llm_model,
            max_tokens=4096,
            temperature=self._settings.llm_temperature,
            system=[
                {
                    "type": "text",
                    "text": self._schema.system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
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
                loads = self._schema.parse_tool_result(
                    block.input,
                    source_document=source_document,
                )
                classification = self._schema.parse_classification(block.input)
                return loads, classification

        raise _NoToolUseBlock()
