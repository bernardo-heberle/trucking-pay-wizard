"""Generate realistic OCR fixture JSON files with correct char offsets.

Run once from the repo root to regenerate all fixture files:

    python -m tests.fixtures.generate_fixtures

All PII is synthetic — names, addresses, phone numbers, VINs are fabricated.
The document structures mirror real CentralDispatch, V2 Dispatch, and Super
Dispatch formats seen in production data.
"""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURES_DIR = Path(__file__).parent


def _build_fixture(
    source_path: str,
    content_hash: str,
    pages: dict[int, list[str]],
) -> dict:
    """Build a fixture dict from page_number -> list of text lines.

    Computes char_start/char_end offsets that match OcrResult.full_text
    (lines joined by \\n within a page, pages separated by \\n\\n).
    Bounding boxes are spaced evenly down the page.
    """
    page_numbers = sorted(pages.keys())
    all_lines = []
    page_summaries = []
    offset = 0

    for page_idx, pn in enumerate(page_numbers):
        lines = pages[pn]
        page_summaries.append({
            "page_number": pn,
            "width_inches": 8.5,
            "height_inches": 11.0,
            "line_count": len(lines),
        })

        y_start = 0.5
        y_step = min(0.4, 9.5 / max(len(lines), 1))

        for line_idx, text in enumerate(lines):
            char_start = offset
            char_end = offset + len(text)
            all_lines.append({
                "text": text,
                "page_number": pn,
                "bounding_box": {
                    "x": 1.0,
                    "y": round(y_start + line_idx * y_step, 2),
                    "width": min(round(len(text) * 0.08, 1), 6.5),
                    "height": 0.25,
                },
                "char_start": char_start,
                "char_end": char_end,
            })
            offset = char_end

            is_last_line_of_page = line_idx == len(lines) - 1
            if not is_last_line_of_page:
                offset += 1  # \n between lines within a page

        is_last_page = page_idx == len(page_numbers) - 1
        if not is_last_page:
            offset += 2  # \n\n page separator

    return {
        "source_path": source_path,
        "content_hash": content_hash,
        "pages": page_summaries,
        "lines": all_lines,
    }


def _central_dispatch_settlement() -> dict:
    """CentralDispatch dispatch sheet — mirrors BSAT1066 format.

    Single-page settlement with carrier info, vehicle, pickup/delivery,
    dispatch instructions, contract terms, and payment block.
    Expected: pay=1850.00, date=04/15/2024
    """
    return _build_fixture(
        source_path="ABCD1234 2019 Honda Civic.pdf",
        content_hash="aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44",
        pages={
            1: [
                "Carrier Information",
                "Carrier: Eagle Express Inc",
                "1200 Commerce Blvd STE# 300",
                "torrance, CA 90501",
                "MC Number: 1234567",
                "Driver: John Doe",
                "Driver Phone: (555) 123-4567",
                "Order ID: ABCD1234",
                "Contact: John, Mike, Sarah",
                "Phone: (555) 123-4567",
                "Phone 2: (555) 987-6543",
                "Fax: (555) 111-2222",
                "Dispatch Sheet",
                "CentralDispatch",
                "by Cox Automotive",
                "Pacific Auto",
                "Transport LLC",
                "9800 Wilshire Blvd #200",
                "beverly hills, CA 90210",
                "Co. Phone: (555) 333-4444 Main",
                "Dispatch Info",
                "Contact: Mark Stevens",
                "Phone: (555) 444-5555",
                "Fax: (555) 444-5556",
                "MC #: 654321",
                "Vehicle Information",
                "Total Vehicles: 1",
                "1 2019 honda civic Type: Car Color: Blue Plate: VIN: 2HGFC2F53KH012345 Lot #: Additional Info:",
                "Pickup Information",
                "Name: Jane Smith",
                "123 Main Street",
                "los angeles, CA 90001",
                "Phone: 555-222-3333",
                "Delivery Information",
                "Name: Jane Smith",
                "456 Oak Avenue #8",
                "phoenix, AZ 85001",
                "Phone: 555-222-3333",
                "DISPATCH INSTRUCTIONS",
                "NOTE: Vehicle is in a gated lot. Driver must check in at the front office before loading.",
                "This needs to load exactly 4/15. Delivery must be within 3 days.",
                "This must be picked up exactly on 04/15/2024. This should be delivered within 3 days of 04/18/2024.",
                "CONTRACT TERMS",
                "*** PLEASE READ CAREFULLY ***",
                "Do not discuss rates with customer!",
                "ADDITIONAL TERMS",
                "Call or text Mark at 555-444-5555",
                "PLEASE GIVE THE CUSTOMER AT LEAST A 24 HOUR NOTICE FOR PICKUP AND DELIVERY. PLEASE DO A THOROUGH INSPECTION OF THE VEHICLE ON",
                "PICKUP.",
                "Authority to transport this vehicle is hereby assigned to Eagle Express Inc. By accepting this agreement Eagle Express Inc certifies that it has the",
                "proper legal authority and insurance to carry the above described vehicle, only on trucks owned by Eagle Express Inc. All invoices must be",
                "accompanied by a signed delivery receipt and faxed to Pacific Auto Transport LLC. The above agreed upon price includes any and all surcharges",
                "unless otherwise agreed to by both Eagle Express Inc and Pacific Auto Transport LLC.",
                "The agreement between Eagle Express Inc and Pacific Auto Transport LLC, as described in this dispatch sheet, is solely between Eagle Express Inc and",
                "Pacific Auto Transport LLC. Dealertrack Central Dispatch, Inc. is not a party to such agreement, has no obligation under such agreement and",
                "expressly disclaims all liability whatsoever arising out of, or in connection with such agreement.",
                "CD reference # 40567890",
                "Order Information",
                "Dispatch Date: 04/10/2024",
                "Pickup Exactly: 04/15/2024",
                "Delivery Estimated: 04/18/2024",
                "Ship Via: Open",
                "Condition: Operable",
                "Price Listed: N/A",
                "Total Payment to Carrier: $1,850.00",
                "On Delivery to Carrier: None",
                "Company* owes Carrier: $1,850.00",
                "Pacific Auto Transport LLC agrees to pay Eagle Express Inc $1,850.00 immediately upon receiving",
                "a signed Bill of Lading. Payment will be made with Company Check.",
                "*The company (broker, dealer, auction, rental company, etc.) that originated this dispatch sheet.",
            ],
        },
    )


