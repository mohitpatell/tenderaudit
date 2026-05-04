#!/usr/bin/env python3
"""TenderAudit — Synthetic Bidder Bundle Generator.

THE demo asset for the ambiguous-bidder moment.

For each of the 8 tender PDFs in seed/pdfs/, generates 4 bidder bundles under
seed/bidders/{tender_stem}/{profile}/ with 12 visually-plausible PDFs each.

Bidder profiles
---------------
  bidder-a-clean        All documents valid; meets every criterion         → PASS all
  bidder-b-shortfall    Turnover ₹38L (vs ₹41.6L threshold)               → FAIL C1
  bidder-c-missing-iso  No ISO 9001 certificate submitted at all           → FAIL ISO
  bidder-d-ambiguous    ISO expired 2024; name on certs slightly differs   → AMBIGUOUS

Documents per bundle (12 PDFs)
-------------------------------
  01_emd.pdf
  02_tender_acceptance_letter.pdf
  03_integrity_pact.pdf
  04_gst_certificate.pdf
  05_pan_card.pdf
  06_audited_balance_sheet.pdf
  07_ca_avg_turnover_certificate.pdf   ← variant per profile
  08_solvency_certificate.pdf
  09_iso_9001_certificate.pdf          ← absent in bidder-c; expired in bidder-d
  10_experience_certificate.pdf        ← name differs in bidder-d
  11_non_blacklisting_affidavit.pdf
  12_dsc_class3.pdf

After generating, writes seed/bidders/{tender}/manifest.json.

Usage
-----
    python scripts/gen_bidder_bundle.py           # generate all bundles
    python scripts/gen_bidder_bundle.py --force   # regenerate even if exists
    python scripts/gen_bidder_bundle.py --tender crpf-2-bhopal-nit71

Dependencies: reportlab (stdlib only otherwise)
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SEED_PDFS_DIR = os.path.join(PROJECT_ROOT, "seed", "pdfs")
BIDDERS_DIR = os.path.join(PROJECT_ROOT, "seed", "bidders")
GROUND_TRUTH_PATH = os.path.join(PROJECT_ROOT, "seed", "ground_truth.json")

TODAY = date.today()
ISSUE_DATE = TODAY - timedelta(days=30)
VALID_DATE_FUTURE = date(TODAY.year + 2, TODAY.month, TODAY.day)
VALID_DATE_EXPIRED = date(2024, 3, 31)  # expired — bidder-d drama
FY_START = date(TODAY.year - 1, 4, 1)

# ---------------------------------------------------------------------------
# Firm names — the subtle name mismatch is the ambiguous bidder's tell
# ---------------------------------------------------------------------------
FIRM_CLEAN = "M/s Ravi Constructions Pvt. Ltd."
FIRM_SHORTFALL = "M/s Ravi Constructions Pvt. Ltd."
FIRM_MISSING_ISO = "M/s Ravi Constructions Pvt. Ltd."
FIRM_AMBIGUOUS_MAIN = "M/s Ravi Constructions Pvt. Ltd."      # on main docs
FIRM_AMBIGUOUS_CERT = "Ravi Construction Pvt Ltd"              # on certs (subtle diff)

FIRM_ADDRESS = "Plot No. 47, Industrial Estate, Sector-12, Bengaluru – 560 058"
FIRM_GSTIN = "29AABCR1234F1Z5"
FIRM_PAN = "AABCR1234F"
FIRM_CIN = "U45200KA2010PTC052341"
FIRM_PHONE = "+91-80-2345-6789"
FIRM_EMAIL = "tenders@raviconstructions.in"

CA_FIRM = "M/s Sharma & Associates, Chartered Accountants"
CA_MEMBER_NO = "ICAI/MRN/094521"
CA_ADDRESS = "No. 12, MG Road, Bengaluru – 560 001"


# ---------------------------------------------------------------------------
# ReportLab helpers
# ---------------------------------------------------------------------------

def get_rl():
    """Import reportlab components; exit with helpful message if missing."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
        )
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
    except ImportError:
        print("[ERROR] reportlab is not installed. Run: pip install reportlab")
        sys.exit(1)
    return {
        "A4": A4, "getSampleStyleSheet": getSampleStyleSheet,
        "ParagraphStyle": ParagraphStyle, "cm": cm, "colors": colors,
        "SimpleDocTemplate": SimpleDocTemplate, "Paragraph": Paragraph,
        "Spacer": Spacer, "HRFlowable": HRFlowable, "Table": Table,
        "TableStyle": TableStyle,
        "TA_CENTER": TA_CENTER, "TA_RIGHT": TA_RIGHT,
        "TA_LEFT": TA_LEFT, "TA_JUSTIFY": TA_JUSTIFY,
    }


