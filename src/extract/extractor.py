from __future__ import annotations

import re

from loguru import logger

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan
from src.extract.rules import ALL_RULES
from src.ocr.models import OcrResult

_CERTAINTY_MAP: dict[str, Certainty] = {
    "high": Certainty.HIGH,
    "review": Certainty.REVIEW,
}


class RulesExtractor:
    """Regex/rule-based field extraction — the original extraction strategy.

    Iterates ``ALL_RULES`` in order.  For each rule module the patterns are
    tried sequentially; first match wins.  Matched spans are resolved to
    ``OcrLine`` bounding boxes for PDF highlighting.
    """

    def extract(self, ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult:
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


def extract_document(ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult:
    """Convenience wrapper that delegates to the configured extractor.

    Existing call sites that import ``extract_document`` continue to work.
    The active extraction strategy is determined by ``EXTRACTION_MODE`` in
    the environment / ``.env`` file.
    """
    from src.config import load_settings
    from src.extract import create_extractor

    settings = load_settings()
    extractor = create_extractor(settings.extraction_mode)
    return extractor.extract(ocr_result, page_count)
