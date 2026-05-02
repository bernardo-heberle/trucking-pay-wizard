"""Synthetic PDF builders for integration and live API tests.

Each function takes a ``tmp_path: Path`` directory and returns a ``Path``
to a saved PDF file that mimics the layout of a real trucking dispatch
document — multi-page, dense boilerplate, and realistically placed fields.

All carrier/driver names, phone numbers, VINs, and addresses are synthetic.
No real PII from the production dataset appears here.

Usage
-----
Call the builder directly in a test:

    def test_something(tmp_path):
        pdf = build_central_dispatch_pdf(tmp_path)
        ingested = ingest_document(pdf)
        ...

Or wire them up as pytest fixtures in conftest.py:

    @pytest.fixture()
    def central_dispatch_pdf(tmp_path):
        return build_central_dispatch_pdf(tmp_path)

Expected extraction values for each builder
-------------------------------------------
    build_central_dispatch_pdf  pay=1850.00  date=04/15/2024
    build_v2_dispatch_pdf       pay=920.00   date contains "April 8, 2024"
    build_super_dispatch_pdf    pay=1350.00  date=04/22/2024
    build_cod_settlement_pdf    pay=1400.00  date=03/12/2024  (tricky: COD=$1,750 also present)
    build_multi_vehicle_pdf     pay=4500.00  date=05/06/2024  (tricky: 3 vehicles, high amount)
    build_revision_history_pdf  pay=750.00   date=03/12/2024  (tricky: revision shows old price=0.00)
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FONT = "helv"
_BODY_SIZE = 9
_LABEL_SIZE = 8
_HEADER_SIZE = 12
_SECTION_SIZE = 10
_LEFT = 50
_RIGHT_COL = 320
_PAGE_W = 612
_PAGE_H = 792


def _new_doc() -> fitz.Document:
    return fitz.open()


def _add_page(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=_PAGE_W, height=_PAGE_H)


def _line(page: fitz.Page, x: float, y: float, text: str, size: float = _BODY_SIZE) -> None:
    page.insert_text((x, y), text, fontname=_FONT, fontsize=size)


def _block(page: fitz.Page, x: float, y: float, lines: list[str], size: float = _BODY_SIZE, leading: float = 13.0) -> float:
    """Render a block of lines, returning the y position after the last line."""
    for text in lines:
        page.insert_text((x, y), text, fontname=_FONT, fontsize=size)
        y += leading
    return y


def _two_col(page: fitz.Page, y: float, pairs: list[tuple[str, str]], size: float = _BODY_SIZE, leading: float = 13.0) -> float:
    """Render label/value pairs in two columns (label left, value right)."""
    for label, value in pairs:
        page.insert_text((_LEFT, y), label, fontname=_FONT, fontsize=size)
        page.insert_text((_RIGHT_COL, y), value, fontname=_FONT, fontsize=size)
        y += leading
    return y


_CENTRAL_DISPATCH_TERMS = [
    "CONTRACT TERMS",
    "*** PLEASE READ CAREFULLY ***",
    "Do not discuss rates with customer!",
    "PLEASE GIVE THE CUSTOMER AT LEAST A 24 HOUR NOTICE FOR PICKUP AND DELIVERY.",
    "PLEASE DO A THOROUGH INSPECTION OF THE VEHICLE ON PICKUP.",
    "Authority to transport this vehicle is hereby assigned to Eagle Express Inc.",
    "By accepting this agreement Eagle Express Inc certifies that it has the proper",
    "legal authority and insurance to carry the above described vehicle, only on",
    "trucks owned by Eagle Express Inc. All invoices must be accompanied by a signed",
    "delivery receipt and faxed to Pacific Auto Transport LLC. The above agreed upon",
    "price includes any and all surcharges unless otherwise agreed to by both parties.",
    "The agreement between Eagle Express Inc and Pacific Auto Transport LLC, as",
    "described in this dispatch sheet, is solely between Eagle Express Inc and",
    "Pacific Auto Transport LLC. Dealertrack Central Dispatch, Inc. is not a party",
    "to such agreement, has no obligation under such agreement and expressly disclaims",
    "all liability whatsoever arising out of, or in connection with such agreement.",
]

_BACKLOTCARS_TERMS_P2 = [
    "CONTRACT TERMS *** PLEASE READ CAREFULLY ***",
    "Please provide at least 24-hour notice to the customer before Pickup and Delivery.",
    "Please complete a careful inspection of the vehicle on Pickup.",
    "Carrier Terms & Agreement",
    "Every shipment tendered to a Carrier by BacklotCars will be subject to the terms",
    "of the BacklotCars Broker-Carrier Agreement; BacklotCars' Terms and Conditions,",
    "to the extent applicable which are posted online at (www.backlotcars.com); and",
    "applicable law.",
    "1. Carrier should contact customers at least two (2) hours prior to pick up or",
    "delivery of a vehicle to schedule a convenient time during normal business hours.",
    "2. In the event that Carrier is unable to perform the requested Services, Carrier",
    "shall notify BacklotCars within one (1) day after Carrier determines it is unable",
    "to perform the requested Services.",
    "3. Carrier shall not disclose or discuss the terms of the BacklotCars Agreement",
    "including the rates or the valuation of the Services with customers or third parties.",
    "4. Carrier will be responsible for loading and unloading all shipments.",
    "5. Carrier must verify that the VIN on the dispatch paperwork matches the vehicle.",
    "6. Carrier shall not drive any vehicle consigned to them without specific approval.",
    "7. BacklotCars pays Carrier via ACH within thirty (30) days from receipt of invoice.",
    "Powered by Super Dispatch",
]


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_central_dispatch_pdf(tmp_path: Path) -> Path:
    """CentralDispatch single-page settlement — baseline clean format.

    Mirrors BSAT1066 layout. Single page with carrier info block, vehicle
    info, pickup/delivery, instructions, contract terms, and payment block.

    Expected: pay=1850.00, date=04/15/2024
    """
    doc = _new_doc()
    page = _add_page(doc)
    y = 50

    # Header — two columns: carrier block left, shipper block right
    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    _line(page, _RIGHT_COL, y, "Dispatch Sheet", _SECTION_SIZE)
    y += 16
    _line(page, _LEFT, y, "Carrier: Eagle Express Inc")
    _line(page, _RIGHT_COL, y, "CentralDispatch")
    y += 13
    _line(page, _LEFT, y, "1200 Commerce Blvd STE# 300")
    _line(page, _RIGHT_COL, y, "by Cox Automotive")
    y += 13
    _line(page, _LEFT, y, "torrance, CA 90501")
    _line(page, _RIGHT_COL, y, "Pacific Auto Transport LLC")
    y += 13
    _line(page, _LEFT, y, "MC Number: 1234567")
    _line(page, _RIGHT_COL, y, "9800 Wilshire Blvd #200")
    y += 13
    _line(page, _LEFT, y, "Driver: John Doe")
    _line(page, _RIGHT_COL, y, "beverly hills, CA 90210")
    y += 13
    _line(page, _LEFT, y, "Driver Phone: (555) 123-4567")
    _line(page, _RIGHT_COL, y, "Co. Phone: (555) 333-4444 Main")
    y += 13
    _line(page, _LEFT, y, "Order ID: ABCD1234")
    _line(page, _RIGHT_COL, y, "Dispatch Info")
    y += 13
    _line(page, _LEFT, y, "Contact: John, Mike, Sarah")
    _line(page, _RIGHT_COL, y, "Contact: Mark Stevens")
    y += 13
    _line(page, _LEFT, y, "Phone: (555) 123-4567")
    _line(page, _RIGHT_COL, y, "Phone: (555) 444-5555")
    y += 13
    _line(page, _LEFT, y, "Phone 2: (555) 987-6543")
    _line(page, _RIGHT_COL, y, "Fax: (555) 444-5556")
    y += 13
    _line(page, _LEFT, y, "Fax: (555) 111-2222")
    _line(page, _RIGHT_COL, y, "MC #: 654321")
    y += 18

    # Vehicle
    _line(page, _LEFT, y, "Vehicle Information", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "Total Vehicles: 1")
    y += 13
    _line(page, _LEFT, y, "1 2019 honda civic  Type: Car  Color: Blue  VIN: 2HGFC2F53KH012345  Lot #:")
    y += 18

    # Pickup / Delivery
    _line(page, _LEFT, y, "Pickup Information", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "Name: Jane Smith")
    y += 13
    _line(page, _LEFT, y, "123 Main Street")
    y += 13
    _line(page, _LEFT, y, "los angeles, CA 90001")
    y += 13
    _line(page, _LEFT, y, "Phone: 555-222-3333")
    y += 18
    _line(page, _LEFT, y, "Delivery Information", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "Name: Jane Smith")
    y += 13
    _line(page, _LEFT, y, "456 Oak Avenue #8")
    y += 13
    _line(page, _LEFT, y, "phoenix, AZ 85001")
    y += 13
    _line(page, _LEFT, y, "Phone: 555-222-3333")
    y += 18

    # Dispatch instructions
    _line(page, _LEFT, y, "DISPATCH INSTRUCTIONS", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "NOTE: Vehicle is in a gated lot. Driver must check in at front office before loading.")
    y += 13
    _line(page, _LEFT, y, "This must be picked up exactly on 04/15/2024. Delivery within 3 days of 04/18/2024.")
    y += 13
    y = _block(page, _LEFT, y, _CENTRAL_DISPATCH_TERMS, leading=12)
    y += 10

    # Order / Payment block
    _line(page, _LEFT, y, "Order Information", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Dispatch Date:", "04/10/2024"),
        ("Pickup Exactly:", "04/15/2024"),
        ("Delivery Estimated:", "04/18/2024"),
        ("Ship Via:", "Open"),
        ("Condition:", "Operable"),
        ("Price Listed:", "N/A"),
        ("Total Payment to Carrier:", "$1,850.00"),
        ("On Delivery to Carrier:", "None"),
        ("Company* owes Carrier:", "$1,850.00"),
    ])
    y += 6
    _line(page, _LEFT, y, "Pacific Auto Transport LLC agrees to pay Eagle Express Inc $1,850.00 immediately")
    y += 13
    _line(page, _LEFT, y, "upon receiving a signed Bill of Lading. Payment will be made with Company Check.")
    y += 13
    _line(page, _LEFT, y, "CD reference # 40567890")

    path = tmp_path / "ABCD1234_2019_honda_civic.pdf"
    doc.save(str(path))
    doc.close()
    return path


def build_v2_dispatch_pdf(tmp_path: Path) -> Path:
    """V2 Dispatch 2-page load summary.

    Mirrors R667644. Page 1 has dispatch details and vehicle table.
    Page 2 has load payment — the pay field appears here, away from the
    date (which is on page 1 as a word-form string).

    Tricky: pay is on page 2, date is word-form ("April 8, 2024 (Mon)").
    Expected: pay=920.00, date contains "April 8, 2024"
    """
    doc = _new_doc()

    # --- Page 1 ---
    page = _add_page(doc)
    y = 50
    _line(page, _LEFT, y, "10/29/24, 12:15 PM", _LABEL_SIZE)
    y += 14
    _line(page, _LEFT, y, "V2 Dispatch | Auto Transport Dispatch Simplified", _HEADER_SIZE)
    y += 18
    _line(page, _LEFT, y, "Dispatch Details | Load #R123456", _SECTION_SIZE)
    y += 16
    y = _two_col(page, y, [
        ("Order ID", "R123456"),
        ("Current Status", "Delivered"),
        ("Last Update", "April 12, 2024 at 3:45 PM"),
        ("V2D Reference #", "556789"),
        ("Dispatch Date", "March 28, 2024 (Thu)"),
        ("Pickup Date", "April 8, 2024 (Mon)"),
        ("Delivery Date", "April 12, 2024 (Fri)"),
        ("Carrier Type", "Open"),
    ])
    y += 12

    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Eagle Express",
        "1200 Commerce Blvd Ste 300",
        "Torrance, CA 90501",
        "Driver Name : John Doe",
        "Driver Phone : (555) 123-4567",
        "Office Phone : (555) 123-4567",
    ])
    y += 8

    _line(page, _LEFT, y, "Agent Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "National Auto Movers",
        "200 Park Avenue Ste 400",
        "New York, NY 10001",
        "Contact : Alex, Chris, Pat",
        "Phone : (555) 888-9999",
        "MC Number : 112233",
    ])
    y += 8

    _line(page, _LEFT, y, "Pickup Location", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Mike Johnson",
        "789 Elm Street",
        "Fayetteville, GA 30215",
        "Phone : (555) 777-6666",
    ])
    y += 8

    _line(page, _LEFT, y, "Delivery Location", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Harbor Auto Receiving",
        "555 Harbor Blvd",
        "Long Beach, CA 90802",
        "Phone : (555) 444-3333",
    ])
    y += 12

    # Vehicle table header
    _line(page, _LEFT, y, "Vehicle Information - 1 Vehicle", _SECTION_SIZE)
    y += 14
    cols = ["Year", "Make", "Model", "Type", "Condition", "Color", "Vin"]
    x_positions = [50, 90, 140, 210, 260, 330, 390]
    for col, x in zip(cols, x_positions):
        _line(page, x, y, col, _LABEL_SIZE)
    y += 12
    vals = ["2020", "Toyota", "Camry", "Car", "Running", "Silver", "4T1BF1FK5LU123456"]
    for val, x in zip(vals, x_positions):
        _line(page, x, y, val, _LABEL_SIZE)
    y += 16

    _line(page, _LEFT, y, "Additional Comments", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "Delivery Window: 4/10/2024 - 4/15/2024  *** DO NOT ACCEPT WITH OVER 1/4 TANK OF GAS ***")
    y += 13
    _line(page, _LEFT, y, "Vin#4T1BF1FK5LU123456  Booking#223344  *** DRIVERS MUST CALL 24 HOURS IN ADVANCE ***")
    y += 13
    _line(page, _LEFT, y, "https://www.v2dispatch.com/print.php")
    y += 13
    _line(page, _LEFT, y, "1/2")

    # --- Page 2 ---
    page = _add_page(doc)
    y = 50
    _line(page, _LEFT, y, "10/29/24, 12:15 PM", _LABEL_SIZE)
    y += 14
    _line(page, _LEFT, y, "V2 Dispatch | Auto Transport Dispatch Simplified", _HEADER_SIZE)
    y += 20

    _line(page, _LEFT, y, "Load Payment", _SECTION_SIZE)
    y += 16
    y = _two_col(page, y, [
        ("Total Payment", "$920"),
        ("Collect On Delivery", "$0"),
        ("Agent Pays Carrier", "$920"),
    ])
    y += 8
    _line(page, _LEFT, y, "Payment will be processed upon confirmation of delivery.")
    y += 20

    _line(page, _LEFT, y, "Contract Terms", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "- As a courtesy, please give clients a call 1-2 hours prior to pickup or delivery.",
        "- All drivers should fill out a BOL upon pickup and delivery.",
        "- Any vehicle listed as INOP must be loaded & unloaded with a winch.",
        "- Dry run fees will not be paid unless agreed upon before assignment of the load.",
        "- We ask that all carriers call in if and when cancelling a load.",
        "- Any additional funds requested will not be paid unless discussed BEFORE loading.",
        "Authority to transport this vehicle is hereby assigned to Eagle Express.",
        "By accepting this agreement Eagle Express certifies that it has the proper legal",
        "authority and insurance to carry the above described vehicle.",
        "@ 2021 V2 Dispatch Inc.",
        "https://www.v2dispatch.com/print.php",
        "2/2",
    ])

    path = tmp_path / "R123456_2020_toyota_camry.pdf"
    doc.save(str(path))
    doc.close()
    return path


def build_super_dispatch_pdf(tmp_path: Path) -> Path:
    """Super Dispatch / BacklotCars 3-page dispatch sheet.

    Mirrors Y605399. Page 1 has carrier/order info with pay and pickup date.
    Page 2 has dispatch instructions and beginning of contract boilerplate.
    Page 3 continues boilerplate — dense legal text that could confuse
    extraction if the model attends to the wrong dollar figures.

    Tricky: 3 pages of contract boilerplate, pick-up date estimated.
    Expected: pay=1350.00, date=04/22/2024
    """
    doc = _new_doc()

    # --- Page 1 ---
    page = _add_page(doc)
    y = 50
    _line(page, _LEFT, y, "Order ID: X789012", _SECTION_SIZE)
    y += 16
    _line(page, _LEFT, y, "Dispatch Sheet", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "OPENLANE dba",
        "BacklotCars Inc",
        "Shipper",
        "1100 Main St #1500",
        "Kansas City, MO 64105",
        "Co. Phone: 816-298-8222",
        "Email: transport@openlane.com",
    ])
    y += 10

    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Carrier: EAGLE EXPRESS INC",
        "1200 Commerce Blvd #300",
        "TORRANCE, California 90501",
    ])
    y += 10

    _line(page, _LEFT, y, "Order Information", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Dispatch Date:", "04/18/2024"),
        ("Carrier Pickup Estimated:", "04/22/2024"),
        ("Carrier Delivery Estimated:", "04/25/2024"),
        ("Ship Via:", "OPEN"),
        ("Condition:", "Operable"),
    ])
    y += 6
    _line(page, _LEFT, y, "OPENLANE")
    y += 13
    _line(page, _LEFT, y, "Contact: John")
    y += 13
    _line(page, _LEFT, y, "Phone: 5551234567")
    y += 13
    _line(page, _LEFT, y, "Email: Dispatch@eagleexpress.com")
    y += 13
    _line(page, _LEFT, y, "Total Payment to Carrier: $1,350.00")
    y += 13
    _line(page, _LEFT, y, "Payment method:")
    y += 13
    _line(page, _LEFT, y, "Payment terms: ACH")
    y += 13
    _line(page, _LEFT, y, "Shipper owes Carrier: $1,350.00")
    y += 16

    # Vehicle table
    _line(page, _LEFT, y, "Vehicle Information", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "Total Vehicles: 1")
    y += 13
    for col, x in zip(["#", "Vehicle", "Type", "Color", "VIN"], [50, 80, 200, 250, 310]):
        _line(page, x, y, col, _LABEL_SIZE)
    y += 12
    for val, x in zip(["1", "2021 Ford F-150", "Pickup", "White", "1FTFW1E86MFA12345"], [50, 80, 200, 250, 310]):
        _line(page, x, y, val, _LABEL_SIZE)
    y += 16

    # Pickup / Delivery
    _line(page, _LEFT, y, "Pickup Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Name: Sam Williams",
        "DESERT AUTO GROUP",
        "4500 EAST MAIN DRIVE",
        "FLAGSTAFF, AZ 86004",
        "Phone: 5556667777",
        "Notes: Gate release code: 7K2N88. No weekend pickups.",
    ])
    y += 8

    _line(page, _LEFT, y, "Delivery Information", _SECTION_SIZE)
    y += 14
    _block(page, _LEFT, y, [
        "Name: TOM BROWN",
        "CAROLINA AUTO SALES INC",
        "1500 West Garrison Blvd",
        "Gastonia, NC 28054",
        "Phone: 5558889999",
        "Notes: CALL 24 hrs in advance. AUTHORIZATION OF DROP MUST BE CONFIRMED",
    ])

    # --- Page 2 ---
    page = _add_page(doc)
    y = 50
    _line(page, _LEFT, y, "DISPATCH INSTRUCTIONS", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Dry run fees (DRF) will only be paid if the vehicle availability has been confirmed",
        "by the carrier along with the customer's name who provided confirmation.",
        "UNATTENDED DROPS: It is MANDATORY that we receive pictures for ALL unattended",
        "deliveries including pictures of the vehicle location, pictures of all 4 angles",
        "of car (front, back, and both sides) and pictures of key location.",
    ])
    y += 10
    y = _block(page, _LEFT, y, _BACKLOTCARS_TERMS_P2)

    # --- Page 3 ---
    page = _add_page(doc)
    y = 50
    y = _block(page, _LEFT, y, [
        "6. Carrier shall not drive any vehicle consigned to them unless given specific",
        "approval from BacklotCars. Unauthorized driving will result in non-payment.",
        "7. Carrier shall provide evidence of pickup in the form designated by BacklotCars",
        "indicating: quantity of vehicles, condition, odometer, BacklotCars Order ID, VINs,",
        "and the legible name and signature of a representative of the pickup location.",
        "8. Carrier will deliver all vehicles to the appropriate destination as listed on",
        "the pickup notice. Carrier shall be liable for any damages from alternate delivery.",
        "9. Carrier shall provide BacklotCars, within twenty-four (24) hours of delivery,",
        "an invoice and detailed condition report including VINs and delivery acknowledgement.",
        "10. BacklotCars pays Carrier, via ACH, all complete and undisputed amounts within",
        "thirty (30) days from the date of BacklotCars' receipt of the invoice.",
        "11. Express payment option: invoice reduced by three percent (3%) of total amount",
        "for next-business-day payment. Deliveries and invoices submitted by 3 pm CST.",
        "12. BacklotCars may withhold payment to protect itself from claims, fraud, or",
        "services not performed in accordance with the terms of this Agreement.",
        "Powered by Super Dispatch",
        "This agreement is made by and between a \"Carrier\" and a \"Broker / Shipper\".",
        "Super Dispatch Inc. and its affiliates are not party to this agreement.",
    ])

    path = tmp_path / "X789012_2021_ford_f150.pdf"
    doc.save(str(path))
    doc.close()
    return path


def build_cod_settlement_pdf(tmp_path: Path) -> Path:
    """CentralDispatch dispatch sheet with COD and conflicting dollar amounts.

    Mirrors RM24105 (Toyota Tacoma). Contains multiple dollar amounts:
      - "Total Payment to Carrier: $1,400.00"  ← correct carrier pay
      - "On Delivery to Carrier: $1,750.00 *COD"  ← COD amount (customer pays driver)
      - "Carrier owes Company **: $350.00 after COD is paid"  ← net payback

    The correct extraction is pay=1400.00. A naive extractor might pick
    $1,750 (the highest dollar amount) or $350 (the last explicit figure).

    Tricky: three dollar values, COD semantics, polarity footnote.
    Expected: pay=1400.00, date=03/12/2024
    """
    doc = _new_doc()
    page = _add_page(doc)
    y = 50

    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Carrier: Eagle Express Inc",
        "1200 Commerce Blvd STE# 300",
        "torrance, CA 90501",
        "MC Number: 1234567",
        "Driver: TBD John",
        "Driver Phone: (555) 123-4567",
    ])
    y += 10

    _line(page, _LEFT, y, "Order Information", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Dispatch Date:", "03/08/2024"),
        ("Pickup Estimated:", "03/12/2024"),
        ("Delivery Estimated:", "03/19/2024"),
        ("Ship Via:", "Open"),
        ("Condition:", "Operable"),
    ])
    y += 8

    # The tricky payment block — three competing dollar amounts
    _line(page, _LEFT, y, "Eagle Express Inc agrees to pay Riverside Logistics LLC $350.00 within")
    y += 13
    _line(page, _LEFT, y, "5 business days of delivery. Payment will be made with Company Check.")
    y += 13
    _line(page, _LEFT, y, "*Cash/Certified Funds on Delivery.")
    y += 13
    _line(page, _LEFT, y, "** The company (broker, dealer, auction, etc.) that originated this sheet.")
    y += 16

    _line(page, _LEFT, y, "Vehicle Information", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "1 2002 toyota tacoma  Type: Pickup  Color: Gray  VIN: 5TENX22N02Z123456  Lot #: 749")
    y += 16

    _line(page, _LEFT, y, "Pickup Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Name: OFFICE (AUCTION HOUSE)",
        "1618 AUCTION DR",
        "pelzer, SC 29669",
        "Phone: 844-450-4960",
    ])
    y += 8

    _line(page, _LEFT, y, "Delivery Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Name: BOB JONES",
        "1326 WEST CHANNEL ISLANDS BLVD",
        "oxnard, CA 93033",
        "Phone: 805-555-8640",
    ])
    y += 10

    _line(page, _LEFT, y, "DISPATCH INSTRUCTIONS", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "This should be picked up within 2 days of 03/12/2024.")
    y += 13
    _line(page, _LEFT, y, "This should be delivered within 2 days of 03/19/2024.")
    y += 13
    y = _block(page, _LEFT, y, _CENTRAL_DISPATCH_TERMS, leading=12)
    y += 8

    # Payment block with all three amounts
    _line(page, _LEFT, y, "CD reference # 40261923", _LABEL_SIZE)
    y += 14
    _line(page, _LEFT, y, "Order Information (continued)", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Contact:", "John, Mike, Sarah"),
        ("Phone:", "(555) 123-4567"),
        ("Price Listed:", "N/A"),
        ("Total Payment to Carrier:", "$1,400.00"),
        ("On Delivery to Carrier:", "$1,750.00 *COD"),
        ("Carrier owes Company **:", "$350.00 after COD is paid"),
    ])

    path = tmp_path / "CODX9999_2002_toyota_tacoma.pdf"
    doc.save(str(path))
    doc.close()
    return path


def build_multi_vehicle_pdf(tmp_path: Path) -> Path:
    """CentralDispatch with 3 vehicles, 2 pages.

    Mirrors 44445 BIRM (Mercedes-Benz batch). A single payment covers
    three vehicles at once — the high dollar amount ($4,500) is the
    total for all three, not per vehicle.

    Page 1: carrier info, vehicle list (3 entries), pickup/delivery.
    Page 2: contract terms (to match real document length).

    Tricky: multiple vehicles with individual VINs, high total payment.
    Expected: pay=4500.00, date=05/06/2024
    """
    doc = _new_doc()

    # --- Page 1 ---
    page = _add_page(doc)
    y = 50

    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    _line(page, _RIGHT_COL, y, "Order ID: 55678 EAST", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Carrier: Eagle Express Inc",
        "1200 Commerce Blvd STE# 300",
        "torrance, CA 90501",
        "MC Number: 1234567",
        "Driver: John Doe",
        "Driver Phone: (555) 123-4567",
        "Contact: John, Mike, Sarah",
        "Phone: (555) 123-4567",
        "Phone 2: (555) 987-6543",
        "Fax: (555) 111-2222",
    ])
    y += 10

    _line(page, _LEFT, y, "Order Information", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Dispatch Date:", "05/01/2024"),
        ("Pickup Estimated:", "05/06/2024"),
        ("Delivery Estimated:", "05/11/2024"),
        ("Ship Via:", "Open"),
        ("Condition:", "Operable"),
        ("Price Listed:", "N/A"),
        ("Total Payment to Carrier:", "$4,500.00"),
        ("On Delivery to Carrier:", "None"),
        ("Company* owes Carrier:", "$4,500.00"),
    ])
    y += 8
    _line(page, _LEFT, y, "Luxury Auto Relocation Inc agrees to pay Eagle Express Inc $4,500.00 within 10")
    y += 13
    _line(page, _LEFT, y, "business days of receiving a signed Bill of Lading. Certified Funds.")
    y += 16

    _line(page, _LEFT, y, "Total Vehicles: 3", _SECTION_SIZE)
    y += 14

    # Three vehicles
    for i, (vin, model) in enumerate([
        ("5UXCR6C09N9K12345", "bmw x5"),
        ("5UXCR6C09N9K67890", "bmw x5"),
        ("5UXCR6C09N9K11223", "bmw x3"),
    ], 1):
        _line(page, _LEFT, y, f"{i} 2022  Type: SUV  Color: White  VIN: {vin}  Lot #:")
        y += 13
        _line(page, _LEFT + 10, y, model)
        y += 13
        _line(page, _LEFT + 10, y, "MUST CHECK FOR MILEAGE: 200 AND UNDER. MUST PICK UP 2 SETS OF KEYS.")
        y += 15

    y += 6
    _line(page, _LEFT, y, "Pickup Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Name: East Coast BMW",
        "500 Auto Center Drive",
        "birmingham, AL 35210",
        "Phone: (555) 444-5555",
    ])
    y += 8

    _line(page, _LEFT, y, "Delivery Information", _SECTION_SIZE)
    y += 14
    _block(page, _LEFT, y, [
        "Name: West Coast Imports",
        "8000 Auto Center Dr",
        "buena park, CA 90621",
        "Phone: (555) 666-7777",
    ])

    # --- Page 2 ---
    page = _add_page(doc)
    y = 50
    _line(page, _LEFT, y, "DISPATCH INSTRUCTIONS", _SECTION_SIZE)
    y += 14
    _line(page, _LEFT, y, "This should be picked up within 2 days of 05/06/2024.")
    y += 13
    _line(page, _LEFT, y, "This should be delivered within 2 days of 05/11/2024.")
    y += 13
    y = _block(page, _LEFT, y, [
        "CONTRACT TERMS",
        "*** PLEASE READ CAREFULLY ***",
        "****** PLEASE DO NOT EVER DISCUSS PRICES WITH CUSTOMERS ******",
        "IF PRICE OF TRANSPORTATION IS DISCUSSED WITH CUSTOMERS THERE WILL",
        "BE A 10% CHARGE FROM TRANSPORTATION AGREED COST.",
        "**** WE DO NOT PAY FOR DRY RUNS*",
        "Call customers a day in advance to schedule pick up time.",
        "PLEASE GIVE THE CUSTOMER AT LEAST A 24 HOUR NOTICE FOR PICKUP AND DELIVERY.",
        "Authority to transport this vehicle is hereby assigned to Eagle Express Inc.",
        "By accepting this agreement Eagle Express Inc certifies that it has the proper",
        "legal authority and insurance to carry the above described vehicle(s), only on",
        "trucks owned by Eagle Express Inc. All invoices must be accompanied by a signed",
        "delivery receipt and faxed to Luxury Auto Relocation Inc.",
        "CD reference # 40334455",
    ])

    path = tmp_path / "55678_EAST_2022_bmw_x5_batch.pdf"
    doc.save(str(path))
    doc.close()
    return path


def build_revision_history_pdf(tmp_path: Path) -> Path:
    """Super Dispatch sheet with a revision table showing old price = $0.00.

    Mirrors 12853712 (Ford Escape / ShipYourCarNow). Contains:
      - A "Revision" section with "Price: Old: $0.00 → New: $750.00"
      - Then the real "Total Payment to Carrier: $750.00" block below

    A naive extractor scanning only for dollar amounts might grab $0.00.
    The redundant triple-label pattern ("Total Payment / Shipper owes /
    Carrier owes") is also present.

    Tricky: revision table with 0.00 → 750.00, triple-labeled payment.
    Expected: pay=750.00, date=03/12/2024
    """
    doc = _new_doc()

    # --- Page 1 ---
    page = _add_page(doc)
    y = 50

    _line(page, _LEFT, y, "Order ID: FE12853712", _SECTION_SIZE)
    y += 16

    y = _block(page, _LEFT, y, [
        "ShipYourCarNow",
        "Powered by Super Dispatch",
        "Shipper",
        "888 Freight Lane",
        "Austin, TX 78701",
        "Co. Phone: 512-555-7890",
        "Email: dispatch@sycn.com",
    ])
    y += 10

    _line(page, _LEFT, y, "Carrier Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Carrier: EAGLE EXPRESS INC",
        "1200 Commerce Blvd #300",
        "TORRANCE, California 90501",
        "Contact: John",
        "Phone: 5551234567",
        "Email: Dispatch@eagleexpress.com",
    ])
    y += 10

    _line(page, _LEFT, y, "Order Information", _SECTION_SIZE)
    y += 14
    y = _two_col(page, y, [
        ("Dispatch Date:", "03/09/2024"),
        ("Carrier Pickup Exact:", "03/12/2024"),
        ("Carrier Delivery Not Later Than:", "03/15/2024"),
        ("Ship Via:", "OPEN"),
        ("Condition:", "Operable"),
        ("Total Payment to Carrier:", "$750.00"),
        ("Carrier owes Shipper:", "$ 0.00"),
        ("Shipper owes Carrier:", "$750.00"),
        ("Payment terms:", "NET 30 / ACH"),
    ])
    y += 16

    # Vehicle
    _line(page, _LEFT, y, "Vehicle Information", _SECTION_SIZE)
    y += 14
    for col, x in zip(["#", "Vehicle", "Type", "Color", "VIN"], [50, 80, 200, 250, 310]):
        _line(page, x, y, col, _LABEL_SIZE)
    y += 12
    for val, x in zip(["1", "2021 Ford Escape", "SUV", "Blue", "1FMCU9G60MUA12345"], [50, 80, 200, 250, 310]):
        _line(page, x, y, val, _LABEL_SIZE)
    y += 16

    # Pickup / Delivery
    _line(page, _LEFT, y, "Pickup Information", _SECTION_SIZE)
    y += 14
    y = _block(page, _LEFT, y, [
        "Name: JOSHUA GREEN",
        "Sunrise Mazda",
        "451 Auto Row Pkwy",
        "Roseville, CA 95661",
        "Phone: 9165554321",
    ])
    y += 8

    _line(page, _LEFT, y, "Delivery Information", _SECTION_SIZE)
    y += 14
    _block(page, _LEFT, y, [
        "Name: DANIELLE MOORE",
        "Coastal Auto Group",
        "777 Ocean Drive",
        "miami, FL 33139",
        "Phone: 3055557890",
    ])

    # --- Page 2 ---
    page = _add_page(doc)
    y = 50

    # Revision history — this is the tricky part
    _line(page, _LEFT, y, "REVISIONS", _SECTION_SIZE)
    y += 16
    _line(page, _LEFT, y, "Mar 9, 2024 at 12:47 PM")
    y += 13
    _line(page, _LEFT, y, "Order Modified")
    y += 13
    _line(page, _LEFT, y, "Updated by Shipper")
    y += 16

    # Table: Field / Old Value / New Value
    for col, x in zip(["Field", "Old Value", "New Value"], [50, 200, 350]):
        _line(page, x, y, col, _SECTION_SIZE)
    y += 14
    for val, x in zip(["Price", "$0.00", "$750.00"], [50, 200, 350]):
        _line(page, x, y, val)
    y += 13
    for val, x in zip(["Pickup Date", "03/09/2024", "03/12/2024"], [50, 200, 350]):
        _line(page, x, y, val)
    y += 20

    y = _block(page, _LEFT, y, [
        "DISPATCH INSTRUCTIONS",
        "Carrier must use the Super Dispatch app to submit BOL and delivery photos.",
        "Payment NET 30 days via ACH after delivery confirmation and invoice receipt.",
        "ACH early payment option available: 7% discount for next-business-day payment.",
        "CONTRACT TERMS *** PLEASE READ CAREFULLY ***",
        "Please provide at least 24-hour notice to the customer before Pickup and Delivery.",
        "Please complete a careful inspection of the vehicle on Pickup.",
        "$50/day storage fee applies for any hold beyond 5 business days.",
        "Carrier Terms & Agreement",
        "This agreement is made by and between a \"Carrier\" and a \"Broker / Shipper\".",
        "Super Dispatch Inc. and its affiliates are not party to this agreement.",
        "Super Dispatch Inc. and affiliates have no obligation under this agreement",
        "and expressly disclaim any and all liability and warranties arising out of,",
        "or in connection with this agreement.",
    ])

    path = tmp_path / "FE12853712_2021_ford_escape.pdf"
    doc.save(str(path))
    doc.close()
    return path
