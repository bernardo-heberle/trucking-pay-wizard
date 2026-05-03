from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from src.extract.models import ExtractedLoad


class ExtractionSchema(ABC):
    """Base class for pluggable LLM extraction schemas.

    Subclasses define *what* fields to extract by providing:
      - a tool definition for Claude's ``tool_use`` (structured output)
      - a system prompt giving the LLM extraction context
      - a parser that converts the LLM's JSON response into ``ExtractedLoad``
        objects with per-field confidence scores

    To support a new document type, create a new subclass — the
    ``LlmExtractor`` does not need to change.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable schema identifier (used in logging and cache keys)."""
        ...

    def fingerprint(self) -> str:
        """Stable fingerprint of this schema's tool definition and system prompt.

        Changes whenever the tool schema or prompt is modified — causing
        cache entries produced under the old schema to become misses.
        """
        content = (
            json.dumps(self.tool_definition(), sort_keys=True)
            + self.system_prompt()
        )
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    @abstractmethod
    def tool_definition(self) -> dict[str, Any]:
        """Return the Anthropic ``tool`` dict sent alongside the API request.

        The dict must follow the Anthropic tool-definition format::

            {
                "name": "extract_fields",
                "description": "...",
                "input_schema": { ... JSON Schema ... }
            }
        """
        ...

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt that tells the LLM how to extract."""
        ...

    @abstractmethod
    def parse_tool_result(
        self,
        tool_input: dict[str, Any],
        source_document: str,
    ) -> list[ExtractedLoad]:
        """Convert the LLM's tool-call input into ``ExtractedLoad`` objects.

        *tool_input* is the parsed JSON the model returned as the tool's
        ``input`` block.  *source_document* is the filename for provenance.
        Each load carries its own ``pay`` and ``date`` ``ExtractedField``
        with confidence scores.
        """
        ...
