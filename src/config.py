from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Application-wide settings loaded from environment variables.

    Azure OCR credentials are still read directly by ``src.ocr.client`` —
    this module owns LLM-related configuration.
    """

    anthropic_api_key: str
    llm_model: str

    # Confidence thresholds for mapping LLM scores to Certainty enum
    confidence_high_threshold: float
    confidence_review_threshold: float


_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_HIGH_THRESHOLD = 0.9
_DEFAULT_REVIEW_THRESHOLD = 0.6


def load_settings() -> Settings:
    """Build a ``Settings`` instance from ``.env`` and environment variables.

    Validates that ``ANTHROPIC_API_KEY`` is present.
    """
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is required. Set it in your .env file."
        )

    llm_model = os.getenv("LLM_MODEL", _DEFAULT_MODEL).strip()

    high_t = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", str(_DEFAULT_HIGH_THRESHOLD)))
    review_t = float(os.getenv("CONFIDENCE_REVIEW_THRESHOLD", str(_DEFAULT_REVIEW_THRESHOLD)))

    return Settings(
        anthropic_api_key=api_key,
        llm_model=llm_model,
        confidence_high_threshold=high_t,
        confidence_review_threshold=review_t,
    )
