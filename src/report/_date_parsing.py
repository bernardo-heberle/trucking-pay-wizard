"""Centralized date parsing for the report stage.

The LLM extractor returns dates exactly as they appear in documents, so the
surface forms vary widely.  This module is the single source of truth for
converting those raw strings to ``datetime.date`` objects.

Both the Excel exporter and the chronological sorter import from here.
"""

from __future__ import annotations

import datetime
import re

_TRAILING_WEEKDAY = re.compile(
    r"\s*\(\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*\)\s*$",
    re.IGNORECASE,
)
_TRAILING_TIME = re.compile(
    r"\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*$",
    re.IGNORECASE,
)
# Strip a leading weekday name (full or abbreviated), optionally followed by a
# comma, e.g. "Sunday, Feb. 16, 2025" -> "Feb. 16, 2025".
_LEADING_WEEKDAY = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*,?\s*",
    re.IGNORECASE,
)
# Remove a period that directly follows a letter, e.g. "Feb." -> "Feb", so the
# abbreviated-month formats match. Numeric dates have no letters before a
# period, so this is a no-op for them.
_ABBREV_PERIOD = re.compile(r"(?<=[A-Za-z])\.")

_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%m-%d-%y",
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
)


def _clean(raw: str) -> str:
    """Strip weekday names, time-of-day clauses, and month-abbreviation periods.

    Removes a leading weekday clause (``"Sunday, "``), trailing weekday and
    time-of-day clauses, and the trailing period on abbreviated month names
    (``"Feb."`` -> ``"Feb"``) so the surface forms reach a known strptime
    format.
    """
    cleaned = raw.strip()
    cleaned = _TRAILING_TIME.sub("", cleaned)
    cleaned = _TRAILING_WEEKDAY.sub("", cleaned)
    cleaned = _LEADING_WEEKDAY.sub("", cleaned)
    cleaned = _ABBREV_PERIOD.sub("", cleaned)
    return cleaned.strip()


def parse_extracted_date(raw: str) -> datetime.date | None:
    """Parse a date string produced by the LLM extractor.

    Before attempting strptime, the raw string is normalized to absorb the
    surface variation seen in real OCR output:
        - leading weekday clauses like ``"Sunday, "``
        - trailing weekday clauses like ``" (Wed)"``
        - trailing time-of-day clauses like ``" at 11:52 AM"`` (e.g. V2 Dispatch)
        - trailing periods on abbreviated month names (``"Feb."`` -> ``"Feb"``)

    Supported input formats:
        - ``MM/DD/YYYY``, ``M/D/YYYY``, ``MM/DD/YY``, ``M/D/YY``
        - ``MM-DD-YYYY``, ``M-D-YYYY``, ``MM-DD-YY``, ``M-D-YY``
        - ``YYYY-MM-DD`` (ISO 8601)
        - ``Month DD, YYYY`` (e.g. ``March 13, 2024``)
        - ``Mon DD, YYYY`` (e.g. ``Mar 13, 2024``)
        - any of the above prefixed with a weekday (e.g. ``Sunday, Feb. 16, 2025``)

    Two-digit years follow Python's ``%y`` default: ``00–68`` map to
    ``2000–2068``, ``69–99`` map to ``1969–1999``.

    Returns ``None`` when no known format matches the cleaned string.
    """
    if not raw or not raw.strip():
        return None
    cleaned = _clean(raw)
    for fmt in _FORMATS:
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None
