# Extraction rules for delivery date.
#
# Each entry is tried in order — first match wins.
# The regex must contain exactly one capture group: the raw date string.
# The extraction logic normalises the captured string to a Python date object.
#
# Priority rationale:
#   1. Actual confirmed delivery (TMS records) — most reliable; truck is already delivered.
#   2. Firm/hard deadline dates — contractually binding.
#   3. "Not later than" dates — upper bound commitments.
#   4. Estimated dates — planned but not guaranteed.
#
# Two date formats appear across the sample set:
#   MM/DD/YYYY  — CentralDispatch, BacklotCars, ShipYourCarNow
#   "Month D, YYYY (Weekday)" — V2Dispatch (weekday suffix stripped by extraction logic)
#   "Month D, YYYY, H:MM AM/PM" — Carrier TMS (time suffix stripped)

COLUMN = "delivery_date"

PATTERNS = [
    {
        # "Delivered on Mar 13, 2024, 3:17 PM"
        # Actual confirmed delivery timestamp from Carrier TMS.
        # Highest priority — this is ground truth, not an estimate.
        "name": "tms_delivered_on",
        "regex": r"Delivered on ([\w]+ \d{1,2}, \d{4})",
        "formats": ["CarrierTMS"],
    },
    {
        # "Delivery Date\nMarch 20, 2024 (Wed)"
        # V2Dispatch confirmed delivery date field.
        "name": "v2dispatch_delivery_date",
        "regex": r"Delivery Date\s*\n([\w]+ \d{1,2},? \d{4})",
        "formats": ["V2Dispatch"],
    },
    {
        # "Delivery Exactly: 03/12/2024"
        # CentralDispatch hard delivery date — contractually binding.
        "name": "centraldispatch_delivery_exactly",
        "regex": r"Delivery Exactly:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["CentralDispatch"],
    },
    {
        # "Carrier Delivery Not Later Than:\n03/15/2024"
        # ShipYourCarNow hard deadline. Date may be on the next line.
        "name": "shipyourcarnow_not_later_than",
        "regex": r"Carrier Delivery Not Later Than:\s*\n?(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["ShipYourCarNow"],
    },
    {
        # "Carrier Delivery Estimated:\n03/16/2024"
        # BacklotCars/Super Dispatch — date is often on the next line.
        "name": "carrier_delivery_estimated",
        "regex": r"Carrier Delivery Estimated:\s*\n?(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["BacklotCars", "SuperDispatch"],
    },
    {
        # "Delivery Estimated: 03/12/2024"
        # CentralDispatch estimated date (used when no Exactly date is present).
        "name": "centraldispatch_delivery_estimated",
        "regex": r"Delivery Estimated:\s*(\d{1,2}/\d{1,2}/\d{4})",
        "formats": ["CentralDispatch"],
    },
]

# ── Known gaps ────────────────────────────────────────────────────────────────
# TQL Rate Confirmation (e.g. 27426207): delivery date appears in a load table
# without a dedicated label — it is the second bare date in the load info block.
# No reliable single-line pattern; needs a multi-line block extractor once more
# TQL samples are available.
#
# Relative date expressions ("This should be delivered within 2 days of 03/12/2024")
# appear in some CentralDispatch notes. These are not extracted — the labelled
# Delivery Estimated/Exactly date on the same document takes priority.
