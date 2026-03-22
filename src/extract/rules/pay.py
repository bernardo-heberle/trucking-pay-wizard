# Extraction rules for pay (total carrier payment per load).
#
# Each entry is tried in order — first match wins.
# The regex must contain exactly one capture group: the raw dollar amount string,
# e.g. "1,500.00" or "820". The extraction logic strips commas and converts to float.
#
# Document formats seen in the sample set:
#   CentralDispatch     — BSAT1066, 44445 BIRM, Call Brandon, RM24105
#   BacklotCars/OPENLANE — 12853712, 557423, A768103, Y605399, Z749620
#   TQL Rate Confirmation — 27426207
#   V2Dispatch          — R667644
#   Carrier TMS (Super Dispatch) — 33702085, 33702194, 33702273, R524566-T254780

COLUMN = "pay"

PATTERNS = [
    {
        # "Total Payment to Carrier: $750.00"
        # Most common label — appears in CentralDispatch and BacklotCars/Super Dispatch.
        "name": "total_payment_to_carrier",
        "regex": r"Total Payment to Carrier:\s*\$([\d,]+(?:\.\d{2})?)",
        "formats": ["CentralDispatch", "BacklotCars", "SuperDispatch"],
        "certainty": "high",
    },
    {
        # "Shipper owes Carrier: $944.00"
        # Alternative label used in BacklotCars/Super Dispatch docs alongside or
        # instead of "Total Payment to Carrier".
        "name": "shipper_owes_carrier",
        "regex": r"Shipper owes Carrier:\s*\$([\d,]+(?:\.\d{2})?)",
        "formats": ["BacklotCars", "SuperDispatch"],
        "certainty": "high",
    },
    {
        # "Company* owes Carrier: $750.00"
        # CentralDispatch summary line. Asterisk is literal in the source text.
        "name": "company_owes_carrier",
        "regex": r"Company\*?\s*owes Carrier:\s*\$([\d,]+(?:\.\d{2})?)",
        "formats": ["CentralDispatch"],
        "certainty": "high",
    },
    {
        # "Total: $1,500.00 USD"
        # TQL Rate Confirmation summary line.
        "name": "tql_total",
        "regex": r"Total:\s*\$([\d,]+(?:\.\d{2})?)\s*USD",
        "formats": ["TQL"],
        "certainty": "high",
    },
    {
        # "Agent Pays Carrier\n$820"
        # V2Dispatch payment section. Amount is on the line immediately after the label.
        "name": "v2dispatch_agent_pays_carrier",
        "regex": r"Agent Pays Carrier\s*\n\s*\$([\d,]+(?:\.\d{2})?)",
        "formats": ["V2Dispatch"],
        "certainty": "high",
    },
    {
        # "Total Payment\n$820"
        # V2Dispatch payment header. Fallback if Agent Pays Carrier is not present.
        "name": "v2dispatch_total_payment",
        "regex": r"Total Payment\s*\n\s*\$([\d,]+(?:\.\d{2})?)",
        "formats": ["V2Dispatch"],
        "certainty": "review",
    },
    {
        # "Invoiced on Mar 14, 2024, 10:15 AM\nPrice\n$800.00"
        # Carrier TMS (Super Dispatch internal records). The payment Price follows
        # the "Invoiced on" line. The "Price" label also appears in the vehicle table
        # header but without a leading "$", so anchoring to the Invoiced line avoids
        # false matches.
        "name": "carrier_tms_invoiced_price",
        "regex": r"Invoiced on .+\nPrice\n\$([\d,]+(?:\.\d{2})?)",
        "formats": ["CarrierTMS"],
        "certainty": "review",
    },
]

# ── Known gaps ────────────────────────────────────────────────────────────────
# No pattern for TQL loads where payment is split across multiple line-haul entries.
# TQL "Total: $X USD" covers single-rate loads; multi-rate loads need a summing step.
