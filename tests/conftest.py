"""Top-level test fixtures shared across all test levels."""

from pathlib import Path

import pytest

_DATA_RAW = Path(__file__).parent.parent / "data" / "raw"


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    """Return the path to a real settlement PDF from data/raw/.

    Tests that depend on this fixture are smoke-tested against an actual
    document. They are skipped automatically when data/raw/ is empty so the
    suite still passes in CI environments that don't carry the raw files.
    """
    pdfs = sorted(_DATA_RAW.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No PDF files found in data/raw/ — skipping real-document tests.")
    return pdfs[0]
