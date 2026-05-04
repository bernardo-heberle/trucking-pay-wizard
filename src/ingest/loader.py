import hashlib
from pathlib import Path

import fitz  # pymupdf
from loguru import logger

from src.ingest.exceptions import IngestionError, UnsupportedFileTypeError
from src.ingest.models import IngestedDocument, PageRender

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
)

DEFAULT_DPI: int = 150


def ingest_document(source_path: Path, dpi: int = DEFAULT_DPI) -> IngestedDocument:
    """Load a document file and render each page to JPEG at the given DPI.

    Preconditions:
    - source_path must exist and be a file.
    - source_path extension must be in SUPPORTED_EXTENSIONS.

    Postconditions:
    - Returns an IngestedDocument whose content_hash is the SHA-256 of the
      file's bytes, pages are ordered 1..N, and every page is rendered as JPEG
      at `dpi` resolution.
    - The source file is never modified.

    Raises:
        UnsupportedFileTypeError: extension is not in SUPPORTED_EXTENSIONS.
        IngestionError: file cannot be opened or rendered by PyMuPDF.
    """
    source_path = Path(source_path)

    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'{source_path.name}' has unsupported extension "
            f"'{source_path.suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    logger.info("Ingesting '{}' at {} DPI", source_path.name, dpi)

    raw_bytes = source_path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    logger.debug("Content hash: {}", content_hash)

    try:
        doc = fitz.open(source_path)
    except Exception as exc:
        raise IngestionError(
            f"Failed to open '{source_path.name}': {exc}"
        ) from exc

    pages: list[PageRender] = []

    for fitz_page in doc:
        page_number = fitz_page.number + 1  # fitz is 0-indexed; we use 1-indexed

        original_width_pts = fitz_page.rect.width
        original_height_pts = fitz_page.rect.height

        try:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = fitz_page.get_pixmap(matrix=mat)
            jpeg_bytes = pix.tobytes("jpeg")
        except Exception as exc:
            raise IngestionError(
                f"Failed to render page {page_number} of '{source_path.name}': {exc}"
            ) from exc

        pages.append(
            PageRender(
                page_number=page_number,
                jpeg_bytes=jpeg_bytes,
                width_px=pix.width,
                height_px=pix.height,
                dpi=dpi,
                original_width_pts=original_width_pts,
                original_height_pts=original_height_pts,
            )
        )
        logger.debug(
            "  Page {}/{}: {}x{} px ({:.2f} MB JPEG)",
            page_number,
            len(doc),
            pix.width,
            pix.height,
            len(jpeg_bytes) / 1024 / 1024,
        )

    doc.close()
    logger.info(
        "Ingested '{}': {} page(s), hash {}",
        source_path.name,
        len(pages),
        content_hash[:12],
    )

    return IngestedDocument(
        source_path=source_path,
        content_hash=content_hash,
        pages=pages,
    )


def hash_document(source_path: Path) -> str:
    """Return the SHA-256 content hash of *source_path* without rendering pages.

    This is the cheap path used to check the cache before committing to full
    ingestion. The returned hash is identical to ``IngestedDocument.content_hash``.

    Raises:
        UnsupportedFileTypeError: extension is not in SUPPORTED_EXTENSIONS.
        FileNotFoundError: file does not exist.
    """
    source_path = Path(source_path)
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'{source_path.name}' has unsupported extension "
            f"'{source_path.suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return hashlib.sha256(source_path.read_bytes()).hexdigest()


def collect_source_files(folder: Path) -> list[Path]:
    """Return all supported document files in folder, sorted by name.

    Only files directly inside the folder are returned — subdirectories
    (including .cache/) are not searched.

    Preconditions:
    - folder must be an existing directory.
    """
    if not folder.is_dir():
        raise IngestionError(f"'{folder}' is not a directory.")

    files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    logger.info("Found {} source file(s) in '{}'", len(files), folder)
    return files
