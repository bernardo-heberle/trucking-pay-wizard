# Extraction rule dictionaries.
#
# Each module exposes:
#   COLUMN    — the output column name (str)
#   PATTERNS  — ordered list of pattern dicts, each with:
#                 "name"    — descriptive identifier for logging/debugging
#                 "regex"   — pattern with exactly one capture group
#                 "formats" — document formats this pattern applies to (informational)
#
# The extraction logic imports these and tries patterns in order, returning the
# first match. Add new field modules here as more document types are handled.

from src.extract.rules import delivery_date, gross_pay

ALL_RULES = [
    gross_pay,
    delivery_date,
]
