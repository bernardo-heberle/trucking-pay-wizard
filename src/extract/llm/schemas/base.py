from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.extract.models import ExtractedField


class ExtractionSchema(ABC):
    """Base class for pluggable LLM extraction schemas.

    Subclasses define *what* fields to extract by providing:
      - a tool definition for Claude's ``tool_use`` (structured output)
      - a system prompt giving the LLM extraction context
      - a parser that converts the LLM's JSON response into ``ExtractedField``
        objects with confidence scores

    To support a new document type, create a new subclass — the
    ``LlmExtractor`` does not need to change.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable schema identifier (used in logging and cache keys)."""
        ...

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
    ) -> list[ExtractedField]:
        """Convert the LLM's tool-call input into ``ExtractedField`` objects.

        *tool_input* is the parsed JSON the model returned as the tool's
        ``input`` block.  *source_document* is the filename for provenance.
        """
        ...