def _v2_dispatch_load() -> dict:
    """V2 Dispatch format — mirrors R667644 format.

    Two-page load summary with dispatch details, carrier/agent info,
    vehicle table, load payment, and contract terms.
    Expected: pay=920.00, date contains "April 8, 2024"
    """
    return _build_fixture(
        source_path="R123456 2020 Toyota Camry.pdf",
        content_hash="bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55",
        pages={
            1: [
                "10/29/24, 12:15 PM",
                "V2 Dispatch | Auto Transport Dispatch Simplified",
                "Dispatch Details | Load #R123456",
                "Order ID",
                "R123456",
                "Current Status",
                "Delivered",
                "Last Update",
                "April 12, 2024 at 3:45 PM",
                "V2D Reference #",
                "556789",
                "Dispatch Date",
                "March 28, 2024 (Thu)",
                "Pickup Date",
                "April 8, 2024 (Mon)",
                "Delivery Date",
                "April 12, 2024 (Fri)",
                "Carrier Type",
                "Open",
                "Carrier Information",
                "Eagle Express",
                "1200 Commerce Blvd Ste 300",
                "Torrance, CA 90501",
                "Driver Name : John Doe",
                "Driver Phone : (555) 123-4567",
                "Office Phone : (555) 123-4567",
                "Agent Information",
                "National Auto Movers",
                "200 Park Avenue Ste 400",
                "New York, NY 10001",
                "Contact : Alex, Chris, Pat",
                "Phone : (555) 888-9999",
                "MC Number : 112233",
                "Pickup Location",
                "Mike Johnson",
                "789 Elm Street",
                "Fayetteville, GA 30215",
                "Phone : (555) 777-6666",
                "Delivery Location",
                "Harbor Auto Receiving",
                "555 Harbor Blvd",
                "Long Beach, CA 90802",
                "Phone : (555) 444-3333",
                "Vehicle Information - 1 Vehicle",
                "Year",
                "Make",
                "Model",
                "Type",
                "Condition",
                "Color",
                "Plate",
                "Vin",
                "Lot #",
                "2020",
                "Toyota",
                "Camry",
                "Car",
                "Running",
                "Silver",
                "4T1BF1FK5LU123456",
                "Additional Comments",
                "Delivery Window: 4/10/2024 - 4/15/2024 *** PLEASE DO NOT ACCEPT WITH OVER 1/4 TANK OF GAS OR ANY CRACKS IN THE WINDSHIELD ***",
                "Vin#4T1BF1FK5LU123456 Booking#223344 *** DRIVERS MUST CALL TO MAKE AN APPOINTMENT FOR PICK UP OR DELIVERY 24 HOURS IN ADVANCE ***",
                "https://www.v2dispatch.com/print.php",
                "1/2",
            ],
            2: [
                "10/29/24, 12:15 PM",
                "V2 Dispatch | Auto Transport Dispatch Simplified",
                "Load Payment",
                "Total Payment",
                "$920",
                "Collect On Delivery",
                "$0",
                "Agent Pays Carrier",
                "$920",
                "Payment will be processed upon confirmation of delivery.",
                "Contract Terms",
                "- As a courtesy, please give clients a call at least 1-2 hours prior to picking up or delivering a vehicle.",
                "- All drivers should fill out a BOL upon pickup and delivery. Please call National Auto Movers if there are any circumstances which prevent driver from doing so.",
                "- Any vehicle that is listed as INOP must be loaded & unloaded with a winch.",
                "- Dry run fees will not be paid out unless agreed upon before assignment of the load.",
                "- We ask that all carriers call in if and when cancelling a load.",
                "- Any additional funds requested for vehicle modifications, items, etc. will not be paid unless discussed BEFORE the vehicle is loaded. * MUST CONTACT",
                "US*",
                "Authority to transport this vehicle is hereby assigned to Eagle Express. By accepting this agreement Eagle Express certifies that is has the proper legal authority and insurance",
                "to carry the above described vehicle, only on trucks owned by Eagle Express.",
                "@ 2021 V2 Dispatch Inc.",
                "https://www.v2dispatch.com/print.php",
                "2/2",
            ],
        },
    )


