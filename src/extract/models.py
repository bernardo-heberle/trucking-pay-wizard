from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.ocr.models import BoundingBox


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
class ExtractedLoad:
    """A single load extracted from a document — pay and date as a paired unit.

    A document may carry N loads (e.g. a settlement statement listing multiple
    trips).  Single-load documents are represented as a one-element list.
    Both ``pay`` and ``date`` may be ``None`` when the LLM could not extract
    that field for this load.
    """

    index: int                    # 1-based position within the document
    pay: ExtractedField | None
    date: ExtractedField | None

    def certainty(self) -> Certainty:
        """Return the worst certainty across pay and date for this load.

        Returns ``NOT_FOUND`` when either field is absent or has ``None``
        certainty.  Returns ``REVIEW`` when both are present but one is
        REVIEW.  Returns ``HIGH`` only when both are present and HIGH.
        """
        worst = Certainty.HIGH
        for fld in (self.pay, self.date):
            if fld is None:
                return Certainty.NOT_FOUND
            cert = fld.certainty
            if cert is None or cert == Certainty.NOT_FOUND:
                return Certainty.NOT_FOUND
            if cert == Certainty.REVIEW:
                worst = Certainty.REVIEW
        return worst


@dataclass
class DocumentExtractionResult:
    """Extraction output for a single document — consumed by the report stage.

    Each document may carry one or more loads (``ExtractedLoad`` objects).
    Single-load documents have ``len(loads) == 1``.

    When extraction fails after all retries are exhausted, ``loads`` is empty
    and ``extraction_error`` carries a human-readable description of the
    failure.  Callers must check ``extraction_error`` before caching — failed
    results are not cached so the document is retried on the next pipeline run.
    """

    source_path: Path
    content_hash: str
    loads: list[ExtractedLoad] = field(default_factory=list)
    page_count: int = 0
    extraction_error: str | None = None

    def overall_certainty(self) -> Certainty:
        """Return the worst certainty across all loads.

        Returns ``NOT_FOUND`` when ``loads`` is empty or any load has
        ``NOT_FOUND`` certainty.  Returns ``REVIEW`` when all loads are
        present but any has ``REVIEW``.  Otherwise returns ``HIGH``.
        """
        if not self.loads:
            return Certainty.NOT_FOUND

        worst = Certainty.HIGH
        for load in self.loads:
            load_cert = load.certainty()
            if load_cert == Certainty.NOT_FOUND:
                return Certainty.NOT_FOUND
            if load_cert == Certainty.REVIEW:
                worst = Certainty.REVIEW
        return worst
