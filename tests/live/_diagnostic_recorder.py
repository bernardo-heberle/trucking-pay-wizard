"""Diagnostic recorder for live API tests.

``RecordingLlmExtractor`` is a test-only subclass of ``LlmExtractor`` that
observes every stage of extraction without altering any behaviour.  Every
override calls ``super()`` and only adds capture; it never branches on test
outcome or changes return values.

After each ``extract()`` call the full record is available as
``extractor.last_record``.  The pytest plugin reads it after the test
finishes to write a per-test JSON artifact.

Nothing in this module imports from ``tests/`` — it is a standalone helper
that the live conftest wires in via fixture replacement.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import anthropic

from src.config import Settings, load_settings
from src.extract.exceptions import MalformedToolResponse
from src.extract.llm.client import build_anthropic_client
from src.extract.llm.extractor import LlmExtractor
from src.extract.llm.sanitizer import sanitize_text
from src.extract.llm.schemas.base import ExtractionSchema
from src.extract.llm.schemas.income import IncomeDocumentSchema, _normalize_pay_value
from src.extract.models import Certainty, ExtractedLoad
from src.ocr.models import OcrResult

# Module-level handle set by the conftest fixture so the plugin can reach the
# extractor instance without passing it through pytest internals.
_active_extractor: "RecordingLlmExtractor | None" = None


# ---------------------------------------------------------------------------
# Per-load diagnostics
# ---------------------------------------------------------------------------

@dataclass
class LoadVerificationRecord:
    """Diagnostic data for one load's pay verification step."""
    load_index: int
    raw_pay_value: str | None
    normalized_pay_value: str | None
    certainty_before_verify: str | None
    certainty_after_verify: str | None
    verification_matched: bool | None
    verification_reason: str | None
    anchor_offset_used: int | None


@dataclass
class LoadSourceRecord:
    """Diagnostic data for one load's source-location resolution step."""
    load_index: int
    # Date field
    date_value: str | None
    date_found_in_ocr: bool | None
    date_offset: int | None
    date_page: int | None
    date_n_matches: int | None
    # Pay field
    pay_value: str | None
    pay_found_in_ocr: bool | None
    pay_offset: int | None
    pay_page: int | None
    pay_n_matches: int | None


# ---------------------------------------------------------------------------
# Top-level extraction record
# ---------------------------------------------------------------------------

@dataclass
class ExtractionRecord:
    """Full diagnostic snapshot for one ``extract()`` call."""

    # Identity
    source_name: str = ""
    timestamp_utc: str = ""

    # Sanitizer
    sanitized_text: str = ""
    sanitizer_redaction_counts: dict[str, int] = field(default_factory=dict)
    sanitizer_total_redactions: int = 0

    # API request / response (last successful attempt, or last attempt if all fail)
    model: str = ""
    max_tokens: int = 0
    system_prompt: str = ""
    tool_definition: dict[str, Any] = field(default_factory=dict)
    user_message: str = ""
    raw_tool_input: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    near_token_cap: bool = False  # True when output_tokens > 0.85 * max_tokens

    # Schema / fallback signals
    schema_fallbacks_used: list[str] = field(default_factory=list)

    # Retry tracking
    total_attempts: int = 0
    retry_reasons: list[str] = field(default_factory=list)

    # Stage snapshots — populated in order: parse → resolve → verify → final
    parsed_loads_raw: list[dict[str, Any]] = field(default_factory=list)
    source_records: list[LoadSourceRecord] = field(default_factory=list)
    verification_records: list[LoadVerificationRecord] = field(default_factory=list)
    final_load_count: int = 0
    final_loads_summary: list[dict[str, Any]] = field(default_factory=list)

    # Outcome
    extraction_error: str | None = None


# ---------------------------------------------------------------------------
# Thin capturing wrapper around the Anthropic client
# ---------------------------------------------------------------------------

class _CapturingMessages:
    """Wraps ``client.messages`` to intercept ``create()``."""

    def __init__(self, real_messages, recorder: _CallRecorder) -> None:
        self._real = real_messages
        self._recorder = recorder

    def create(self, **kwargs) -> Any:
        response = self._real.create(**kwargs)
        self._recorder.on_api_response(kwargs, response)
        return response


class _CallRecorder:
    """Accumulates raw request/response data from one API round-trip."""

    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] = {}
        self.last_input_tokens: int | None = None
        self.last_output_tokens: int | None = None
        self.last_raw_tool_input: dict[str, Any] | None = None

    def on_api_response(self, kwargs: dict[str, Any], response: Any) -> None:
        self.last_kwargs = kwargs
        try:
            usage = response.usage
            self.last_input_tokens = getattr(usage, "input_tokens", None)
            self.last_output_tokens = getattr(usage, "output_tokens", None)
        except Exception:
            pass
        # Extract the tool_use input block if present
        try:
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    self.last_raw_tool_input = block.input
                    break
        except Exception:
            pass


