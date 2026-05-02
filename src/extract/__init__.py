from src.extract.base import Extractor
from src.extract.exceptions import ExtractionError
from src.extract.extractor import extract_document
from src.extract.models import Certainty, DocumentExtractionResult, ExtractedField, SourceSpan

__all__ = [
    "Certainty",
    "create_extractor",
    "extract_document",
    "DocumentExtractionResult",
    "ExtractionError",
    "ExtractedField",
    "Extractor",
    "SourceSpan",
]


def create_extractor(mode: str) -> Extractor:
    """Return an extractor implementation for the given *mode*.

    Lazy imports keep both strategies optional at import time — the LLM
    dependencies are only loaded when ``mode="llm"``.
    """
    if mode == "rules":
        from src.extract.extractor import RulesExtractor

        return RulesExtractor()

    if mode == "llm":
        from src.extract.llm.extractor import LlmExtractor

        return LlmExtractor.from_config()

    raise ValueError(f"Unknown extraction mode: {mode!r}")