def _super_dispatch_backlotcars() -> dict:
    """Super Dispatch / BacklotCars format — mirrors Y605399 format.

    Three-page dispatch with carrier info, order info, vehicle table,
    pickup/delivery, dispatch instructions, and long contract terms.
    Expected: pay=1350.00, date=04/22/2024
    """
    return _build_fixture(
        source_path="X789012 2021 Ford F-150.pdf",
        content_hash="cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66",
        pages={
            1: [
                "Order ID: X789012",
                "Dispatch Sheet",
                "OPENLANE dba",
                "BacklotCars Inc",
                "Shipper",
                "1100 Main St #1500",
                "Kansas City, MO 64105",
                "Co. Phone: 816-298-8222",
                "Email: transport@openlane.com",
                "Carrier Information",
                "Carrier: EAGLE EXPRESS INC",
                "1200 Commerce Blvd #300",
                "TORRANCE, California 90501",
                "Order Information",
                "Dispatch Date: 04/18/2024",
                "Carrier Pickup Estimated:",
                "04/22/2024",
                "Carrier Delivery Estimated:",
                "04/25/2024",
                "Ship Via: OPEN",
                "Condition: Operable",
                "OPENLANE",
                "Contact: John",
                "Phone: 5551234567",
                "Email: Dispatch@eagleexpress.com",
                "Total Payment to Carrier: $1,350.00",
                "Payment method:",
                "Payment terms: ACH",
                "Shipper owes Carrier: $1,350.00",
                "Billing Information",
                "Contact:",
                "Phone:",
                "Email:",
                "Vehicle Information",
                "Total Vehicles: 1",
                "#",
                "Vehicle",
                "Type",
                "Color",
                "VIN",
                "Lot #",
                "1 2021 Ford F-150",
                "Pickup",
                "White",
                "1FTFW1E86MFA12345",
                "Pickup Information",
                "Name: Sam Williams",
                "DESERT AUTO GROUP",
                "4500 EAST MAIN DRIVE",
                "FLAGSTAFF, AZ 86004",
                "Phone: 5556667777",
                "Mobile:",
                "Notes: Gate release code: 7K2N88. Pickup",
                "instructions:",
                "Delivery Information",
                "Name: TOM BROWN",
                "CAROLINA AUTO SALES INC",
                "1500 West Garrison Blvd",
                "Gastonia, NC 28054",
                "Phone: 5558889999",
                "Mobile:",
                "Notes: Drop off instructions: CALL CALL",
                "CALL 24 hrs in advance DON'T USE HOURS",
                "Tom 555-888-9999 Maria 555-777-1234",
                "Please do not leave vehicles unattended",
                "AUTHORIZATION OF DROP MUST BE CONFIRMED",
            ],
            2: [
                "DISPATCH INSTRUCTIONS",
                "Dry run fees (DRF) will only be paid if the vehicle availability has been confirmed by the carrier along with the",
                "customer's name who provided confirmation.",
                "UNATTENDED DROPS It is MANDATORY that we receive pictures for ALL unattended deliveries including pictures of",
                "the vehicle location, pictures of all 4 angles of car (front, back, and both sides) and pictures of key location.",
                "CONTRACT TERMS *** PLEASE READ CAREFULLY ***",
                "Please provide at least 24-hour notice to the customer before Pickup and Delivery. Please complete a careful",
                "inspection of the vehicle on Pickup.",
                "Carrier Terms & Agreement",
                "Every shipment tendered to a Carrier by BacklotCars will be subject to the terms of the BacklotCars Broker-Carrier Agreement;",
                "BacklotCars' Terms and Conditions, to the extent applicable which are posted online at (www.backlotcars.com); and applicable",
                "law.",
                "In the event of a conflict between the terms and provisions of the BacklotCars Broker-Carrier Agreement and the BacklotCars'",
                "Terms and Conditions, the terms and provisions of the Agreement shall control.",
                "Documentation and General Procedures:",
                "1. Carrier should contact customers at least two (2) hours prior to pick up or delivery of a vehicle to schedule a convenient time",
                "during normal business hours for access. Failure to schedule an appointment may result in a missed or delayed pick up or",
                "delivery. BacklotCars will not incur any dry run fees as a result of Carrier's failure to schedule an appointment.",
                "2. In the event that Carrier is unable to perform the requested Services, Carrier shall notify BacklotCars within one (1) day after",
                "Carrier determines it is unable to perform the requested Services.",
                "3. Carrier shall not disclose or discuss the terms of the BacklotCars Broker-Carrier Agreement including the rates or the",
                "valuation of the Services with customers or other third parties.",
                "4. Carrier will be responsible for loading and unloading all shipments. Carrier must utilize appropriate equipment, including a",
                "winch for inoperable vehicles, when loading and unloading vehicles.",
                "5. Carrier must verify that the vehicle identification number (VIN) on the BacklotCars dispatch paperwork matches the VIN on",
                "the vehicle. Any discrepancies must be reported to BacklotCars prior to pick up.",
            ],
            3: [
                "6. Carrier shall not, under any circumstances aside from loading and unloading, drive any vehicle consigned to them unless",
                "given specific approval from BacklotCars. Driving vehicles without authorization will result in non-payment of carriage as well as",
                "any additional BacklotCars Customer imposed penalties (including, but not limited to, additional mileage charges).",
                "7. Carrier shall provide evidence of pickup in the form designated by BacklotCars indicating the quantity of vehicles picked up,",
                "a description of each vehicle including its condition, odometer reading, BacklotCars Order ID, VIN(s), and the legible name and",
                "signature of a representative of the pickup location.",
                "8. Carrier will deliver all vehicles to the appropriate destination as listed on the pickup notice. Carrier shall be liable for any",
                "damages resulting from delivery at an alternative destination.",
                "9. Carrier shall provide to BacklotCars, within twenty-four (24) hours of delivery, an invoice and detailed condition report",
                "containing the quantity of vehicles delivered, a description of each vehicle and its condition, VIN(s), and acknowledgement of",
                "delivery by the recipient of the shipment, including the recipient's legible name and signature.",
                "10. BacklotCars pays Carrier, via ACH, all complete and undisputed amounts set forth in each Carrier invoice in full within thirty",
                "(30) days from the date of BacklotCars' receipt of the invoice.",
                "Powered by Super Dispatch",
                "This agreement is made by and between a \"Carrier\" and a \"Broker / Shipper\". Super Dispatch",
                "Inc. and its affiliates are not party to this agreement. Super Dispatch Inc. and affiliates",
                "have no obligation under this agreement and expressly disclaim any and all liability and",
                "warranties arising out of, or in connection with this agreement.",
            ],
        },
    )


