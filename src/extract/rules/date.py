# Extraction rules for date (pickup / earliest date per load).
#
# Each entry is tried in order — first match wins.
# The regex must contain exactly one capture group: the raw date string.
# The extraction logic normalises the captured string to a Python date object.
#
# Priority rationale:
#   1. Actual confirmed pickup (TMS records) — most reliable; truck has been picked up.
#   2. Firm/exact pickup dates — contractually binding.
#   3. Estimated pickup dates — planned but not guaranteed.
#   4. TQL load-table pickup date — positional extraction.
#   5. Dispatch/schedule fallbacks — used only when no pickup date is present.
#
# Date formats across the sample set:
#   MM/DD/YYYY  — CentralDispatch, BacklotCars, ShipYourCarNow, TQL
#   M/D/YYYY    — TQL (no zero-padding)
#   "Month D, YYYY (Weekday)" — V2Dispatch (weekday suffix stripped by extraction logic)
#   "Month D, YYYY, H:MM AM/PM" — Carrier TMS (time suffix stripped)

COLUMN = "date"

PATTERNS = [
    {
        # "Picked Up on Mar 11, 2024, 4:36 PM"
        # Actual confirmed pickup timestamp from Carrier TMS — ground truth.
        "name": "tms_picked_up_on",
        "regex": r"Picked Up on ([\w]+ \d{1,2}, \d{4})",
        "formats": ["CarrierTMS"],
    },
    {
        # "Pickup Date\nMarch 13, 2024 (Wed)"
        # V2Dispatch pickup date field. Date is on the line after the label.
        "name": "v2dispatch_pickup_date",
        "regex": r"Pickup Date\s*\n([\w]+ \d{1,2},? \d{4})",
        "formats": ["V2Dispatch"],
    },
    {
        # "Pickup Exactly: 03/09/2024"
        # CentralDispatch firm pickup date — contractually binding.
        "name": "centraldispatch_pickup_exactly",
        "regex": r"Pickup Exactly:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["CentralDispatch"],
    },
    {
        # "Carrier Pickup Exact: 03/12/2024"
        # ShipYourCarNow firm pickup date.
        "name": "shipyourcarnow_pickup_exact",
        "regex": r"Carrier Pickup Exact:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["ShipYourCarNow"],
    },
    {
        # "Carrier Pickup Estimated:\n03/12/2024"
        # BacklotCars/OPENLANE — date may be on the next line.
        "name": "carrier_pickup_estimated",
        "regex": r"Carrier Pickup Estimated:\s*\n?(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["BacklotCars", "OPENLANE"],
    },
    {
        # "Pickup Estimated: 03/11/2024"
        # CentralDispatch estimated pickup date (when no Exactly date is present).
        "name": "centraldispatch_pickup_estimated",
        "regex": r"Pickup Estimated:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["CentralDispatch"],
    },
    {
        # "Pick-up Location\nDate\nTime\n<city>\n3/13/2024"
        # TQL rate confirmation — pickup date in the load info table.
        "name": "tql_pickup_date",
        "regex": r"Pick-up Location\nDate\nTime\n.+\n(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["TQL"],
    },
    {
        # "Dispatch Date: 03/09/2024"
        # CentralDispatch / ShipYourCarNow fallback when no pickup label exists.
        "name": "dispatch_date",
        "regex": r"Dispatch Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["CentralDispatch", "ShipYourCarNow"],
    },
    {
        # "Scheduled for Mar 11, 2024"
        # Carrier TMS fallback — scheduled date before actual pickup is recorded.
        "name": "tms_scheduled_for",
        "regex": r"Scheduled for ([\w]+ \d{1,2}, \d{4})",
        "formats": ["CarrierTMS"],
    },
]

# ── Known gaps ────────────────────────────────────────────────────────────────
# Relative date expressions ("Pick up within 2 days of 03/12/2024") appear in some
# CentralDispatch notes. These are not extracted — the labelled Pickup date on the
# same document takes priority.
