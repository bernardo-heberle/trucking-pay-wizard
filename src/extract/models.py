from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.ocr.models import BoundingBox

EXPECTED_FIELDS: list[str] = ["pay", "date"]


class Certainty(str, Enum):
    """How reliable an extracted value is.

    HIGH — the pattern is a strong, unambiguous anchor.
    REVIEW — the pattern is a fallback, estimated, or positional extraction.
    NOT_FOUND — no pattern matched for the field.
    """

    HIGH = "High"
    REVIEW = "Review"
    NOT_FOUND = "Not Found"


@dataclass
class SourceSpan:
    """A page location for an extracted value — enough for PDF highlighting."""

    page_number: int
    bounding_box: BoundingBox


@dataclass
class ExtractedField:
    """A single extracted value with full provenance back to the source document.

    Every field carries enough information to highlight the source text
    in the combined report PDF and to trace the value back to its origin.
    """

    name: str
    value: str
    source_document: str
    source_page: int | None
    source_spans: list[SourceSpan] = field(default_factory=list)
    confidence: float | None = None
    certainty: Certainty | None = None


@dataclass
class DocumentExtractionResult:
    """Extraction output for a single document — consumed by the report stage.

    When extraction fails after all retries are exhausted, ``fields`` is empty
    and ``extraction_error`` carries a human-readable description of the
    failure.  Callers must check ``extraction_error`` before caching — failed
    results are not cached so the document is retried on the next pipeline run.
    """

    source_path: Path
    content_hash: str
    fields: list[ExtractedField] = field(default_factory=list)
    page_count: int = 0
    extraction_error: str | None = None

    def overall_certainty(self, expected_fields: list[str]) -> Certainty:
        """Return the worst certainty across *expected_fields*.

        If any expected field is missing entirely, returns ``NOT_FOUND``.
        If all are present but any has ``REVIEW``, returns ``REVIEW``.
        Otherwise returns ``HIGH``.
        """
        field_map = {f.name: f for f in self.fields}

        for name in expected_fields:
            if name not in field_map:
                return Certainty.NOT_FOUND

        worst = Certainty.HIGH
        for name in expected_fields:
            cert = field_map[name].certainty
            if cert is None or cert == Certainty.NOT_FOUND:
                return Certainty.NOT_FOUND
            if cert == Certainty.REVIEW:
                worst = Certainty.REVIEW

        return worst