def _multi_vehicle_central_dispatch() -> dict:
    """CentralDispatch with multiple vehicles — mirrors 44445 BIRM format.

    Two-page dispatch shipping 3 vehicles at once, higher total payment.
    Expected: pay=4500.00, date=05/06/2024
    """
    return _build_fixture(
        source_path="55678 EAST 2022 BMW X5.pdf",
        content_hash="dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11",
        pages={
            1: [
                "Carrier Information",
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
                "Order Information",
                "Dispatch Date: 05/01/2024",
                "Pickup Estimated: 05/06/2024",
                "Delivery Estimated: 05/11/2024",
                "Ship Via: Open",
                "Condition: Operable",
                "Price Listed: N/A",
                "Total Payment to Carrier: $4,500.00",
                "On Delivery to Carrier: None",
                "Company* owes Carrier: $4,500.00",
                "Luxury Auto Relocation Inc agrees to pay Eagle Express Inc $4,500.00 within 10",
                "business days of receiving a signed Bill of Lading. Payment will be made with Certified Funds.",
                "*The company (broker, dealer, auction, rental company, etc.) that originated this dispatch sheet.",
                "Total Vehicles: 3",
                "1 2022",
                "Type: SUV Color: White Plate: VIN: 5UXCR6C09N9K12345 Lot #: Additional Info: MUST CHECK FOR MILEAGE : 200 AND",
                "bmw x5",
                "UNDER IS OK FOR PICK UP, MUST PICK UP 2 SETS OF KEYS",
                "2 2022",
                "Type: SUV Color: Black Plate: VIN: 5UXCR6C09N9K67890 Lot #: Additional Info: MUST CHECK FOR MILEAGE : 200 AND",
                "bmw x5",
                "UNDER IS OK FOR PICK UP, MUST PICK UP 2 SETS OF KEYS",
                "3 2022",
                "Type: SUV Color: Gray Plate: VIN: 5UXCR6C09N9K11223 Lot #: Additional Info: MUST CHECK FOR MILEAGE : 200 AND",
                "bmw x3",
                "UNDER IS OK FOR PICK UP, MUST PICK UP 2 SETS OF KEYS",
                "Pickup Information",
                "Name: East Coast BMW",
                "500 Auto Center Drive",
                "birmingham, AL 35210",
                "Phone: (555) 444-5555",
                "Delivery Information",
                "Name: West Coast Imports",
                "8000 Auto Center Dr",
                "buena park, CA 90621",
                "Phone: (555) 666-7777",
                "DISPATCH INSTRUCTIONS",
                "This should be picked up within 2 days of 05/06/2024. This should be delivered within 2 days of 05/11/2024.",
                "Order ID: 55678 EAST",
                "Dispatch Sheet",
                "CentralDispatch",
                "by Cox Automotive",
                "Luxury Auto",
                "Relocation Inc",
                "500 Wake Forest Road #100",
                "raleigh, NC 27601",
                "Co. Phone: (555) 888-1111",
                "Dispatch Info",
                "Contact: Jennifer",
                "Phone: (555) 888-1111",
                "Fax: (555) 888-1112",
                "MC #: 998877",
                "Vehicle Information",
            ],
            2: [
                "CONTRACT TERMS",
                "*** PLEASE READ CAREFULLY ***",
                "****** PLEASE DO NOT EVER DISCUSS PRICES WITH CUSTOMERS ****** IF PRICE OF TRANSPORTATION IS DISCUSS WITH CUSTOMERS THERE WILL",
                "BE A 10% CHARGE FROM TRANSPORTATION AGREED COST.",
                "**** WE DO NOT PAY FOR DRY RUNS*",
                "WE DO NOT PAY FOR DRY RUNS .",
                "Call customers a day in advance to schedule pick up time, if your not able to reach customer, CALL JENNIFER 555-888-1111 immediately,",
                "************ MUST CALL CUSTOMERS IN ADVANCE*",
                "FOR CARRIERS: ZELLE PAYMENT MUST CALL OR EMAIL JENNIFER@555-888-1111 OR JENNIFER@LUXURYAUTO.COM",
                "INVOICES, SIGN DELIVERED BILL OF LADING (BOL), W-9, AND ZELLE INFO. PICTURES MUST BE SENT OVER FOR PAYMENT PROCESS",
                "****",
                "*** VERY IMPORTANT *",
                "PLEASE TEXT OR EMAIL ZELLE INFO WITH PROFILE NAME OF ACCOUNT HOLDER.",
                "WE DO NOT PAY FOR DRY RUNS .",
                "PLEASE GIVE THE CUSTOMER AT LEAST A 24 HOUR NOTICE FOR PICKUP AND DELIVERY. PLEASE DO A THOROUGH INSPECTION OF THE VEHICLE ON",
                "PICKUP.",
                "Authority to transport this vehicle is hereby assigned to Eagle Express Inc. By accepting this agreement Eagle Express Inc certifies that it has the",
                "proper legal authority and insurance to carry the above described vehicle, only on trucks owned by Eagle Express Inc. All invoices must be",
                "accompanied by a signed delivery receipt and faxed to Luxury Auto Relocation Inc. The above agreed upon price includes any and all",
                "surcharges unless otherwise agreed to by both Eagle Express Inc and Luxury Auto Relocation Inc.",
                "The agreement between Eagle Express Inc and Luxury Auto Relocation Inc, as described in this dispatch sheet, is solely between Eagle Express",
                "Inc and Luxury Auto Relocation Inc. Dealertrack Central Dispatch, Inc. is not a party to such agreement, has no obligation under such",
                "agreement and expressly disclaims all liability whatsoever arising out of, or in connection with such agreement.",
                "CD reference # 40334455",
            ],
        },
    )


