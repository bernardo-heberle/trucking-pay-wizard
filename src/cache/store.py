from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from src.extract.models import (
    Certainty,
    DocumentExtractionResult,
    ExtractedField,
    ExtractedLoad,
    SourceSpan,
)
from src.ocr.models import BoundingBox

_CERTAINTY_LOOKUP: dict[str, Certainty] = {c.value: c for c in Certainty}

_MODE = "llm"


def _cache_dir(working_folder: Path) -> Path:
    return working_folder / ".cache"


def _cache_filename(content_hash: str, version: str | None = None) -> str:
    """Build the cache filename, incorporating the version fingerprint.

    The optional *version* is a fingerprint of the extraction configuration
    (sanitizer patterns, schema definition) so that changes to those
    components automatically invalidate stale cached results.

    Files written by earlier versions (no mode/version suffix) are
    intentionally NOT matched — they are treated as cache misses and
    reprocessed under the current configuration.
    """
    if version:
        return f"{content_hash}_{_MODE}_{version}.json"
    return f"{content_hash}_{_MODE}.json"


def cache_get(
    working_folder: Path,
    content_hash: str,
    version: str | None = None,
) -> DocumentExtractionResult | None:
    """Return the cached extraction result for *content_hash* + *version*, or ``None`` on miss.

    Returns ``None`` without raising if the cache file is absent or corrupt.
    """
    cache_file = _cache_dir(working_folder) / _cache_filename(content_hash, version)
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        source_path = Path(data["source_path"])
        return _deserialize(data, source_path)
    except Exception as exc:
        logger.warning("Cache file '{}' is unreadable — treating as miss: {}", cache_file.name, exc)
        return None


def cache_put(
    working_folder: Path,
    result: DocumentExtractionResult,
    version: str | None = None,
) -> None:
    """Write *result* to ``.cache/<content_hash>_llm[_<version>].json``.

    Uses an atomic write (tmp file + rename) to prevent corrupt partial writes
    if the process is interrupted.
    """
    cache_directory = _cache_dir(working_folder)
    cache_directory.mkdir(parents=True, exist_ok=True)

    filename = _cache_filename(result.content_hash, version)
    cache_file = cache_directory / filename
    tmp_file = cache_directory / f"{result.content_hash}.tmp"

    try:
        data = _serialize(result)
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.replace(cache_file)
        logger.debug("Cached extraction result for hash {}", result.content_hash[:12])
    except Exception as exc:
        logger.warning("Failed to write cache for '{}': {}", result.source_path.name, exc)
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)


def _serialize_field(field: ExtractedField | None) -> dict | None:
    """Serialize an ``ExtractedField`` to a JSON-serialisable dict, or None."""
    if field is None:
        return None
    return {
        "name": field.name,
        "value": field.value,
        "source_document": field.source_document,
        "source_page": field.source_page,
        "confidence": field.confidence,
        "certainty": field.certainty.value if field.certainty is not None else None,
        "source_spans": [
            {
                "page_number": span.page_number,
                "bounding_box": {
                    "x": span.bounding_box.x,
                    "y": span.bounding_box.y,
                    "width": span.bounding_box.width,
                    "height": span.bounding_box.height,
                },
            }
            for span in field.source_spans
        ],
    }


def _deserialize_field(data: dict | None) -> ExtractedField | None:
    """Reconstruct an ``ExtractedField`` from a deserialised dict, or None."""
    if data is None:
        return None
    return ExtractedField(
        name=data["name"],
        value=data["value"],
        source_document=data["source_document"],
        source_page=data["source_page"],
        confidence=data.get("confidence"),
        certainty=_CERTAINTY_LOOKUP.get(data.get("certainty", ""), None),
        source_spans=[
            SourceSpan(
                page_number=s["page_number"],
                bounding_box=BoundingBox(
                    x=s["bounding_box"]["x"],
                    y=s["bounding_box"]["y"],
                    width=s["bounding_box"]["width"],
                    height=s["bounding_box"]["height"],
                ),
            )
            for s in data.get("source_spans", [])
        ],
    )


def _serialize(result: DocumentExtractionResult) -> dict:
    """Convert *result* to a JSON-serialisable dict.

    ``Path`` values are converted to strings.  Loads are stored as a list
    of ``{index, pay, date}`` objects, each containing the full field dict.
    """
    return {
        "source_path": str(result.source_path),
        "content_hash": result.content_hash,
        "page_count": result.page_count,
        "extraction_error": result.extraction_error,
        "loads": [
            {
                "index": load.index,
                "pay": _serialize_field(load.pay),
                "date": _serialize_field(load.date),
            }
            for load in result.loads
        ],
    }


def _deserialize(data: dict, source_path: Path) -> DocumentExtractionResult:
    """Reconstruct a ``DocumentExtractionResult`` from a deserialised dict.

    *source_path* overrides the stored path so that the result is valid even
    if the working folder has been moved since the cache was written.
    """
    loads = [
        ExtractedLoad(
            index=entry.get("index", i + 1),
            pay=_deserialize_field(entry.get("pay")),
            date=_deserialize_field(entry.get("date")),
        )
        for i, entry in enumerate(data.get("loads", []))
    ]

    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=data["content_hash"],
        loads=loads,
        page_count=data.get("page_count", 0),
        extraction_error=data.get("extraction_error"),
    )