def _styles(rl):
    """Build a dict of named paragraph styles."""
    PS = rl["ParagraphStyle"]
    base = rl["getSampleStyleSheet"]()
    colors = rl["colors"]

    return {
        "title": PS("DocTitle", parent=base["Normal"],
                    fontSize=13, fontName="Helvetica-Bold",
                    alignment=rl["TA_CENTER"], spaceAfter=6, spaceBefore=0),
        "subtitle": PS("DocSub", parent=base["Normal"],
                       fontSize=10, alignment=rl["TA_CENTER"], spaceAfter=4),
        "h2": PS("DocH2", parent=base["Normal"],
                 fontSize=11, fontName="Helvetica-Bold",
                 spaceAfter=3, spaceBefore=8),
        "body": PS("DocBody", parent=base["Normal"],
                   fontSize=9.5, leading=14,
                   alignment=rl["TA_JUSTIFY"], spaceAfter=4),
        "body_left": PS("DocBodyL", parent=base["Normal"],
                        fontSize=9.5, leading=14,
                        alignment=rl["TA_LEFT"], spaceAfter=4),
        "small": PS("DocSmall", parent=base["Normal"],
                    fontSize=8, leading=12,
                    alignment=rl["TA_LEFT"], spaceAfter=3),
        "right": PS("DocRight", parent=base["Normal"],
                    fontSize=9.5, alignment=rl["TA_RIGHT"], spaceAfter=3),
        "stamp": PS("DocStamp", parent=base["Normal"],
                    fontSize=8, textColor=colors.darkblue,
                    alignment=rl["TA_CENTER"], spaceAfter=2),
        "warning": PS("DocWarn", parent=base["Normal"],
                      fontSize=8, textColor=colors.red,
                      alignment=rl["TA_CENTER"], spaceAfter=2),
    }


def _build_doc(path: str, story: list, rl) -> None:
    """Build a simple A4 PDF from story flowables."""
    doc = rl["SimpleDocTemplate"](
        path, pagesize=rl["A4"],
        leftMargin=2.2 * rl["cm"], rightMargin=2.2 * rl["cm"],
        topMargin=2.2 * rl["cm"], bottomMargin=2.2 * rl["cm"],
    )
    doc.build(story)


def _divider(rl, color=None):
    color = color or rl["colors"].black
    return rl["HRFlowable"](width="100%", thickness=0.5, color=color)


def _sp(rl, h=0.3):
    return rl["Spacer"](1, h * rl["cm"])


def _gov_header(rl, st, body_text: str) -> list:
    """Standard GoI letterhead top block."""
    return [
        rl["Paragraph"]("भारत सरकार / GOVERNMENT OF INDIA", st["title"]),
        rl["Paragraph"](body_text, st["subtitle"]),
        _divider(rl),
        _sp(rl, 0.2),
    ]


def _signature_block(rl, st, signer: str, designation: str, org: str,
                     stamp_text: Optional[str] = None) -> list:
    """Signature block with optional stamp."""
    block = [
        _sp(rl, 0.8),
        rl["Paragraph"](f"Sd/-", st["right"]),
        rl["Paragraph"](f"<b>{signer}</b>", st["right"]),
        rl["Paragraph"](designation, st["right"]),
        rl["Paragraph"](org, st["right"]),
    ]
    if stamp_text:
        block += [
            _sp(rl, 0.2),
            rl["Paragraph"](f"[STAMP: {stamp_text}]", st["stamp"]),
        ]
    return block


def _issue_validity(rl, st, issue: date, valid: date,
                    extra_note: str = "") -> list:
    color = rl["colors"]
    valid_str = valid.strftime("%d-%b-%Y")
    is_expired = valid < TODAY
    validity_style = st["warning"] if is_expired else st["body_left"]
    expired_note = "  ⚠ EXPIRED" if is_expired else ""
    rows = [
        rl["Paragraph"](
            f"Date of Issue: {issue.strftime('%d-%b-%Y')}",
            st["body_left"],
        ),
        rl["Paragraph"](
            f"Valid Until: {valid_str}{expired_note}",
            validity_style,
        ),
    ]
    if extra_note:
        rows.append(rl["Paragraph"](extra_note, st["small"]))
    return rows


# ===========================================================================
# Document generators
# ===========================================================================

def gen_emd(path, rl, st, tender_title: str, emd_amount: int,
            issuing_bank: str = "State Bank of India",
            branch: str = "MG Road, Bengaluru") -> None:
    """01_emd.pdf — Earnest Money Deposit / Bank Guarantee"""
    story = []
    story += _gov_header(rl, st, issuing_bank)
    story.append(rl["Paragraph"]("BANK GUARANTEE / EARNEST MONEY DEPOSIT", st["title"]))
    story.append(_sp(rl))
    story.append(rl["Paragraph"](
        f"This is to certify that <b>{FIRM_CLEAN}</b> (GSTIN: {FIRM_GSTIN}), "
        f"having its registered office at {FIRM_ADDRESS}, has deposited an Earnest "
        f"Money Deposit of <b>₹{emd_amount:,}/- (Rupees {_amount_words(emd_amount)} only)</b> "
        f"as Bid Security in favour of the Tender Inviting Authority for the following tender:",
        st["body"],
    ))
    story.append(_sp(rl, 0.2))
    story.append(rl["Paragraph"](f"<b>Tender:</b> {tender_title}", st["body_left"]))
    story.append(rl["Paragraph"](
        f"<b>Bank Guarantee No.:</b> SBI/MGB/BG/{ISSUE_DATE.year}/04721",
        st["body_left"],
    ))
    story += _issue_validity(rl, st, ISSUE_DATE, VALID_DATE_FUTURE)
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](
        "This Bank Guarantee is issued in accordance with the terms of the tender "
        "document and shall be forfeited in the event of withdrawal of bid or failure "
        "to execute the contract after award.",
        st["body"],
    ))
    story += _signature_block(rl, st,
                              "Shri Prakash Nair", "Branch Manager",
                              f"{issuing_bank}, {branch}",
                              stamp_text="SBI AUTHORISED SIGNATORY")
    _build_doc(path, story, rl)


