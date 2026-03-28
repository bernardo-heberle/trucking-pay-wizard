from __future__ import annotations

from anthropic import Anthropic
from loguru import logger

from src.config import Settings, load_settings
from src.extract.llm.client import build_anthropic_client
from src.extract.llm.sanitizer import sanitize_text
from src.extract.llm.schemas.base import ExtractionSchema
from src.extract.llm.schemas.income import IncomeDocumentSchema
from src.extract.models import DocumentExtractionResult, ExtractedField
from src.ocr.models import OcrResult


class LlmExtractor:
    """Schema-driven field extraction using the Anthropic API (Claude).

    The extractor sanitises OCR text (PII scrubbing), sends it to the
    configured model with a ``tool_use`` call matching the active schema,
    and parses the structured response into ``ExtractedField`` objects.
    """

    def __init__(
        self,
        client: Anthropic,
        settings: Settings,
        schema: ExtractionSchema | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._schema = schema or IncomeDocumentSchema()

    @classmethod
    def from_config(cls) -> LlmExtractor:
        """Construct an ``LlmExtractor`` from current environment settings."""
        settings = load_settings()
        client = build_anthropic_client(settings)
        return cls(client=client, settings=settings)

    def extract(self, ocr_result: OcrResult, page_count: int) -> DocumentExtractionResult:
        source_name = ocr_result.source_path.name
        logger.info("LLM extraction starting for '{}'", source_name)

        sanitized_text, report = sanitize_text(ocr_result.full_text)

        fields = self._call_llm(sanitized_text, source_name)

        logger.info(
            "LLM extraction complete for '{}' — {} field(s) found",
            source_name,
            len(fields),
        )

        return DocumentExtractionResult(
            source_path=ocr_result.source_path,
            content_hash=ocr_result.content_hash,
            fields=fields,
            page_count=page_count,
        )

    def _call_llm(self, text: str, source_document: str) -> list[ExtractedField]:
        """Send *text* to Claude and parse the structured tool response."""
        tool_def = self._schema.tool_definition()
        tool_name = tool_def["name"]

        response = self._client.messages.create(
            model=self._settings.llm_model,
            max_tokens=1024,
            system=self._schema.system_prompt(),
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract the requested fields from the following "
                        "document text.\n\n"
                        "--- DOCUMENT START ---\n"
                        f"{text}\n"
                        "--- DOCUMENT END ---"
                    ),
                }
            ],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return self._schema.parse_tool_result(
                    block.input,
                    source_document=source_document,
                )

        logger.warning(
            "LLM response for '{}' contained no tool_use block", source_document
        )
        return []
