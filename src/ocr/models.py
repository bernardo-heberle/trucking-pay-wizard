from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class BoundingBox:
    """Axis-aligned bounding box with coordinates in inches (Azure native unit).

    Use `as_pts()` when placing highlights in the PDF report.
    """

    x: float
    y: float
    width: float
    height: float

    def as_pts(self) -> tuple[float, float, float, float]:
        """Return (x, y, width, height) converted to PDF points (1 pt = 1/72 inch)."""
        return (self.x * 72, self.y * 72, self.width * 72, self.height * 72)


@dataclass
class OcrLine:
    """A single text line returned by Azure, with page position and char offsets.

    `char_start` and `char_end` are global offsets into `OcrResult.full_text`.
    Call `OcrResult.find_lines_for_span(match.start(), match.end())` after a
    regex match to retrieve the bounding boxes for that match.
    """

    text: str
    page_number: int        # 1-indexed, matches PageRender.page_number
    bounding_box: BoundingBox
    char_start: int         # global offset into OcrResult.full_text (inclusive)
    char_end: int           # global offset into OcrResult.full_text (exclusive)


@dataclass
class OcrPage:
    """Per-page summary from the OCR response."""

    page_number: int
    width_inches: float
    height_inches: float
    line_count: int


@dataclass
class OcrResult:
    """Top-level output of the OCR stage for a single document.

    `content_hash` is copied from the source `IngestedDocument` and serves as
    the pipeline cache key — the OCR stage itself performs no caching.
    """

    source_path: Path
    content_hash: str
    pages: list[OcrPage]
    lines: list[OcrLine]    # all pages, ordered, with global char offsets

    @property
    def full_text(self) -> str:
        """Full document text with lines joined by \\n and pages separated by \\n\\n.

        The global char offsets stored on each `OcrLine` index into exactly this
        string, so regex matches can be mapped back to bounding boxes via
        `find_lines_for_span()`.
        """
        if not self.lines:
            return ""

        pages_dict: dict[int, list[str]] = {}
        for line in self.lines:
            pages_dict.setdefault(line.page_number, []).append(line.text)

        page_texts = ["\n".join(pages_dict[pn]) for pn in sorted(pages_dict)]
        return "\n\n".join(page_texts)

    def find_lines_for_span(self, start: int, end: int) -> list[OcrLine]:
        """Return all OcrLines whose character range overlaps [start, end).

        Used by the extraction stage to resolve regex match positions to the
        bounding boxes needed for PDF highlighting.
        """
        return [
            line for line in self.lines
            if line.char_start < end and line.char_end > start
        ]
