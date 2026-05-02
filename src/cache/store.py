from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from loguru import logger

from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox

_CERTAINTY_LOOKUP: dict[str, Certainty] = {c.value: c for c in Certainty}


def _cache_dir(working_folder: Path) -> Path:
    return working_folder / ".cache"


def _cache_filename(content_hash: str, mode: str, version: str | None = None) -> str:
    """Build the cache filename, incorporating the extraction mode and version.

    The optional *version* is a fingerprint of the extraction configuration
    (sanitizer patterns, schema definition) so that changes to those
    components automatically invalidate stale cached results.

    Files written by earlier versions (no mode/version suffix) are
    intentionally NOT matched — they are treated as cache misses and
    reprocessed under the current configuration.
    """
    if version:
        return f"{content_hash}_{mode}_{version}.json"
    return f"{content_hash}_{mode}.json"


def cache_get(
    working_folder: Path,
    content_hash: str,
    mode: str = "rules",
    version: str | None = None,
) -> DocumentExtractionResult | None:
    """Return the cached extraction result for *content_hash* + *mode* + *version*, or ``None`` on miss.

    Returns ``None`` without raising if the cache file is absent or corrupt.
    """
    cache_file = _cache_dir(working_folder) / _cache_filename(content_hash, mode, version)
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
    mode: str = "rules",
    version: str | None = None,
) -> None:
    """Write *result* to ``.cache/<content_hash>_<mode>[_<version>].json``.

    Uses an atomic write (tmp file + rename) to prevent corrupt partial writes
    if the process is interrupted.
    """
    cache_directory = _cache_dir(working_folder)
    cache_directory.mkdir(parents=True, exist_ok=True)

    filename = _cache_filename(result.content_hash, mode, version)
    cache_file = cache_directory / filename
    tmp_file = cache_directory / f"{result.content_hash}.tmp"

    try:
        data = _serialize(result)
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.replace(cache_file)
        logger.debug("Cached extraction result for hash {} (mode={})", result.content_hash[:12], mode)
    except Exception as exc:
        logger.warning("Failed to write cache for '{}': {}", result.source_path.name, exc)
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)


def _serialize(result: DocumentExtractionResult) -> dict:
    """Convert *result* to a JSON-serialisable dict.

    ``Path`` values are converted to strings; all other fields are plain
    Python primitives via ``dataclasses.asdict()``.
    """
    raw = dataclasses.asdict(result)
    raw["source_path"] = str(result.source_path)
    return raw


def _deserialize(data: dict, source_path: Path) -> DocumentExtractionResult:
    """Reconstruct a ``DocumentExtractionResult`` from a deserialised dict.

    *source_path* overrides the stored path so that the result is valid even
    if the working folder has been moved since the cache was written.
    """
    fields = [
        ExtractedField(
            name=f["name"],
            value=f["value"],
            source_document=f["source_document"],
            source_page=f["source_page"],
            confidence=f.get("confidence"),
            certainty=_CERTAINTY_LOOKUP.get(f.get("certainty", ""), None),
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
                for s in f.get("source_spans", [])
            ],
        )
        for f in data.get("fields", [])
    ]

    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=data["content_hash"],
        fields=fields,
        page_count=data.get("page_count", 0),
        extraction_error=data.get("extraction_error"),
    )