def gen_tender_acceptance(path, rl, st, tender_title: str,
                          firm_name: str = None) -> None:
    """02_tender_acceptance_letter.pdf"""
    firm = firm_name or FIRM_CLEAN
    story = []
    story.append(rl["Paragraph"]("TENDER ACCEPTANCE LETTER", st["title"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.2))
    story.append(rl["Paragraph"](f"Date: {ISSUE_DATE.strftime('%d-%B-%Y')}", st["right"]))
    story.append(rl["Paragraph"]("To,", st["body_left"]))
    story.append(rl["Paragraph"]("The Tender Inviting Authority,", st["body_left"]))
    story.append(rl["Paragraph"]("(As specified in the NIT)", st["body_left"]))
    story.append(_sp(rl, 0.2))
    story.append(rl["Paragraph"](f"<b>Subject:</b> Acceptance of tender for — {tender_title}", st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(rl["Paragraph"](
        f"I/We, <b>{firm}</b>, having read and examined the Notice Inviting Tender, "
        "Tender Documents including all addenda, do hereby agree to execute the said "
        "work in accordance with the provisions of the tender documents. I/We further "
        "declare that all information submitted herein is true and correct to the best "
        "of our knowledge.",
        st["body"],
    ))
    story.append(_sp(rl, 0.2))
    story.append(rl["Paragraph"](
        "I/We have read and understood all terms and conditions and agree to abide by them.",
        st["body"],
    ))
    story += _signature_block(rl, st,
                              "Authorised Signatory", "Director",
                              firm)
    _build_doc(path, story, rl)


def gen_integrity_pact(path, rl, st, tender_title: str,
                       firm_name: str = None) -> None:
    """03_integrity_pact.pdf"""
    firm = firm_name or FIRM_CLEAN
    story = []
    story += _gov_header(rl, st, "Central Vigilance Commission — Integrity Pact Format")
    story.append(rl["Paragraph"]("INTEGRITY PACT", st["title"]))
    story.append(rl["Paragraph"](
        "Between the Government of India (Principal) and the Bidder / Contractor",
        st["subtitle"],
    ))
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](
        f"This Integrity Pact is entered into on {ISSUE_DATE.strftime('%d-%B-%Y')} between "
        f"the Principal (represented by the Tender Inviting Authority) and <b>{firm}</b> "
        "(hereinafter 'the Bidder').",
        st["body"],
    ))
    for clause_num, clause_text in [
        ("1. Commitments of the Principal",
         "The Principal commits itself to take all measures necessary to prevent "
         "corruption and to observe the following principles: No employee of the Principal "
         "shall demand or accept any advantage whatsoever from the Bidder."),
        ("2. Commitments of the Bidder",
         "The Bidder commits itself to take all measures necessary to prevent corruption "
         "during the bidding process and subsequent contract execution. The Bidder shall "
         "not offer, directly or through intermediaries, any financial or other advantage "
         "to any official of the Principal."),
        ("3. Violations",
         "Any violation of the Integrity Pact shall result in disqualification from the "
         "tendering process, forfeiture of the Bid Security, and/or termination of the "
         "contract."),
    ]:
        story.append(rl["Paragraph"](f"<b>{clause_num}</b>", st["h2"]))
        story.append(rl["Paragraph"](clause_text, st["body"]))

    story.append(rl["Paragraph"]("Signed by:", st["h2"]))
    story.append(rl["Paragraph"]("For the Principal:", st["body_left"]))
    story.append(rl["Paragraph"]("Sd/-  [Authorised Signatory of Tendering Authority]", st["body_left"]))
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](f"For the Bidder: <b>{firm}</b>", st["body_left"]))
    story += _signature_block(rl, st, "Authorised Signatory", "Director", firm)
    _build_doc(path, story, rl)


def gen_gst_certificate(path, rl, st) -> None:
    """04_gst_certificate.pdf"""
    story = []
    story += _gov_header(rl, st, "Goods and Services Tax Network (GSTN)")
    story.append(rl["Paragraph"]("CERTIFICATE OF GST REGISTRATION", st["title"]))
    story.append(_sp(rl, 0.3))
    data = [
        ["GSTIN", FIRM_GSTIN],
        ["Legal Name", FIRM_CLEAN],
        ["Trade Name", "Ravi Constructions"],
        ["Constitution of Business", "Private Limited Company"],
        ["Date of Registration", "01-Apr-2018"],
        ["Type", "Regular"],
        ["Principal Place of Business", FIRM_ADDRESS],
        ["Nature of Business Activities", "Construction of Buildings; Civil Works"],
        ["Status", "ACTIVE"],
    ]
    table = rl["Table"](data, colWidths=[5 * rl["cm"], 10 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].lightblue),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [rl["colors"].white, rl["colors"].HexColor("#f5f5f5")]),
    ]))
    story.append(table)
    story.append(_sp(rl))
    story.append(rl["Paragraph"](
        "This certificate is issued by the GST Portal and is auto-generated. "
        "Verify at https://www.gst.gov.in/",
        st["small"],
    ))
    story += [_sp(rl, 0.2), rl["Paragraph"]("[STAMP: GSTN VERIFIED — DIGITAL CERTIFICATE]", st["stamp"])]
    _build_doc(path, story, rl)


