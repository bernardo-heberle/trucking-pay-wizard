from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from src.extract.exceptions import MalformedToolResponse
from src.extract.models import Certainty, Classification, ExtractedField, ExtractedLoad

from .base import ExtractionSchema

_TOOL_NAME = "extract_income_fields"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": (
        "Extract financial fields from a trucking income document.  "
        "Return one entry per distinct load with its pay and date."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_payment_document": {
                "type": "boolean",
                "description": (
                    "True if this document is some form of proof that the "
                    "carrier received (or is owed) a payment — e.g. a settlement "
                    "statement, dispatch/load sheet with a carrier pay amount, "
                    "carrier statement, COD settlement, or remittance / "
                    "advice-of-deposit notification.  False ONLY when the "
                    "document clearly contains no proof of payment to a carrier "
                    "(e.g. a bill of lading or rate confirmation with no payment "
                    "amount, an insurance certificate, or an unrelated/misfiled "
                    "document).  When uncertain, return true."
                ),
            },
            "classification_confidence": {
                "type": "number",
                "description": (
                    "Confidence 0.0-1.0 that the is_payment_document "
                    "classification is correct."
                ),
            },
            "classification_reason": {
                "type": "string",
                "description": (
                    "One short sentence explaining the classification decision."
                ),
            },
            "loads": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "One entry per distinct load on the document. "
                    "Single-load documents return a one-element array."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "pay": {
                            "type": ["object", "null"],
                            "description": (
                                "Total payment to carrier for this load — the dollar "
                                "amount the carrier receives."
                            ),
                            "properties": {
                                "value": {
                                    "type": "string",
                                    "description": (
                                        "Dollar amount as it appears in the document "
                                        "(e.g. '$1,500.00', '$820.00')."
                                    ),
                                },
                                "confidence": {
                                    "type": "number",
                                    "description": "Confidence 0.0-1.0 that this value is correct.",
                                },
                                "source_line": {
                                    "type": "string",
                                    "description": (
                                        "Complete line of text containing this value, "
                                        "copied verbatim from the document."
                                    ),
                                },
                            },
                            "required": ["value", "confidence", "source_line"],
                        },
                        "date": {
                            "type": ["object", "null"],
                            "description": (
                                "The most relevant date for this load — pickup date if "
                                "present, otherwise the earliest date on the document."
                            ),
                            "properties": {
                                "value": {
                                    "type": "string",
                                    "description": (
                                        "Date string as it appears in the document "
                                        "(e.g. '03/11/2024', 'March 13, 2024')."
                                    ),
                                },
                                "confidence": {
                                    "type": "number",
                                    "description": "Confidence 0.0-1.0 that this value is correct.",
                                },
                                "source_line": {
                                    "type": "string",
                                    "description": (
                                        "Complete line of text containing this value, "
                                        "copied verbatim from the document."
                                    ),
                                },
                            },
                            "required": ["value", "confidence", "source_line"],
                        },
                    },
                    "required": ["pay", "date"],
                },
            },
        },
        "required": ["is_payment_document", "loads"],
    },
}

