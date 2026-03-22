from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.ocr.models import BoundingBox


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


@dataclass
class DocumentExtractionResult:
    """Extraction output for a single document — consumed by the report stage."""

    source_path: Path
    content_hash: str
    fields: list[ExtractedField] = field(default_factory=list)
    page_count: int = 0