def gen_pan_card(path, rl, st) -> None:
    """05_pan_card.pdf"""
    story = []
    story += _gov_header(rl, st,
                         "Income Tax Department, Government of India\n"
                         "Permanent Account Number (PAN) Card")
    story.append(rl["Paragraph"]("PERMANENT ACCOUNT NUMBER CARD", st["title"]))
    story.append(_sp(rl, 0.4))
    data = [
        ["PAN", FIRM_PAN],
        ["Name of Company / Firm", FIRM_CLEAN],
        ["Father's Name / Entity", "Not Applicable (Company)"],
        ["Date of Incorporation", "15-Mar-2010"],
        ["Signature / Seal", "[Authorised Signatory Seal]"],
    ]
    table = rl["Table"](data, colWidths=[6 * rl["cm"], 9 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].HexColor("#e8f4e8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(_sp(rl))
    story.append(rl["Paragraph"]("[STAMP: INCOME TAX DEPARTMENT — GOVT. OF INDIA]", st["stamp"]))
    _build_doc(path, story, rl)


def gen_balance_sheet(path, rl, st, turnover_lakhs: float) -> None:
    """06_audited_balance_sheet.pdf"""
    story = []
    story.append(rl["Paragraph"](FIRM_CLEAN, st["title"]))
    story.append(rl["Paragraph"](
        f"CIN: {FIRM_CIN} | Registered: {FIRM_ADDRESS}",
        st["subtitle"],
    ))
    story.append(_divider(rl))
    story.append(rl["Paragraph"]("AUDITED BALANCE SHEET & PROFIT AND LOSS ACCOUNT", st["title"]))
    story.append(rl["Paragraph"](
        f"For the Financial Year ended 31st March {TODAY.year - 1}",
        st["subtitle"],
    ))
    story.append(_sp(rl, 0.3))

    turnover_cr = turnover_lakhs / 100.0
    profit = turnover_lakhs * 0.12

    fy0 = f"FY {TODAY.year - 3}–{str(TODAY.year - 2)[-2:]}"
    fy1 = f"FY {TODAY.year - 2}–{str(TODAY.year - 1)[-2:]}"
    fy2 = f"FY {TODAY.year - 1}–{str(TODAY.year)[-2:]}"

    data = [
        ["Particulars", fy0, fy1, fy2],
        ["Revenue from Operations (₹ Lakhs)", f"{turnover_lakhs * 0.85:.2f}", f"{turnover_lakhs * 0.93:.2f}", f"{turnover_lakhs:.2f}"],
        ["Other Income (₹ Lakhs)", "1.20", "1.45", "1.60"],
        ["Total Income (₹ Lakhs)", f"{turnover_lakhs * 0.85 + 1.20:.2f}", f"{turnover_lakhs * 0.93 + 1.45:.2f}", f"{turnover_lakhs + 1.60:.2f}"],
        ["Total Expenditure (₹ Lakhs)", f"{turnover_lakhs * 0.85 * 0.88:.2f}", f"{turnover_lakhs * 0.93 * 0.88:.2f}", f"{turnover_lakhs * 0.88:.2f}"],
        ["Profit Before Tax (₹ Lakhs)", f"{turnover_lakhs * 0.85 * 0.12:.2f}", f"{turnover_lakhs * 0.93 * 0.12:.2f}", f"{profit:.2f}"],
        ["Net Worth (₹ Lakhs)", f"{turnover_lakhs * 1.8:.2f}", f"{turnover_lakhs * 2.0:.2f}", f"{turnover_lakhs * 2.2:.2f}"],
    ]
    table = rl["Table"](data, colWidths=[7 * rl["cm"], 3 * rl["cm"], 3 * rl["cm"], 3 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl["colors"].white, rl["colors"].HexColor("#f0f4f8")]),
    ]))
    story.append(table)
    story.append(_sp(rl))
    story.append(rl["Paragraph"](
        f"This Balance Sheet has been prepared in accordance with the Companies Act, 2013 "
        f"and applicable Accounting Standards. Audited and certified by {CA_FIRM}.",
        st["small"],
    ))
    story += _signature_block(rl, st,
                              "CA R. Sharma", "Proprietor",
                              CA_FIRM,
                              stamp_text="ICAI MEMBER — UDIN: 24094521ABCDEF1234")
    _build_doc(path, story, rl)


def gen_ca_turnover_cert(path, rl, st, turnover_lakhs: float,
                         note: str = "") -> None:
    """07_ca_avg_turnover_certificate.pdf — the financial gatekeeping doc."""
    avg_3yr = turnover_lakhs  # we pass the 3-year average directly
    story = []
    story += _gov_header(rl, st,
                         f"{CA_FIRM}\n{CA_ADDRESS}")
    story.append(rl["Paragraph"](
        "CERTIFICATE OF AVERAGE ANNUAL TURNOVER", st["title"],
    ))
    story.append(rl["Paragraph"]("(As per Appendix prescribed in the Tender Document)", st["subtitle"]))
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](
        f"This is to certify that we have audited the books of accounts of "
        f"<b>{FIRM_CLEAN}</b> (PAN: {FIRM_PAN}, GSTIN: {FIRM_GSTIN}) having its "
        f"registered office at {FIRM_ADDRESS}, for the last three financial years.",
        st["body"],
    ))
    story.append(_sp(rl, 0.2))

    fy0 = f"FY {TODAY.year - 3}–{str(TODAY.year - 2)[-2:]}"
    fy1 = f"FY {TODAY.year - 2}–{str(TODAY.year - 1)[-2:]}"
    fy2 = f"FY {TODAY.year - 1}–{str(TODAY.year)[-2:]}"
    t0 = round(avg_3yr * 0.85, 2)
    t1 = round(avg_3yr * 0.93, 2)
    t2 = round(avg_3yr, 2)
    avg = round((t0 + t1 + t2) / 3, 2)

    data = [
        ["Financial Year", "Turnover from Civil Works (₹ Lakhs)"],
        [fy0, f"{t0:.2f}"],
        [fy1, f"{t1:.2f}"],
        [fy2, f"{t2:.2f}"],
        ["Average Annual Turnover (3 years)", f"<b>{avg:.2f}</b>"],
    ]
    table = rl["Table"](data, colWidths=[8 * rl["cm"], 7 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), rl["colors"].HexColor("#fff3cd")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [rl["colors"].white, rl["colors"].HexColor("#f5f5f5")]),
    ]))
    story.append(table)
    story.append(_sp(rl, 0.3))

    # Highlight shortfall clearly if present
    if note:
        story.append(rl["Paragraph"](
            f"<b>NOTE:</b> {note}", st["warning"],
        ))
        story.append(_sp(rl, 0.2))

    story.append(rl["Paragraph"](
        f"Based on the books of accounts duly audited, the Average Annual Turnover of "
        f"<b>{FIRM_CLEAN}</b> from Civil Works during the last three financial years is "
        f"<b>₹ {avg:.2f} Lakhs</b>.",
        st["body"],
    ))
    story += _signature_block(
        rl, st,
        "CA R. Sharma", "Proprietor",
        f"{CA_FIRM}\nMembership No.: {CA_MEMBER_NO}",
        stamp_text="ICAI MEMBER — UDIN: 24094521ABCDEF1234",
    )
    _build_doc(path, story, rl)


