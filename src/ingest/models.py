from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageRender:
    """A single document page rendered to JPEG, ready for the OCR stage.

    Geometry fields exist to support traceability: Azure Document Intelligence
    returns bounding box coordinates in inches. To draw highlights in the
    combined report PDF later, those inch coordinates must be mapped back to
    PDF point space (1 pt = 1/72 inch).

    The mapping at highlight time:
        x_pts = bbox_x_inches * 72
        y_pts = bbox_y_inches * 72

    `original_width_pts` and `original_height_pts` are the page dimensions
    from the source PDF (in points). For image files these are derived from
    the pixel dimensions at the render DPI. They are recorded here so report
    assembly can embed pages at their correct size without re-opening the
    source file.
    """

    page_number: int            # 1-indexed position within the source document
    jpeg_bytes: bytes           # JPEG-encoded image sent to OCR
    width_px: int               # rendered image width  (at `dpi`)
    height_px: int              # rendered image height (at `dpi`)
    dpi: int                    # resolution used for rendering
    original_width_pts: float   # source page width  in PDF points (72 pts/inch)
    original_height_pts: float  # source page height in PDF points (72 pts/inch)


@dataclass
class IngestedDocument:
    """Result of the ingestion stage for a single source file.

    Postconditions (guaranteed by ingest_document()):
    - source_path exists and has not been modified.
    - content_hash is the SHA-256 hex digest of the file's bytes at the time
      of ingestion. Use this as the cache key to skip re-processing unchanged
      files.
    - pages is non-empty and ordered by page_number ascending.
    - Every page is rendered at the same DPI.
    """

    source_path: Path
    content_hash: str           # SHA-256 hex digest — cache key
    pages: list[PageRender] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)
