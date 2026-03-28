from __future__ import annotations

from typing import Protocol

from src.extract.models import DocumentExtractionResult
from src.ocr.models import OcrResult


class Extractor(Protocol):
    """Strategy interface for document field extraction.

    Implementations receive the OCR output for a single document and return
    a typed extraction result.  Both rules-based and LLM-based extractors
    conform to this protocol so the pipeline can swap strategies via config.
    """

    def extract(self, ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult: ...
