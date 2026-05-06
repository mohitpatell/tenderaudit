#!/usr/bin/env python3
"""TenderAudit — Demo Tender PDF Generator.

Produces a single tender PDF at ``seed/pdfs/demo-tender-armoured-vehicles.pdf``
whose six eligibility criteria are calibrated to map directly to the four
bidder profiles produced by ``gen_demo_zips.py``:

    Mahindra Defence       -> all 6 criteria pass clearly  -> Eligible
    BEML Limited           -> turnover fails (3.21 Cr < 5 Cr) -> NotEligible
    Tata Advanced Systems  -> ISO 9001 missing (only 14001) -> NotEligible
    Force Motors           -> ISO scope wrong plant + stale  -> NeedsReview
                              affidavit + borderline net worth

Usage
-----
    python scripts/gen_demo_tender.py
    python scripts/gen_demo_tender.py --force      # overwrite if exists
"""

from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(PROJECT_ROOT, "seed", "pdfs")
OUT_PATH = os.path.join(OUT_DIR, "demo-tender-armoured-vehicles.pdf")


def get_rl() -> dict:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
            Table, TableStyle, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
    except ImportError:
        print("[ERROR] reportlab is not installed. "
              "Activate api/.venv first: source api/.venv/bin/activate")
        sys.exit(1)
    return {
        "A4": A4, "getSampleStyleSheet": getSampleStyleSheet,
        "ParagraphStyle": ParagraphStyle, "cm": cm, "colors": colors,
        "SimpleDocTemplate": SimpleDocTemplate, "Paragraph": Paragraph,
        "Spacer": Spacer, "HRFlowable": HRFlowable, "Table": Table,
        "TableStyle": TableStyle, "PageBreak": PageBreak,
        "TA_CENTER": TA_CENTER, "TA_RIGHT": TA_RIGHT,
        "TA_LEFT": TA_LEFT, "TA_JUSTIFY": TA_JUSTIFY,
    }


def _styles(rl: dict) -> dict:
    PS = rl["ParagraphStyle"]
    base = rl["getSampleStyleSheet"]()
    colors = rl["colors"]
    return {
        "title": PS("T", parent=base["Normal"], fontSize=14,
                    fontName="Helvetica-Bold", alignment=rl["TA_CENTER"],
                    spaceAfter=6),
        "subtitle": PS("ST", parent=base["Normal"], fontSize=10,
                       alignment=rl["TA_CENTER"], spaceAfter=4),
        "h1": PS("H1", parent=base["Normal"], fontSize=12,
                 fontName="Helvetica-Bold", alignment=rl["TA_LEFT"],
                 spaceAfter=4, spaceBefore=12, textColor=colors.HexColor("#1a3d6b")),
        "h2": PS("H2", parent=base["Normal"], fontSize=10.5,
                 fontName="Helvetica-Bold", alignment=rl["TA_LEFT"],
                 spaceAfter=3, spaceBefore=8),
        "body": PS("B", parent=base["Normal"], fontSize=9.5,
                   leading=14, alignment=rl["TA_JUSTIFY"], spaceAfter=4),
        "clause": PS("C", parent=base["Normal"], fontSize=9.5,
                     leading=14, alignment=rl["TA_JUSTIFY"], spaceAfter=4,
                     leftIndent=18, firstLineIndent=-18),
        "small": PS("S", parent=base["Normal"], fontSize=8.5,
                    leading=11, alignment=rl["TA_LEFT"], spaceAfter=3,
                    textColor=colors.grey),
        "right": PS("R", parent=base["Normal"], fontSize=9.5,
                    alignment=rl["TA_RIGHT"], spaceAfter=2),
    }


def _divider(rl: dict):
    return rl["HRFlowable"](width="100%", thickness=0.5,
                            color=rl["colors"].black)


def _sp(rl: dict, h: float = 0.3):
    return rl["Spacer"](1, h * rl["cm"])


