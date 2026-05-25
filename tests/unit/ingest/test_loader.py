"""Unit tests for src/ingest/loader.py.

Covers ingest_document() and collect_source_files().

Fixtures:
  synthetic_pdf           – single-page A4 PDF (from conftest)
  synthetic_multipage_pdf – 3-page PDF (from conftest)
  png_file                – valid 100×100 PNG (from conftest)
  corrupt_pdf             – .pdf file with invalid bytes (from conftest)
"""

import hashlib
from pathlib import Path

import pytest

from src.ingest.exceptions import IngestionError, UnsupportedFileTypeError
from src.ingest.loader import (
    DEFAULT_DPI,
    SUPPORTED_EXTENSIONS,
    collect_source_files,
    deduplicate_files,
    ingest_document,
)
from src.ingest.models import IngestedDocument, PageRender

_JPEG_MAGIC = b"\xff\xd8\xff"


# ---------------------------------------------------------------------------
# ingest_document — return type and structure
# ---------------------------------------------------------------------------


class TestIngestDocumentReturnType:
    def test_returns_ingested_document_instance(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert isinstance(result, IngestedDocument)

    def test_source_path_is_preserved(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert result.source_path == synthetic_pdf

    def test_pages_are_page_render_instances(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert all(isinstance(p, PageRender) for p in result.pages)

    def test_accepts_str_path(self, synthetic_pdf: Path) -> None:
        """ingest_document should coerce a plain string to Path internally."""
        result = ingest_document(str(synthetic_pdf))  # type: ignore[arg-type]
        assert isinstance(result, IngestedDocument)


# ---------------------------------------------------------------------------
# ingest_document — page count and ordering
# ---------------------------------------------------------------------------


class TestIngestDocumentPages:
    def test_single_page_document(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert result.page_count == 1

    def test_multipage_document(self, synthetic_multipage_pdf: Path) -> None:
        result = ingest_document(synthetic_multipage_pdf)
        assert result.page_count == 3

    def test_pages_are_ordered_one_indexed(self, synthetic_multipage_pdf: Path) -> None:
        result = ingest_document(synthetic_multipage_pdf)
        numbers = [p.page_number for p in result.pages]
        assert numbers == list(range(1, result.page_count + 1))

    def test_pages_list_is_nonempty(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert len(result.pages) > 0


# ---------------------------------------------------------------------------
# ingest_document — DPI handling
# ---------------------------------------------------------------------------


class TestIngestDocumentDPI:
    def test_default_dpi_is_150(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert DEFAULT_DPI == 150
        assert all(p.dpi == 150 for p in result.pages)

    def test_custom_dpi_stored_on_pages(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf, dpi=72)
        assert all(p.dpi == 72 for p in result.pages)

    def test_higher_dpi_produces_more_pixels(self, synthetic_pdf: Path) -> None:
        low = ingest_document(synthetic_pdf, dpi=72)
        high = ingest_document(synthetic_pdf, dpi=150)
        assert high.pages[0].width_px > low.pages[0].width_px
        assert high.pages[0].height_px > low.pages[0].height_px


# ---------------------------------------------------------------------------
# ingest_document — JPEG bytes
# ---------------------------------------------------------------------------


class TestIngestDocumentJPEGBytes:
    def test_jpeg_bytes_are_nonempty(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert all(len(p.jpeg_bytes) > 0 for p in result.pages)

    def test_jpeg_bytes_start_with_magic_header(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        for page in result.pages:
            assert page.jpeg_bytes[:3] == _JPEG_MAGIC, (
                f"Page {page.page_number} jpeg_bytes do not start with FF D8 FF"
            )


# ---------------------------------------------------------------------------
# ingest_document — geometry
# ---------------------------------------------------------------------------


class TestIngestDocumentGeometry:
    def test_pixel_dimensions_are_positive(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        for page in result.pages:
            assert page.width_px > 0
            assert page.height_px > 0

    def test_original_pt_dimensions_are_positive(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        for page in result.pages:
            assert page.original_width_pts > 0
            assert page.original_height_pts > 0

    def test_original_pts_reflect_a4_source_dimensions(self, synthetic_pdf: Path) -> None:
        """synthetic_pdf is created as 595×842 pt (A4). Those values should survive."""
        result = ingest_document(synthetic_pdf)
        page = result.pages[0]
        assert page.original_width_pts == pytest.approx(595, abs=1)
        assert page.original_height_pts == pytest.approx(842, abs=1)


# ---------------------------------------------------------------------------
# ingest_document — content hash
# ---------------------------------------------------------------------------


class TestIngestDocumentContentHash:
    def test_hash_is_64_char_hex(self, synthetic_pdf: Path) -> None:
        result = ingest_document(synthetic_pdf)
        assert len(result.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.content_hash)

    def test_hash_matches_sha256_of_file_bytes(self, synthetic_pdf: Path) -> None:
        expected = hashlib.sha256(synthetic_pdf.read_bytes()).hexdigest()
        result = ingest_document(synthetic_pdf)
        assert result.content_hash == expected

    def test_hash_is_stable_across_calls(self, synthetic_pdf: Path) -> None:
        r1 = ingest_document(synthetic_pdf)
        r2 = ingest_document(synthetic_pdf)
        assert r1.content_hash == r2.content_hash

    def test_different_files_produce_different_hashes(
        self, synthetic_pdf: Path, synthetic_multipage_pdf: Path
    ) -> None:
        r1 = ingest_document(synthetic_pdf)
        r2 = ingest_document(synthetic_multipage_pdf)
        assert r1.content_hash != r2.content_hash


# ---------------------------------------------------------------------------
# ingest_document — source file integrity
# ---------------------------------------------------------------------------


class TestIngestDocumentFileIntegrity:
    def test_source_file_bytes_unchanged_after_ingest(self, synthetic_pdf: Path) -> None:
        before = synthetic_pdf.read_bytes()
        ingest_document(synthetic_pdf)
        assert synthetic_pdf.read_bytes() == before


# ---------------------------------------------------------------------------
# ingest_document — image file support
# ---------------------------------------------------------------------------


class TestIngestDocumentImageInputs:
    def test_ingest_png_returns_single_page(self, png_file: Path) -> None:
        result = ingest_document(png_file)
        assert isinstance(result, IngestedDocument)
        assert result.page_count == 1

    def test_ingest_png_jpeg_bytes_valid(self, png_file: Path) -> None:
        result = ingest_document(png_file)
        assert result.pages[0].jpeg_bytes[:3] == _JPEG_MAGIC


# ---------------------------------------------------------------------------
# ingest_document — error handling
# ---------------------------------------------------------------------------


class TestIngestDocumentErrors:
    def test_unsupported_extension_raises_unsupported_error(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "document.docx"
        path.write_bytes(b"content")
        with pytest.raises(UnsupportedFileTypeError):
            ingest_document(path)

    def test_txt_extension_raises_unsupported_error(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.txt"
        path.write_bytes(b"plain text")
        with pytest.raises(UnsupportedFileTypeError):
            ingest_document(path)

    def test_unsupported_file_type_error_is_ingestion_error_subclass(
        self, tmp_path: Path
    ) -> None:
        """UnsupportedFileTypeError must be catchable as IngestionError."""
        path = tmp_path / "document.docx"
        path.write_bytes(b"content")
        with pytest.raises(IngestionError):
            ingest_document(path)

    def test_error_message_includes_bad_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "my_doc.xyz"
        path.write_bytes(b"content")
        with pytest.raises(UnsupportedFileTypeError, match=r"\.xyz"):
            ingest_document(path)

    def test_corrupt_pdf_raises_ingestion_error(self, corrupt_pdf: Path) -> None:
        with pytest.raises(IngestionError):
            ingest_document(corrupt_pdf)

    def test_ingestion_error_message_includes_filename(self, corrupt_pdf: Path) -> None:
        with pytest.raises(IngestionError, match="corrupt.pdf"):
            ingest_document(corrupt_pdf)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """A missing file must raise FileNotFoundError before any OCR work begins."""
        path = tmp_path / "ghost.pdf"
        with pytest.raises(FileNotFoundError):
            ingest_document(path)


# ---------------------------------------------------------------------------
# collect_source_files
# ---------------------------------------------------------------------------


class TestCollectSourceFiles:
    def test_returns_list(self, tmp_path: Path) -> None:
        result = collect_source_files(tmp_path)
        assert isinstance(result, list)

    def test_empty_folder_returns_empty_list(self, tmp_path: Path) -> None:
        assert collect_source_files(tmp_path) == []

    def test_returns_only_supported_files(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"pdf")
        (tmp_path / "notes.txt").write_bytes(b"txt")
        (tmp_path / "data.csv").write_bytes(b"csv")
        result = collect_source_files(tmp_path)
        assert [p.name for p in result] == ["doc.pdf"]

    def test_all_supported_extensions_collected(self, tmp_path: Path) -> None:
        for ext in SUPPORTED_EXTENSIONS:
            (tmp_path / f"file{ext}").write_bytes(b"data")
        result = collect_source_files(tmp_path)
        found = {p.suffix.lower() for p in result}
        assert found == SUPPORTED_EXTENSIONS

    def test_only_unsupported_files_returns_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_bytes(b"text")
        (tmp_path / "sheet.csv").write_bytes(b"csv")
        assert collect_source_files(tmp_path) == []

    def test_results_sorted_by_name(self, tmp_path: Path) -> None:
        for name in ["charlie.pdf", "alpha.pdf", "bravo.pdf"]:
            (tmp_path / name).write_bytes(b"data")
        result = collect_source_files(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_skips_subdirectories(self, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.pdf").write_bytes(b"pdf")
        (tmp_path / "top_level.pdf").write_bytes(b"pdf")
        result = collect_source_files(tmp_path)
        assert len(result) == 1
        assert result[0].name == "top_level.pdf"

    def test_skips_cache_subdirectory(self, tmp_path: Path) -> None:
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "cached.pdf").write_bytes(b"pdf")
        (tmp_path / "real.pdf").write_bytes(b"pdf")
        result = collect_source_files(tmp_path)
        assert len(result) == 1
        assert result[0].name == "real.pdf"

    def test_returned_paths_are_absolute(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"pdf")
        result = collect_source_files(tmp_path)
        assert all(p.is_absolute() for p in result)

    def test_returned_paths_exist(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"pdf")
        result = collect_source_files(tmp_path)
        assert all(p.exists() for p in result)

    def test_nonexistent_folder_raises_ingestion_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        with pytest.raises(IngestionError):
            collect_source_files(missing)

    def test_file_path_raises_ingestion_error(self, tmp_path: Path) -> None:
        """Passing a file path instead of a directory must raise."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_bytes(b"content")
        with pytest.raises(IngestionError):
            collect_source_files(file_path)


# ---------------------------------------------------------------------------
# deduplicate_files
# ---------------------------------------------------------------------------


class TestDeduplicateFiles:
    """deduplicate_files() groups files by SHA-256 content hash.

    Only the first file (alphabetically) per unique-content group is kept.
    Skipped files are recorded in the returned duplicate_map.
    """

    def test_empty_list_returns_empty_results(self, tmp_path: Path) -> None:
        unique, dup_map = deduplicate_files([])

        assert unique == []
        assert dup_map == {}

    def test_single_file_returns_that_file_no_duplicates(self, tmp_path: Path) -> None:
        f = tmp_path / "only.pdf"
        f.write_bytes(b"unique content")

        unique, dup_map = deduplicate_files([f])

        assert unique == [f]
        assert dup_map == {}

    def test_two_unique_files_both_returned(self, tmp_path: Path) -> None:
        a = tmp_path / "alpha.pdf"
        b = tmp_path / "bravo.pdf"
        a.write_bytes(b"content_a")
        b.write_bytes(b"content_b")

        unique, dup_map = deduplicate_files([a, b])

        assert set(unique) == {a, b}
        assert dup_map == {}

    def test_two_identical_files_keeps_first_alphabetically(self, tmp_path: Path) -> None:
        payload = b"identical bytes"
        a = tmp_path / "alpha.pdf"
        b = tmp_path / "bravo.pdf"
        a.write_bytes(payload)
        b.write_bytes(payload)
        # collect_source_files sorts alphabetically, so pass in sorted order
        files = sorted([a, b], key=lambda p: p.name)

        unique, dup_map = deduplicate_files(files)

        assert unique == [a]
        assert dup_map == {"alpha.pdf": ["bravo.pdf"]}

    def test_three_identical_files_keeps_first_lists_both_others(self, tmp_path: Path) -> None:
        payload = b"same bytes"
        a = tmp_path / "alpha.pdf"
        b = tmp_path / "bravo.pdf"
        c = tmp_path / "charlie.pdf"
        for f in (a, b, c):
            f.write_bytes(payload)
        files = sorted([a, b, c], key=lambda p: p.name)

        unique, dup_map = deduplicate_files(files)

        assert unique == [a]
        assert dup_map == {"alpha.pdf": ["bravo.pdf", "charlie.pdf"]}

    def test_two_independent_duplicate_groups(self, tmp_path: Path) -> None:
        """Two separate groups of duplicates are each handled independently."""
        group1_a = tmp_path / "a1.pdf"
        group1_b = tmp_path / "a2.pdf"
        group2_a = tmp_path / "b1.pdf"
        group2_b = tmp_path / "b2.pdf"
        group1_a.write_bytes(b"group one")
        group1_b.write_bytes(b"group one")
        group2_a.write_bytes(b"group two")
        group2_b.write_bytes(b"group two")
        files = sorted([group1_a, group1_b, group2_a, group2_b], key=lambda p: p.name)

        unique, dup_map = deduplicate_files(files)

        assert set(unique) == {group1_a, group2_a}
        assert dup_map == {
            "a1.pdf": ["a2.pdf"],
            "b1.pdf": ["b2.pdf"],
        }

    def test_all_unique_files_returns_empty_duplicate_map(self, tmp_path: Path) -> None:
        files = []
        for i in range(4):
            f = tmp_path / f"doc_{i}.pdf"
            f.write_bytes(f"unique content {i}".encode())
            files.append(f)

        unique, dup_map = deduplicate_files(files)

        assert len(unique) == 4
        assert dup_map == {}

    def test_unique_files_preserve_input_order(self, tmp_path: Path) -> None:
        """Unique files appear in the same order as in the input list."""
        # Pass in reverse-alphabetical order to confirm output order matches input
        c = tmp_path / "charlie.pdf"
        b = tmp_path / "bravo.pdf"
        a = tmp_path / "alpha.pdf"
        c.write_bytes(b"c")
        b.write_bytes(b"b")
        a.write_bytes(b"a")

        unique, _ = deduplicate_files([c, b, a])

        assert [p.name for p in unique] == ["charlie.pdf", "bravo.pdf", "alpha.pdf"]

    def test_duplicate_uses_content_hash_not_filename(self, tmp_path: Path) -> None:
        """Files with different names but identical bytes are flagged as duplicates."""
        payload = b"settlement statement bytes"
        original = tmp_path / "settlement.pdf"
        copy = tmp_path / "settlement_copy.pdf"
        original.write_bytes(payload)
        copy.write_bytes(payload)

        unique, dup_map = deduplicate_files([original, copy])

        assert len(unique) == 1
        assert len(dup_map) == 1

    def test_different_content_not_flagged_as_duplicate(self, tmp_path: Path) -> None:
        """Files that differ by even one byte must not be grouped together."""
        f1 = tmp_path / "doc_a.pdf"
        f2 = tmp_path / "doc_b.pdf"
        f1.write_bytes(b"content version 1")
        f2.write_bytes(b"content version 2")

        unique, dup_map = deduplicate_files([f1, f2])

        assert len(unique) == 2
        assert dup_map == {}