def _cod_settlement() -> dict:
    """CentralDispatch with COD — three competing dollar amounts on one page.

    Based on RM24105 (Toyota Tacoma). Contains:
      - "Total Payment to Carrier: $1,400.00"  ← correct carrier pay
      - "On Delivery to Carrier: $1,750.00 *COD"  ← COD amount paid by customer
      - "Carrier owes Company **: $350.00 after COD is paid"  ← broker rebate

    A naive extractor may grab $1,750 (highest amount) or $350 (net after COD).
    The correct answer is $1,400.00 — the gross payment to the carrier.
    Expected: pay=1400.00, date=03/12/2024
    """
    return _build_fixture(
        source_path="CODX9999 2002 Toyota Tacoma.pdf",
        content_hash="ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22",
        pages={
            1: [
                "Carrier Information",
                "Carrier: Eagle Express Inc",
                "1200 Commerce Blvd STE# 300",
                "torrance, CA 90501",
                "MC Number: 1234567",
                "Driver: TBD John",
                "Driver Phone: (555) 123-4567",
                "Order Information",
                "Dispatch Date: 03/08/2024",
                "Pickup Estimated: 03/12/2024",
                "Delivery Estimated: 03/19/2024",
                "Ship Via: Open",
                "Condition: Operable",
                "Eagle Express Inc agrees to pay Riverside Logistics LLC $350.00 within 5 business days of delivery.",
                "Payment will be made with Company Check.",
                "*Cash/Certified Funds on Delivery.",
                "** The company (broker, dealer, auction, etc.) that originated this dispatch sheet.",
                "Vehicle Information",
                "1 2002 toyota tacoma  Type: Pickup  Color: Gray  VIN: 5TENX22N02Z123456  Lot #: 749",
                "Pickup Information",
                "Name: OFFICE (AUCTION HOUSE)",
                "1618 AUCTION DR",
                "pelzer, SC 29669",
                "Phone: 844-450-4960",
                "Delivery Information",
                "Name: BOB JONES",
                "1326 WEST CHANNEL ISLANDS BLVD",
                "oxnard, CA 93033",
                "Phone: 805-555-8640",
                "DISPATCH INSTRUCTIONS",
                "This should be picked up within 2 days of 03/12/2024.",
                "This should be delivered within 2 days of 03/19/2024.",
                "CONTRACT TERMS",
                "*** PLEASE READ CAREFULLY ***",
                "Do not discuss rates with customer!",
                "PLEASE GIVE THE CUSTOMER AT LEAST A 24 HOUR NOTICE FOR PICKUP AND DELIVERY.",
                "Authority to transport this vehicle is hereby assigned to Eagle Express Inc.",
                "CD reference # 40261923",
                "Contact: John, Mike, Sarah",
                "Phone: (555) 123-4567",
                "Phone 2: (555) 987-6543",
                "Fax: (555) 111-2222",
                "Price Listed: N/A",
                "Total Payment to Carrier: $1,400.00",
                "On Delivery to Carrier: $1,750.00 *COD",
                "Carrier owes Company **: $350.00 after COD is paid",
            ],
        },
    )


def _revision_history() -> dict:
    """Super Dispatch sheet with revision table showing old price = $0.00.

    Based on 12853712 (Ford Escape). Contains a revision section:
      Field      Old Value   New Value
      Price      $0.00       $750.00
      Pickup     03/09/2024  03/12/2024

    Then separately the actual payment block: "Total Payment to Carrier: $750.00".
    A naive extractor scanning for dollar amounts may grab $0.00 first.
    The payment terms block also mentions "$50/day storage fee" as noise.
    Expected: pay=750.00, date=03/12/2024
    """
    return _build_fixture(
        source_path="FE12853712 2021 Ford Escape.pdf",
        content_hash="ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33dd44ee55ff66aa11bb22cc33",
        pages={
            1: [
                "Order ID: FE12853712",
                "ShipYourCarNow",
                "Powered by Super Dispatch",
                "Shipper",
                "888 Freight Lane",
                "Austin, TX 78701",
                "Co. Phone: 512-555-7890",
                "Email: dispatch@sycn.com",
                "Carrier Information",
                "Carrier: EAGLE EXPRESS INC",
                "1200 Commerce Blvd #300",
                "TORRANCE, California 90501",
                "Contact: John",
                "Phone: 5551234567",
                "Email: Dispatch@eagleexpress.com",
                "Order Information",
                "Dispatch Date: 03/09/2024",
                "Carrier Pickup Exact: 03/12/2024",
                "Carrier Delivery Not Later Than: 03/15/2024",
                "Ship Via: OPEN",
                "Condition: Operable",
                "Total Payment to Carrier: $750.00",
                "Carrier owes Shipper: $ 0.00",
                "Shipper owes Carrier: $750.00",
                "Payment terms: NET 30 / ACH",
                "Vehicle Information",
                "Total Vehicles: 1",
                "#   Vehicle             Type   Color   VIN",
                "1   2021 Ford Escape    SUV    Blue    1FMCU9G60MUA12345",
                "Pickup Information",
                "Name: JOSHUA GREEN",
                "Sunrise Mazda",
                "451 Auto Row Pkwy",
                "Roseville, CA 95661",
                "Phone: 9165554321",
                "Delivery Information",
                "Name: DANIELLE MOORE",
                "Coastal Auto Group",
                "777 Ocean Drive",
                "miami, FL 33139",
                "Phone: 3055557890",
            ],
            2: [
                "REVISIONS",
                "Mar 9, 2024 at 12:47 PM",
                "Order Modified",
                "Updated by Shipper",
                "Field         Old Value     New Value",
                "Price         $0.00         $750.00",
                "Pickup Date   03/09/2024    03/12/2024",
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
            ],
        },
    )


