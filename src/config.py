from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Application-wide settings loaded from environment variables.

    Azure OCR credentials are still read directly by ``src.ocr.client`` —
    this module owns extraction-mode and LLM-related configuration.
    """

    extraction_mode: str
    anthropic_api_key: str
    llm_model: str

    # Confidence thresholds for mapping LLM scores to Certainty enum
    confidence_high_threshold: float
    confidence_review_threshold: float


_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_HIGH_THRESHOLD = 0.9
_DEFAULT_REVIEW_THRESHOLD = 0.6

_VALID_MODES = ("rules", "llm")


def load_settings() -> Settings:
    """Build a ``Settings`` instance from ``.env`` and environment variables.

    Validates that ``EXTRACTION_MODE`` is one of the recognised values and
    that ``ANTHROPIC_API_KEY`` is present when LLM mode is active.
    """
    load_dotenv()

    mode = os.getenv("EXTRACTION_MODE", "rules").strip().lower()
    if mode not in _VALID_MODES:
        raise ValueError(
            f"EXTRACTION_MODE must be one of {_VALID_MODES!r}, got {mode!r}"
        )

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if mode == "llm" and not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is required when EXTRACTION_MODE is 'llm'. "
            "Set it in your .env file."
        )

    llm_model = os.getenv("LLM_MODEL", _DEFAULT_MODEL).strip()

    high_t = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", str(_DEFAULT_HIGH_THRESHOLD)))
    review_t = float(os.getenv("CONFIDENCE_REVIEW_THRESHOLD", str(_DEFAULT_REVIEW_THRESHOLD)))

    return Settings(
        extraction_mode=mode,
        anthropic_api_key=api_key,
        llm_model=llm_model,
        confidence_high_threshold=high_t,
        confidence_review_threshold=review_t,
    )
