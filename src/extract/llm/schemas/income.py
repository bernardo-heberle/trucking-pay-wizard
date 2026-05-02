from __future__ import annotations

from typing import Any

from src.extract.models import Certainty, ExtractedField

from .base import ExtractionSchema

_TOOL_NAME = "extract_income_fields"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": (
        "Extract financial fields from a trucking income document.  "
        "Return each field with a confidence score between 0.0 and 1.0."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pay": {
                "type": ["object", "null"],
                "description": (
                    "Total payment to carrier — the dollar amount the "
                    "carrier receives for the load."
                ),
                "properties": {
                    "value": {
                        "type": "string",
                        "description": (
                            "Numeric amount only, no currency symbol or units "
                            "(e.g. '1,500.00', '820', '1200.50')."
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 that this value is correct.",
                    },
                },
                "required": ["value", "confidence"],
            },
            "date": {
                "type": ["object", "null"],
                "description": (
                    "Pickup or earliest date for the load — the date the "
                    "truck was or will be picked up."
                ),
                "properties": {
                    "value": {
                        "type": "string",
                        "description": (
                            "Raw date string as it appears in the document "
                            "(e.g. '03/11/2024', 'March 13, 2024')."
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 that this value is correct.",
                    },
                },
                "required": ["value", "confidence"],
            },
        },
        "required": ["pay", "date"],
    },
}

_SYSTEM_PROMPT = """\
You are a precise document data extractor for trucking income documents.

Your task:
- Extract the **total payment to carrier** (the dollar amount the carrier \
receives for the load).
- Extract the **pickup date** (or the earliest date associated with the load).

Rules:
- For pay: return the numeric value only — no currency symbols, no units \
(e.g. '1,500.00' not '$1,500.00').
- For date: return the date string exactly as it appears in the document text.
- If a field is clearly present, return it with high confidence (>= 0.9).
- If you are uncertain or the value is ambiguous, lower your confidence score.
- If a field is not present in the document, return null for that field.
- Do NOT fabricate values. Only extract what is explicitly stated."""


class IncomeDocumentSchema(ExtractionSchema):
    """Schema for extracting pay and date from trucking income documents."""

    @property
    def name(self) -> str:
        return "income"

    def tool_definition(self) -> dict[str, Any]:
        return _TOOL_SCHEMA

    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def parse_tool_result(
        self,
        tool_input: dict[str, Any],
        source_document: str,
    ) -> list[ExtractedField]:
        fields: list[ExtractedField] = []

        for field_name in ("pay", "date"):
            entry = tool_input.get(field_name)
            if entry is None:
                continue

            raw_value = entry.get("value", "")
            confidence = float(entry.get("confidence", 0.0))

            if not raw_value:
                continue

            if field_name == "pay":
                raw_value = raw_value.lstrip("$").strip()

            fields.append(
                ExtractedField(
                    name=field_name,
                    value=raw_value,
                    source_document=source_document,
                    source_page=None,
                    confidence=confidence,
                    certainty=_confidence_to_certainty(confidence),
                )
            )

        return fields


def _confidence_to_certainty(confidence: float) -> Certainty:
    from src.config import load_settings

    settings = load_settings()
    if confidence >= settings.confidence_high_threshold:
        return Certainty.HIGH
    if confidence >= settings.confidence_review_threshold:
        return Certainty.REVIEW
    return Certainty.NOT_FOUND