def _build(out_path: str) -> None:
    rl = get_rl()
    st = _styles(rl)
    P = rl["Paragraph"]
    PB = rl["PageBreak"]

    doc = rl["SimpleDocTemplate"](
        out_path, pagesize=rl["A4"],
        leftMargin=2.0 * rl["cm"], rightMargin=2.0 * rl["cm"],
        topMargin=2.0 * rl["cm"], bottomMargin=2.0 * rl["cm"],
        title="Procurement of Armoured / Special-Mission Vehicles - NIT-71/2024",
    )
    story: list = []

    # ====================== Page 1 — Front matter ======================
    story.append(P("भारत सरकार / GOVERNMENT OF INDIA", st["subtitle"]))
    story.append(P("Ministry of Home Affairs", st["subtitle"]))
    story.append(P("Central Reserve Police Force (CRPF), Directorate General",
                   st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.4))
    story.append(P("NOTICE INVITING TENDER (NIT)", st["title"]))
    story.append(P("e-Procurement of Armoured / Special-Mission Vehicles",
                   st["subtitle"]))
    story.append(P("NIT No.: CRPF/DGS/EQPT/AV/NIT-71/2024-25", st["subtitle"]))
    story.append(_sp(rl, 0.5))

    meta_rows = [
        ["Tender Inviting Authority",
         "Director General, Central Reserve Police Force"],
        ["Issuing Office",
         "Directorate General, CGO Complex, Lodhi Road, New Delhi - 110003"],
        ["NIT Number", "CRPF/DGS/EQPT/AV/NIT-71/2024-25"],
        ["Item of Procurement",
         "Armoured / Special-Mission Vehicles - 240 units (4 variants)"],
        ["Estimated Bid Value", "INR 412 Crore (approximate)"],
        ["Bid Submission Mode",
         "e-Procurement Portal (https://defproc.gov.in)"],
        ["Tender Document Issue Date", "14-March-2025"],
        ["Last Date of Submission", "30-April-2025, 1500 hrs IST"],
        ["Date of Technical Bid Opening", "02-May-2025, 1100 hrs IST"],
        ["Earnest Money Deposit (EMD)",
         "INR 25,00,000 (Twenty-Five Lakh)"],
        ["Tender Document Fee", "Nil (e-tender)"],
        ["Bid Validity", "180 days from date of bid opening"],
    ]
    table = rl["Table"](meta_rows,
                        colWidths=[6 * rl["cm"], 11 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1),
         rl["colors"].HexColor("#1a3d6b")),
        ("TEXTCOLOR", (0, 0), (0, -1), rl["colors"].white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(_sp(rl, 0.4))
    story.append(P(
        "1. Sealed bids in two-bid system (Technical and Financial) are invited "
        "from manufacturers / authorised firms for the supply of Armoured / "
        "Special-Mission Vehicles to the Central Reserve Police Force (CRPF) "
        "for deployment in counter-insurgency, anti-Naxal and frontier "
        "operations. Detailed Qualitative Requirements are placed at "
        "Schedule-I.",
        st["body"]))
    story.append(P(
        "2. Only those bidders meeting <b>each and every</b> eligibility "
        "criterion specified at <b>Section 2 (Eligibility Criteria)</b> below "
        "shall be considered for technical evaluation. Bids failing any "
        "mandatory eligibility criterion shall be summarily rejected.",
        st["body"]))
    story.append(P(
        "3. Bids shall be uploaded on the e-Procurement portal "
        "(https://defproc.gov.in) digitally signed using a Class-3 Digital "
        "Signature Certificate of the authorised signatory of the bidder.",
        st["body"]))
    story.append(PB())

    # ====================== Page 2 — Eligibility Criteria ==============
    story.append(P("SECTION 2 - ELIGIBILITY CRITERIA",
                   st["title"]))
    story.append(P("(All criteria are mandatory; non-compliance with any "
                   "one shall render the bid ineligible.)",
                   st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))

    story.append(P(
        "The Bidder must satisfy <b>all</b> of the following eligibility "
        "criteria. Documentary evidence in respect of each criterion shall "
        "be enclosed with the Technical Bid; bids without supporting "
        "documents shall be rejected without further evaluation.",
        st["body"]))
    story.append(_sp(rl, 0.2))

    # ---- Criterion 1: Turnover ----
    story.append(P("2.1 Average Annual Turnover (Mandatory)", st["h2"]))
    story.append(P(
        "The Bidder shall have an <b>average annual turnover of at least "
        "INR 5,00,00,000 (Indian Rupees Five Crore only)</b> from the "
        "<b>Defence / Special-Vehicles segment</b> over the last three "
        "completed financial years (FY 2021-22, FY 2022-23 and FY 2023-24), "
        "duly certified by a Chartered Accountant in practice along with "
        "the UDIN. Consolidated revenue across non-defence segments shall "
        "<b>not</b> be considered for this purpose.",
        st["clause"]))
    story.append(P(
        "Required Document: CA-attested Certificate of Average Annual "
        "Turnover (Defence segment) on CA letterhead with ICAI Membership "
        "Number and UDIN, supported by audited Profit &amp; Loss statements.",
        st["small"]))

    # ---- Criterion 2: ISO 9001 ----
    story.append(P("2.2 ISO 9001:2015 Quality Management Certification "
                   "(Mandatory)", st["h2"]))
    story.append(P(
        "The Bidder shall hold a <b>valid ISO 9001:2015 (Quality Management "
        "System) certificate</b> issued by a certification body accredited "
        "by the National Accreditation Board for Certification Bodies "
        "(NABCB). The <b>scope of certification</b> shall expressly cover "
        "the manufacturing facility at which the tender work would be "
        "executed. Certificates limited to environmental management "
        "(ISO 14001) or other adjacent standards shall <b>not</b> be "
        "accepted as substitutes for ISO 9001:2015.",
        st["clause"]))
    story.append(P(
        "Required Document: Original ISO 9001:2015 certificate (or "
        "self-attested copy) showing certificate number, issuing body, "
        "scope of certification, and validity dates.",
        st["small"]))

    # ---- Criterion 3: Past Experience ----
    story.append(P("2.3 Prior Government Experience (Mandatory)", st["h2"]))
    story.append(P(
        "The Bidder shall have <b>successfully completed at least three (3) "
        "supply contracts</b> for Armoured / Special-Mission Vehicles for "
        "the Indian Armed Forces, Central Armed Police Forces, paramilitary "
        "or any State Police Organisation in the <b>last five (5) "
        "financial years</b>. Each contract shall be evidenced by a "
        "Performance / Work Completion Certificate issued by the customer.",
        st["clause"]))
    story.append(P(
        "Required Document: Customer-issued Work Completion Certificates "
        "with order value, date of award, date of final acceptance and "
        "remarks on quality of execution.",
        st["small"]))
    story.append(PB())

    # ====================== Page 3 — Continued criteria ===============
    # ---- Criterion 4: Net Worth ----
    story.append(P("2.4 Net Worth (Mandatory)", st["h2"]))
    story.append(P(
        "The Bidder shall have a <b>certified positive Net Worth of at "
        "least INR 2,00,00,000 (Indian Rupees Two Crore only)</b> as at "
        "the latest audited balance-sheet date (31st March 2024), computed "
        "in accordance with Section 2(57) of the Companies Act, 2013.",
        st["clause"]))
    story.append(P(
        "Required Document: CA-attested Net Worth Certificate as at "
        "31-March-2024.",
        st["small"]))

    # ---- Criterion 5: Non-Blacklisting Affidavit ----
    story.append(P("2.5 Non-Blacklisting Self-Declaration (Mandatory)",
                   st["h2"]))
    story.append(P(
        "The Bidder shall submit a <b>Non-Blacklisting Affidavit</b> on "
        "INR 100 non-judicial stamp paper, sworn before a Notary Public, "
        "declaring that the firm has not been blacklisted, debarred or "
        "suspended by any Central / State Government, Public Sector "
        "Undertaking, Armed Force or Public Procurement entity. The "
        "affidavit shall have been sworn <b>not earlier than twelve (12) "
        "months</b> prior to the bid submission date; affidavits older "
        "than 12 months shall not be accepted.",
        st["clause"]))
    story.append(P(
        "Required Document: Original (scanned) affidavit on INR 100 "
        "non-judicial stamp paper, attested by Notary Public.",
        st["small"]))

    # ---- Criterion 6: Class 3 DSC ----
    story.append(P("2.6 Class-3 Digital Signature Certificate (Mandatory)",
                   st["h2"]))
    story.append(P(
        "The authorised signatory of the Bidder shall hold a <b>valid "
        "Class-3 Digital Signature Certificate</b> issued by a Licensed "
        "Certifying Authority under the Information Technology Act, 2000, "
        "for use on the e-Procurement portal. The DSC shall be valid on "
        "the date of bid submission and the bid documents shall be "
        "digitally signed therewith.",
        st["clause"]))
    story.append(P(
        "Required Document: Class-3 DSC details printout showing "
        "Common Name, Organisation, Issuing CA, Serial Number and "
        "validity dates.",
        st["small"]))

    story.append(_sp(rl, 0.3))
    story.append(P("SECTION 3 - SUBMISSION CHECKLIST", st["h1"]))
    story.append(_divider(rl))
    checklist = [
        "[ ] CA-attested Average Annual Turnover certificate "
        "(Defence segment) - covering FY 2021-22 to FY 2023-24",
        "[ ] Audited Profit &amp; Loss statement / Balance sheet extracts "
        "for the last three financial years",
        "[ ] CA-attested Net Worth certificate as at 31-March-2024",
        "[ ] Valid ISO 9001:2015 certificate from NABCB-accredited body, "
        "with scope covering the work facility",
        "[ ] Three (3) Performance / Work Completion certificates from "
        "Government / Armed Forces customers (last 5 financial years)",
        "[ ] Non-Blacklisting Affidavit on INR 100 stamp paper, "
        "notarised within preceding 12 months",
        "[ ] Class-3 Digital Signature Certificate details",
        "[ ] EMD of INR 25,00,000 in the form of Bank Guarantee / FDR / DD",
        "[ ] Pre-contract Integrity Pact, signed",
        "[ ] PAN, GST registration, Certificate of Incorporation",
    ]
    for item in checklist:
        story.append(P(item, st["body"]))

    story.append(_sp(rl, 0.4))
    story.append(P(
        "Sd/- Director General (Procurement)<br/>"
        "Central Reserve Police Force<br/>"
        "[OFFICE SEAL: CRPF DIRECTORATE GENERAL]",
        st["right"]))
    story.append(_sp(rl, 0.3))
    story.append(P(
        "Issued: 14-March-2025  |  NIT No.: CRPF/DGS/EQPT/AV/NIT-71/2024-25",
        st["small"]))

    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the TenderAudit demo tender PDF")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing tender PDF")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(OUT_PATH) and not args.force:
        print(f"[SKIP] {OUT_PATH} (exists; use --force to overwrite)")
        return 0

    print(f"Building demo tender PDF -> {OUT_PATH}")
    _build(OUT_PATH)
    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"Done. {os.path.basename(OUT_PATH)} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