_SYSTEM_PROMPT = """\
You are a precise document data extractor for trucking income documents.

Common formats include: CentralDispatch settlement sheets, V2 Dispatch load \
summaries, Super Dispatch / BacklotCars carrier statements, COD settlement \
statements, and remittance advice / advice-of-deposit payment notifications \
(e.g. from shippers such as Weyerhaeuser).

Your task:
- First, classify whether the document is a proof-of-payment document (set \
is_payment_document) — see "Document classification" below.
- Then extract the **total payment to carrier** (the dollar amount the carrier \
receives) and **the most relevant date** for each load on the document.
- Some documents list a single load; many settlement statements list several. \
Return one entry per distinct load with its own pay and date. If the document \
has only one load, return a single-element array.

Document classification — is_payment_document:
- Truckers sometimes upload the wrong files, so a packet may contain documents \
that have nothing to do with proof of payment. Flag those.
- Set is_payment_document = true when the document is any form of proof that a \
carrier received (or is owed) a payment: settlement statements, dispatch/load \
sheets showing a carrier pay amount, carrier statements, COD settlements, \
remittance advice, or advice-of-deposit / payment notifications.
- Set is_payment_document = false ONLY when the document clearly has no proof of \
payment to a carrier — for example a bill of lading or rate confirmation with no \
payment amount, an insurance certificate or COI, a driver's license, an inspection \
report, or an unrelated / misfiled document.
- ERR ON THE SIDE OF CAUTION: if you are unsure whether the document shows proof \
of payment, return true. Only return false when you are confident the document is \
not a payment document.
- Always also return classification_confidence (0.0-1.0) and a one-sentence \
classification_reason.
- When is_payment_document is false there is usually no pay or date to extract — \
return a single load with pay = null and date = null.

Rules:
- For pay: return the dollar amount exactly as it appears in the document, \
including any currency symbols, commas, or formatting (e.g. '$1,500.00', \
'$820.00', '1200.50').
- For date: return the date string exactly as it appears in the document text.
- For each field, also return source_line: the complete line of text from the \
document that contains the value. Copy it exactly as it appears — do not \
paraphrase, truncate, or rearrange. This is used to locate the value in the \
original document.
- If a field is clearly present, return it with high confidence (>= 0.9).
- If you are uncertain or the value is ambiguous, lower your confidence score.
- If a field is not present for a load, return null for that field.
- Do NOT fabricate values. Only extract what is explicitly stated.
- Do NOT merge multiple loads into one — each distinct load is its own entry.

Disambiguation — Pay:
- "Total payment to carrier" is the net amount the carrier receives after any \
deductions. It is NOT the shipper price, broker fee, COD amount, deposit, or \
insurance fee. If multiple dollar amounts appear, choose the one explicitly \
labeled as carrier payment, "Company owes Carrier", or equivalent.
- If the document shows invoice line items (individual invoice amounts) followed \
by a labeled "TOTAL" row, return exactly ONE load using the TOTAL row amount as \
the pay. The individual line items are components that sum to the TOTAL — they \
are NOT separate loads. Never split a document into multiple loads solely \
because it lists multiple invoice line items.
- Some documents show negative line items (credits or adjustments) with a \
trailing minus sign (e.g. "2,324.50-"). These are deductions already reflected \
in the TOTAL; do not negate or adjust the TOTAL.
- If the document shows a revision history with older amounts (e.g. $0.00 from \
a previous revision), extract only the current/final amount — not the \
historical one.
- Some documents open with a settlement summary section (labeled, e.g., \
"Settlement at a glance" or "a summary of the activity on your account this \
period") that states the period's net pay-out, followed by pages of detailed \
breakdown tables (per-trip earning rows, per-pro or per-truck subtotals, \
deduction line items). When such a summary section is present, treat the whole \
document as ONE settlement: return exactly one load whose pay is the net amount \
paid out to the carrier from the summary (labeled, e.g., "Total Period Pay-Out", \
"Total Pay-Out", "Net Pay", or "Total Paid"). Do NOT use the gross "Total Period \
Earnings" figure, and do NOT create a separate load for each detail row — ignore \
the item-by-item earning and deduction calculations on the detail pages.

Disambiguation — Date:
- Prefer "Pickup Date" or "Pickup Exactly" when present.
- For settlement summaries with a leading summary section (see the pay rule \
above), use the "Period ending" date shown in that summary.
- If no pickup date is present, use the earliest date visible anywhere in the \
document (e.g. a date labeled "electronically processed on", "payment date", \
"transaction date", "invoice date", or "statement date").
- Do NOT return null for date when any date is visible in the document — always \
fall back to the earliest date rather than leaving the field empty."""


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