def gen_solvency_cert(path, rl, st, amount: int) -> None:
    """08_solvency_certificate.pdf"""
    story = []
    story += _gov_header(rl, st, "State Bank of India — Corporate Banking Branch")
    story.append(rl["Paragraph"]("SOLVENCY CERTIFICATE", st["title"]))
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](
        f"This is to certify that <b>{FIRM_CLEAN}</b> (Account No. 37821946830) is a "
        f"valued customer of State Bank of India, MG Road, Bengaluru Branch. Based on "
        f"the records available with us, we certify that the aforesaid firm is solvent "
        f"to the extent of <b>₹{amount:,}/- (Rupees {_amount_words(amount)} only)</b>.",
        st["body"],
    ))
    story.append(_sp(rl, 0.3))
    story += _issue_validity(rl, st, ISSUE_DATE, VALID_DATE_FUTURE)
    story.append(rl["Paragraph"](
        "This certificate is issued for the purpose of participating in Government tenders "
        "and shall not be construed as a financial guarantee.",
        st["small"],
    ))
    story += _signature_block(rl, st,
                              "Shri Prakash Nair", "Branch Manager",
                              "State Bank of India, MG Road, Bengaluru",
                              stamp_text="SBI AUTHORISED SIGNATORY")
    _build_doc(path, story, rl)


def gen_iso_certificate(path, rl, st, firm_name: str,
                        valid_until: date, expired: bool = False) -> None:
    """09_iso_9001_certificate.pdf — valid or expired variant."""
    story = []
    story += _gov_header(rl, st,
                         "Quality Council of India — Accreditation Body\n"
                         "ISO/IEC 17021-1 Accredited Certification Body")
    story.append(rl["Paragraph"]("CERTIFICATE OF REGISTRATION", st["title"]))
    story.append(rl["Paragraph"]("ISO 9001:2015 — Quality Management System", st["subtitle"]))
    story.append(_sp(rl, 0.4))

    data = [
        ["Certificate No.", f"QCI/ISO9001/BLR/2021/04892"],
        ["Certified Organisation", firm_name],
        ["Address", FIRM_ADDRESS],
        ["Scope of Certification", "Civil Construction, Building Works, and Infrastructure Projects"],
        ["Standard", "ISO 9001:2015"],
        ["Date of First Certification", "15-Jan-2021"],
        ["Date of Recertification", "15-Jan-2024"],
        ["Certificate Valid Until", valid_until.strftime("%d-%b-%Y")],
        ["Status", "EXPIRED ⚠" if expired else "VALID ✓"],
    ]
    table = rl["Table"](data, colWidths=[6 * rl["cm"], 9 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].HexColor("#e8f0fe")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1),
         rl["colors"].HexColor("#ffd7d7") if expired else rl["colors"].HexColor("#d4edda")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, -1), (1, -1),
         rl["colors"].red if expired else rl["colors"].HexColor("#155724")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -2), [rl["colors"].white, rl["colors"].HexColor("#f8f9fa")]),
    ]))
    story.append(table)
    story.append(_sp(rl))

    if expired:
        story.append(rl["Paragraph"](
            "⚠ WARNING: This certificate has EXPIRED. The organisation must apply for "
            "recertification before this certificate can be accepted for tendering purposes.",
            st["warning"],
        ))
    else:
        story.append(rl["Paragraph"](
            "This certificate confirms that the organisation's Quality Management System "
            "has been assessed and found to conform to the requirements of ISO 9001:2015.",
            st["body"],
        ))

    story += _signature_block(
        rl, st,
        "Certification Authority", "Chief Certifying Officer",
        "Quality Council of India, New Delhi",
        stamp_text="QCI ACCREDITED CERTIFICATION BODY",
    )
    _build_doc(path, story, rl)


