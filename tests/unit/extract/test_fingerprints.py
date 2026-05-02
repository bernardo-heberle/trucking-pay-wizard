"""Tests for extraction fingerprinting (cache version invalidation).

Verifies that sanitizer and schema fingerprints are stable across calls
and change when their underlying definitions are modified — ensuring
that cached results from a previous configuration become automatic
cache misses after a sanitizer bug fix or schema change.
"""

from __future__ import annotations

import re
from typing import Any

from src.extract.llm.sanitizer import (
    DEFAULT_PATTERNS,
    RedactionPattern,
    sanitizer_fingerprint,
)
from src.extract.llm.schemas.base import ExtractionSchema
from src.extract.llm.schemas.income import IncomeDocumentSchema
from src.extract.models import ExtractedField


class TestSanitizerFingerprint:

    def test_deterministic_across_calls(self) -> None:
        assert sanitizer_fingerprint() == sanitizer_fingerprint()

    def test_is_12_hex_chars(self) -> None:
        fp = sanitizer_fingerprint()
        assert len(fp) == 12
        int(fp, 16)  # raises if not valid hex

    def test_changes_when_pattern_added(self) -> None:
        original = sanitizer_fingerprint()

        extended = DEFAULT_PATTERNS + [
            RedactionPattern(
                name="phone",
                regex=re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),
                placeholder="[PHONE-REDACTED]",
            )
        ]
        modified = sanitizer_fingerprint(extended)

        assert original != modified

    def test_changes_when_pattern_removed(self) -> None:
        original = sanitizer_fingerprint()
        fewer = DEFAULT_PATTERNS[:1]
        modified = sanitizer_fingerprint(fewer)

        assert original != modified

    def test_changes_when_regex_modified(self) -> None:
        original = sanitizer_fingerprint()

        tweaked = [
            RedactionPattern(
                name=p.name,
                regex=re.compile(p.regex.pattern + "X") if p.name == "ein" else p.regex,
                placeholder=p.placeholder,
            )
            for p in DEFAULT_PATTERNS
        ]
        modified = sanitizer_fingerprint(tweaked)

        assert original != modified

    def test_changes_when_placeholder_modified(self) -> None:
        original = sanitizer_fingerprint()

        tweaked = [
            RedactionPattern(
                name=p.name,
                regex=p.regex,
                placeholder="[CHANGED]" if p.name == "ssn_dashed" else p.placeholder,
            )
            for p in DEFAULT_PATTERNS
        ]
        modified = sanitizer_fingerprint(tweaked)

        assert original != modified


class _TweakedSchema(ExtractionSchema):
    """Schema with a modified prompt, used to test fingerprint sensitivity."""

    @property
    def name(self) -> str:
        return "tweaked"

    def tool_definition(self) -> dict[str, Any]:
        base = IncomeDocumentSchema().tool_definition()
        return base

    def system_prompt(self) -> str:
        return IncomeDocumentSchema().system_prompt() + "\nExtra instruction."

    def parse_tool_result(
        self, tool_input: dict[str, Any], source_document: str,
    ) -> list[ExtractedField]:
        return []


class TestSchemaFingerprint:

    def test_deterministic_across_calls(self) -> None:
        schema = IncomeDocumentSchema()
        assert schema.fingerprint() == schema.fingerprint()

    def test_is_12_hex_chars(self) -> None:
        fp = IncomeDocumentSchema().fingerprint()
        assert len(fp) == 12
        int(fp, 16)

    def test_changes_when_prompt_modified(self) -> None:
        original = IncomeDocumentSchema().fingerprint()
        tweaked = _TweakedSchema().fingerprint()

        assert original != tweaked

    def test_separate_instances_same_fingerprint(self) -> None:
        a = IncomeDocumentSchema().fingerprint()
        b = IncomeDocumentSchema().fingerprint()
        assert a == b


class TestCombinedVersion:
    """The pipeline combines sanitizer + schema fingerprints.
    Verify that a change to either component changes the combined value."""

    @staticmethod
    def _combined(
        patterns: list[RedactionPattern] | None = None,
        schema: ExtractionSchema | None = None,
    ) -> str:
        if schema is None:
            schema = IncomeDocumentSchema()
        return sanitizer_fingerprint(patterns) + schema.fingerprint()

    def test_stable(self) -> None:
        assert self._combined() == self._combined()

    def test_sanitizer_change_changes_combined(self) -> None:
        original = self._combined()
        modified = self._combined(patterns=DEFAULT_PATTERNS[:1])

        assert original != modified

    def test_schema_change_changes_combined(self) -> None:
        original = self._combined()
        modified = self._combined(schema=_TweakedSchema())

        assert original != modified
