"""Unit tests for src.report._date_parsing.parse_extracted_date.

Each test answers: what specific bug would this catch that no other test catches?

- Format-coverage tests: catch a format being silently dropped from the tuple.
- Cleaning tests: catch the weekday/time-stripping regexes regressing.
- Invalid-input tests: catch the helper accidentally returning a value for garbage.
- Two-digit-year test: catch the pivot boundary shifting.
- Leap-day test: catch over-strict date validation.
"""

from __future__ import annotations

import datetime

import pytest

from src.report._date_parsing import parse_extracted_date


class TestSupportedFormats:
    """Each parametrized case covers a distinct surface format from real OCR output."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("03/12/2024", datetime.date(2024, 3, 12)),   # MM/DD/YYYY zero-padded
            ("3/19/2024",  datetime.date(2024, 3, 19)),   # M/D/YYYY single-digit month
            ("1/5/2024",   datetime.date(2024, 1, 5)),    # both components single-digit
        ],
        ids=["mdy_4digit_padded", "mdy_4digit_single_month", "mdy_4digit_both_single"],
    )
    def test_slash_four_digit_year(self, raw: str, expected: datetime.date) -> None:
        assert parse_extracted_date(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("10/29/24", datetime.date(2024, 10, 29)),
            ("01/05/68", datetime.date(2068, 1, 5)),   # boundary: 68 -> 2068
        ],
        ids=["mdy_2digit_year", "mdy_2digit_year_boundary"],
    )
    def test_slash_two_digit_year(self, raw: str, expected: datetime.date) -> None:
        assert parse_extracted_date(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("03-12-2024", datetime.date(2024, 3, 12)),
            ("3-5-2024",   datetime.date(2024, 3, 5)),
        ],
        ids=["mdy_dashed_padded", "mdy_dashed_single"],
    )
    def test_dashed_format(self, raw: str, expected: datetime.date) -> None:
        assert parse_extracted_date(raw) == expected

    def test_iso_format(self) -> None:
        assert parse_extracted_date("2024-03-13") == datetime.date(2024, 3, 13)

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("March 13, 2024", datetime.date(2024, 3, 13)),
            ("January 1, 2024", datetime.date(2024, 1, 1)),
        ],
        ids=["month_full_march", "month_full_january"],
    )
    def test_full_month_name(self, raw: str, expected: datetime.date) -> None:
        assert parse_extracted_date(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Mar 13, 2024", datetime.date(2024, 3, 13)),
            ("Jan 1, 2024",  datetime.date(2024, 1, 1)),
        ],
        ids=["month_abbrev_mar", "month_abbrev_jan"],
    )
    def test_abbreviated_month_name(self, raw: str, expected: datetime.date) -> None:
        assert parse_extracted_date(raw) == expected


class TestCleaning:
    """Cleaning rules strip non-date suffixes before strptime is attempted."""

    def test_strips_trailing_weekday_long(self) -> None:
        """'March 13, 2024 (Wed)' -> date(2024, 3, 13) — seen in V2 Dispatch docs."""
        assert parse_extracted_date("March 13, 2024 (Wed)") == datetime.date(2024, 3, 13)

    def test_strips_trailing_weekday_full(self) -> None:
        """'March 2, 2024 (Saturday)' also matches the weekday-stripping regex."""
        assert parse_extracted_date("March 2, 2024 (Saturday)") == datetime.date(2024, 3, 2)

    def test_strips_trailing_time_am(self) -> None:
        """'March 20, 2024 at 11:52 AM' -> date(2024, 3, 20) — seen in V2 Dispatch docs."""
        assert parse_extracted_date("March 20, 2024 at 11:52 AM") == datetime.date(2024, 3, 20)

    def test_strips_trailing_time_pm(self) -> None:
        assert parse_extracted_date("January 5, 2024 at 2:30 PM") == datetime.date(2024, 1, 5)

    def test_strips_trailing_time_no_ampm(self) -> None:
        assert parse_extracted_date("March 1, 2024 at 9:00") == datetime.date(2024, 3, 1)

    def test_strips_both_clauses_noop(self) -> None:
        """A string with neither clause parses fine — cleaning is a no-op."""
        assert parse_extracted_date("03/12/2024") == datetime.date(2024, 3, 12)

    def test_surrounding_whitespace_stripped(self) -> None:
        assert parse_extracted_date("  03/12/2024  ") == datetime.date(2024, 3, 12)


class TestInvalidInputs:
    """The helper must return None rather than raise or guess for bad inputs."""

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "unknown date",
            "N/A",
            "TBD",
            "13/01/2024",    # month 13 — invalid
            "00/15/2024",    # month 0 — invalid
        ],
        ids=[
            "empty_string",
            "whitespace_only",
            "garbage_text",
            "na",
            "tbd",
            "month_13",
            "month_0",
        ],
    )
    def test_invalid_returns_none(self, raw: str) -> None:
        assert parse_extracted_date(raw) is None

    def test_non_leap_year_feb29_returns_none(self) -> None:
        """Feb 29 in a non-leap year is invalid and must not silently succeed."""
        assert parse_extracted_date("02/29/2023") is None

    def test_iso_date_with_invalid_month_returns_none(self) -> None:
        assert parse_extracted_date("2024-13-01") is None


class TestTwoDigitYearPivot:
    """Two-digit year pivot: 00-68 -> 2000s, 69-99 -> 1900s (Python %y default)."""

    def test_68_maps_to_2068(self) -> None:
        assert parse_extracted_date("01/05/68") == datetime.date(2068, 1, 5)

    def test_69_maps_to_1969(self) -> None:
        assert parse_extracted_date("01/05/69") == datetime.date(1969, 1, 5)

    def test_00_maps_to_2000(self) -> None:
        assert parse_extracted_date("03/12/00") == datetime.date(2000, 3, 12)

    def test_99_maps_to_1999(self) -> None:
        assert parse_extracted_date("03/12/99") == datetime.date(1999, 3, 12)


class TestLeapDay:
    def test_feb29_in_leap_year_parses(self) -> None:
        assert parse_extracted_date("02/29/2024") == datetime.date(2024, 2, 29)
