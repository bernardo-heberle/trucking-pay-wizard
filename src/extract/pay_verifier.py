"""Cross-reference an extracted pay value against dollar amounts in OCR text.

This module provides a single public function, ``verify_pay_against_ocr``,
that checks whether a normalized pay value (as returned by the LLM and
processed by ``_normalize_pay_value``) can be found as a dollar amount
anywhere in the document's OCR text (or near a specific anchor position for
multi-load documents).

A mismatch does not mean the extraction is wrong — the LLM may have
correctly read a value that appears in a different format than the regex
patterns cover — but it is a strong signal that human review is warranted,
and the caller should downgrade certainty from HIGH to REVIEW.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Matches dollar amounts in several common OCR formats, e.g.:
#   $1,234.56   1,234.56   1234.56   $1234   1,234   10000.00
#
# The first alternative starts with \d+ (not \d{1,3}) so that numbers with
# 4+ digits and no thousand separator (e.g. 1000.00, 10000.00) are captured
# in full rather than stopping at 3 digits and leaving the remainder as a
# separate token.  The comma-grouping sub-pattern (?:,\d{3})* handles
# formatted amounts like $1,500.00 correctly when commas are present.
_AMOUNT_PATTERN = re.compile(
    r"\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)"
)


def _line_window(ocr_text: str, anchor_offset: int) -> str:
    """Return the OCR text within the same line as *anchor_offset*.

    OCR full_text uses ``\n`` within a page and ``\n\n`` between pages.
    This function finds the line boundaries surrounding *anchor_offset* and
    returns just that line, giving the verifier a locality constraint so it
    can confirm a pay value is near its anchor date rather than anywhere in
    the document.

    If the anchor falls at a newline character (edge case), the surrounding
    content is still returned correctly.
    """
    anchor_offset = max(0, min(anchor_offset, len(ocr_text)))
    line_start = ocr_text.rfind("\n", 0, anchor_offset)
    line_start = 0 if line_start == -1 else line_start + 1

    line_end = ocr_text.find("\n", anchor_offset)
    line_end = len(ocr_text) if line_end == -1 else line_end

    return ocr_text[line_start:line_end]


def verify_pay_against_ocr(
    normalized_pay: str,
    ocr_text: str,
    anchor_offset: int | None = None,
) -> tuple[bool, str]:
    """Check whether *normalized_pay* matches any dollar amount in *ocr_text*.

    When *anchor_offset* is provided the search is restricted to the OCR line
    that contains that character offset (typically the line where the load's
    date was found).  This prevents a pay value from being "verified" against
    an amount that belongs to a different load in the same document.  If the
    locality search fails, the function falls back to a global search so the
    caller can decide whether to downgrade certainty.

    Parameters
    ----------
    normalized_pay:
        A canonical pay string produced by ``_normalize_pay_value`` —
        plain digits with exactly two decimal places, e.g. ``'1500.00'``.
    ocr_text:
        The full (sanitized) OCR text for the document.
    anchor_offset:
        Optional character offset of an anchor value (e.g. the load's date)
        in *ocr_text*.  When given the verifier first searches the same line
        as the anchor; global search is used only when anchor_offset is None.

    Returns
    -------
    (True, reason)
        When a matching amount is found.  *reason* quotes the matched
        text from the document.
    (False, reason)
        When no matching amount is found.  *reason* describes the
        mismatch for logging and report notes.

    Notes
    -----
    The verifier can only confirm *presence* of the number in the
    document (or on the anchor's line), not semantic correctness.

    A False result means the exact numeric value does not appear anywhere
    in the search window — a strong indicator of a transposed digit, dropped
    digit, or decimal-point error.
    """
    try:
        target = Decimal(normalized_pay)
    except InvalidOperation:
        return False, f"Could not parse normalized pay value '{normalized_pay}'"

    search_text = _line_window(ocr_text, anchor_offset) if anchor_offset is not None else ocr_text

    for match in _AMOUNT_PATTERN.finditer(search_text):
        raw_match = match.group(0).strip()
        digits_only = match.group(1).replace(",", "")
        try:
            candidate = Decimal(digits_only)
        except InvalidOperation:
            continue
        if candidate == target:
            locality = "on anchor line" if anchor_offset is not None else "in document text"
            return True, f"Matched '{raw_match}' {locality}"

    if anchor_offset is not None:
        # Locality search failed — fall back to global search so the caller
        # can still detect a flat mismatch (wrong digits) vs. a locality miss.
        for match in _AMOUNT_PATTERN.finditer(ocr_text):
            raw_match = match.group(0).strip()
            digits_only = match.group(1).replace(",", "")
            try:
                candidate = Decimal(digits_only)
            except InvalidOperation:
                continue
            if candidate == target:
                return True, f"Matched '{raw_match}' in document text (not on anchor line)"

    return False, (
        f"Pay value {normalized_pay} not found in document "
        f"— possible misread, transposed digits, or wrong field"
    )
