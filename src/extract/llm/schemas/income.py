from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from src.extract.exceptions import MalformedToolResponse
from src.extract.models import Certainty, ExtractedField

from .base import ExtractionSchema

_TOOL_NAME = "extract_income_fields"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": (
        "Extract financial fields from a trucking income document.  "
        "Always return the full object structure for every field — never a "
        "plain string or number.  Set value to null when a field is not found."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pay": {
                # Always an object — value is null when not found.
                # Using a type union here risks the model returning a plain
                # string instead of the required object structure.
                "type": "object",
                "description": (
                    "Total payment to carrier — the dollar amount the "
                    "carrier receives for the load.  Always return this "
                    "as an object with 'value' and 'confidence' keys."
                ),
                "properties": {
                    "value": {
                        "type": ["string", "null"],
                        "description": (
                            "Plain decimal number — no currency symbol, no commas, "
                            "always two decimal places (e.g. '1500.00', '820.00', '1200.50'). "
                            "null when not found."
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 that this value is correct. Use 0.0 when value is null.",
                    },
                },
                "required": ["value", "confidence"],
                "additionalProperties": False,
            },
            "date": {
                "type": "object",
                "description": (
                    "Pickup or earliest date for the load — the date the "
                    "truck was or will be picked up.  Always return this "
                    "as an object with 'value' and 'confidence' keys."
                ),
                "properties": {
                    "value": {
                        "type": ["string", "null"],
                        "description": (
                            "Raw date string as it appears in the document "
                            "(e.g. '03/11/2024', 'March 13, 2024'). "
                            "null when not found."
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 that this value is correct. Use 0.0 when value is null.",
                    },
                },
                "required": ["value", "confidence"],
                "additionalProperties": False,
            },
        },
        "required": ["pay", "date"],
        "additionalProperties": False,
    },
}

_SYSTEM_PROMPT = """\
You are a precise document data extractor for trucking income documents.

Your task:
- Extract the **total payment to carrier** (the dollar amount the carrier \
receives for the load).
- Extract the **pickup date** (or the earliest date associated with the load).

Rules:
- For pay: return a plain decimal number — no currency symbols, no commas, \
always two decimal places (e.g. '1500.00', '820.00', '1200.50').
- For date: return the date string exactly as it appears in the document text.
- If a field is clearly present, return it with high confidence (>= 0.9).
- If you are uncertain or the value is ambiguous, lower your confidence score.
- Do NOT fabricate values. Only extract what is explicitly stated.

Output format — always use this exact JSON structure, never a plain string:
  Found:     {"value": "1500.00", "confidence": 0.95}
  Not found: {"value": null, "confidence": 0.0}"""


def _normalize_pay_value(raw: str) -> str | None:
    """Normalize a pay string to a plain decimal with two decimal places.

    Strips currency symbols, commas, spaces, and surrounding whitespace.
    Returns None if the string cannot be parsed as a valid positive number.
    """
    cleaned = re.sub(r"[$, ]", "", raw.strip())
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return str(amount.quantize(Decimal("0.01")))


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
                # Field omitted entirely — treated as not found.
                continue

            if not isinstance(entry, dict):
                raise MalformedToolResponse(
                    f"Field '{field_name}' has unexpected type {type(entry).__name__!r} "
                    f"(expected object with 'value' and 'confidence'). "
                    f"Raw value: {entry!r}"
                )

            raw_value = entry.get("value") or ""  # null value → empty string → not found
            confidence = float(entry.get("confidence", 0.0))

            if not raw_value:
                continue

            certainty = _confidence_to_certainty(confidence)

            if field_name == "pay":
                normalized = _normalize_pay_value(raw_value)
                if normalized is None:
                    # Unparseable — keep raw string but cap certainty at REVIEW
                    if certainty == Certainty.HIGH:
                        certainty = Certainty.REVIEW
                else:
                    raw_value = normalized

            fields.append(
                ExtractedField(
                    name=field_name,
                    value=raw_value,
                    source_document=source_document,
                    source_page=None,
                    confidence=confidence,
                    certainty=certainty,
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
