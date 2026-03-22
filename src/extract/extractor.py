from __future__ import annotations

import re

from loguru import logger

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan

_CERTAINTY_MAP: dict[str, Certainty] = {
    "high": Certainty.HIGH,
    "review": Certainty.REVIEW,
}
from src.extract.rules import ALL_RULES
from src.ocr.models import OcrResult


def extract_document(ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult:
    """Run all extraction rules against *ocr_result* and return typed results.

    Each rule module exposes ``COLUMN`` (field name) and ``PATTERNS`` (ordered
    list of regex pattern dicts). Patterns are tried in order; **first match
    wins** for each rule.  On a match the overlapping ``OcrLine`` bounding
    boxes are resolved via ``ocr_result.find_lines_for_span()`` and stored as
    ``SourceSpan`` values on the ``ExtractedField``.

    Fields that are not found produce no ``ExtractedField`` entry (not an error).
    """
    full_text = ocr_result.full_text
    source_name = ocr_result.source_path.name
    fields: list[ExtractedField] = []

    for rule_module in ALL_RULES:
        column: str = rule_module.COLUMN
        patterns: list[dict] = rule_module.PATTERNS
        matched = False

        for pattern_def in patterns:
            m = re.search(pattern_def["regex"], full_text)
            if m is None:
                continue

            raw_value = m.group(1)

            overlapping_lines = ocr_result.find_lines_for_span(m.start(), m.end())
            spans = [
                SourceSpan(
                    page_number=line.page_number,
                    bounding_box=line.bounding_box,
                )
                for line in overlapping_lines
            ]

            primary_page = spans[0].page_number if spans else None

            certainty = _CERTAINTY_MAP.get(
                pattern_def.get("certainty", ""), Certainty.REVIEW
            )

            fields.append(
                ExtractedField(
                    name=column,
                    value=raw_value,
                    source_document=source_name,
                    source_page=primary_page,
                    source_spans=spans,
                    certainty=certainty,
                )
            )

            logger.info(
                "  [{}] matched '{}' → '{}'",
                column,
                pattern_def["name"],
                raw_value,
            )
            matched = True
            break  # first match wins

        if not matched:
            logger.info("  [{}] no pattern matched", column)

    logger.info(
        "Extraction complete for '{}' — {} field(s) found",
        source_name,
        len(fields),
    )

    return DocumentExtractionResult(
        source_path=ocr_result.source_path,
        content_hash=ocr_result.content_hash,
        fields=fields,
        page_count=page_count,
    )