def _noisy_boilerplate() -> dict:
    """Super Dispatch / BacklotCars sheet dense with penalty dollar amounts.

    Based on Y605399 / A768103 pattern. Contains near the real pay line:
      - "$50/day storage fee" in contract terms
      - "3% discount for express payment"
      - "not exceed $100 per day penalty"
    The correct pay is the "Total Payment to Carrier: $944.00" line.
    Expected: pay=944.00, date=03/16/2024
    """
    return _build_fixture(
        source_path="NOISY567 2020 Jeep Wrangler.pdf",
        content_hash="aabb1122cc33dd44ee55ff66aabb1122cc33dd44ee55ff66aabb1122cc33dd44",
        pages={
            1: [
                "Order ID: NOISY567",
                "Dispatch Sheet",
                "OPENLANE dba",
                "BacklotCars Inc",
                "Shipper",
                "1100 Main St #1500",
                "Kansas City, MO 64105",
                "Co. Phone: 816-298-8222",
                "Email: transport@openlane.com",
                "Carrier Information",
                "Carrier: EAGLE EXPRESS INC",
                "1200 Commerce Blvd #300",
                "TORRANCE, California 90501",
                "Order Information",
                "Dispatch Date: 03/12/2024",
                "Carrier Pickup Estimated:",
                "03/16/2024",
                "Carrier Delivery Estimated:",
                "03/20/2024",
                "Ship Via: OPEN",
                "Condition: Operable",
                "OPENLANE",
                "Contact: Mike",
                "Phone: 5551234567",
                "Email: Dispatch@eagleexpress.com",
                "Total Payment to Carrier: $944.00",
                "Payment method:",
                "Payment terms: ACH",
                "Shipper owes Carrier: $944.00",
                "Vehicle Information",
                "Total Vehicles: 1",
                "#   Vehicle              Type   Color   VIN",
                "1   2020 Jeep Wrangler   Car    Red     1C4GJXAG5LW229114",
                "Pickup Information",
                "Name: FLAGSTAFF NISSAN SUBARU",
                "4960 EAST MARKETPLACE DRIVE",
                "FLAGSTAFF, AZ 86001",
                "Phone: (928) 522-6386",
                "Delivery Information",
                "Name: ED VOYLES CHRYSLER DODGE JEEP RAM",
                "789 COBB PARKWAY SOUTH",
                "MARIETTA, GA 30060",
                "Phone: (404) 392-1166",
            ],
            2: [
                "DISPATCH INSTRUCTIONS",
                "Dry run fees (DRF) will only be paid if confirmed by carrier with customer name.",
                "UNATTENDED DROPS: Pictures required for all unattended deliveries.",
                "CONTRACT TERMS *** PLEASE READ CAREFULLY ***",
                "Please provide at least 24-hour notice before Pickup and Delivery.",
                "Carrier Terms & Agreement",
                "BacklotCars pays Carrier, via ACH, all complete and undisputed amounts within",
                "thirty (30) days from the date of BacklotCars' receipt of the invoice.",
                "Express payment option: invoice amount reduced by three percent (3%) of total",
                "for payment within one (1) business day of invoice receipt.",
                "Storage and storage fees accrued as a result of Carrier delay are the sole",
                "responsibility of Carrier. Storage fees not to exceed $100 per day.",
                "BacklotCars may withhold payment to protect itself from services not performed",
                "in accordance with this Agreement or from claims arising out of Carrier performance.",
                "Failure to submit invoice may result in delay in payment and/or non-payment.",
                "Carrier must report any delay in pickup or delivery to BacklotCars immediately.",
                "Carrier shall not pick up a vehicle and hold prior to delivery to BacklotCars.",
                "Load building should occur prior to pickup — not during transit.",
                "Powered by Super Dispatch",
            ],
        },
    )


