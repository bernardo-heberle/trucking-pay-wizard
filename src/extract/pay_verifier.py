"""Cross-reference an extracted pay value against dollar amounts in OCR text.

This module provides a single public function, ``verify_pay_against_ocr``,
that checks whether a normalized pay value (as returned by the LLM and
processed by ``_normalize_pay_value``) can be found as a dollar amount
anywhere in the document's OCR text.

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


def verify_pay_against_ocr(
    normalized_pay: str,
    ocr_text: str,
) -> tuple[bool, str]:
    """Check whether *normalized_pay* matches any dollar amount in *ocr_text*.

    Extracts every number that looks like a dollar amount from *ocr_text*,
    normalizes each to a ``Decimal``, and compares against the already-
    normalized *normalized_pay*.

    Parameters
    ----------
    normalized_pay:
        A canonical pay string produced by ``_normalize_pay_value`` —
        plain digits with exactly two decimal places, e.g. ``'1500.00'``.
    ocr_text:
        The full (sanitized) OCR text for the document.

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
    document, not semantic correctness.  If the document contains
    multiple dollar amounts (e.g. gross pay and a deduction) and the
    LLM returns a value that happens to match any of them, the function
    returns True even if the LLM selected the wrong field.

    A False result means the exact numeric value does not appear anywhere
    in the document — a strong indicator of a transposed digit, dropped
    digit, or decimal-point error.
    """
    try:
        target = Decimal(normalized_pay)
    except InvalidOperation:
        return False, f"Could not parse normalized pay value '{normalized_pay}'"

    for match in _AMOUNT_PATTERN.finditer(ocr_text):
        raw_match = match.group(0).strip()
        digits_only = match.group(1).replace(",", "")
        try:
            candidate = Decimal(digits_only)
        except InvalidOperation:
            continue
        if candidate == target:
            return True, f"Matched '{raw_match}' in document text"

    return False, (
        f"Pay value {normalized_pay} not found in document "
        f"— possible misread, transposed digits, or wrong field"
    )