class _CapturingClient:
    """Wraps an ``anthropic.Anthropic`` instance to intercept ``messages.create``."""

    def __init__(self, real_client: anthropic.Anthropic) -> None:
        self._real = real_client
        self._call_recorder = _CallRecorder()
        self.messages = _CapturingMessages(real_client.messages, self._call_recorder)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


# ---------------------------------------------------------------------------
# RecordingLlmExtractor
# ---------------------------------------------------------------------------

class RecordingLlmExtractor(LlmExtractor):
    """Test-only subclass that observes every extraction stage.

    Every override calls ``super()`` and records inputs/outputs without
    altering any return value.  Call ``extractor.last_record`` after
    ``extract()`` to retrieve the full diagnostic snapshot.
    """

    def __init__(
        self,
        client: anthropic.Anthropic,
        settings: Settings,
        schema: ExtractionSchema | None = None,
    ) -> None:
        self._capturing_client = _CapturingClient(client)
        # Pass the capturing client to the base class so all API calls go through it.
        super().__init__(
            client=self._capturing_client,  # type: ignore[arg-type]
            settings=settings,
            schema=schema,
        )
        self.last_record: ExtractionRecord = ExtractionRecord()

    @classmethod
    def from_config(cls) -> "RecordingLlmExtractor":
        settings = load_settings()
        client = build_anthropic_client(settings)
        return cls(client=client, settings=settings)

    # ------------------------------------------------------------------
    # extract() — outermost hook: sanitizer capture + final result
    # ------------------------------------------------------------------

    def extract(self, ocr_result: OcrResult, page_count: int):  # type: ignore[override]
        record = ExtractionRecord(
            source_name=ocr_result.source_path.name,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            model=self._settings.llm_model,
            max_tokens=1024,
            system_prompt=self._schema.system_prompt(),
            tool_definition=self._schema.tool_definition(),
        )
        self.last_record = record

        # Capture sanitizer report BEFORE the parent calls sanitize_text again.
        # The parent will call it on the same text; the result is identical.
        _, san_report = sanitize_text(ocr_result.full_text)
        record.sanitized_text = _apply_sanitizer_for_capture(ocr_result.full_text)
        record.sanitizer_redaction_counts = dict(san_report.counts_by_pattern)
        record.sanitizer_total_redactions = san_report.total_redactions

        result = super().extract(ocr_result, page_count)

        record.extraction_error = result.extraction_error
        record.final_load_count = len(result.loads)
        record.final_loads_summary = [_load_summary(load) for load in result.loads]
        return result

    # ------------------------------------------------------------------
    # _call_llm() — capture prompt artefacts and raw LLM response
    # ------------------------------------------------------------------

    def _call_llm(self, text: str, source_document: str) -> list[ExtractedLoad]:
        self.last_record.total_attempts += 1

        # Reset the API recorder for this attempt so we get fresh data.
        api_rec = self._capturing_client._call_recorder
        api_rec.last_kwargs = {}
        api_rec.last_input_tokens = None
        api_rec.last_output_tokens = None
        api_rec.last_raw_tool_input = None

        parsed_loads = super()._call_llm(text, source_document)

        # Populate record from the just-completed API call.
        rec = self.last_record
        rec.user_message = text  # the sanitized OCR text that was sent
        rec.input_tokens = api_rec.last_input_tokens
        rec.output_tokens = api_rec.last_output_tokens
        if rec.max_tokens and api_rec.last_output_tokens is not None:
            rec.near_token_cap = api_rec.last_output_tokens > 0.85 * rec.max_tokens

        # Store the verbatim tool_input the model returned.
        rec.raw_tool_input = api_rec.last_raw_tool_input

        # Detect schema fallback paths from the raw tool input.
        if api_rec.last_raw_tool_input is not None:
            _detect_schema_fallbacks(api_rec.last_raw_tool_input, rec)

        # Snapshot of parsed loads before resolution/verification.
        rec.parsed_loads_raw = [_load_summary(load) for load in parsed_loads]

        return parsed_loads

    # ------------------------------------------------------------------
    # _resolve_source_locations() — capture per-field OCR match info
    # ------------------------------------------------------------------

    def _resolve_source_locations(
        self,
        loads: list[ExtractedLoad],
        ocr_result: OcrResult,
    ) -> list[ExtractedLoad]:
        full_text = ocr_result.full_text

        # Pre-compute match counts for pay/date values BEFORE resolution.
        pre_info: dict[int, dict[str, Any]] = {}
        for load in loads:
            info: dict[str, Any] = {}
            for fname in ("pay", "date"):
                fld = getattr(load, fname)
                if fld is not None and fld.value:
                    pattern = re.compile(re.escape(fld.value), re.IGNORECASE)
                    matches = list(pattern.finditer(full_text))
                    info[fname] = {"n_matches": len(matches)}
                else:
                    info[fname] = {"n_matches": 0}
            pre_info[load.index] = info

        resolved_loads = super()._resolve_source_locations(loads, ocr_result)

        # After resolution, record what was found per field.
        src_records: list[LoadSourceRecord] = []
        for orig, resolved in zip(loads, resolved_loads):
            pre = pre_info.get(orig.index, {})
            src = LoadSourceRecord(
                load_index=orig.index,
                date_value=orig.date.value if orig.date else None,
                date_found_in_ocr=(
                    bool(resolved.date and resolved.date.source_spans)
                    if orig.date else None
                ),
                date_offset=None,
                date_page=(
                    resolved.date.source_page if resolved.date else None
                ),
                date_n_matches=pre.get("date", {}).get("n_matches"),
                pay_value=orig.pay.value if orig.pay else None,
                pay_found_in_ocr=(
                    bool(resolved.pay and resolved.pay.source_spans)
                    if orig.pay else None
                ),
                pay_offset=None,
                pay_page=(
                    resolved.pay.source_page if resolved.pay else None
                ),
                pay_n_matches=pre.get("pay", {}).get("n_matches"),
            )
            src_records.append(src)

        self.last_record.source_records = src_records
        return resolved_loads

    # ------------------------------------------------------------------
    # _verify_pay_fields() — capture per-load verification outcomes
    # ------------------------------------------------------------------

    def _verify_pay_fields(
        self,
        loads: list[ExtractedLoad],
        sanitized_text: str,
        source_name: str,
    ) -> list[ExtractedLoad]:
        # Snapshot certainties before verification.
        certainties_before: dict[int, str | None] = {
            load.index: (load.pay.certainty.value if load.pay and load.pay.certainty else None)
            for load in loads
        }

        verified_loads = super()._verify_pay_fields(loads, sanitized_text, source_name)

        ver_records: list[LoadVerificationRecord] = []
        for orig, verified in zip(loads, verified_loads):
            pay_before = orig.pay
            pay_after = verified.pay

            cert_before = certainties_before.get(orig.index)
            cert_after = (
                pay_after.certainty.value
                if pay_after and pay_after.certainty
                else None
            )

            # Determine verification outcome by comparing certainty change.
            # HIGH→REVIEW means verification failed; HIGH→HIGH means it passed.
            # Skipped when certainty was not HIGH to begin with.
            verification_matched: bool | None = None
            verification_reason: str | None = None
            if cert_before == Certainty.HIGH.value:
                if cert_after == Certainty.HIGH.value:
                    verification_matched = True
                    verification_reason = "certainty stayed HIGH"
                elif cert_after == Certainty.REVIEW.value:
                    verification_matched = False
                    verification_reason = "certainty downgraded HIGH→REVIEW"

            normalized_pay = None
            if pay_before and pay_before.value:
                normalized_pay = _normalize_pay_value(pay_before.value)

            ver_records.append(LoadVerificationRecord(
                load_index=orig.index,
                raw_pay_value=pay_before.value if pay_before else None,
                normalized_pay_value=normalized_pay,
                certainty_before_verify=cert_before,
                certainty_after_verify=cert_after,
                verification_matched=verification_matched,
                verification_reason=verification_reason,
                anchor_offset_used=None,  # not easily accessible without deeper hooks
            ))

        self.last_record.verification_records = ver_records
        return verified_loads


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_sanitizer_for_capture(raw_text: str) -> str:
    """Return the sanitized version of *raw_text* (same call the extractor makes)."""
    sanitized, _ = sanitize_text(raw_text)
    return sanitized