def _multi_date_formats() -> dict:
    """V2 Dispatch with multiple date types that could confuse extraction.

    Based on R667644. Contains:
      - "10/29/24, 12:15 PM" — PDF print timestamp at top of page
      - "Dispatch Date: March 2, 2024 (Sat)" — dispatch date (wrong choice)
      - "Pickup Date: March 13, 2024 (Wed)" — correct pickup date
      - "Delivery Date: March 20, 2024 (Wed)" — delivery date (wrong choice)
      - "Last Update: March 20, 2024 at 11:52 AM" — metadata timestamp

    The correct date is the Pickup Date. Extraction must not grab the PDF
    print timestamp, the dispatch date, or the delivery date.
    Expected: pay=820.00, date contains "March 13, 2024"
    """
    return _build_fixture(
        source_path="MULTI667 2017 Chevrolet SS.pdf",
        content_hash="1122aabb3344ccdd5566eeff1122aabb3344ccdd5566eeff1122aabb3344ccdd",
        pages={
            1: [
                "10/29/24, 12:15 PM",
                "V2 Dispatch | Auto Transport Dispatch Simplified",
                "Dispatch Details | Load #MULTI667",
                "Order ID",
                "MULTI667",
                "Current Status",
                "Delivered",
                "Last Update",
                "March 20, 2024 at 11:52 AM",
                "V2D Reference #",
                "988343",
                "Dispatch Date",
                "March 2, 2024 (Sat)",
                "Pickup Date",
                "March 13, 2024 (Wed)",
                "Delivery Date",
                "March 20, 2024 (Wed)",
                "Carrier Type",
                "Open",
                "Carrier Information",
                "Eagle Express",
                "1200 Commerce Blvd Ste B300",
                "Torrance, CA 90501",
                "Driver Name : John Doe",
                "Driver Phone : (555) 123-4567",
                "Office Phone : (555) 123-4567",
                "Agent Information",
                "RoadRunner Auto Transport",
                "15 Grumman Rd W Ste 1500",
                "Bethpage, NY 11714",
                "Contact : Chris, Shawn, Carlos",
                "Phone : (555) 605-2666",
                "MC Number : 89820",
                "Pickup Location",
                "Sam Torres",
                "565 Emerald Lake Dr",
                "Fayetteville, GA 30215",
                "Phone : (555) 704-5507",
                "Delivery Location",
                "Pasha Auto",
                "15501 Texaco Ave.",
                "Paramount, CA 90723",
                "Phone : (555) 363-7485",
                "Vehicle Information - 1 Vehicle",
                "Year   Make        Model   Type   Condition   Color   Vin",
                "2017   Chevrolet   SS      Car    Running     Black   6G3F15RW7HL308730",
                "Additional Comments",
                "Delivery Window: 3/19/2024 - 3/25/2024",
                "*** PLEASE DO NOT ACCEPT WITH OVER 1/4 TANK OF GAS ***",
                "https://www.v2dispatch.com/print.php",
                "1/2",
            ],
            2: [
                "10/29/24, 12:15 PM",
                "V2 Dispatch | Auto Transport Dispatch Simplified",
                "Load Payment",
                "Total Payment",
                "$820",
                "Collect On Delivery",
                "$0",
                "Agent Pays Carrier",
                "$820",
                "Payment will be processed upon confirmation of delivery.",
                "Contract Terms",
                "- As a courtesy, please give clients a call 1-2 hours prior to pickup or delivery.",
                "- All drivers should fill out a BOL upon pickup and delivery.",
                "- Any vehicle listed as INOP must be loaded & unloaded with a winch.",
                "- Dry run fees will not be paid unless agreed upon before assignment.",
                "- We ask that all carriers call in if and when cancelling a load.",
                "Authority to transport this vehicle is hereby assigned to Eagle Express.",
                "By accepting this agreement Eagle Express certifies that it has the proper legal",
                "authority and insurance to carry the above described vehicle.",
                "@ 2021 V2 Dispatch Inc.",
                "https://www.v2dispatch.com/print.php",
                "2/2",
            ],
        },
    )


def _sparse_tms_print() -> dict:
    """Super Dispatch Carrier TMS print — sparse layout with ambiguous payment status.

    Based on 33702085/33702194 (Nissan Frontier trio). The TMS print shows:
      - "Price  $800.00" in a structured field row
      - "Method  QuickPay"
      - "No Payment received."  ← accounts-receivable status, NOT the price
      - "Broker Fee  No details"
      - "Driver Pay  No details"

    The correct pay is $800.00 (the price of the load). "No Payment received"
    is a receivables flag, not a denial of the price. The print timestamp
    "10/29/24, 12:15 PM" is again present at the top.
    Expected: pay=800.00, date=03/13/2024 (Pickup date)
    """
    return _build_fixture(
        source_path="TMS337 2024 Nissan Frontier.pdf",
        content_hash="ccdd3344eeff5566aabb1122ccdd3344eeff5566aabb1122ccdd3344eeff5566",
        pages={
            1: [
                "10/29/24, 12:15 PM",
                "Loads - Carrier TMS",
                "carrier.superdispatch.com/loads/12345678/print",
                "Load Details",
                "Load ID",
                "TMS337",
                "Status",
                "Delivered",
                "Dispatcher",
                "John Doe",
                "Carrier",
                "Eagle Express",
                "Load Details",
                "Lot Number",
                "Price",
                "27MHSYN",
                "$800.00",
                "Method",
                "Pickup Date",
                "QuickPay",
                "03/11/2024",
                "Delivery Date",
                "03/13/2024",
                "Broker",
                "Anew Transport LLC",
                "Broker Phone",
                "Broker Email",
                "(555) 400-1234",
                "contact@anewtransport.com",
                "Vehicle Details",
                "Lot Number",
                "Price",
                "27MHSYN",
                "$800.00",
                "Pickup",
                "Name",
                "Address",
                "Phone",
                "Jack Smith",
                "5010 Slide Rd, Lubbock, TX 79414",
                "(555) 745-0001",
                "Delivery",
                "Name",
                "Address",
                "Phone",
                "Dale Martin",
                "2640 Denton Dr, Dallas, TX 75235",
                "(555) 352-7777",
                "Vehicle",
                "VIN",
                "Color",
                "Year",
                "Make",
                "Model",
                "7N8AT4MT0LA123456",
                "Gray",
                "2024",
                "Nissan",
                "Frontier",
                "Pickup Date",
                "03/11/2024",
                "Delivery Date",
                "03/13/2024",
                "Scheduled",
                "Picked Up",
                "Delivered",
                "03/11/2024",
                "03/11/2024 at 10:15 AM",
                "03/13/2024 at 2:58 PM",
                "Invoiced",
                "03/14/2024",
                "Payment",
                "No Payment received.",
                "Broker Fee",
                "Driver Pay",
                "No details",
                "No details",
            ],
        },
    )


