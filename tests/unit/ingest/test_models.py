"""Unit tests for src/ingest/models.py.

These tests verify dataclass construction, defaults, and the page_count
property — no file I/O, no external dependencies.
"""

from pathlib import Path

import pytest

from src.ingest.models import IngestedDocument, PageRender


def _make_page(number: int) -> PageRender:
    return PageRender(
        page_number=number,
        jpeg_bytes=b"\xff\xd8\xff\x00",
        width_px=800,
        height_px=1100,
        dpi=150,
        original_width_pts=595.0,
        original_height_pts=842.0,
    )


# ---------------------------------------------------------------------------
# PageRender
# ---------------------------------------------------------------------------


class TestPageRender:
    def test_stores_all_fields(self) -> None:
        page = PageRender(
            page_number=3,
            jpeg_bytes=b"\xff\xd8\xff",
            width_px=1240,
            height_px=1754,
            dpi=150,
            original_width_pts=595.0,
            original_height_pts=842.0,
        )
        assert page.page_number == 3
        assert page.jpeg_bytes == b"\xff\xd8\xff"
        assert page.width_px == 1240
        assert page.height_px == 1754
        assert page.dpi == 150
        assert page.original_width_pts == 595.0
        assert page.original_height_pts == 842.0

    def test_equality_on_same_values(self) -> None:
        kwargs = dict(
            page_number=1,
            jpeg_bytes=b"\xff\xd8\xff",
            width_px=100,
            height_px=100,
            dpi=72,
            original_width_pts=100.0,
            original_height_pts=100.0,
        )
        assert PageRender(**kwargs) == PageRender(**kwargs)

    def test_inequality_on_different_page_number(self) -> None:
        a = _make_page(1)
        b = _make_page(2)
        assert a != b


# ---------------------------------------------------------------------------
# IngestedDocument — construction
# ---------------------------------------------------------------------------


class TestIngestedDocumentConstruction:
    def test_stores_source_path(self) -> None:
        path = Path("some/document.pdf")
        doc = IngestedDocument(source_path=path, content_hash="a" * 64)
        assert doc.source_path == path

    def test_stores_content_hash(self) -> None:
        h = "b" * 64
        doc = IngestedDocument(source_path=Path("x.pdf"), content_hash=h)
        assert doc.content_hash == h

    def test_default_pages_is_empty_list(self) -> None:
        doc = IngestedDocument(source_path=Path("x.pdf"), content_hash="c" * 64)
        assert doc.pages == []

    def test_explicit_pages_stored(self) -> None:
        pages = [_make_page(1), _make_page(2)]
        doc = IngestedDocument(
            source_path=Path("x.pdf"), content_hash="d" * 64, pages=pages
        )
        assert doc.pages == pages

    def test_default_pages_are_independent_per_instance(self) -> None:
        """Mutable default: each instance must get its own list."""
        doc_a = IngestedDocument(source_path=Path("a.pdf"), content_hash="e" * 64)
        doc_b = IngestedDocument(source_path=Path("b.pdf"), content_hash="f" * 64)
        doc_a.pages.append(_make_page(1))
        assert doc_b.pages == [], "Default pages list was shared between instances"


# ---------------------------------------------------------------------------
# IngestedDocument.page_count
# ---------------------------------------------------------------------------


class TestPageCount:
    def test_zero_when_pages_is_empty(self) -> None:
        doc = IngestedDocument(source_path=Path("x.pdf"), content_hash="a" * 64)
        assert doc.page_count == 0

    def test_one_for_single_page(self) -> None:
        doc = IngestedDocument(
            source_path=Path("x.pdf"),
            content_hash="b" * 64,
            pages=[_make_page(1)],
        )
        assert doc.page_count == 1

    def test_reflects_list_length(self) -> None:
        pages = [_make_page(i) for i in range(1, 6)]
        doc = IngestedDocument(
            source_path=Path("x.pdf"), content_hash="c" * 64, pages=pages
        )
        assert doc.page_count == len(pages)

    def test_updates_when_pages_list_is_mutated(self) -> None:
        doc = IngestedDocument(source_path=Path("x.pdf"), content_hash="d" * 64)
        assert doc.page_count == 0
        doc.pages.append(_make_page(1))
        assert doc.page_count == 1
        doc.pages.append(_make_page(2))
        assert doc.page_count == 2