def _parse_field_entry(
    entry: Any,
    field_name: str,
    source_document: str,
) -> ExtractedField | None:
    """Parse a single field entry from within a load object.

    Returns an ``ExtractedField`` on success, ``None`` when the entry is
    null or has an empty value.  Raises ``MalformedToolResponse`` when the
    entry is an unexpected type (number, list, bool …).
    """
    if entry is None:
        return None

    if isinstance(entry, dict):
        raw_value = entry.get("value", "") or ""
        confidence = float(entry.get("confidence", 0.0))
        certainty = _confidence_to_certainty(confidence)
        source_line = entry.get("source_line") or None
    elif isinstance(entry, str):
        # Haiku occasionally collapses the field to a plain string instead
        # of the required {"value": "...", "confidence": ...} object.
        # The model reported no confidence score, so we store 0.0.
        # Certainty is set to REVIEW as an explicit business policy:
        # a structurally-degraded response always needs human verification.
        raw_value = entry
        confidence = 0.0
        certainty = Certainty.REVIEW
        source_line = None
    else:
        raise MalformedToolResponse(
            f"Field '{field_name}' has unexpected type {type(entry).__name__!r} "
            f"(expected object or string). Raw value: {entry!r}"
        )

    if not raw_value:
        return None

    if field_name == "pay":
        # Keep the raw value as returned by the LLM so it can be matched back
        # to the exact OCR text for PDF highlighting.  Only cap certainty when
        # the string contains no parseable number at all — a completely
        # unrecognisable value needs review.
        if _normalize_pay_value(raw_value) is None:
            if certainty == Certainty.HIGH:
                certainty = Certainty.REVIEW

    return ExtractedField(
        name=field_name,
        value=raw_value,
        source_document=source_document,
        source_page=None,
        source_line=source_line,
        confidence=confidence,
        certainty=certainty,
    )


class IncomeDocumentSchema(ExtractionSchema):
    """Schema for extracting pay and date from trucking income documents."""

    @property
    def name(self) -> str:
        return "income"

    def tool_definition(self) -> dict[str, Any]:
        return _TOOL_SCHEMA

    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def parse_classification(self, tool_input: dict[str, Any]) -> Classification:
        """Read the document-level classification fields from *tool_input*.

        Defaults to ``is_payment_document=True`` when the flag is missing or not
        a boolean, so an under-specified response keeps the document included
        (err on the side of caution).
        """
        raw_flag = tool_input.get("is_payment_document", True)
        is_payment = raw_flag if isinstance(raw_flag, bool) else True

        raw_conf = tool_input.get("classification_confidence")
        try:
            confidence = float(raw_conf) if raw_conf is not None else None
        except (TypeError, ValueError):
            confidence = None

        raw_reason = tool_input.get("classification_reason")
        reason = raw_reason if isinstance(raw_reason, str) and raw_reason else None

        return Classification(
            is_payment_document=is_payment,
            confidence=confidence,
            reason=reason,
        )

    def parse_tool_result(
        self,
        tool_input: dict[str, Any],
        source_document: str,
    ) -> list[ExtractedLoad]:
        raw_loads = tool_input.get("loads")

        # Graceful handling: if the model returns the old flat shape
        # ({"pay": ..., "date": ...}) instead of {"loads": [...]}, wrap it.
        if raw_loads is None and ("pay" in tool_input or "date" in tool_input):
            raw_loads = [{"pay": tool_input.get("pay"), "date": tool_input.get("date")}]

        if not isinstance(raw_loads, list) or len(raw_loads) == 0:
            raise MalformedToolResponse(
                f"Expected 'loads' to be a non-empty list; got: {raw_loads!r}"
            )

        loads: list[ExtractedLoad] = []
        for i, load_entry in enumerate(raw_loads, start=1):
            if not isinstance(load_entry, dict):
                raise MalformedToolResponse(
                    f"Load entry {i} has unexpected type "
                    f"{type(load_entry).__name__!r} (expected object). "
                    f"Raw value: {load_entry!r}"
                )

            pay_field = _parse_field_entry(
                load_entry.get("pay"),
                field_name="pay",
                source_document=source_document,
            )
            date_field = _parse_field_entry(
                load_entry.get("date"),
                field_name="date",
                source_document=source_document,
            )

            loads.append(ExtractedLoad(index=i, pay=pay_field, date=date_field))

        return loads


def _confidence_to_certainty(confidence: float) -> Certainty:
    from src.config import load_settings

    settings = load_settings()
    if confidence >= settings.confidence_high_threshold:
        return Certainty.HIGH
    if confidence >= settings.confidence_review_threshold:
        return Certainty.REVIEW
    return Certainty.NOT_FOUND
