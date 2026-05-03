"""Unit tests for src.cache.store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cache.store import _cache_filename, cache_get, cache_put
from src.extract.models import (
    Certainty,
    DocumentExtractionResult,
    ExtractedField,
    ExtractedLoad,
    SourceSpan,
)
from src.ocr.models import BoundingBox


_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _make_field(
    name: str,
    value: str,
    source_path: Path,
    *,
    page: int = 1,
    y: float = 4.5,
) -> ExtractedField:
    return ExtractedField(
        name=name,
        value=value,
        source_document=source_path.name,
        source_page=page,
        source_spans=[
            SourceSpan(
                page_number=page,
                bounding_box=BoundingBox(x=1.0, y=y, width=4.0, height=0.25),
            )
        ],
    )


def _make_result(
    source_path: Path,
    content_hash: str = _HASH_A,
    page_count: int = 1,
) -> DocumentExtractionResult:
    """Build a realistic DocumentExtractionResult (single load) for testing."""
    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        page_count=page_count,
        loads=[
            ExtractedLoad(
                index=1,
                pay=_make_field("pay", "750.00", source_path, y=4.5),
                date=_make_field("date", "03/12/2024", source_path, y=6.0),
            )
        ],
    )


def _make_multi_load_result(
    source_path: Path,
    content_hash: str = _HASH_A,
) -> DocumentExtractionResult:
    """Three-load result for round-trip and serialisation tests."""
    return DocumentExtractionResult(
        source_path=source_path,
        content_hash=content_hash,
        page_count=1,
        loads=[
            ExtractedLoad(
                index=1,
                pay=_make_field("pay", "1250.00", source_path, y=1.0),
                date=_make_field("date", "03/05/2024", source_path, y=1.5),
            ),
            ExtractedLoad(
                index=2,
                pay=_make_field("pay", "2400.00", source_path, y=3.0),
                date=_make_field("date", "03/12/2024", source_path, y=3.5),
            ),
            ExtractedLoad(
                index=3,
                pay=_make_field("pay", "875.50", source_path, y=5.0),
                date=_make_field("date", "03/19/2024", source_path, y=5.5),
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
        cache_put(tmp_path, result)

        loaded = cache_get(tmp_path, _HASH_A)
        assert loaded is not None
        # Idempotent write must not drop loads.
        assert len(loaded.loads) == 1

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)

        tmp_file = tmp_path / ".cache" / f"{_HASH_A}.tmp"
        assert not tmp_file.exists()


class TestRoundTrip:

    def test_single_load_roundtrip_preserves_all_fields(self, tmp_path: Path) -> None:
        source = tmp_path / "settlement.pdf"
        original = _make_result(source, content_hash=_HASH_A, page_count=2)
        cache_put(tmp_path, original)
        loaded = cache_get(tmp_path, _HASH_A)

        assert loaded is not None
        assert loaded.content_hash == original.content_hash
        assert loaded.page_count == original.page_count
        assert len(loaded.loads) == 1

        orig_load = original.loads[0]
        loaded_load = loaded.loads[0]
        assert loaded_load.index == orig_load.index

        # Pay field
        assert loaded_load.pay is not None
        assert loaded_load.pay.value == orig_load.pay.value
        assert loaded_load.pay.source_document == orig_load.pay.source_document
        assert loaded_load.pay.source_page == orig_load.pay.source_page
        assert len(loaded_load.pay.source_spans) == 1
        assert loaded_load.pay.source_spans[0].page_number == orig_load.pay.source_spans[0].page_number
        assert loaded_load.pay.source_spans[0].bounding_box.x == orig_load.pay.source_spans[0].bounding_box.x
        assert loaded_load.pay.source_spans[0].bounding_box.y == pytest.approx(orig_load.pay.source_spans[0].bounding_box.y)

        # Date field
        assert loaded_load.date is not None
        assert loaded_load.date.value == orig_load.date.value

    def test_three_load_roundtrip_preserves_all_loads(self, tmp_path: Path) -> None:
        source = tmp_path / "multi_load.pdf"
        original = _make_multi_load_result(source, content_hash=_HASH_A)
        cache_put(tmp_path, original)
        loaded = cache_get(tmp_path, _HASH_A)

        assert loaded is not None
        assert len(loaded.loads) == 3

        # Pin every value — a mutation that drops a load or swaps pay/date must fail.
        assert loaded.loads[0].index == 1
        assert loaded.loads[0].pay.value == "1250.00"
        assert loaded.loads[0].date.value == "03/05/2024"

        assert loaded.loads[1].index == 2
        assert loaded.loads[1].pay.value == "2400.00"
        assert loaded.loads[1].date.value == "03/12/2024"

        assert loaded.loads[2].index == 3
        assert loaded.loads[2].pay.value == "875.50"
        assert loaded.loads[2].date.value == "03/19/2024"

    def test_cache_file_serialises_loads_not_fields(self, tmp_path: Path) -> None:
        """The raw JSON must contain a 'loads' key, not a legacy 'fields' key."""
        result = _make_result(tmp_path / "doc.pdf", content_hash=_HASH_A)
        cache_put(tmp_path, result)

        cache_file = tmp_path / ".cache" / f"{_HASH_A}_llm.json"
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "loads" in data
        assert "fields" not in data
        assert data["content_hash"] == _HASH_A
        assert "page_count" in data

    def test_load_with_null_pay_roundtrips_correctly(self, tmp_path: Path) -> None:
        """A load where pay is None must round-trip without error."""
        source = tmp_path / "no_pay.pdf"
        result = DocumentExtractionResult(
            source_path=source,
            content_hash=_HASH_A,
            page_count=1,
            loads=[
                ExtractedLoad(
                    index=1,
                    pay=None,
                    date=_make_field("date", "01/01/2024", source),
                )
            ],
        )
        cache_put(tmp_path, result)
        loaded = cache_get(tmp_path, _HASH_A)

        assert loaded is not None
        assert len(loaded.loads) == 1
        assert loaded.loads[0].pay is None
        assert loaded.loads[0].date is not None
        assert loaded.loads[0].date.value == "01/01/2024"

    def test_certainty_roundtrips_correctly(self, tmp_path: Path) -> None:
        """Certainty enum values must survive JSON serialisation."""
        source = tmp_path / "cert.pdf"
        pay = _make_field("pay", "500.00", source)
        pay = ExtractedField(
            name="pay", value="500.00", source_document=source.name,
            source_page=1, certainty=Certainty.REVIEW,
        )
        date = ExtractedField(
            name="date", value="05/01/2024", source_document=source.name,
            source_page=1, certainty=Certainty.HIGH,
        )
        result = DocumentExtractionResult(
            source_path=source,
            content_hash=_HASH_A,
            page_count=1,
            loads=[ExtractedLoad(index=1, pay=pay, date=date)],
        )
        cache_put(tmp_path, result)
        loaded = cache_get(tmp_path, _HASH_A)

        assert loaded.loads[0].pay.certainty == Certainty.REVIEW
        assert loaded.loads[0].date.certainty == Certainty.HIGH


class TestCacheVersioning:

    def test_filename_without_version(self) -> None:
        assert _cache_filename("abc123") == "abc123_llm.json"

    def test_filename_with_version(self) -> None:
        assert _cache_filename("abc123", "v1fp") == "abc123_llm_v1fp.json"

    def test_filename_exact_separator_is_underscore_not_hyphen(self) -> None:
        result = _cache_filename("abc123", "v1fp")
        assert result == "abc123_llm_v1fp.json"
        assert "-" not in result

    def test_filename_without_version_exact_format(self) -> None:
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