def gen_experience_certificate(path, rl, st, firm_name: str,
                                tender_title: str) -> None:
    """10_experience_certificate.pdf"""
    story = []
    story += _gov_header(rl, st, "Public Works Department, Government of Karnataka")
    story.append(rl["Paragraph"]("EXPERIENCE / WORK COMPLETION CERTIFICATE", st["title"]))
    story.append(_sp(rl, 0.3))

    work_value = 75.0  # lakhs
    story.append(rl["Paragraph"](
        f"This is to certify that <b>{firm_name}</b> satisfactorily completed the "
        f"following civil / construction work for this Department:",
        st["body"],
    ))
    story.append(_sp(rl, 0.2))
    data = [
        ["Name of Work", "Construction of PWD Office Complex, Phase II, Bengaluru"],
        ["Agreement No.", f"PWD/KAR/BLR/2022-23/0441"],
        ["Work Order Date", "15-Jun-2022"],
        ["Completion Date", "30-Nov-2023"],
        ["Work Order Value", f"₹ {work_value:.2f} Lakhs"],
        ["Actual Completion Value", f"₹ {work_value * 1.02:.2f} Lakhs"],
        ["Quality of Work", "Satisfactory"],
        ["Name of Contractor", firm_name],
    ]
    table = rl["Table"](data, colWidths=[6.5 * rl["cm"], 8.5 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].HexColor("#fff9e6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [rl["colors"].white, rl["colors"].HexColor("#fefefe")]),
    ]))
    story.append(table)
    story.append(_sp(rl))
    story.append(rl["Paragraph"](
        "This certificate is issued for the purpose of participating in Government tenders "
        "and does not constitute a recommendation.",
        st["small"],
    ))
    story += _signature_block(
        rl, st,
        "Executive Engineer", "PWD Division, Bengaluru",
        "Public Works Department, Government of Karnataka",
        stamp_text="PWD GOVT OF KARNATAKA — OFFICE SEAL",
    )
    _build_doc(path, story, rl)


def gen_non_blacklisting(path, rl, st, firm_name: str = None) -> None:
    """11_non_blacklisting_affidavit.pdf"""
    firm = firm_name or FIRM_CLEAN
    story = []
    story.append(rl["Paragraph"]("AFFIDAVIT", st["title"]))
    story.append(rl["Paragraph"]("(Non-Blacklisting Self-Declaration)", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"](
        f"I, the undersigned, being the duly authorised signatory of "
        f"<b>{firm}</b> (GSTIN: {FIRM_GSTIN}), do hereby solemnly affirm and declare as under:",
        st["body"],
    ))
    story.append(_sp(rl, 0.2))
    for i, clause in enumerate([
        f"{firm} has NOT been blacklisted, debarred, or suspended by any Central Government Ministry, "
        "Department, PSU, or State Government as on the date of submission of this bid.",
        f"{firm} has NOT been convicted by any court of law for any offence related to corrupt practices, "
        "fraudulent practices, collusive practices, or coercive practices.",
        "No criminal proceedings are pending against the firm or its directors in any court of competent "
        "jurisdiction relating to the subject matter of this tender.",
        "The information furnished in this bid is true and correct to the best of our knowledge. "
        "We are aware that providing false information shall render this bid liable for rejection and "
        "may attract penal action.",
    ], start=1):
        story.append(rl["Paragraph"](f"{i}. {clause}", st["body"]))
    story.append(_sp(rl, 0.4))
    story.append(rl["Paragraph"]("Deponent / Authorised Signatory:", st["body_left"]))
    story += _signature_block(rl, st, "Authorised Signatory", "Director", firm)
    story.append(_sp(rl, 0.3))
    story.append(rl["Paragraph"]("[STAMP: NOTARY PUBLIC — BENGALURU]", st["stamp"]))
    story.append(rl["Paragraph"]("[STAMP: ₹100 STAMP PAPER]", st["stamp"]))
    _build_doc(path, story, rl)


def gen_dsc(path, rl, st, firm_name: str = None) -> None:
    """12_dsc_class3.pdf — Digital Signature Certificate"""
    firm = firm_name or FIRM_CLEAN
    story = []
    story += _gov_header(rl, st,
                         "Controller of Certifying Authorities (CCA)\n"
                         "Ministry of Electronics & Information Technology, GoI")
    story.append(rl["Paragraph"]("DIGITAL SIGNATURE CERTIFICATE — CLASS 3", st["title"]))
    story.append(_sp(rl, 0.3))
    data = [
        ["Certificate Type", "Class 3 — Organisation (Signing & Encryption)"],
        ["Common Name (CN)", "AUTHORISED SIGNATORY"],
        ["Organisation (O)", firm],
        ["Organisation Unit (OU)", "Tendering"],
        ["Country (C)", "IN"],
        ["Serial Number", "4A:3F:BC:91:DE:07:22:A8:FF:01"],
        ["Valid From", ISSUE_DATE.strftime("%d-%b-%Y")],
        ["Valid To", VALID_DATE_FUTURE.strftime("%d-%b-%Y")],
        ["Issuing CA", "eMudhra Consumer Services Limited"],
        ["Key Usage", "Digital Signature, Non-Repudiation"],
        ["Status", "ACTIVE"],
    ]
    table = rl["Table"](data, colWidths=[6.5 * rl["cm"], 8.5 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].HexColor("#e8f0fe")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), rl["colors"].HexColor("#d4edda")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -2), [rl["colors"].white, rl["colors"].HexColor("#f8f9fa")]),
    ]))
    story.append(table)
    story.append(_sp(rl))
    story.append(rl["Paragraph"](
        "This Digital Signature Certificate is issued under the Information Technology "
        "Act, 2000 and is valid for use on Government e-procurement portals.",
        st["small"],
    ))
    story.append(rl["Paragraph"]("[STAMP: CCA INDIA — LICENSED CERTIFYING AUTHORITY]", st["stamp"]))
    _build_doc(path, story, rl)