def _multi_load_settlement() -> dict:
    """Settlement statement listing three distinct loads.

    Mirrors the case_2 production layout where one PDF aggregates several
    weekly loads with their own date and pay value.  Layout deliberately
    interleaves each load's date and pay on adjacent lines so the
    date-anchored resolver can pick the correct pay per load even when
    other dollar amounts (boilerplate fees, totals) are present nearby.

    Expected (per ExtractedLoad):
        loads[0]: date=03/05/2024, pay=$1,250.00
        loads[1]: date=03/12/2024, pay=$2,400.00
        loads[2]: date=03/19/2024, pay=$875.50
    """
    return _build_fixture(
        source_path="MultiLoad_Settlement_2024Q1.pdf",
        content_hash="11aa22bb33cc44dd55ee66ff11aa22bb33cc44dd55ee66ff11aa22bb33cc44dd",
        pages={
            1: [
                "SETTLEMENT STATEMENT",
                "Carrier: ACME Trucking LLC",
                "Payee: Joe Doe",
                "Period: 03/01/2024 - 03/31/2024",
                "MC Number: 9999999",
                "",
                "Load Detail",
                "Each load below is paid separately upon delivery confirmation.",
                "Settlement totals appear at the bottom of the statement.",
                "",
                "Load 1 of 3",
                "Pickup Date: 03/05/2024",
                "Origin: Cleveland, OH",
                "Destination: Pittsburgh, PA",
                "Reference: BOL-1001",
                "Total Payment to Carrier: $1,250.00",
                "",
                "Load 2 of 3",
                "Pickup Date: 03/12/2024",
                "Origin: Detroit, MI",
                "Destination: Buffalo, NY",
                "Reference: BOL-1002",
                "Total Payment to Carrier: $2,400.00",
                "",
                "Load 3 of 3",
                "Pickup Date: 03/19/2024",
                "Origin: Akron, OH",
                "Destination: Erie, PA",
                "Reference: BOL-1003",
                "Total Payment to Carrier: $875.50",
                "",
                "Settlement Totals",
                "Gross Pay: $4,525.50",
                "Deductions: $0.00",
                "Net Pay to Carrier: $4,525.50",
                "Payment terms: Net 30 / ACH",
                "Authority to transport vehicles is hereby assigned to ACME Trucking LLC.",
            ],
        },
    )


def _multi_load_duplicate_pay() -> dict:
    """Two loads on different dates that happen to share the same pay value.

    This is a regression fixture for the date-anchored source-location
    resolver: a naive ``re.search`` would always pick the first occurrence
    of ``$1,200.00`` for both loads.  The resolver must use each load's
    sibling date as an anchor to land on the correct OCR span.

    Expected:
        loads[0]: date=04/02/2024, pay=$1,200.00 (first $1,200 in OCR)
        loads[1]: date=04/16/2024, pay=$1,200.00 (second $1,200 in OCR)
    """
    return _build_fixture(
        source_path="MultiLoad_DuplicatePay_April.pdf",
        content_hash="22bb33cc44dd55ee66ff11aa22bb33cc44dd55ee66ff11aa22bb33cc44dd55ee",
        pages={
            1: [
                "SETTLEMENT STATEMENT",
                "Carrier: ACME Trucking LLC",
                "Payee: Joe Doe",
                "Period: 04/01/2024 - 04/30/2024",
                "",
                "Load 1",
                "Pickup Date: 04/02/2024",
                "Origin: Columbus, OH",
                "Destination: Indianapolis, IN",
                "Total Payment to Carrier: $1,200.00",
                "",
                "Load 2",
                "Pickup Date: 04/16/2024",
                "Origin: Cincinnati, OH",
                "Destination: Louisville, KY",
                "Total Payment to Carrier: $1,200.00",
                "",
                "Settlement Totals",
                "Gross Pay: $2,400.00",
                "Net Pay to Carrier: $2,400.00",
            ],
        },
    )


def _single_load_settlement() -> dict:
    """A single-load settlement to confirm the new schema handles N=1.

    The ``loads`` array must always be present; single-load documents
    return a one-element array with no special branching.

    Expected:
        loads[0]: date=05/10/2024, pay=$985.00
    """
    return _build_fixture(
        source_path="SingleLoad_Settlement.pdf",
        content_hash="33cc44dd55ee66ff11aa22bb33cc44dd55ee66ff11aa22bb33cc44dd55ee66ff",
        pages={
            1: [
                "Settlement Statement",
                "Carrier: ACME Trucking LLC",
                "Payee: Joe Doe",
                "",
                "Pickup Date: 05/10/2024",
                "Origin: Toledo, OH",
                "Destination: Lansing, MI",
                "Reference: BOL-2001",
                "Total Payment to Carrier: $985.00",
                "Payment terms: Net 30",
            ],
        },
    )


_ALL_FIXTURES = {
    "central_dispatch_settlement.json": _central_dispatch_settlement,
    "v2_dispatch_load.json": _v2_dispatch_load,
    "super_dispatch_backlotcars.json": _super_dispatch_backlotcars,
    "multi_vehicle_central_dispatch.json": _multi_vehicle_central_dispatch,
    # Edge-case fixtures that stress extraction logic
    "cod_settlement_ocr.json": _cod_settlement,
    "revision_history_ocr.json": _revision_history,
    "noisy_boilerplate_ocr.json": _noisy_boilerplate,
    "multi_date_formats_ocr.json": _multi_date_formats,
    "sparse_tms_print_ocr.json": _sparse_tms_print,
    # Multi-load fixtures (one Excel row per load downstream)
    "multi_load_settlement.json": _multi_load_settlement,
    "multi_load_duplicate_pay.json": _multi_load_duplicate_pay,
    "single_load_settlement.json": _single_load_settlement,
}


def generate_all() -> None:
    for filename, builder in _ALL_FIXTURES.items():
        data = builder()
        path = _FIXTURES_DIR / filename
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        line_count = len(data["lines"])
        page_count = len(data["pages"])
        print(f"  {filename}: {line_count} lines, {page_count} page(s)")


if __name__ == "__main__":
    generate_all()