def _load_summary(load: ExtractedLoad) -> dict[str, Any]:
    """Serialise an ``ExtractedLoad`` to a plain dict for JSON output."""
    return {
        "index": load.index,
        "pay": {
            "value": load.pay.value,
            "normalized": _normalize_pay_value(load.pay.value),
            "confidence": load.pay.confidence,
            "certainty": load.pay.certainty.value if load.pay.certainty else None,
            "source_line": load.pay.source_line,
            "source_page": load.pay.source_page,
            "n_spans": len(load.pay.source_spans),
        } if load.pay else None,
        "date": {
            "value": load.date.value,
            "confidence": load.date.confidence,
            "certainty": load.date.certainty.value if load.date.certainty else None,
            "source_line": load.date.source_line,
            "source_page": load.date.source_page,
            "n_spans": len(load.date.source_spans),
        } if load.date else None,
    }


def _detect_schema_fallbacks(raw_tool_input: dict[str, Any], record: ExtractionRecord) -> None:
    """Inspect the raw LLM response dict for known fallback paths."""
    # Flat format: model returned {pay: ..., date: ...} instead of {loads: [...]}
    if "loads" not in raw_tool_input and (
        "pay" in raw_tool_input or "date" in raw_tool_input
    ):
        record.schema_fallbacks_used.append("flat_format_wrapped")
        return  # flat format, no further checks needed

    loads = raw_tool_input.get("loads", [])
    if not isinstance(loads, list):
        return

    for i, load_entry in enumerate(loads):
        if not isinstance(load_entry, dict):
            continue
        for fname in ("pay", "date"):
            val = load_entry.get(fname)
            if isinstance(val, str):
                record.schema_fallbacks_used.append(
                    f"plain_string_field:{fname}:load{i + 1}"
                )