# ---------------------------------------------------------------------------
# Bundle orchestrator
# ---------------------------------------------------------------------------

PROFILES = ["bidder-a-clean", "bidder-b-shortfall", "bidder-c-missing-iso", "bidder-d-ambiguous"]


def gen_bundle(tender_stem: str, tender_title: str, criteria: list[dict],
               profile: str, base_dir: str, rl, force: bool) -> list[dict]:
    """Generate all docs for one bidder profile. Returns doc metadata list."""
    bundle_dir = os.path.join(base_dir, profile)
    os.makedirs(bundle_dir, exist_ok=True)

    # Determine profile-specific params
    if profile == "bidder-a-clean":
        turnover = 50.0        # comfortably above any threshold
        firm_name = FIRM_CLEAN
        cert_firm = FIRM_CLEAN
        iso_valid = VALID_DATE_FUTURE
        iso_expired = False
        has_iso = True
        turnover_note = ""
    elif profile == "bidder-b-shortfall":
        turnover = 38.0        # below the common ₹41.6L threshold → FAIL C1
        firm_name = FIRM_SHORTFALL
        cert_firm = FIRM_SHORTFALL
        iso_valid = VALID_DATE_FUTURE
        iso_expired = False
        has_iso = True
        turnover_note = (
            f"The average annual turnover of ₹{(38.0 * 0.85 + 38.0 * 0.93 + 38.0) / 3:.2f} Lakhs "
            f"is BELOW the required threshold of ₹41.6 Lakhs for NIT-71."
        )
    elif profile == "bidder-c-missing-iso":
        turnover = 50.0
        firm_name = FIRM_MISSING_ISO
        cert_firm = FIRM_MISSING_ISO
        iso_valid = VALID_DATE_FUTURE
        iso_expired = False
        has_iso = False          # ← ISO certificate deliberately omitted
        turnover_note = ""
    else:  # bidder-d-ambiguous
        turnover = 50.0
        firm_name = FIRM_AMBIGUOUS_MAIN
        cert_firm = FIRM_AMBIGUOUS_CERT   # ← subtle name mismatch on certs
        iso_valid = VALID_DATE_EXPIRED
        iso_expired = True               # ← ISO expired 2024
        has_iso = True
        turnover_note = ""

    # Infer EMD and solvency from criteria if available
    emd_amount = 41600
    solvency_amount = 20800
    for c in criteria:
        if c.get("id") == "C2" and c.get("threshold_unit") == "INR":
            emd_amount = int(c.get("threshold_value", 41600))
        if "solvency" in c.get("name", "").lower():
            solvency_amount = int(c.get("threshold_value", 20800))

    doc_meta = []

    def _make(filename: str, generator_fn, doc_type: str):
        path = os.path.join(bundle_dir, filename)
        if os.path.exists(path) and os.path.getsize(path) > 0 and not force:
            print(f"    [SKIP] {filename}")
        else:
            generator_fn(path)
            size_kb = os.path.getsize(path) // 1024
            print(f"    [OK]   {filename} ({size_kb} KB)")
        doc_meta.append({
            "filename": filename,
            "doc_type": doc_type,
            "path": os.path.relpath(path, PROJECT_ROOT),
        })

    st = _styles(rl)

    _make("01_emd.pdf",
          lambda p: gen_emd(p, rl, st, tender_title, emd_amount),
          "EMD")
    _make("02_tender_acceptance_letter.pdf",
          lambda p: gen_tender_acceptance(p, rl, st, tender_title, firm_name),
          "TenderAcceptanceLetter")
    _make("03_integrity_pact.pdf",
          lambda p: gen_integrity_pact(p, rl, st, tender_title, firm_name),
          "IntegrityPact")
    _make("04_gst_certificate.pdf",
          lambda p: gen_gst_certificate(p, rl, st),
          "GSTCertificate")
    _make("05_pan_card.pdf",
          lambda p: gen_pan_card(p, rl, st),
          "PANCard")
    _make("06_audited_balance_sheet.pdf",
          lambda p: gen_balance_sheet(p, rl, st, turnover),
          "AuditedBalanceSheet")
    _make("07_ca_avg_turnover_certificate.pdf",
          lambda p: gen_ca_turnover_cert(p, rl, st, turnover, turnover_note),
          "CATurnoverCertificate")
    _make("08_solvency_certificate.pdf",
          lambda p: gen_solvency_cert(p, rl, st, solvency_amount),
          "SolvencyCertificate")

    if has_iso:
        _make("09_iso_9001_certificate.pdf",
              lambda p: gen_iso_certificate(p, rl, st, cert_firm,
                                            iso_valid, iso_expired),
              "ISO9001Certificate")
    else:
        # bidder-c: no ISO doc — record as absent in manifest
        doc_meta.append({
            "filename": "09_iso_9001_certificate.pdf",
            "doc_type": "ISO9001Certificate",
            "path": None,
            "absent": True,
            "note": "ISO certificate deliberately not submitted (bidder-c-missing-iso profile)",
        })
        print(f"    [OMIT] 09_iso_9001_certificate.pdf (absent by design — bidder-c)")

    _make("10_experience_certificate.pdf",
          lambda p: gen_experience_certificate(p, rl, st, cert_firm, tender_title),
          "ExperienceCertificate")
    _make("11_non_blacklisting_affidavit.pdf",
          lambda p: gen_non_blacklisting(p, rl, st, firm_name),
          "NonBlacklistingAffidavit")
    _make("12_dsc_class3.pdf",
          lambda p: gen_dsc(p, rl, st, firm_name),
          "DSCClass3")

    return doc_meta


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _amount_words(n: int) -> str:
    """Very simple ₹ amount → words for small values."""
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
             "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]
    if n < 20:
        return units[n]
    if n < 100:
        return tens[n // 10] + (" " + units[n % 10] if n % 10 else "")
    if n < 1000:
        return units[n // 100] + " Hundred" + (" and " + _amount_words(n % 100) if n % 100 else "")
    if n < 100000:
        return _amount_words(n // 1000) + " Thousand" + (" " + _amount_words(n % 1000) if n % 1000 else "")
    if n < 10000000:
        return _amount_words(n // 100000) + " Lakh" + (" " + _amount_words(n % 100000) if n % 100000 else "")
    return str(n)


def load_ground_truth() -> dict[str, dict]:
    """Load ground truth keyed by pdf_filename stem."""
    if not os.path.exists(GROUND_TRUTH_PATH):
        return {}
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return {
        os.path.splitext(item["pdf_filename"])[0]: item
        for item in items
    }


def discover_tenders() -> list[str]:
    """Return list of tender PDF stems found in seed/pdfs/."""
    if not os.path.isdir(SEED_PDFS_DIR):
        return []
    return [
        os.path.splitext(f)[0]
        for f in sorted(os.listdir(SEED_PDFS_DIR))
        if f.endswith(".pdf") and not f.startswith(".")
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TenderAudit synthetic bidder bundles")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if files already exist")
    parser.add_argument("--tender", metavar="STEM",
                        help="Generate for one tender only (e.g. crpf-2-bhopal-nit71)")
    args = parser.parse_args()

    os.makedirs(BIDDERS_DIR, exist_ok=True)

    print("=== TenderAudit Bidder Bundle Generator ===")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Bidders dir  : {BIDDERS_DIR}")
    print()

    # Load reportlab once
    rl = get_rl()

    # Discover tenders
    gt = load_ground_truth()
    all_stems = discover_tenders()
    if not all_stems:
        print("[WARN] No tender PDFs found in seed/pdfs/ — generating bundles with generic data.")
        print("       Run 'make seed' first to download or generate tender placeholders.")
        print("       Proceeding with ground-truth manifest entries instead...\n")
        all_stems = [os.path.splitext(v["pdf_filename"])[0] for v in gt.values()]

    if args.tender:
        if args.tender not in all_stems:
            print(f"[ERROR] Tender '{args.tender}' not found. Available: {all_stems}")
            return 1
        tender_stems = [args.tender]
    else:
        tender_stems = all_stems

    total_bundles = 0
    total_docs = 0

    for stem in tender_stems:
        gt_entry = gt.get(stem, {})
        tender_title = gt_entry.get("title", stem.replace("-", " ").title())
        criteria = gt_entry.get("criteria", [])

        tender_bundle_dir = os.path.join(BIDDERS_DIR, stem)
        os.makedirs(tender_bundle_dir, exist_ok=True)

        print(f"Tender: {stem}")
        print(f"  Title: {tender_title}")
        print(f"  Criteria: {len(criteria)} loaded from ground truth")

        tender_manifest = {
            "tender_stem": stem,
            "tender_title": tender_title,
            "generated_date": TODAY.isoformat(),
            "profiles": {},
        }

        for profile in PROFILES:
            print(f"\n  [{profile}]")
            doc_meta = gen_bundle(
                stem, tender_title, criteria, profile,
                tender_bundle_dir, rl, args.force,
            )
            tender_manifest["profiles"][profile] = {
                "description": _profile_description(profile),
                "expected_result": _profile_expected(profile),
                "documents": doc_meta,
            }
            total_bundles += 1
            total_docs += len(doc_meta)

        # Write per-tender manifest.json
        manifest_path = os.path.join(tender_bundle_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(tender_manifest, f, indent=2, ensure_ascii=False)
        print(f"\n  [manifest] Written → {os.path.relpath(manifest_path, PROJECT_ROOT)}")
        print()

    print("=" * 60)
    print(f"Done. {total_bundles} bundles generated across {len(tender_stems)} tender(s).")
    print(f"Total documents: {total_docs} (12 per bundle; ISO omitted for bidder-c).")
    print()
    print("Profile summary:")
    for p in PROFILES:
        print(f"  {p:30s} → {_profile_description(p)}")
        print(f"  {'':30s}   Expected: {_profile_expected(p)}")
    return 0


def _profile_description(profile: str) -> str:
    return {
        "bidder-a-clean":        "All docs valid; turnover ₹50L (above threshold)",
        "bidder-b-shortfall":    "Turnover ₹38L < ₹41.6L threshold — financial shortfall",
        "bidder-c-missing-iso":  "ISO 9001 certificate absent — not submitted",
        "bidder-d-ambiguous":    "ISO expired Mar-2024; name on certs: 'Ravi Construction Pvt Ltd' vs 'M/s Ravi Constructions Pvt. Ltd.'",
    }.get(profile, profile)


def _profile_expected(profile: str) -> str:
    return {
        "bidder-a-clean":        "PASS all criteria",
        "bidder-b-shortfall":    "FAIL C1 (Average Annual Turnover)",
        "bidder-c-missing-iso":  "FAIL ISO criterion (missing document)",
        "bidder-d-ambiguous":    "AMBIGUOUS — requires human review (expired cert + name mismatch)",
    }.get(profile, "Unknown")


if __name__ == "__main__":
    sys.exit(main())
