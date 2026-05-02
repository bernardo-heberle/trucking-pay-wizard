"""One-shot script to generate realistic OCR fixture JSON files.

Run once to produce the fixtures, then delete or keep for reference.
The generated JSON mirrors real Azure Document Intelligence output structure
with all PII replaced by synthetic dummy values.

Usage:
    python scripts/generate_fixtures.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


@dataclass
class LineSpec:
    text: str
    page_number: int
    x: float
    y: float
    width: float
    height: float = 0.25


def build_fixture(
    source_path: str,
    content_hash: str,
    page_specs: list[tuple[int, float, float]],
    line_specs: list[LineSpec],
) -> dict:
    global_offset = 0
    lines_json = []
    prev_page = None

    for ls in line_specs:
        if prev_page is not None and ls.page_number != prev_page:
            global_offset += 2  # \n\n page separator
        elif prev_page is not None:
            global_offset += 1  # \n within page

        char_start = global_offset
        char_end = global_offset + len(ls.text)

        lines_json.append({
            "text": ls.text,
            "page_number": ls.page_number,
            "bounding_box": {
                "x": ls.x, "y": ls.y, "width": ls.width, "height": ls.height,
            },
            "char_start": char_start,
            "char_end": char_end,
        })

        global_offset = char_end
        prev_page = ls.page_number

    page_line_counts = {}
    for ls in line_specs:
        page_line_counts[ls.page_number] = page_line_counts.get(ls.page_number, 0) + 1

    pages_json = []
    for pn, w, h in page_specs:
        pages_json.append({
            "page_number": pn,
            "width_inches": w,
            "height_inches": h,
            "line_count": page_line_counts.get(pn, 0),
        })

    return {
        "source_path": source_path,
        "content_hash": content_hash,
        "pages": pages_json,
        "lines": lines_json,
    }


# ---------------------------------------------------------------------------
# Fixture 1: CentralDispatch settlement sheet (single page, ~35 lines)
# Based on real BSAT-style dispatch sheets
# ---------------------------------------------------------------------------

def central_dispatch_settlement() -> dict:
    L = LineSpec
    lines = [
        L("Carrier Information", 1, 1.0, 0.5, 3.0, 0.3),
        L("Carrier: Acme Trucking LLC", 1, 1.0, 0.9, 3.5),
        L("1234 Main Street Ste 100", 1, 1.0, 1.2, 3.0),
        L("Springfield, IL 62701", 1, 1.0, 1.5, 2.5),
        L("MC Number: 1234567", 1, 1.0, 1.8, 2.5),
        L("Driver: John Doe, dispatcher", 1, 1.0, 2.1, 3.5),
        L("Driver Phone: (555) 123-4567", 1, 1.0, 2.4, 3.5),
        L("Order ID: XYZ7890", 1, 1.0, 2.7, 2.5),
        L("Contact: Mike, Sarah, Tom", 1, 1.0, 3.0, 3.0),
        L("Phone: (555) 123-4567", 1, 1.0, 3.3, 2.5),
        L("Phone 2: (555) 234-5678 (555) 345-6789 Tom", 1, 1.0, 3.6, 5.0),
        L("Fax: (555) 456-7890", 1, 1.0, 3.9, 2.5),
        L("Dispatch Sheet", 1, 3.0, 0.5, 2.5, 0.3),
        L("CentralDispatch", 1, 5.5, 0.5, 2.5),
        L("by Cox Automotive", 1, 5.5, 0.8, 2.5),
        L("National Auto Brokers", 1, 5.5, 1.2, 3.0),
        L("500 Commerce Drive Ste 200", 1, 5.5, 1.5, 3.5),
        L("Kansas City, MO 64105", 1, 5.5, 1.8, 2.5),
        L("Co. Phone: (816) 555-0100 Main", 1, 5.5, 2.1, 3.5),
        L("Dispatch Info", 1, 5.5, 2.4, 2.0),
        L("Contact: Robert Brown", 1, 5.5, 2.7, 3.0),
        L("Phone: (816) 555-0101", 1, 5.5, 3.0, 2.5),
        L("Fax: (816) 555-0102", 1, 5.5, 3.3, 2.5),
        L("MC #: 567890", 1, 5.5, 3.6, 2.0),
        L("Vehicle Information", 1, 1.0, 4.2, 3.0, 0.3),
        L("Total Vehicles: 1", 1, 1.0, 4.5, 2.0),
        L("1 2019 Toyota Camry Type: Car Color: Silver Plate: VIN: 4T1B11HK5KU123456 Lot #: Additional Info:", 1, 1.0, 4.8, 7.0),
        L("Pickup Information", 1, 1.0, 5.2, 3.0, 0.3),
        L("Name: Jane Smith", 1, 1.0, 5.5, 2.5),
        L("456 Oak Avenue", 1, 1.0, 5.8, 2.0),
        L("Los Angeles, CA 90001", 1, 1.0, 6.1, 2.5),
        L("Phone: (555) 234-5678", 1, 1.0, 6.4, 2.5),
        L("Delivery Information", 1, 5.5, 5.2, 3.0, 0.3),
        L("Name: Jane Smith", 1, 5.5, 5.5, 2.5),
        L("789 Pine Road Apt 3B", 1, 5.5, 5.8, 2.5),
        L("Denver, CO 80201", 1, 5.5, 6.1, 2.0),
        L("Phone: (555) 234-5678", 1, 5.5, 6.4, 2.5),
        L("This must be picked up exactly on 04/15/2024. This should be delivered within 2 days of 04/18/2024.", 1, 1.0, 7.0, 7.0),
        L("CONTRACT TERMS", 1, 1.0, 7.4, 2.5, 0.3),
        L("*** PLEASE READ CAREFULLY ***", 1, 1.0, 7.7, 3.5),
        L("Do not discuss rates with customer!", 1, 1.0, 8.0, 4.0),
        L("CD reference # 50123456", 1, 1.0, 8.5, 3.0),
        L("Order Information", 1, 1.0, 8.9, 3.0, 0.3),
        L("Dispatch Date: 04/08/2024", 1, 1.0, 9.2, 3.0),
        L("Pickup Exactly: 04/15/2024", 1, 1.0, 9.5, 3.0),
        L("Delivery Estimated: 04/18/2024", 1, 1.0, 9.8, 3.5),
        L("Ship Via: Open", 1, 5.5, 9.2, 2.0),
        L("Condition: Operable", 1, 5.5, 9.5, 2.0),
        L("Price Listed: N/A", 1, 5.5, 9.8, 2.0),
        L("Total Payment to Carrier: $850.00", 1, 1.0, 10.2, 4.0),
        L("On Delivery to Carrier: None", 1, 1.0, 10.5, 3.5),
        L("Company* owes Carrier: $850.00", 1, 1.0, 10.8, 3.5),
    ]
    return build_fixture(
        source_path="central_dispatch_settlement.pdf",
        content_hash="b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
        page_specs=[(1, 8.5, 11.0)],
        line_specs=lines,
    )


# ---------------------------------------------------------------------------
# Fixture 2: V2 Dispatch load summary (2 pages)
# Based on real V2 Dispatch web-printed format
# ---------------------------------------------------------------------------

def v2_dispatch_summary() -> dict:
    L = LineSpec
    lines = [
        # Page 1
        L("11/15/24, 10:30 AM", 1, 1.0, 0.3, 2.5),
        L("V2 Dispatch | Auto Transport Dispatch Simplified", 1, 1.5, 0.6, 5.5, 0.3),
        L("Dispatch Details | Load #V892345", 1, 1.0, 1.0, 4.5, 0.3),
        L("Order ID", 1, 1.0, 1.5, 1.5),
        L("V892345", 1, 1.0, 1.8, 1.5),
        L("Current Status", 1, 3.0, 1.5, 2.0),
        L("Delivered", 1, 3.0, 1.8, 1.5),
        L("Last Update", 1, 5.0, 1.5, 2.0),
        L("May 14, 2024 at 3:45 PM", 1, 5.0, 1.8, 3.0),
        L("V2D Reference #", 1, 1.0, 2.3, 2.5),
        L("776541", 1, 1.0, 2.6, 1.5),
        L("Dispatch Date", 1, 1.0, 3.0, 2.0),
        L("May 1, 2024 (Wed)", 1, 1.0, 3.3, 2.5),
        L("Pickup Date", 1, 3.0, 3.0, 2.0),
        L("May 8, 2024 (Wed)", 1, 3.0, 3.3, 2.5),
        L("Delivery Date", 1, 5.0, 3.0, 2.0),
        L("May 14, 2024 (Tue)", 1, 5.0, 3.3, 2.5),
        L("Carrier Type", 1, 1.0, 3.8, 2.0),
        L("Open", 1, 1.0, 4.1, 1.0),
        L("Carrier Information", 1, 1.0, 4.6, 3.0, 0.3),
        L("Acme Trucking", 1, 1.0, 4.9, 2.5),
        L("1234 Main Street Ste 100", 1, 1.0, 5.2, 3.0),
        L("Springfield, IL 62701", 1, 1.0, 5.5, 2.5),
        L("Driver Name : John Doe", 1, 1.0, 5.8, 3.0),
        L("Driver Phone : (555) 123-4567", 1, 1.0, 6.1, 3.5),
        L("Office Phone : (555) 123-4567", 1, 1.0, 6.4, 3.5),
        L("Agent Information", 1, 5.0, 4.6, 3.0, 0.3),
        L("National Auto Shipping Inc", 1, 5.0, 4.9, 3.5),
        L("800 Transport Way Ste 300", 1, 5.0, 5.2, 3.5),
        L("Bethpage, NY 11714", 1, 5.0, 5.5, 2.5),
        L("Contact : Chris, Shawn, Carlos", 1, 5.0, 5.8, 3.5),
        L("Phone : (516) 555-0200", 1, 5.0, 6.1, 3.0),
        L("MC Number : 234567", 1, 5.0, 6.4, 2.5),
        L("Pickup Location", 1, 1.0, 7.0, 2.5, 0.3),
        L("Robert Brown", 1, 1.0, 7.3, 2.0),
        L("321 Elm Street", 1, 1.0, 7.6, 2.0),
        L("Atlanta, GA 30301", 1, 1.0, 7.9, 2.0),
        L("Phone : (404) 555-0300", 1, 1.0, 8.2, 3.0),
        L("Delivery Location", 1, 5.0, 7.0, 2.5, 0.3),
        L("Mike's Auto Port", 1, 5.0, 7.3, 2.5),
        L("555 Harbor Blvd", 1, 5.0, 7.6, 2.0),
        L("Long Beach, CA 90802", 1, 5.0, 7.9, 2.5),
        L("Phone : (562) 555-0400", 1, 5.0, 8.2, 3.0),
        L("Vehicle Information - 1 Vehicle", 1, 1.0, 8.7, 4.0, 0.3),
        L("Year", 1, 1.0, 9.0, 0.8),
        L("Make", 1, 1.8, 9.0, 0.8),
        L("Model", 1, 2.6, 9.0, 1.0),
        L("Type", 1, 3.6, 9.0, 0.8),
        L("Condition", 1, 4.4, 9.0, 1.2),
        L("Color", 1, 5.6, 9.0, 0.8),
        L("Plate", 1, 6.4, 9.0, 0.8),
        L("Vin", 1, 7.2, 9.0, 0.8),
        L("2021", 1, 1.0, 9.3, 0.8),
        L("Honda", 1, 1.8, 9.3, 0.8),
        L("Civic", 1, 2.6, 9.3, 1.0),
        L("Car", 1, 3.6, 9.3, 0.8),
        L("Running", 1, 4.4, 9.3, 1.2),
        L("Blue", 1, 5.6, 9.3, 0.8),
        L("2HGFC2F51MH512345", 1, 7.2, 9.3, 2.5),
        L("Additional Comments", 1, 1.0, 9.8, 3.0),
        L("Delivery Window: 5/12/2024 - 5/18/2024 *** PLEASE DO NOT ACCEPT WITH OVER 1/4 TANK OF GAS ***", 1, 1.0, 10.1, 7.5),
        L("https://www.v2dispatch.com/print.php", 1, 1.0, 10.5, 4.0),
        L("1/2", 1, 4.0, 10.5, 0.5),
        # Page 2
        L("11/15/24, 10:30 AM", 2, 1.0, 0.3, 2.5),
        L("V2 Dispatch | Auto Transport Dispatch Simplified", 2, 1.5, 0.6, 5.5, 0.3),
        L("Load Payment", 2, 1.0, 1.2, 2.5, 0.3),
        L("Total Payment", 2, 1.0, 1.6, 2.0),
        L("$1,050", 2, 1.0, 1.9, 1.5),
        L("Collect On Delivery", 2, 3.0, 1.6, 2.5),
        L("$0", 2, 3.0, 1.9, 0.5),
        L("Agent Pays Carrier", 2, 5.0, 1.6, 2.5),
        L("$1,050", 2, 5.0, 1.9, 1.5),
        L("Payment will be processed upon confirmation of delivery.", 2, 1.0, 2.4, 6.0),
        L("Contract Terms", 2, 1.0, 3.0, 2.5, 0.3),
        L("- As a courtesy, please give clients a call at least 1-2 hours prior to picking up or delivering a vehicle.", 2, 1.0, 3.4, 7.5),
        L("- All drivers should fill out a BOL upon pickup and delivery.", 2, 1.0, 3.7, 6.0),
        L("- Any vehicle that is listed as INOP must be loaded & unloaded with a winch.", 2, 1.0, 4.0, 6.5),
        L("- Dry run fees will not be paid out unless agreed upon before assignment of the load.", 2, 1.0, 4.3, 7.0),
        L("Authority to transport this vehicle is hereby assigned to Acme Trucking. By accepting this agreement Acme Trucking certifies that is has the proper legal authority and insurance", 2, 1.0, 5.0, 7.5),
        L("to carry the above described vehicle, only on trucks owned by Acme Trucking.", 2, 1.0, 5.3, 6.5),
        L("@ 2021 V2 Dispatch Inc.", 2, 1.0, 6.0, 3.0),
        L("https://www.v2dispatch.com/print.php", 2, 1.0, 6.3, 4.0),
        L("2/2", 2, 4.0, 6.3, 0.5),
    ]
    return build_fixture(
        source_path="v2_dispatch_summary.pdf",
        content_hash="c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
        page_specs=[(1, 8.5, 11.0), (2, 8.5, 11.0)],
        line_specs=lines,
    )


# ---------------------------------------------------------------------------
# Fixture 3: Super Dispatch / BacklotCars dispatch sheet (2 pages)
# Based on real OPENLANE / BacklotCars formatted dispatch sheets
# ---------------------------------------------------------------------------

def super_dispatch_sheet() -> dict:
    L = LineSpec
    lines = [
        # Page 1
        L("Order ID: B456789", 1, 1.0, 0.5, 2.5),
        L("Dispatch Sheet", 1, 3.5, 0.5, 2.5, 0.3),
        L("OPENLANE dba", 1, 1.0, 1.0, 2.0),
        L("BacklotCars Inc", 1, 1.0, 1.3, 2.5),
        L("Shipper", 1, 1.0, 1.6, 1.5),
        L("1100 Main St #1500", 1, 1.0, 1.9, 2.5),
        L("Kansas City, MO 64105", 1, 1.0, 2.2, 2.5),
        L("Co. Phone: 816-555-0100", 1, 1.0, 2.5, 3.0),
        L("Email: transport@example.com", 1, 1.0, 2.8, 3.5),
        L("Carrier Information", 1, 5.0, 1.0, 3.0, 0.3),
        L("Carrier: ACME TRUCKING LLC", 1, 5.0, 1.3, 3.5),
        L("1234 Main Street Ste 100", 1, 5.0, 1.6, 3.0),
        L("SPRINGFIELD, Illinois 62701", 1, 5.0, 1.9, 3.5),
        L("Order Information", 1, 1.0, 3.3, 3.0, 0.3),
        L("Dispatch Date: 06/15/2024", 1, 1.0, 3.6, 3.0),
        L("Carrier Pickup Estimated:", 1, 1.0, 3.9, 3.0),
        L("06/20/2024", 1, 1.0, 4.2, 1.5),
        L("Carrier Delivery Estimated:", 1, 1.0, 4.5, 3.0),
        L("06/23/2024", 1, 1.0, 4.8, 1.5),
        L("Ship Via: OPEN", 1, 1.0, 5.1, 2.0),
        L("Condition: Operable", 1, 1.0, 5.4, 2.0),
        L("OPENLANE", 1, 5.0, 3.3, 2.0),
        L("Contact: Mike", 1, 5.0, 3.6, 2.0),
        L("Phone: 5551234567", 1, 5.0, 3.9, 2.0),
        L("Email: dispatch@acmetrucking.com", 1, 5.0, 4.2, 3.5),
        L("Total Payment to Carrier: $1,375.00", 1, 1.0, 5.9, 4.0),
        L("Payment method:", 1, 1.0, 6.2, 2.5),
        L("Payment terms: ACH", 1, 1.0, 6.5, 2.5),
        L("Shipper owes Carrier: $1,375.00", 1, 1.0, 6.8, 3.5),
        L("Vehicle Information", 1, 1.0, 7.3, 3.0, 0.3),
        L("Total Vehicles: 1", 1, 1.0, 7.6, 2.0),
        L("#", 1, 1.0, 7.9, 0.3),
        L("Vehicle", 1, 1.3, 7.9, 1.5),
        L("Type", 1, 3.0, 7.9, 0.8),
        L("Color", 1, 4.0, 7.9, 0.8),
        L("VIN", 1, 5.0, 7.9, 0.8),
        L("Lot #", 1, 6.5, 7.9, 0.8),
        L("1 2022 Ford F-150", 1, 1.0, 8.2, 2.5),
        L("Pickup", 1, 3.0, 8.2, 1.0),
        L("White", 1, 4.0, 8.2, 0.8),
        L("1FTEW1EP2NFA54321", 1, 5.0, 8.2, 2.5),
        L("Pickup Information", 1, 1.0, 8.7, 3.0, 0.3),
        L("Name: Tom Wilson", 1, 1.0, 9.0, 2.5),
        L("Summit Auto Group", 1, 1.0, 9.3, 2.5),
        L("500 Commerce Drive", 1, 1.0, 9.6, 2.5),
        L("Columbus, OH 43215", 1, 1.0, 9.9, 2.5),
        L("Phone: 6145550200", 1, 1.0, 10.2, 2.5),
        L("Mobile:", 1, 1.0, 10.5, 1.0),
        L("Delivery Information", 1, 5.0, 8.7, 3.0, 0.3),
        L("Name: Sarah Johnson", 1, 5.0, 9.0, 2.5),
        L("Lakeside Motors", 1, 5.0, 9.3, 2.5),
        L("800 Waterfront Way", 1, 5.0, 9.6, 2.5),
        L("Milwaukee, WI 53202", 1, 5.0, 9.9, 2.5),
        L("Phone: 4145550300", 1, 5.0, 10.2, 2.5),
        L("Mobile:", 1, 5.0, 10.5, 1.0),
        # Page 2
        L("DISPATCH INSTRUCTIONS", 2, 1.0, 0.5, 3.5, 0.3),
        L("Dry run fees (DRF) will only be paid if the vehicle availability has been confirmed by the carrier along with the", 2, 1.0, 0.9, 7.5),
        L("customer's name who provided confirmation.", 2, 1.0, 1.2, 5.0),
        L("UNATTENDED DROPS It is MANDATORY that we receive pictures for ALL unattended deliveries including pictures of", 2, 1.0, 1.6, 7.5),
        L("the vehicle location, pictures of all 4 angles of car (front, back, and both sides) and pictures of key location.", 2, 1.0, 1.9, 7.5),
        L("CONTRACT TERMS *** PLEASE READ CAREFULLY ***", 2, 1.0, 2.4, 5.5, 0.3),
        L("Please provide at least 24-hour notice to the customer before Pickup and Delivery. Please complete a careful", 2, 1.0, 2.8, 7.5),
        L("inspection of the vehicle on Pickup.", 2, 1.0, 3.1, 4.0),
        L("Carrier Terms & Agreement", 2, 1.0, 3.6, 3.5, 0.3),
        L("Every shipment tendered to a Carrier by BacklotCars will be subject to the terms of the BacklotCars Broker-Carrier Agreement;", 2, 1.0, 4.0, 7.5),
        L("BacklotCars' Terms and Conditions, to the extent applicable which are posted online at (www.backlotcars.com); and applicable", 2, 1.0, 4.3, 7.5),
        L("law.", 2, 1.0, 4.6, 0.5),
        L("1. Carrier should contact customers at least two (2) hours prior to pick up or delivery of a vehicle.", 2, 1.0, 5.0, 7.5),
        L("2. Carrier shall not disclose or discuss the terms of the BacklotCars Broker-Carrier Agreement including the rates.", 2, 1.0, 5.3, 7.5),
        L("3. Carrier will be responsible for loading and unloading all shipments.", 2, 1.0, 5.6, 6.5),
        L("Powered by Super Dispatch", 2, 1.0, 6.5, 3.0),
    ]
    return build_fixture(
        source_path="super_dispatch_sheet.pdf",
        content_hash="d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
        page_specs=[(1, 8.5, 11.0), (2, 8.5, 11.0)],
        line_specs=lines,
    )


# ---------------------------------------------------------------------------
# Fixture 4: Carrier TMS load page (single page, short)
# Based on real Super Dispatch Carrier TMS export
# ---------------------------------------------------------------------------

def carrier_tms_load() -> dict:
    L = LineSpec
    lines = [
        L("11/01/24, 9:45 AM", 1, 1.0, 0.3, 2.5),
        L("45678901 - Loads - Carrier TMS", 1, 1.0, 0.6, 4.0, 0.3),
        L("45678901", 1, 1.0, 1.0, 1.5),
        L("Internal Load ID:", 1, 1.0, 1.3, 2.5),
        L("Advanced Delivered", 1, 3.5, 1.0, 2.5),
        L("Assigned to John Doe", 1, 3.5, 1.3, 3.0),
        L("Deactivated", 1, 6.0, 1.0, 1.5),
        L("T", 1, 1.0, 1.8, 0.3),
        L("Michael Chen", 1, 1.0, 2.1, 2.0),
        L("9", 1, 1.0, 2.4, 0.3),
        L("2500 Industry Blvd, Austin, TX 78701", 1, 1.0, 2.7, 4.5),
        L("Scheduled for Mar 25, 2024", 1, 1.0, 3.0, 3.5),
        L("Picked Up on Mar 25, 2024, 2:15 PM", 1, 1.0, 3.3, 4.5),
        L("& Michael Chen", 1, 1.0, 3.6, 2.5),
        L("5125550100", 1, 1.0, 3.9, 2.0),
        L("E No pickup notes", 1, 1.0, 4.2, 2.5),
        L("1 Vehicle", 1, 1.0, 4.7, 1.5, 0.3),
        L("Vehicle", 1, 1.0, 5.0, 1.5),
        L("2023 Hyundai Tucson SUV", 1, 1.0, 5.3, 3.5),
        L("KM8JBCA19PU123456", 1, 1.0, 5.6, 2.5),
        L("Payment", 1, 5.0, 4.7, 1.5, 0.3),
        L("No Payment received.", 1, 5.0, 5.0, 2.5),
        L("Invoiced on Mar 28, 2024, 11:30 AM", 1, 5.0, 5.3, 4.0),
        L("Price", 1, 5.0, 5.6, 1.0),
        L("$650.00", 1, 5.5, 5.6, 1.0),
        L("Method", 1, 5.0, 5.9, 1.5),
        L("QuickPay", 1, 5.5, 5.9, 1.5),
        L("Broker Fee", 1, 5.0, 6.2, 1.5),
        L("No details", 1, 5.5, 6.2, 1.5),
        L("Driver Pay", 1, 5.0, 6.5, 1.5),
        L("No details", 1, 5.5, 6.5, 1.5),
        L("Lisa Park", 1, 1.0, 7.0, 2.0),
        L("9", 1, 1.0, 7.3, 0.3),
        L("1800 Commerce St, Portland, OR 97201", 1, 1.0, 7.6, 4.5),
        L("Scheduled for Mar 28, 2024", 1, 1.0, 7.9, 3.5),
        L("Delivered on Mar 28, 2024, 4:50 PM", 1, 1.0, 8.2, 4.5),
        L("& Lisa Park", 1, 1.0, 8.5, 2.0),
        L("5035550200", 1, 1.0, 8.8, 2.0),
        L("E No delivery notes", 1, 1.0, 9.1, 2.5),
        L("Customer Information", 1, 1.0, 9.6, 3.0, 0.3),
        L("Pacific Auto Logistics", 1, 1.0, 9.9, 3.0),
        L("400 Gateway Blvd, San Francisco, CA 94080", 1, 1.0, 10.2, 5.0),
        L("No contact name", 1, 1.0, 10.5, 2.5),
        L("(877) 555-0500", 1, 1.0, 10.8, 2.5),
        L("dispatch@pacificautologistics.com", 1, 1.0, 11.1, 4.0),
        L("https://carrier.superdispatch.com/tms/loads/fake-uuid-1234/print", 1, 1.0, 11.5, 6.0),
        L("1/1", 1, 4.0, 11.5, 0.5),
    ]
    return build_fixture(
        source_path="carrier_tms_load.pdf",
        content_hash="e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6",
        page_specs=[(1, 8.5, 11.0)],
        line_specs=lines,
    )


# ---------------------------------------------------------------------------
# Generate all fixtures
# ---------------------------------------------------------------------------

def main() -> None:
    fixtures = {
        "central_dispatch_settlement_ocr.json": central_dispatch_settlement(),
        "v2_dispatch_summary_ocr.json": v2_dispatch_summary(),
        "super_dispatch_sheet_ocr.json": super_dispatch_sheet(),
        "carrier_tms_load_ocr.json": carrier_tms_load(),
    }

    for name, data in fixtures.items():
        path = FIXTURES_DIR / name
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        line_count = len(data["lines"])
        page_count = len(data["pages"])
        print(f"  {name}: {line_count} lines across {page_count} page(s)")

    print(f"\nAll fixtures written to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
