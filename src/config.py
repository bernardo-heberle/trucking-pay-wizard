from __future__ import annotations

from dataclasses import dataclass

from src import credentials as _creds


@dataclass(frozen=True)
class Settings:
    """Application-wide settings loaded from credential store and environment.

    Azure OCR credentials are still read directly by ``src.ocr.client`` —
    this module owns LLM-related configuration.
    """

    anthropic_api_key: str
    llm_model: str
    llm_temperature: float

    # Confidence thresholds for mapping LLM scores to Certainty enum
    confidence_high_threshold: float
    confidence_review_threshold: float


_DEFAULT_MODEL = "claude-sonnet-4-5"
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_HIGH_THRESHOLD = 0.9
_DEFAULT_REVIEW_THRESHOLD = 0.6


def load_settings() -> Settings:
    """Build a ``Settings`` instance from the credential store and environment.

    Raises:
        ValueError: ``ANTHROPIC_API_KEY`` is not available in either keyring
            or environment variables.  The GUI routes to the credentials page
            before calling this, so a raise here is a programming error.
    """
    import os

    from dotenv import load_dotenv

    api_key = _creds.get_anthropic_key()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is required but was not found. "
            "Set it via the credentials screen or a .env file."
        )

    load_dotenv()
    llm_model = (os.getenv("LLM_MODEL") or _DEFAULT_MODEL).strip()
    llm_temperature = float(os.getenv("LLM_TEMPERATURE") or _DEFAULT_TEMPERATURE)

    high_t = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD") or _DEFAULT_HIGH_THRESHOLD)
    review_t = float(os.getenv("CONFIDENCE_REVIEW_THRESHOLD") or _DEFAULT_REVIEW_THRESHOLD)

    return Settings(
        anthropic_api_key=api_key,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        confidence_high_threshold=high_t,
        confidence_review_threshold=review_t,
    )
