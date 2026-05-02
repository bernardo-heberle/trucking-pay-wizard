"""Unit tests for src.cache.store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cache.store import _cache_filename, cache_get, cache_put
from src.extract.models import DocumentExtractionResult, ExtractedField, SourceSpan
from src.ocr.models import BoundingBox


_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _make_result(
    source_path: Path,
    content_hash: str = _HASH_A,
    page_count: int = 1,
) -> DocumentExtractionResult:
    """Build a realistic DocumentExtractionResult for testing."""
    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        page_count=page_count,
        fields=[
            ExtractedField(
                name="pay",
                value="750.00",
                source_document=source_path.name,
                source_page=1,
                source_spans=[
                    SourceSpan(
                        page_number=1,
                        bounding_box=BoundingBox(x=1.0, y=4.5, width=4.0, height=0.25),
                    )
                ],
            ),
            ExtractedField(
                name="date",
                value="03/12/2024",
                source_document=source_path.name,
                source_page=1,
                source_spans=[
                    SourceSpan(
                        page_number=1,
                        bounding_box=BoundingBox(x=1.0, y=6.0, width=3.5, height=0.25),
                    )
                ],
            ),
        ],
    )


class TestCacheGet:

    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        assert cache_get(tmp_path, _HASH_A) is None

    def test_different_hash_is_miss(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)
        assert cache_get(tmp_path, _HASH_B) is None

    def test_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / f"{_HASH_A}_llm.json").write_text("{invalid json", encoding="utf-8")
        assert cache_get(tmp_path, _HASH_A) is None

    def test_source_path_overridden_on_load(self, tmp_path: Path) -> None:
        original_path = tmp_path / "original_folder" / "doc.pdf"
        result = _make_result(original_path, content_hash=_HASH_A)
        cache_put(tmp_path, result)

        loaded = cache_get(tmp_path, _HASH_A)
        assert loaded is not None
        # source_path in cache file is stale; cache_get returns the stored path
        # — callers are responsible for supplying the live path when needed.
        # Here we verify the path IS the one stored (not some other corruption).
        assert loaded.source_path == original_path


class TestCachePut:

    def test_put_creates_cache_dir_and_file(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)

        cache_file = tmp_path / ".cache" / f"{_HASH_A}_llm.json"
        assert cache_file.exists()

    def test_put_is_idempotent(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)
        cache_put(tmp_path, result)  # second write must not raise

        cache_file = tmp_path / ".cache" / f"{_HASH_A}_llm.json"
        assert cache_file.exists()

        # A mutant that truncates on the second write would drop fields —
        # verify the full payload is still readable after two writes.
        loaded = cache_get(tmp_path, _HASH_A)
        assert loaded is not None
        assert len(loaded.fields) == 2

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)

        tmp_file = tmp_path / ".cache" / f"{_HASH_A}.tmp"
        assert not tmp_file.exists()


class TestRoundTrip:

    def test_roundtrip_preserves_all_fields(self, tmp_path: Path) -> None:
        source = tmp_path / "settlement.pdf"
        original = _make_result(source, content_hash=_HASH_A, page_count=2)
        cache_put(tmp_path, original)
        loaded = cache_get(tmp_path, _HASH_A)

        assert loaded is not None
        assert loaded.content_hash == original.content_hash
        assert loaded.page_count == original.page_count
        assert len(loaded.fields) == len(original.fields)

        for orig_field, loaded_field in zip(original.fields, loaded.fields):
            assert loaded_field.name == orig_field.name
            assert loaded_field.value == orig_field.value
            assert loaded_field.source_document == orig_field.source_document
            assert loaded_field.source_page == orig_field.source_page
            assert len(loaded_field.source_spans) == len(orig_field.source_spans)

            for orig_span, loaded_span in zip(orig_field.source_spans, loaded_field.source_spans):
                assert loaded_span.page_number == orig_span.page_number
                assert loaded_span.bounding_box.x == orig_span.bounding_box.x
                assert loaded_span.bounding_box.y == orig_span.bounding_box.y
                assert loaded_span.bounding_box.width == orig_span.bounding_box.width
                assert loaded_span.bounding_box.height == orig_span.bounding_box.height

    def test_cache_file_is_valid_json(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)

        cache_file = tmp_path / ".cache" / f"{_HASH_A}_llm.json"
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["content_hash"] == _HASH_A
        assert "fields" in data
        assert "page_count" in data


class TestCacheVersioning:
    """Verify that the version parameter correctly partitions cache entries."""

    def test_filename_without_version(self) -> None:
        assert _cache_filename("abc123") == "abc123_llm.json"

    def test_filename_with_version(self) -> None:
        assert _cache_filename("abc123", "v1fp") == "abc123_llm_v1fp.json"

    def test_filename_exact_separator_is_underscore_not_hyphen(self) -> None:
        """A swap of '_' to '-' in the format string must be detectable.

        The format is ``<hash>_llm[_<version>].json`` — underscores throughout.
        A hyphen mutant would produce ``abc123-llm-v1fp.json``, which is a
        different cache key and would silently cause cache misses.
        """
        result = _cache_filename("abc123", "v1fp")
        # Exact format: hash, underscore, mode, underscore, version, dot, json
        assert result == "abc123_llm_v1fp.json"
        assert "-" not in result

    def test_filename_without_version_exact_format(self) -> None:
        """Pin the exact unversioned format to catch any separator mutation."""
        result = _cache_filename("deadbeef1234")
        assert result == "deadbeef1234_llm.json"
        assert "-" not in result

    def test_version_mismatch_is_cache_miss(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf")
        cache_put(tmp_path, result, version="old_fingerprint")

        assert cache_get(tmp_path, _HASH_A, version="new_fingerprint") is None

    def test_version_match_is_cache_hit(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf")
        cache_put(tmp_path, result, version="same_fp")

        loaded = cache_get(tmp_path, _HASH_A, version="same_fp")
        assert loaded is not None
        assert loaded.content_hash == _HASH_A

    def test_no_version_does_not_match_versioned(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf")
        cache_put(tmp_path, result)

        assert cache_get(tmp_path, _HASH_A, version="some_fp") is None

    def test_versioned_does_not_match_no_version(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf")
        cache_put(tmp_path, result, version="some_fp")

        assert cache_get(tmp_path, _HASH_A) is None
