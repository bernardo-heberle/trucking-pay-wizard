# Extraction rule dictionaries.
#
# Each module exposes:
#   COLUMN    — the output column name (str)
#   PATTERNS  — ordered list of pattern dicts, each with:
#                 "name"      — descriptive identifier for logging/debugging
#                 "regex"     — pattern with exactly one capture group
#                 "formats"   — document formats this pattern applies to (informational)
#                 "certainty" — "high" or "review"; how reliable the match is
#
# The extraction logic imports these and tries patterns in order, returning the
# first match. Add new field modules here as more document types are handled.

from src.extract.rules import date, pay

ALL_RULES = [
    pay,
    date,
]

EXPECTED_FIELDS: list[str] = [mod.COLUMN for mod in ALL_RULES]
