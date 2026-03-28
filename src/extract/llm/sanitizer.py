from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger

_PLACEHOLDER = "[REDACTED]"


@dataclass
class RedactionPattern:
    """A single PII pattern to scrub from text before it reaches an external API."""

    name: str
    regex: re.Pattern[str]
    placeholder: str = _PLACEHOLDER


@dataclass
class RedactionReport:
    """Summary of what was redacted — counts only, never the actual values."""

    total_redactions: int = 0
    counts_by_pattern: dict[str, int] = field(default_factory=dict)


# ── Built-in patterns ─────────────────────────────────────────────────────────

_SSN_DASHED = RedactionPattern(
    name="ssn_dashed",
    regex=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    placeholder="[SSN-REDACTED]",
)

_SSN_NODASH = RedactionPattern(
    name="ssn_no_dash",
    # Nine consecutive digits that are NOT part of a longer number.
    # Negative lookbehind/lookahead avoids matching phone numbers, zip+4, etc.
    regex=re.compile(r"(?<!\d)\d{9}(?!\d)"),
    placeholder="[SSN-REDACTED]",
)

_EIN = RedactionPattern(
    name="ein",
    regex=re.compile(r"\b\d{2}-\d{7}\b"),
    placeholder="[EIN-REDACTED]",
)

DEFAULT_PATTERNS: list[RedactionPattern] = [_SSN_DASHED, _SSN_NODASH, _EIN]


def sanitize_text(
    text: str,
    patterns: list[RedactionPattern] | None = None,
) -> tuple[str, RedactionReport]:
    """Scrub PII from *text* and return ``(sanitized_text, report)``.

    The report logs how many redactions occurred per pattern (never the
    actual matched values).  Patterns are applied in the order given —
    place more specific patterns first to avoid partial matches.
    """
    if patterns is None:
        patterns = DEFAULT_PATTERNS

    report = RedactionReport()

    for pat in patterns:
        occurrences = len(pat.regex.findall(text))
        if occurrences:
            text = pat.regex.sub(pat.placeholder, text)
            report.total_redactions += occurrences
            report.counts_by_pattern[pat.name] = occurrences

    if report.total_redactions:
        logger.info(
            "PII sanitizer redacted {} item(s): {}",
            report.total_redactions,
            report.counts_by_pattern,
        )
    else:
        logger.debug("PII sanitizer found nothing to redact")

    return text, report
