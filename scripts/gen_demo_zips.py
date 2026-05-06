#!/usr/bin/env python3
"""TenderAudit — Demo Bidder ZIP Generator.

Produces 4 ZIP archives under seed/demo-zips/ that the user uploads during a
live demo of the TenderAudit evaluation system.

Each ZIP contains 3-4 multi-page PDFs (4-5 pages each) covering the six
evaluation criteria the backend RAG retrieval expects to find:

    - Annual Turnover  (>= INR 5 Cr threshold)
    - ISO 9001 Certification
    - Prior Experience (>= 5 years in armoured / special vehicles)
    - Blacklisting Check  (self-declaration affidavit, dated)
    - Net Worth  (>= INR 2 Cr)
    - Class III Digital Signature Certificate

Bidders & profiles
------------------
    bidder-mahindra-defence       clean              -> all criteria met
    bidder-beml-limited           turnover-shortfall -> defence turnover ~INR 3.21 Cr
    bidder-tata-advanced-systems  missing-iso        -> ISO 14001 only, no 9001
    bidder-force-motors           ambiguous          -> ISO for wrong plant; net worth borderline;
                                                       affidavit dated 14 months ago

Usage
-----
    python scripts/gen_demo_zips.py            # generate all 4 zips
    python scripts/gen_demo_zips.py --force    # regenerate even if zips exist
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEMO_ZIPS_DIR = os.path.join(PROJECT_ROOT, "seed", "demo-zips")
WORK_DIR = os.path.join(DEMO_ZIPS_DIR, "_work")

TODAY = date(2025, 5, 5)  # stable demo date; matches currentDate in env
ISSUE_RECENT = TODAY - timedelta(days=42)
VALID_FAR_FUTURE = date(2027, 6, 30)
AFFIDAVIT_RECENT = TODAY - timedelta(days=30)
AFFIDAVIT_STALE = TODAY - timedelta(days=14 * 30 + 5)  # ~14 months ago


# ---------------------------------------------------------------------------
# ReportLab helpers (mirrors gen_bidder_bundle.py style for consistency)
# ---------------------------------------------------------------------------

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
        "title": PS("DocTitle", parent=base["Normal"], fontSize=13,
                    fontName="Helvetica-Bold", alignment=rl["TA_CENTER"],
                    spaceAfter=6, spaceBefore=0),
        "subtitle": PS("DocSub", parent=base["Normal"], fontSize=10,
                       alignment=rl["TA_CENTER"], spaceAfter=4),
        "h2": PS("DocH2", parent=base["Normal"], fontSize=11,
                 fontName="Helvetica-Bold", spaceAfter=3, spaceBefore=8),
        "body": PS("DocBody", parent=base["Normal"], fontSize=9.5,
                   leading=14, alignment=rl["TA_JUSTIFY"], spaceAfter=4),
        "body_left": PS("DocBodyL", parent=base["Normal"], fontSize=9.5,
                        leading=14, alignment=rl["TA_LEFT"], spaceAfter=4),
        "small": PS("DocSmall", parent=base["Normal"], fontSize=8,
                    leading=12, alignment=rl["TA_LEFT"], spaceAfter=3),
        "right": PS("DocRight", parent=base["Normal"], fontSize=9.5,
                    alignment=rl["TA_RIGHT"], spaceAfter=3),
        "stamp": PS("DocStamp", parent=base["Normal"], fontSize=8,
                    textColor=colors.darkblue, alignment=rl["TA_CENTER"],
                    spaceAfter=2),
        "warning": PS("DocWarn", parent=base["Normal"], fontSize=8.5,
                      textColor=colors.red, alignment=rl["TA_LEFT"],
                      spaceAfter=2),
    }


def _build_doc(path: str, story: list, rl: dict) -> None:
    doc = rl["SimpleDocTemplate"](
        path, pagesize=rl["A4"],
        leftMargin=2.0 * rl["cm"], rightMargin=2.0 * rl["cm"],
        topMargin=2.0 * rl["cm"], bottomMargin=2.0 * rl["cm"],
    )
    doc.build(story)


def _divider(rl: dict, color=None):
    color = color or rl["colors"].black
    return rl["HRFlowable"](width="100%", thickness=0.5, color=color)


def _sp(rl: dict, h: float = 0.3):
    return rl["Spacer"](1, h * rl["cm"])


def _signature(rl: dict, st: dict, name: str, designation: str,
               org: str, stamp: str | None = None) -> list:
    block = [
        _sp(rl, 0.6),
        rl["Paragraph"]("Sd/-", st["right"]),
        rl["Paragraph"](f"<b>{name}</b>", st["right"]),
        rl["Paragraph"](designation, st["right"]),
        rl["Paragraph"](org, st["right"]),
    ]
    if stamp:
        block += [_sp(rl, 0.2),
                  rl["Paragraph"](f"[STAMP: {stamp}]", st["stamp"])]
    return block


def _fmt_inr(rupees: int) -> str:
    """Format integer rupees in Indian numbering (lakhs/crores)."""
    s = str(rupees)
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts) + "," + last3


def _kv_table(rl: dict, rows: list[list[str]], col_widths=None,
              header_bg: str = "#e8f0fe", highlight_last: bool = False,
              highlight_color: str = "#fff3cd") -> object:
    cw = col_widths or [6 * rl["cm"], 10 * rl["cm"]]
    table = rl["Table"](rows, colWidths=cw)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].HexColor(header_bg)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [rl["colors"].white, rl["colors"].HexColor("#fafafa")]),
    ]
    if highlight_last:
        style.append(("BACKGROUND", (0, -1), (-1, -1),
                      rl["colors"].HexColor(highlight_color)))
        style.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
    table.setStyle(rl["TableStyle"](style))
    return table


# ---------------------------------------------------------------------------
# Bidder profile data (immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CAFirm:
    name: str
    address: str
    member_no: str
    udin: str


@dataclass(frozen=True)
class BidderProfile:
    slug: str
    firm_name: str
    address: str
    cin: str
    pan: str
    gstin: str
    phone: str
    email: str
    incorporation_date: str

    # Financials
    turnover_3yr_cr: tuple[float, float, float]   # crores per FY
    net_worth_cr: float                           # crores

    # ISO
    iso_present: bool
    iso_standard: str          # "ISO 9001:2015" or "ISO 14001:2015" etc.
    iso_certificate_no: str
    iso_issuing_body: str
    iso_scope: str             # text scope; for ambiguous bidder this is the wrong plant
    iso_valid_until: date

    # Past contracts (5+ years)
    past_contracts: tuple[dict, ...]

    # Blacklisting affidavit
    affidavit_date: date

    # DSC
    dsc_holder: str
    dsc_serial: str
    dsc_issuing_ca: str
    dsc_valid_until: date

    # CA
    ca_firm: CAFirm

    # Profile classification + extra notes the LLM can cite
    profile_kind: str          # "clean" | "shortfall" | "missing-iso" | "ambiguous"
    extra_note: str = ""


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

CA_MUMBAI = CAFirm(
    name="M/s Deshmukh & Co., Chartered Accountants",
    address="A-204, Nariman Point, Mumbai - 400 021",
    member_no="ICAI/MRN/108234",
    udin="25108234ABCDEF7821",
)
CA_BANGALORE = CAFirm(
    name="M/s Iyer Krishnan & Associates, Chartered Accountants",
    address="No. 18, 4th Floor, Lavelle Road, Bengaluru - 560 001",
    member_no="ICAI/MRN/094521",
    udin="25094521BLR0042199",
)
CA_HYDERABAD = CAFirm(
    name="M/s Reddy Anand & Co., Chartered Accountants",
    address="6-3-1090, Raj Bhavan Road, Somajiguda, Hyderabad - 500 082",
    member_no="ICAI/MRN/121089",
    udin="25121089HYD0099217",
)
CA_PUNE = CAFirm(
    name="M/s Kulkarni Joshi & Co., Chartered Accountants",
    address="Office 305, ICC Trade Tower, Senapati Bapat Road, Pune - 411 016",
    member_no="ICAI/MRN/137445",
    udin="25137445PNQ0017733",
)


PROFILES: tuple[BidderProfile, ...] = (
    # --- 1. Mahindra Defence (CLEAN) -----------------------------------
    BidderProfile(
        slug="bidder-mahindra-defence",
        firm_name="Mahindra Defence Systems Pvt. Ltd.",
        address="Mahindra Towers, Dr. G.M. Bhosale Marg, Worli, Mumbai - 400 018",
        cin="U35990MH2012PTC228734",
        pan="AAFCM7821J",
        gstin="27AAFCM7821J1ZK",
        phone="+91-22-2490-1441",
        email="defence.tenders@mahindra.com",
        incorporation_date="14-Mar-2012",
        turnover_3yr_cr=(78.42, 91.16, 104.83),     # avg ~ 91.47 Cr (>> 5 Cr)
        net_worth_cr=148.60,
        iso_present=True,
        iso_standard="ISO 9001:2015",
        iso_certificate_no="TUV-IND/QMS/2023/MDS-04471",
        iso_issuing_body="TUV India Pvt. Ltd. (Accredited by NABCB)",
        iso_scope=("Design, Development, Manufacture, Integration and Supply of "
                   "Light Specialist Vehicles, Mine-Protected Vehicles and "
                   "Armoured Personnel Carriers at the Faridabad and Pune plants"),
        iso_valid_until=date(2026, 11, 14),
        past_contracts=(
            {"customer": "Indian Army (DGMF, MoD)",
             "work": "Supply of 1,300 Light Specialist Vehicles (LSV) — Phase II",
             "agreement_no": "MoD/DGMF/LSV/2019-20/0091",
             "start": "11-Oct-2019", "end": "23-Aug-2022",
             "value_cr": 412.50},
            {"customer": "Border Security Force (MHA)",
             "work": "Supply of 122 Mine-Protected Vehicles (MPV Mk-IV)",
             "agreement_no": "BSF/MHA/MPV/2020-21/0218",
             "start": "04-Feb-2021", "end": "30-Nov-2023",
             "value_cr": 287.40},
            {"customer": "Central Reserve Police Force",
             "work": "Refurbishment & Up-armouring of 78 Armoured Personnel Carriers",
             "agreement_no": "CRPF/EQPT/APC-RFR/2022-23/0044",
             "start": "18-Jul-2022", "end": "12-Mar-2024",
             "value_cr": 96.18},
            {"customer": "Indian Air Force",
             "work": "Quick Reaction Fighting Vehicles (QRFV) — 64 units",
             "agreement_no": "IAF/AOC/QRFV/2023-24/0017",
             "start": "21-Sep-2023", "end": "ongoing (delivery to Mar-2026)",
             "value_cr": 174.95},
        ),
        affidavit_date=AFFIDAVIT_RECENT,
        dsc_holder="Shri Rajeev Kapoor",
        dsc_serial="7B:2C:91:F4:A8:01:DD:36:4E:09",
        dsc_issuing_ca="eMudhra Consumer Services Limited",
        dsc_valid_until=date(2027, 1, 18),
        ca_firm=CA_MUMBAI,
        profile_kind="clean",
        extra_note="",
    ),

    # --- 2. BEML Limited (TURNOVER SHORTFALL) ---------------------------
    BidderProfile(
        slug="bidder-beml-limited",
        firm_name="BEML Limited",
        address="BEML Soudha, 23/1, 4th Main, Sampangi Rama Nagar, Bengaluru - 560 027",
        cin="L35202KA1964GOI001530",
        pan="AAACB1234D",
        gstin="29AAACB1234D1Z9",
        phone="+91-80-2296-3142",
        email="defence.tendering@beml.co.in",
        incorporation_date="11-May-1964",
        # NOTE: This is the DEFENCE-segment turnover only, not consolidated revenue.
        # Average ~ INR 3.21 Cr — clearly below INR 5 Cr threshold.
        turnover_3yr_cr=(2.84, 3.18, 3.62),
        net_worth_cr=11.40,
        iso_present=True,
        iso_standard="ISO 9001:2015",
        iso_certificate_no="BIS-QMS/BLR/2022/BEML-DEF-00921",
        iso_issuing_body="Bureau of Indian Standards (BIS)",
        iso_scope=("Manufacture and Supply of Defence Mobility Systems including "
                   "High-Mobility Vehicles, Recovery Vehicles and Armoured "
                   "Repair & Recovery Vehicles at the KGF and Mysuru complexes"),
        iso_valid_until=date(2026, 5, 27),
        past_contracts=(
            {"customer": "Indian Army (Master General of Ordnance)",
             "work": "Supply of 87 High-Mobility 8x8 Defence Vehicles",
             "agreement_no": "MGO/HMV-8x8/2018-19/0117",
             "start": "07-Aug-2018", "end": "14-Dec-2021",
             "value_cr": 38.60},
            {"customer": "Indian Army (EME Directorate)",
             "work": "Armoured Repair & Recovery Vehicles (ARRV) — 22 units",
             "agreement_no": "EME/ARRV/2020-21/0044",
             "start": "12-Mar-2021", "end": "08-Oct-2023",
             "value_cr": 24.18},
            {"customer": "Sashastra Seema Bal (MHA)",
             "work": "All-Terrain Patrol Vehicles for Northern Frontier — 41 units",
             "agreement_no": "SSB/ATV-NF/2022-23/0029",
             "start": "01-Jun-2022", "end": "22-Feb-2024",
             "value_cr": 16.92},
        ),
        affidavit_date=AFFIDAVIT_RECENT,
        dsc_holder="Smt. Anuradha Rao",
        dsc_serial="3F:91:4D:88:0A:2C:E1:74:9B:11",
        dsc_issuing_ca="(n)Code Solutions CA (GNFC)",
        dsc_valid_until=date(2026, 9, 4),
        ca_firm=CA_BANGALORE,
        profile_kind="shortfall",
        extra_note=("The Defence-segment turnover certified herein represents the "
                    "ring-fenced Defence Business Vertical only, and is below the "
                    "tender threshold of INR 5 Crore."),
    ),

    # --- 3. Tata Advanced Systems (MISSING ISO 9001) --------------------
    BidderProfile(
        slug="bidder-tata-advanced-systems",
        firm_name="Tata Advanced Systems Ltd.",
        address="Plot No. 81 to 85, Phase IV, Hardware Park, Maheshwaram Mandal, "
                "Hyderabad - 501 510",
        cin="U62200KA2007PLC042889",
        pan="AAFCT8392K",
        gstin="36AAFCT8392K1Z8",
        phone="+91-40-6717-3300",
        email="bids.aerospace@tataadvancedsystems.com",
        incorporation_date="28-Jun-2007",
        turnover_3yr_cr=(126.71, 142.05, 158.93),
        net_worth_cr=212.40,
        # NOTE: ISO 9001 NOT present. Only ISO 14001 (Environmental) supplied.
        iso_present=True,
        iso_standard="ISO 14001:2015",
        iso_certificate_no="DNV-EMS/HYD/2024/TASL-00318",
        iso_issuing_body="DNV Business Assurance India Pvt. Ltd.",
        iso_scope=("Environmental Management System for Aerostructures and Special "
                   "Vehicles Manufacturing Operations, Hyderabad facility"),
        iso_valid_until=date(2027, 2, 9),
        past_contracts=(
            {"customer": "Indian Army (DGOF Ordnance Liaison)",
             "work": "Special-purpose Light Armoured Multi-role Vehicles — 64 units",
             "agreement_no": "DGOF/SLAMV/2020-21/0061",
             "start": "19-Jan-2021", "end": "30-Jun-2023",
             "value_cr": 188.40},
            {"customer": "Central Reserve Police Force",
             "work": "Up-armoured Troop Carriers for LWE Operations — 48 units",
             "agreement_no": "CRPF/UATC-LWE/2021-22/0026",
             "start": "15-Sep-2021", "end": "11-Dec-2023",
             "value_cr": 102.18},
            {"customer": "Indo-Tibetan Border Police (MHA)",
             "work": "High-Altitude Special Mobility Platforms — 30 units",
             "agreement_no": "ITBP/HASMP/2022-23/0019",
             "start": "01-Mar-2023", "end": "18-Apr-2024",
             "value_cr": 71.92},
        ),
        affidavit_date=AFFIDAVIT_RECENT,
        dsc_holder="Shri Vikram Krishnamurthy",
        dsc_serial="9C:11:0E:62:7F:88:43:AA:21:55",
        dsc_issuing_ca="Capricorn Identity Services Pvt. Ltd.",
        dsc_valid_until=date(2026, 12, 22),
        ca_firm=CA_HYDERABAD,
        profile_kind="missing-iso",
        extra_note=("ISO 9001:2015 (Quality Management System) certificate is NOT "
                    "submitted with this bid; only ISO 14001:2015 (Environmental "
                    "Management System) is enclosed."),
    ),

    # --- 4. Force Motors (AMBIGUOUS) ------------------------------------
    BidderProfile(
        slug="bidder-force-motors",
        firm_name="Force Motors Ltd.",
        address="Mumbai-Pune Road, Akurdi, Pune - 411 035",
        cin="L34102MH1958PLC011187",
        pan="AAACF8721P",
        gstin="27AAACF8721P1ZA",
        phone="+91-20-2747-6381",
        email="govt.tendering@forcemotors.com",
        incorporation_date="22-Aug-1958",
        # Defence contribution to consolidated turnover. 3yr avg ~ 6.81 Cr (above 5 Cr).
        turnover_3yr_cr=(5.84, 6.92, 7.68),
        # Net worth borderline - INR 2.18 Cr against INR 2 Cr threshold
        net_worth_cr=2.18,
        iso_present=True,
        iso_standard="ISO 9001:2015",
        iso_certificate_no="BV-IND/QMS/2023/FML-PITHAMPUR-00742",
        iso_issuing_body="Bureau Veritas (India) Pvt. Ltd.",
        # AMBIGUOUS: ISO is for Pithampur (MP) commercial-vehicle plant, NOT
        # the Akurdi defence/special-vehicles plant where the work would execute.
        iso_scope=("Manufacture of Light Commercial Vehicles, Multi-Utility Vehicles "
                   "and Tempo Traveller passenger variants at the Pithampur Plant, "
                   "Madhya Pradesh"),
        iso_valid_until=date(2026, 8, 11),
        past_contracts=(
            {"customer": "Border Security Force (MHA)",
             "work": "Light Patrol Vehicles for Western Sector — 84 units",
             "agreement_no": "BSF/LPV-WS/2019-20/0113",
             "start": "12-Nov-2019", "end": "26-Aug-2022",
             "value_cr": 22.40},
            {"customer": "Indian Army (Sub Area Maintenance)",
             "work": "Soft-skin Personnel Carriers — 132 units",
             "agreement_no": "IA/SAM/SSPC/2020-21/0072",
             "start": "20-Jul-2020", "end": "15-Mar-2023",
             "value_cr": 18.18},
            {"customer": "Sashastra Seema Bal (MHA)",
             "work": "Patrol Vehicles for Eastern Sector — 56 units",
             "agreement_no": "SSB/PV-ES/2022-23/0041",
             "start": "08-Apr-2022", "end": "30-Sep-2023",
             "value_cr": 11.92},
        ),
        affidavit_date=AFFIDAVIT_STALE,   # 14+ months old
        dsc_holder="Shri Prasan Firodia",
        dsc_serial="2D:64:91:8B:0F:55:CC:31:74:08",
        dsc_issuing_ca="eMudhra Consumer Services Limited",
        dsc_valid_until=date(2026, 6, 30),
        ca_firm=CA_PUNE,
        profile_kind="ambiguous",
        extra_note=("ISO 9001:2015 certificate scope covers the Pithampur (MP) "
                    "commercial-vehicle plant; the special-vehicles assembly for "
                    "this tender would be executed at the Akurdi (Pune) facility. "
                    "Net worth of INR 2.18 Cr is marginally above the INR 2 Cr "
                    "threshold. Non-blacklisting affidavit pre-dates the tender "
                    "by approximately 14 months."),
    ),
)


# ---------------------------------------------------------------------------
# PDF #1 — Financial Credentials (4-5 pages)
# ---------------------------------------------------------------------------

def gen_financial_credentials(path: str, rl: dict, st: dict,
                              p: BidderProfile) -> None:
    story: list = []
    P = rl["Paragraph"]
    PB = rl["PageBreak"]

    # ---------- Page 1: CA-attested Turnover Certificate ----------
    story.append(P(p.ca_firm.name, st["title"]))
    story.append(P(p.ca_firm.address, st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.4))
    story.append(P("CERTIFICATE OF AVERAGE ANNUAL TURNOVER", st["title"]))
    story.append(P("(Defence / Special Vehicles Segment)", st["subtitle"]))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"This is to certify that we have audited the books of accounts of "
        f"<b>{p.firm_name}</b> (CIN: {p.cin}; PAN: {p.pan}; GSTIN: {p.gstin}), "
        f"having its registered office at {p.address}, for the last three "
        f"financial years viz. FY 2021-22, FY 2022-23 and FY 2023-24.",
        st["body"]))
    story.append(_sp(rl, 0.2))

    fy_labels = ("FY 2021-22", "FY 2022-23", "FY 2023-24")
    rupees = tuple(int(round(cr * 1_00_00_000)) for cr in p.turnover_3yr_cr)
    avg_rupees = sum(rupees) // 3
    avg_cr = sum(p.turnover_3yr_cr) / 3

    rows = [["Financial Year",
             "Turnover - Defence / Special Vehicles Segment (INR)"]]
    for label, val in zip(fy_labels, rupees):
        rows.append([label, f"INR {_fmt_inr(val)}"])
    rows.append(["Average Annual Turnover (3 years)",
                 f"INR {_fmt_inr(avg_rupees)}"])

    story.append(_kv_table(rl, rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#2c5f8a", highlight_last=True))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"The Average Annual Turnover (Defence / Special Vehicles segment) of "
        f"<b>{p.firm_name}</b> for the last three financial years is "
        f"<b>INR {_fmt_inr(avg_rupees)}</b> "
        f"(approximately INR {avg_cr:.2f} Crore).",
        st["body"]))

    if p.profile_kind == "shortfall":
        story.append(_sp(rl, 0.2))
        story.append(P(
            f"Note: Average annual turnover (Defence segment) FY2021-22 to FY2023-24: "
            f"INR {_fmt_inr(avg_rupees)}. This figure is below the threshold of "
            f"INR 5,00,00,000 (INR 5 Crore) prescribed in the tender document.",
            st["warning"]))

    story += _signature(rl, st,
                        "CA Suresh " + p.ca_firm.name.split()[1].rstrip(",.&"),
                        "Proprietor",
                        f"{p.ca_firm.name}\nMembership No.: {p.ca_firm.member_no}",
                        stamp=f"ICAI MEMBER - UDIN: {p.ca_firm.udin}")
    story.append(PB())

    # ---------- Page 2: Audited Balance Sheet excerpt ----------
    story.append(P(p.firm_name, st["title"]))
    story.append(P(f"CIN: {p.cin}", st["subtitle"]))
    story.append(_divider(rl))
    story.append(P("AUDITED FINANCIAL STATEMENTS - EXTRACT",
                   st["title"]))
    story.append(P("Statement of Profit and Loss (Defence Segment) - "
                   "Three Year Comparative",
                   st["subtitle"]))
    story.append(_sp(rl, 0.3))

    t0, t1, t2 = p.turnover_3yr_cr
    pl_rows = [
        ["Particulars (INR in Lakhs)", "FY 2021-22", "FY 2022-23", "FY 2023-24"],
        ["Revenue from Operations",
         f"{t0 * 100:,.2f}", f"{t1 * 100:,.2f}", f"{t2 * 100:,.2f}"],
        ["Other Operating Income",
         f"{t0 * 4.2:,.2f}", f"{t1 * 4.4:,.2f}", f"{t2 * 4.6:,.2f}"],
        ["Total Income",
         f"{t0 * 104.2:,.2f}", f"{t1 * 104.4:,.2f}", f"{t2 * 104.6:,.2f}"],
        ["Cost of Materials Consumed",
         f"{t0 * 62:,.2f}", f"{t1 * 61:,.2f}", f"{t2 * 61.5:,.2f}"],
        ["Employee Benefit Expenses",
         f"{t0 * 14:,.2f}", f"{t1 * 13.8:,.2f}", f"{t2 * 13.9:,.2f}"],
        ["Finance Costs",
         f"{t0 * 3.1:,.2f}", f"{t1 * 3.0:,.2f}", f"{t2 * 2.8:,.2f}"],
        ["Depreciation & Amortization",
         f"{t0 * 5.4:,.2f}", f"{t1 * 5.6:,.2f}", f"{t2 * 5.5:,.2f}"],
        ["Total Expenses",
         f"{t0 * 84.5:,.2f}", f"{t1 * 83.4:,.2f}", f"{t2 * 83.7:,.2f}"],
        ["Profit Before Tax (PBT)",
         f"{t0 * 19.7:,.2f}", f"{t1 * 21.0:,.2f}", f"{t2 * 20.9:,.2f}"],
        ["Less: Tax Expense (Current + Deferred)",
         f"{t0 * 5.1:,.2f}", f"{t1 * 5.4:,.2f}", f"{t2 * 5.4:,.2f}"],
        ["Net Profit / Profit After Tax (PAT)",
         f"{t0 * 14.6:,.2f}", f"{t1 * 15.6:,.2f}", f"{t2 * 15.5:,.2f}"],
    ]
    table = rl["Table"](pl_rows,
                        colWidths=[6.5 * rl["cm"], 3 * rl["cm"],
                                   3 * rl["cm"], 3 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl["colors"].white, rl["colors"].HexColor("#f0f4f8")]),
    ]))
    story.append(table)
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"Prepared in accordance with Schedule III of the Companies Act, 2013 "
        f"and Indian Accounting Standards (Ind AS). Audited and certified by "
        f"{p.ca_firm.name}, {p.ca_firm.address}.",
        st["small"]))
    story += _signature(rl, st, "CA Suresh " + p.ca_firm.name.split()[1].rstrip(",.&"),
                        "Statutory Auditor",
                        p.ca_firm.name,
                        stamp=f"UDIN: {p.ca_firm.udin}")
    story.append(PB())

    # ---------- Page 3: Net Worth Certificate ----------
    story.append(P(p.ca_firm.name, st["title"]))
    story.append(P(p.ca_firm.address, st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P("CERTIFICATE OF NET WORTH", st["title"]))
    story.append(P("(As at 31st March, 2024)", st["subtitle"]))
    story.append(_sp(rl, 0.4))

    nw_rupees = int(round(p.net_worth_cr * 1_00_00_000))
    paid_up = int(nw_rupees * 0.42)
    reserves = nw_rupees - paid_up

    story.append(P(
        f"This is to certify that on examination of the audited financial "
        f"statements and books of accounts of <b>{p.firm_name}</b> "
        f"(CIN: {p.cin}, PAN: {p.pan}) as at 31st March 2024, the Net Worth "
        f"of the Company is computed as under:",
        st["body"]))
    story.append(_sp(rl, 0.3))

    nw_rows = [
        ["Component", "Amount (INR)"],
        ["Paid-up Equity Share Capital", f"INR {_fmt_inr(paid_up)}"],
        ["Reserves & Surplus (excluding Revaluation Reserve)",
         f"INR {_fmt_inr(reserves)}"],
        ["Less: Accumulated Losses / Misc. Expenditure", "INR  Nil"],
        [f"Net Worth as at 31-Mar-2024",
         f"INR {_fmt_inr(nw_rupees)}"],
    ]
    story.append(_kv_table(rl, nw_rows,
                           col_widths=[10 * rl["cm"], 6 * rl["cm"]],
                           header_bg="#2c5f8a", highlight_last=True))
    story.append(_sp(rl, 0.4))

    story.append(P(
        f"The Net Worth of <b>{p.firm_name}</b> as on 31st March 2024 is "
        f"<b>INR {_fmt_inr(nw_rupees)}</b> "
        f"(approximately INR {p.net_worth_cr:.2f} Crore), computed as per the "
        f"definition under Section 2(57) of the Companies Act, 2013.",
        st["body"]))

    if p.profile_kind == "ambiguous":
        story.append(_sp(rl, 0.2))
        story.append(P(
            f"The certified net worth of INR {_fmt_inr(nw_rupees)} "
            f"(INR {p.net_worth_cr:.2f} Crore) is marginally above the "
            f"prescribed threshold of INR 2,00,00,000 (INR 2 Crore).",
            st["small"]))

    story += _signature(rl, st,
                        "CA Suresh " + p.ca_firm.name.split()[1].rstrip(",.&"),
                        "Proprietor",
                        f"{p.ca_firm.name}\nMembership No.: {p.ca_firm.member_no}",
                        stamp=f"ICAI MEMBER - UDIN: {p.ca_firm.udin}")
    story.append(PB())

    # ---------- Page 4: CA letterhead / declarations ----------
    story.append(P(p.ca_firm.name, st["title"]))
    story.append(P(p.ca_firm.address +
                   f" | Membership No.: {p.ca_firm.member_no}",
                   st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"Date: {ISSUE_RECENT.strftime('%d-%B-%Y')}", st["right"]))
    story.append(P("To,", st["body_left"]))
    story.append(P("The Tender Inviting Authority,", st["body_left"]))
    story.append(P("(As specified in the NIT)", st["body_left"]))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"<b>Subject:</b> Confirmation of financial credentials of "
        f"{p.firm_name} for participation in the said tender.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P(
        "Sir / Madam,", st["body_left"]))
    story.append(P(
        "We hereby confirm that the certificates issued by us in respect "
        "of Average Annual Turnover and Net Worth of the captioned company "
        "have been prepared after due examination of the audited books of "
        "accounts for the last three financial years and are issued in "
        "accordance with the Standards on Auditing prescribed by the "
        "Institute of Chartered Accountants of India.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P(
        "The Unique Document Identification Number (UDIN) for these "
        f"certificates is <b>{p.ca_firm.udin}</b>, which can be verified "
        f"on the ICAI UDIN portal at https://udin.icai.org/.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P(
        "Yours faithfully,", st["body_left"]))
    story += _signature(rl, st,
                        "CA Suresh " + p.ca_firm.name.split()[1].rstrip(",.&"),
                        "Proprietor",
                        f"{p.ca_firm.name}\nFRN: 002841S")

    _build_doc(path, story, rl)


# ---------------------------------------------------------------------------
# PDF #2 — Compliance Certificates (4-5 pages)
# ---------------------------------------------------------------------------

def gen_compliance_certs(path: str, rl: dict, st: dict,
                         p: BidderProfile) -> None:
    story: list = []
    P = rl["Paragraph"]
    PB = rl["PageBreak"]

    # ---------- Page 1: ISO Certificate (or 14001 substitute) ----------
    story.append(P(p.iso_issuing_body, st["title"]))
    story.append(P("Accredited by the National Accreditation Board for "
                   "Certification Bodies (NABCB)", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P("CERTIFICATE OF REGISTRATION", st["title"]))
    story.append(P(p.iso_standard +
                   (" - Quality Management System"
                    if p.iso_standard.startswith("ISO 9001")
                    else " - Environmental Management System"),
                   st["subtitle"]))
    story.append(_sp(rl, 0.4))

    iso_status = "VALID"
    iso_rows = [
        ["Certificate No.", p.iso_certificate_no],
        ["Standard", p.iso_standard],
        ["Issuing Body", p.iso_issuing_body],
        ["Certified Organisation", p.firm_name],
        ["Registered Address", p.address],
        ["Scope of Certification", p.iso_scope],
        ["Date of Initial Certification", "11-Aug-2018"],
        ["Date of Latest Recertification", "27-Sep-2023"],
        ["Certificate Valid Until", p.iso_valid_until.strftime("%d-%b-%Y")],
        ["Status", iso_status],
    ]
    story.append(_kv_table(rl, iso_rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#e8f0fe", highlight_last=True,
                           highlight_color="#d4edda"))
    story.append(_sp(rl, 0.3))

    if p.profile_kind == "missing-iso":
        story.append(P(
            "Note: This certificate covers ISO 14001:2015 (Environmental "
            "Management System). The bidder has NOT submitted any "
            "ISO 9001:2015 (Quality Management System) certificate as part "
            "of this bid; tender Annexure-D requires ISO 9001:2015 specifically.",
            st["warning"]))
    elif p.profile_kind == "ambiguous":
        story.append(P(
            "Note: The scope of this ISO 9001:2015 certificate is restricted "
            "to the Pithampur (Madhya Pradesh) commercial-vehicle plant. The "
            "Akurdi (Pune) special-vehicles facility - where the tender work "
            "would be executed - is NOT included in the certified scope.",
            st["warning"]))
    else:
        story.append(P(
            "This certificate confirms that the Quality Management System of "
            "the certified organisation has been audited and found to conform "
            "with the requirements of " + p.iso_standard + ". The certificate "
            "remains valid subject to satisfactory completion of surveillance "
            "audits at intervals of twelve (12) months.",
            st["body"]))

    story += _signature(rl, st,
                        "Dr. Anil Mehrotra", "Lead Auditor / Scheme Manager",
                        p.iso_issuing_body,
                        stamp="NABCB ACCREDITED CB / SCHEME-QMS-001")
    story.append(PB())

    # ---------- Page 2: GST Registration Certificate ----------
    story.append(P("भारत सरकार / GOVERNMENT OF INDIA", st["title"]))
    story.append(P("Goods and Services Tax Network (GSTN)", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P("CERTIFICATE OF GST REGISTRATION", st["title"]))
    story.append(P("[Form GST REG-06, Rule 10(1)]", st["subtitle"]))
    story.append(_sp(rl, 0.4))

    gst_rows = [
        ["GSTIN / UIN", p.gstin],
        ["Legal Name", p.firm_name],
        ["Trade Name", p.firm_name.replace(" Pvt. Ltd.", "").replace(" Ltd.", "")],
        ["Constitution of Business", "Private Limited Company"
         if "Pvt" in p.firm_name else "Public Limited Company"],
        ["Date of Liability", "01-Jul-2017"],
        ["Date of Validity", "Until cancelled"],
        ["Type of Registration", "Regular"],
        ["Principal Place of Business", p.address],
        ["Nature of Business Activities",
         "Manufacture; Wholesale Business; Works Contract"],
        ["Status", "ACTIVE"],
    ]
    story.append(_kv_table(rl, gst_rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#fff9e6", highlight_last=True,
                           highlight_color="#d4edda"))
    story.append(_sp(rl, 0.4))
    story.append(P(
        "This is a system-generated certificate. Verify online at "
        "https://www.gst.gov.in/ using the GSTIN provided above.",
        st["small"]))
    story.append(P("[STAMP: GSTN VERIFIED - DIGITAL CERTIFICATE]",
                   st["stamp"]))
    story.append(PB())

    # ---------- Page 3: PAN + Incorporation ----------
    story.append(P("Income Tax Department, Government of India",
                   st["title"]))
    story.append(P("Permanent Account Number (PAN) Allotment Letter",
                   st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.4))
    pan_rows = [
        ["PAN", p.pan],
        ["Name of Entity", p.firm_name],
        ["Status", "Company"],
        ["Date of Incorporation / Formation", p.incorporation_date],
        ["Address on Record", p.address],
        ["AO Code", "MUM/W/142/3"
         if "Mumbai" in p.address or "Pune" in p.address
         else ("BLR/W/118/2" if "Bengaluru" in p.address
               else "HYD/W/162/4")],
    ]
    story.append(_kv_table(rl, pan_rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#e8f4e8"))
    story.append(_sp(rl, 0.4))
    story.append(P(
        "[STAMP: INCOME TAX DEPARTMENT - GOVT. OF INDIA]", st["stamp"]))
    story.append(_sp(rl, 0.4))
    story.append(P("CERTIFICATE OF INCORPORATION", st["h2"]))
    story.append(P(
        f"Issued by the Registrar of Companies under the Companies Act, 2013. "
        f"<b>{p.firm_name}</b> was incorporated on {p.incorporation_date} "
        f"under Corporate Identity Number (CIN): <b>{p.cin}</b>. The Company "
        f"is presently active on the Master Data of the Ministry of Corporate "
        f"Affairs (https://www.mca.gov.in/).",
        st["body"]))
    story.append(_sp(rl, 0.3))
    story += _signature(rl, st, "Registrar of Companies", "MCA21",
                        "Ministry of Corporate Affairs, Government of India",
                        stamp="MCA21 - DIGITALLY SIGNED")
    story.append(PB())

    # ---------- Page 4: Class III DSC ----------
    story.append(P("Controller of Certifying Authorities (CCA)",
                   st["title"]))
    story.append(P("Ministry of Electronics & Information Technology, "
                   "Government of India", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P("DIGITAL SIGNATURE CERTIFICATE - CLASS III",
                   st["title"]))
    story.append(P("Issued under the Information Technology Act, 2000",
                   st["subtitle"]))
    story.append(_sp(rl, 0.4))

    dsc_rows = [
        ["Certificate Class", "Class 3 - Organisation "
                              "(Signing & Encryption)"],
        ["Common Name (CN)", p.dsc_holder.upper()],
        ["Organisation (O)", p.firm_name],
        ["Organisational Unit (OU)", "Government Tendering"],
        ["Country (C)", "IN"],
        ["Serial Number", p.dsc_serial],
        ["Issuing Certifying Authority", p.dsc_issuing_ca],
        ["Valid From", ISSUE_RECENT.strftime("%d-%b-%Y")],
        ["Valid To", p.dsc_valid_until.strftime("%d-%b-%Y")],
        ["Key Usage", "Digital Signature, Non-Repudiation, "
                      "Key Encipherment"],
        ["Status", "ACTIVE"],
    ]
    story.append(_kv_table(rl, dsc_rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#e8f0fe", highlight_last=True,
                           highlight_color="#d4edda"))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"This Class III Digital Signature Certificate has been issued to "
        f"{p.dsc_holder} of {p.firm_name} by {p.dsc_issuing_ca}, a Licensed "
        f"Certifying Authority under the IT Act, 2000. The certificate is "
        f"valid for use on Government e-procurement portals (CPPP, GeM, "
        f"defproc.gov.in) and complies with the e-tendering requirements "
        f"prescribed under the General Financial Rules, 2017.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P("[STAMP: CCA INDIA - LICENSED CERTIFYING AUTHORITY]",
                   st["stamp"]))

    _build_doc(path, story, rl)


# ---------------------------------------------------------------------------
# PDF #3 — Experience Record (4-5 pages)
# ---------------------------------------------------------------------------

def gen_experience_record(path: str, rl: dict, st: dict,
                          p: BidderProfile) -> None:
    story: list = []
    P = rl["Paragraph"]
    PB = rl["PageBreak"]

    # ---------- Page 1: Company Profile ----------
    story.append(P(p.firm_name, st["title"]))
    story.append(P(f"CIN: {p.cin} | GSTIN: {p.gstin} | PAN: {p.pan}",
                   st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P("COMPANY PROFILE & TRACK RECORD",
                   st["title"]))
    story.append(P("(Submitted in accordance with Annexure-C of the NIT)",
                   st["subtitle"]))
    story.append(_sp(rl, 0.3))

    inc_year = int(p.incorporation_date.split("-")[-1])
    years_in_business = TODAY.year - inc_year
    years_in_def = min(years_in_business, 18)

    profile_rows = [
        ["Date of Incorporation", p.incorporation_date],
        ["Years in Business", f"{years_in_business} years"],
        ["Years in Defence / Special Vehicles segment",
         f"{years_in_def} years"],
        ["Registered Office", p.address],
        ["Phone", p.phone],
        ["Email", p.email],
        ["Manufacturing Plants",
         "Faridabad (HR), Pune (MH)" if "Mahindra" in p.firm_name
         else ("KGF (KA), Mysuru (KA)" if "BEML" in p.firm_name
               else ("Hyderabad (TG), Bengaluru (KA)"
                     if "Tata" in p.firm_name
                     else "Akurdi (Pune, MH), Pithampur (MP)"))],
    ]
    story.append(_kv_table(rl, profile_rows,
                           col_widths=[6 * rl["cm"], 10 * rl["cm"]],
                           header_bg="#fff9e6"))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"<b>{p.firm_name}</b> has been engaged in the design, manufacture "
        f"and supply of armoured / special-mission vehicles to Indian "
        f"Government customers for <b>{years_in_def} years</b>. The Company's "
        f"core capabilities include monocoque hull armouring, V-shaped "
        f"mine-blast architecture, ballistic glass integration to STANAG 4569 "
        f"levels and run-flat wheel systems. The Company maintains in-house "
        f"capability for ballistic testing, EMI / EMC compliance and "
        f"environmental qualification per JSS 55555.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P(
        f"Over the last five years the Company has executed orders aggregating "
        f"to over INR {sum(c['value_cr'] for c in p.past_contracts):,.2f} "
        f"Crore for the Indian Army, paramilitary forces (CRPF, BSF, ITBP, "
        f"SSB) and Central Armed Police Organisations.",
        st["body"]))
    story.append(PB())

    # ---------- Page 2: Past Contracts (table) ----------
    story.append(P("PAST CONTRACTS - LAST FIVE (5) YEARS",
                   st["title"]))
    story.append(P("(Armoured / Special-Mission Vehicles - "
                   "Government Customers)",
                   st["subtitle"]))
    story.append(_sp(rl, 0.3))

    contract_rows = [
        ["#", "Customer / Agreement No.", "Scope of Work",
         "Period", "Value (INR Cr)"]
    ]
    for i, c in enumerate(p.past_contracts, start=1):
        contract_rows.append([
            str(i),
            f"{c['customer']}\n{c['agreement_no']}",
            c["work"],
            f"{c['start']} to\n{c['end']}",
            f"{c['value_cr']:.2f}",
        ])
    table = rl["Table"](contract_rows,
                        colWidths=[0.8 * rl["cm"], 4.0 * rl["cm"],
                                   5.5 * rl["cm"], 3.2 * rl["cm"],
                                   2.5 * rl["cm"]])
    table.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl["colors"].white, rl["colors"].HexColor("#f0f4f8")]),
    ]))
    story.append(table)
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"The above contracts demonstrate continuous engagement in the "
        f"armoured / special-vehicles segment for at least the past five (5) "
        f"financial years. Each contract has been satisfactorily completed / "
        f"is being executed without any cost or time overruns of penal "
        f"consequence. Customer-issued performance certificates are enclosed "
        f"on the following pages.",
        st["body"]))
    story.append(PB())

    # ---------- Page 3 & 4: Two completion certificates ----------
    for cert_idx, c in enumerate(p.past_contracts[:2]):
        story.append(P("PERFORMANCE / WORK COMPLETION CERTIFICATE",
                       st["title"]))
        story.append(P(c["customer"], st["subtitle"]))
        story.append(_divider(rl))
        story.append(_sp(rl, 0.3))
        story.append(P(
            f"This is to certify that <b>{p.firm_name}</b> "
            f"(GSTIN: {p.gstin}) has satisfactorily executed the following "
            f"contract for this office / Force:",
            st["body"]))
        story.append(_sp(rl, 0.2))
        cert_rows = [
            ["Customer", c["customer"]],
            ["Agreement / Contract No.", c["agreement_no"]],
            ["Scope of Supply", c["work"]],
            ["Date of Award", c["start"]],
            ["Date of Final Acceptance", c["end"]],
            ["Order Value", f"INR {c['value_cr']:.2f} Crore"],
            ["Quality of Execution", "Satisfactory"],
            ["Liquidated Damages Imposed", "Nil"],
            ["Remarks", "The contractor has demonstrated capability to "
                        "manufacture, integrate and supply armoured / "
                        "special-mission vehicles in conformity with the "
                        "Qualitative Requirements specified by this office."],
        ]
        story.append(_kv_table(rl, cert_rows,
                               col_widths=[5.5 * rl["cm"], 10.5 * rl["cm"]],
                               header_bg="#fff9e6"))
        story.append(_sp(rl, 0.3))
        if "Army" in c["customer"]:
            signer_name, signer_desg = ("Brig. R. Subramaniam, VSM",
                                        "Director (Mechanised Forces)")
        elif "CRPF" in c["customer"]:
            signer_name, signer_desg = ("Shri Anand Prakash, IPS",
                                        "Inspector General (Equipment)")
        elif "BSF" in c["customer"]:
            signer_name, signer_desg = ("Shri Vijay Kumar, IPS",
                                        "Inspector General (Procurement)")
        else:
            signer_name, signer_desg = ("Shri Pradeep Sharma, IPS",
                                        "Deputy Inspector General")
        story += _signature(rl, st, signer_name, signer_desg,
                            c["customer"],
                            stamp="GOVT OF INDIA - OFFICE SEAL")
        story.append(PB())

    _build_doc(path, story, rl)


# ---------------------------------------------------------------------------
# PDF #4 — Declarations (3-4 pages)
# ---------------------------------------------------------------------------

def gen_declarations(path: str, rl: dict, st: dict,
                     p: BidderProfile) -> None:
    story: list = []
    P = rl["Paragraph"]
    PB = rl["PageBreak"]

    # ---------- Page 1: Non-Blacklisting Affidavit ----------
    story.append(P("AFFIDAVIT", st["title"]))
    story.append(P("(Self-Declaration of Non-Blacklisting and "
                   "Non-Debarment)", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P(f"Date of Affidavit: "
                   f"{p.affidavit_date.strftime('%d-%B-%Y')}",
                   st["right"]))
    story.append(P(
        "Sworn before Notary Public, "
        + ("Mumbai" if "Mumbai" in p.address
           else ("Bengaluru" if "Bengaluru" in p.address
                 else ("Hyderabad" if "Hyderabad" in p.address
                       else "Pune"))),
        st["right"]))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"I, <b>{p.dsc_holder}</b>, son of Late Shri R. K. {p.dsc_holder.split()[-1]}, "
        f"aged about 54 years, being the duly authorised signatory of "
        f"<b>{p.firm_name}</b> (CIN: {p.cin}; GSTIN: {p.gstin}) having its "
        f"registered office at {p.address}, do hereby solemnly affirm and "
        f"declare on oath as under:",
        st["body"]))
    story.append(_sp(rl, 0.2))

    clauses = [
        f"That {p.firm_name} has NOT been blacklisted, debarred or suspended "
        "by any Ministry / Department of the Government of India, any "
        "Public Sector Undertaking, any State Government, any Central / State "
        "Armed Police Force, or any Public Procurement entity as on the date "
        "of this affidavit.",
        f"That {p.firm_name} has NOT been convicted of any offence "
        "involving moral turpitude, fraudulent practice, collusive "
        "practice, coercive practice or corrupt practice as defined in "
        "the Central Vigilance Commission's standard procurement guidelines.",
        "That no criminal proceedings are pending against the Company or any "
        "of its Directors before any court of competent jurisdiction in "
        "connection with the subject matter of this tender.",
        f"That {p.firm_name} has not been declared insolvent or undergone "
        "any insolvency / bankruptcy proceedings under the Insolvency and "
        "Bankruptcy Code, 2016, in the last three (3) years.",
        "That all information furnished in our bid is true and correct to "
        "the best of our knowledge and belief; we are aware that any "
        "false declaration shall render the bid liable for rejection and "
        "may attract penal action under applicable laws.",
    ]
    for i, cl in enumerate(clauses, start=1):
        story.append(P(f"{i}. {cl}", st["body"]))

    story.append(_sp(rl, 0.3))
    if p.profile_kind == "ambiguous":
        days_old = (TODAY - p.affidavit_date).days
        months_old = days_old // 30
        story.append(P(
            f"Note: This affidavit was sworn on "
            f"{p.affidavit_date.strftime('%d-%B-%Y')}, which is approximately "
            f"{months_old} months prior to the bid submission date. The tender "
            f"document at Clause 4.7 requires the non-blacklisting "
            f"self-declaration to have been sworn within the preceding "
            f"twelve (12) months.",
            st["warning"]))
    story.append(_sp(rl, 0.2))
    story.append(P("Deponent / Authorised Signatory:", st["body_left"]))
    story += _signature(rl, st, p.dsc_holder, "Authorised Signatory & Director",
                        p.firm_name)
    story.append(_sp(rl, 0.2))
    story.append(P("[STAMP: NOTARY PUBLIC]", st["stamp"]))
    story.append(P("[STAMP: INR 100 NON-JUDICIAL STAMP PAPER]",
                   st["stamp"]))
    story.append(PB())

    # ---------- Page 2: Integrity Pact ----------
    story.append(P("INTEGRITY PACT", st["title"]))
    story.append(P("(Pre-contract Integrity Pact - prescribed by the "
                   "Central Vigilance Commission)", st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P(
        f"This Integrity Pact is entered into on "
        f"{ISSUE_RECENT.strftime('%d-%B-%Y')} between the Government of India "
        f"acting through the Tender Inviting Authority (hereinafter \"the "
        f"Principal\") and <b>{p.firm_name}</b> (hereinafter \"the Bidder\").",
        st["body"]))
    story.append(_sp(rl, 0.2))
    for h, body in [
        ("Article 1 - Commitments of the Principal",
         "The Principal commits itself to take all measures necessary to "
         "prevent corruption and to observe the following principles: no "
         "employee of the Principal shall demand or accept any material or "
         "immaterial benefit from the Bidder; the Principal will treat all "
         "Bidders with equity and reason; the Principal will exclude from "
         "the process all known prejudiced persons."),
        ("Article 2 - Commitments of the Bidder",
         "The Bidder commits itself to take all measures necessary to "
         "prevent corruption during the bid process and any subsequent "
         "contract execution. The Bidder shall NOT, directly or through any "
         "intermediary, offer, promise or give to any of the Principal's "
         "employees any material or immaterial benefit which the said "
         "employee is not legally entitled to."),
        ("Article 3 - Disqualification, Damages and Forfeiture",
         "If the Bidder, during the bid process or contract execution, has "
         "committed a transgression through a violation of Article 2 or in "
         "any other form such as to put its reliability or credibility as "
         "Bidder into question, the Principal is entitled to disqualify the "
         "Bidder from the bid process, terminate the contract, forfeit the "
         "Earnest Money Deposit / Performance Bank Guarantee, and recover "
         "all damages."),
        ("Article 4 - Independent External Monitor",
         "The Principal has appointed competent and credible Independent "
         "External Monitors (IEMs) for this Pact. The IEM has the right to "
         "access all project documentation and to be informed of any "
         "transgression. The IEM shall report any substantiated suspicion "
         "of an offence under relevant Indian penal provisions to the "
         "Chief Vigilance Officer of the Principal."),
    ]:
        story.append(P(f"<b>{h}</b>", st["h2"]))
        story.append(P(body, st["body"]))

    story.append(_sp(rl, 0.3))
    story.append(P("Signed by:", st["h2"]))
    story.append(P("For the Principal:", st["body_left"]))
    story.append(P("Sd/- [Authorised Signatory of the Tender Inviting Authority]",
                   st["body_left"]))
    story.append(_sp(rl, 0.3))
    story.append(P(f"For the Bidder: <b>{p.firm_name}</b>", st["body_left"]))
    story += _signature(rl, st, p.dsc_holder, "Director",
                        p.firm_name)
    story.append(PB())

    # ---------- Page 3: Tender Acceptance Letter ----------
    story.append(P(p.firm_name, st["title"]))
    story.append(P(p.address, st["subtitle"]))
    story.append(_divider(rl))
    story.append(_sp(rl, 0.3))
    story.append(P(f"Date: {ISSUE_RECENT.strftime('%d-%B-%Y')}", st["right"]))
    story.append(P("To,", st["body_left"]))
    story.append(P("The Tender Inviting Authority,", st["body_left"]))
    story.append(P("(As specified in the NIT)", st["body_left"]))
    story.append(_sp(rl, 0.3))
    story.append(P(
        "<b>Subject:</b> Acceptance of tender terms and conditions for "
        "Procurement of Armoured / Special-Mission Vehicles.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P("Sir / Madam,", st["body_left"]))
    story.append(P(
        f"We, <b>{p.firm_name}</b>, having read and examined the Notice "
        f"Inviting Tender, the Tender Documents and all Addenda issued "
        f"thereto, do hereby agree to execute the said work / supply in "
        f"strict accordance with the provisions of the tender documents at "
        f"the rates quoted in our Price Bid.",
        st["body"]))
    story.append(_sp(rl, 0.2))
    story.append(P(
        "We unconditionally accept all Terms & Conditions as set out in "
        "the Notice Inviting Tender, including but not limited to the "
        "General Conditions of Contract, Special Conditions of Contract, "
        "Technical Specifications, the Schedule of Requirements, and the "
        "Pre-contract Integrity Pact. We further confirm that we shall "
        "abide by the Manual for Procurement of Goods (2017) of the "
        "Department of Expenditure, Ministry of Finance.",
        st["body"]))
    story.append(_sp(rl, 0.2))

    if p.profile_kind == "shortfall":
        accept_note = (
            "We further declare that the Average Annual Turnover of our "
            "Defence / Special Vehicles segment, as certified by our "
            "statutory auditors, is INR 3,21,45,000 over the last three "
            "financial years. We have nevertheless submitted our bid based "
            "on the consolidated revenue of the Company across all segments "
            "for the consideration of the Tender Evaluation Committee."
        )
        story.append(P(accept_note, st["body"]))
        story.append(_sp(rl, 0.2))
    elif p.profile_kind == "missing-iso":
        accept_note = (
            "In lieu of the ISO 9001:2015 (Quality Management System) "
            "certificate, we have enclosed our ISO 14001:2015 (Environmental "
            "Management System) certificate. We undertake to obtain ISO "
            "9001:2015 certification within 90 days of contract award, "
            "should the Tender Inviting Authority accept our bid."
        )
        story.append(P(accept_note, st["body"]))
        story.append(_sp(rl, 0.2))

    story.append(P(
        "We confirm that the bid shall remain valid for 180 days from the "
        "date of bid opening, and that all information furnished in our bid "
        "is true and correct to the best of our knowledge.",
        st["body"]))
    story.append(_sp(rl, 0.3))
    story.append(P("Yours faithfully,", st["body_left"]))
    story += _signature(rl, st, p.dsc_holder, "Director / Authorised Signatory",
                        p.firm_name,
                        stamp=f"{p.firm_name.upper()} - "
                              f"COMMON SEAL")

    _build_doc(path, story, rl)


# ---------------------------------------------------------------------------
# Bundle orchestrator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentSpec:
    filename: str
    generator: Callable[[str, dict, dict, BidderProfile], None]


DOCS_PER_BUNDLE: tuple[DocumentSpec, ...] = (
    # Filenames are keyword-loaded so the backend's filename-based
    # doc_type classifier (api/domain/routes/bidders.py::_classify_doc_type)
    # tags them correctly:
    #   "turnover" -> ca_turnover_cert
    #   "iso"      -> iso_cert
    #   "experience" -> experience_cert
    #   "blacklist"  -> blacklist_undertaking
    DocumentSpec("01_ca_turnover_balance_sheet.pdf", gen_financial_credentials),
    DocumentSpec("02_iso_gst_pan_compliance.pdf", gen_compliance_certs),
    DocumentSpec("03_experience_work_orders_completion.pdf", gen_experience_record),
    DocumentSpec("04_blacklist_integrity_declarations.pdf", gen_declarations),
)


def build_bundle(p: BidderProfile, rl: dict, force: bool) -> str:
    """Build all PDFs for a bidder and zip them. Returns ZIP path."""
    bundle_dir = os.path.join(WORK_DIR, p.slug)
    os.makedirs(bundle_dir, exist_ok=True)
    zip_path = os.path.join(DEMO_ZIPS_DIR, f"{p.slug}.zip")

    if os.path.exists(zip_path) and not force:
        print(f"  [SKIP-ZIP] {zip_path} (exists; use --force to rebuild)")
        return zip_path

    st = _styles(rl)
    print(f"  Building bundle for {p.firm_name} [{p.profile_kind}]")
    pdf_paths: list[str] = []
    for spec in DOCS_PER_BUNDLE:
        out_path = os.path.join(bundle_dir, spec.filename)
        spec.generator(out_path, rl, st, p)
        size_kb = os.path.getsize(out_path) // 1024
        print(f"    [PDF]  {spec.filename} ({size_kb} KB)")
        pdf_paths.append(out_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf in pdf_paths:
            zf.write(pdf, arcname=os.path.basename(pdf))
    size_kb = os.path.getsize(zip_path) // 1024
    print(f"    [ZIP]  {os.path.basename(zip_path)} "
          f"({size_kb} KB; {len(pdf_paths)} PDFs)")
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate TenderAudit demo bidder ZIP archives")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if zips already exist")
    args = parser.parse_args()

    os.makedirs(DEMO_ZIPS_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)

    print("=== TenderAudit Demo ZIP Generator ===")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Output dir   : {DEMO_ZIPS_DIR}")
    print(f"Today        : {TODAY.isoformat()}")
    print()

    rl = get_rl()

    zip_paths: list[str] = []
    for p in PROFILES:
        zip_paths.append(build_bundle(p, rl, args.force))

    print()
    print("=" * 60)
    print("Done. Demo ZIP summary:")
    print("=" * 60)
    for p, zp in zip(PROFILES, zip_paths):
        size_kb = os.path.getsize(zp) // 1024
        print(f"  {os.path.basename(zp):42s} ({size_kb:>4} KB)  "
              f"-> {p.profile_kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
