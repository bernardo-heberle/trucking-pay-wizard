from __future__ import annotations

from anthropic import Anthropic

from src.config import Settings


def build_anthropic_client(settings: Settings) -> Anthropic:
    """Return a configured Anthropic client using credentials from *settings*."""
    return Anthropic(api_key=settings.anthropic_api_key)
