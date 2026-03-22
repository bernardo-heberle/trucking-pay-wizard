import io
import time

from azure.ai.documentintelligence import DocumentIntelligenceClient
from loguru import logger

from src.ingest.models import IngestedDocument, PageRender
from src.ocr.exceptions import OcrError
from src.ocr.models import BoundingBox, OcrLine, OcrPage, OcrResult

# Azure DocumentPageLengthUnit values
_UNIT_PIXEL = "pixel"
_UNIT_INCH = "inch"


def analyze_document(
    document: IngestedDocument,
    client: DocumentIntelligenceClient,
    rate_limit_delay: float = 1.1,  # seconds between pages; set 0 for S0 tier
) -> OcrResult:
    """Send each page of `document` to Azure prebuilt-read and return an OcrResult.

    Preconditions:
    - document.pages is non-empty and ordered by page_number ascending.
    - client is a configured DocumentIntelligenceClient.

    Postconditions:
    - Returns an OcrResult whose `content_hash` matches document.content_hash.
    - Every OcrLine's char_start/char_end indexes into OcrResult.full_text.
    - BoundingBox coordinates are in inches regardless of the Azure response unit.

    Raises:
        OcrError: An Azure API call fails or returns an unexpected response.
    """
    ocr_pages: list[OcrPage] = []
    all_lines: list[OcrLine] = []
    global_offset = 0

    total_pages = len(document.pages)
    logger.info(
        "Starting OCR for '{}' — {} page(s)",
        document.source_path.name,
        total_pages,
    )

    for idx, page_render in enumerate(document.pages):
        page_number = page_render.page_number
        logger.debug(
            "  Page {}/{} — sending {:.2f} MB JPEG",
            page_number,
            total_pages,
            len(page_render.jpeg_bytes) / 1024 / 1024,
        )

        try:
            poller = client.begin_analyze_document(
                "prebuilt-read",
                body=io.BytesIO(page_render.jpeg_bytes),
            )
            result = poller.result()
        except Exception as exc:
            raise OcrError(
                f"Azure API call failed for page {page_number} of "
                f"'{document.source_path.name}': {exc}"
            ) from exc

        if not result.pages:
            raise OcrError(
                f"Azure returned no page data for page {page_number} of "
                f"'{document.source_path.name}'."
            )

        azure_page = result.pages[0]
        scale = _inch_scale(azure_page.unit, page_render)

        page_width_inches = (azure_page.width or 0.0) * scale
        page_height_inches = (azure_page.height or 0.0) * scale
        azure_lines = azure_page.lines or []

        page_lines: list[OcrLine] = []

        for line_idx, azure_line in enumerate(azure_lines):
            text = azure_line.content
            bbox = _polygon_to_bbox(azure_line.polygon, scale)

            char_start = global_offset
            char_end = global_offset + len(text)

            page_lines.append(
                OcrLine(
                    text=text,
                    page_number=page_number,
                    bounding_box=bbox,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

            global_offset += len(text)

            is_last_line_of_page = line_idx == len(azure_lines) - 1
            if not is_last_line_of_page:
                global_offset += 1  # \n between lines within a page

        all_lines.extend(page_lines)

        ocr_pages.append(
            OcrPage(
                page_number=page_number,
                width_inches=page_width_inches,
                height_inches=page_height_inches,
                line_count=len(page_lines),
            )
        )

        is_last_page = idx == total_pages - 1
        if not is_last_page:
            global_offset += 2  # \n\n page separator

        logger.debug(
            "  Page {}/{} — {} line(s) extracted",
            page_number,
            total_pages,
            len(page_lines),
        )

        if not is_last_page and rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    logger.info(
        "OCR complete for '{}' — {} line(s) across {} page(s)",
        document.source_path.name,
        len(all_lines),
        total_pages,
    )

    return OcrResult(
        source_path=document.source_path,
        content_hash=document.content_hash,
        pages=ocr_pages,
        lines=all_lines,
    )


def _inch_scale(unit: str | None, page_render: PageRender) -> float:
    """Return the multiplier to convert Azure coordinates to inches.

    Azure returns pixel coordinates for image inputs and inch coordinates for
    PDF inputs. When unit is 'pixel', divide by the render DPI to get inches.
    """
    if unit == _UNIT_PIXEL:
        return 1.0 / page_render.dpi
    return 1.0  # "inch" or unknown — treat as inches


def _polygon_to_bbox(polygon: list[float] | None, scale: float) -> BoundingBox:
    """Convert an Azure flat polygon [x0,y0,x1,y1,...] to an axis-aligned BoundingBox.

    Coordinates are scaled by `scale` to produce inch values.
    Falls back to a zero-size box if the polygon is missing or malformed.
    """
    if not polygon or len(polygon) < 4:
        return BoundingBox(x=0.0, y=0.0, width=0.0, height=0.0)

    xs = [polygon[i] * scale for i in range(0, len(polygon), 2)]
    ys = [polygon[i] * scale for i in range(1, len(polygon), 2)]

    x_min = min(xs)
    y_min = min(ys)
    return BoundingBox(
        x=x_min,
        y=y_min,
        width=max(xs) - x_min,
        height=max(ys) - y_min,
    )
