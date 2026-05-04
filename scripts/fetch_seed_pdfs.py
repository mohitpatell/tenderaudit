#!/usr/bin/env python3
"""Auto-download TenderAudit seed tender PDFs with placeholder fallback.

Behavior
--------
- Reads seed/MANIFEST.md from the project root, parses the table rows
- For each row: HEADs the URL; if accessible and Content-Type ~ pdf, GETs it and
  saves to seed/pdfs/{filename}
- On failure: generates a placeholder PDF using reportlab that contains:
    - Tender title and issuing body from the manifest
    - Synthetic eligibility clauses matching ground-truth criteria
    - Visible PLACEHOLDER watermark
- Idempotent: skips files that already exist with non-zero size (use --force to re-fetch)
- Logs a summary: "Downloaded X / Y real PDFs; Z placeholders generated"

Usage
-----
    python scripts/fetch_seed_pdfs.py           # from project root
    python scripts/fetch_seed_pdfs.py --force   # re-fetch even if file exists

Dependencies: reportlab, requests (plus stdlib)
"""

import argparse
import json
import os
import sys
import time

# ---------------------------------------------------------------------------
# Resolve paths relative to project root regardless of cwd
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "seed", "MANIFEST.md")
GROUND_TRUTH_PATH = os.path.join(PROJECT_ROOT, "seed", "ground_truth.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "seed", "pdfs")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
NETWORK_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

def parse_manifest(path: str) -> list[dict]:
    """Parse the markdown table in MANIFEST.md and return list of row dicts."""
    entries = []
    in_table = False
    header_skipped = False

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                if in_table:
                    break
                continue
            if not in_table:
                in_table = True
                header_skipped = False
                continue  # skip header
            if not header_skipped:
                header_skipped = True
                continue  # skip separator
            cols = [c.strip() for c in line.split("|") if c.strip()]
            if len(cols) < 4:
                continue
            filename = cols[0].strip("`")
            url = cols[1].strip()
            tender = cols[2].strip()
            issuer = cols[3].strip() if len(cols) > 3 else ""
            entries.append({
                "filename": filename,
                "url": url,
                "tender": tender,
                "issuer": issuer,
            })
    return entries


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def try_download(url: str, dest: str) -> bool:
    """Attempt to download a PDF. Returns True on success."""
    try:
        import requests
    except ImportError:
        print("  [WARN] requests not installed — cannot attempt download")
        return False

    headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"}
    try:
        print(f"  HEAD {url}")
        head = requests.head(url, headers=headers, timeout=NETWORK_TIMEOUT,
                             allow_redirects=True)
        ct = head.headers.get("Content-Type", "")
        if head.status_code != 200:
            print(f"  [SKIP] HEAD returned {head.status_code}")
            return False
        if "pdf" not in ct.lower() and "octet-stream" not in ct.lower():
            print(f"  [SKIP] Content-Type is '{ct}' — not a PDF")
            return False

        print(f"  GET  {url}")
        resp = requests.get(url, headers=headers, timeout=NETWORK_TIMEOUT,
                            allow_redirects=True, stream=True)
        resp.raise_for_status()

        content = resp.content
        if not content.startswith(b"%PDF"):
            print("  [SKIP] Response body does not start with %PDF")
            return False

        with open(dest, "wb") as f:
            f.write(content)
        size_kb = len(content) // 1024
        print(f"  [OK]  Saved {size_kb} KB → {os.path.relpath(dest, PROJECT_ROOT)}")
        return True

    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return False


# ---------------------------------------------------------------------------
# Placeholder PDF generation
# ---------------------------------------------------------------------------

def build_placeholder(entry: dict, criteria: list[dict], dest: str) -> None:
    """Generate a placeholder tender PDF with synthetic eligibility clauses."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    except ImportError:
        print("  [ERROR] reportlab not installed. Run: pip install reportlab")
        sys.exit(1)

    doc = SimpleDocTemplate(
        dest,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )
    styles = getSampleStyleSheet()

    watermark_style = ParagraphStyle(
        "Watermark", parent=styles["Normal"],
        fontSize=9, textColor=colors.red, alignment=TA_CENTER, spaceAfter=4,
    )
    title_style = ParagraphStyle(
        "TATitle", parent=styles["Heading1"],
        fontSize=13, alignment=TA_CENTER, spaceAfter=6,
    )
    heading2 = ParagraphStyle(
        "TAH2", parent=styles["Heading2"],
        fontSize=11, spaceAfter=4, spaceBefore=8,
    )
    body = ParagraphStyle(
        "TABody", parent=styles["Normal"],
        fontSize=10, leading=15, alignment=TA_JUSTIFY, spaceAfter=5,
    )
    clause_style = ParagraphStyle(
        "TAClause", parent=styles["Normal"],
        fontSize=9, leading=13, leftIndent=0.5 * cm, spaceAfter=3,
    )

    story = []

    # Watermark banner
    story.append(Paragraph(
        "⚠  PLACEHOLDER — Replace with real PDF from source URL in seed/MANIFEST.md  ⚠",
        watermark_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.red))
    story.append(Spacer(1, 0.3 * cm))

    # Government header
    story.append(Paragraph("GOVERNMENT OF INDIA", title_style))
    story.append(Paragraph(entry.get("issuer", "Issuing Authority"), title_style))
    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        f"<b>NOTICE INVITING TENDER (NIT)</b>",
        ParagraphStyle("NITHead", parent=styles["Normal"],
                       fontSize=12, alignment=TA_CENTER, spaceAfter=6),
    ))
    story.append(Paragraph(f"<b>Tender:</b> {entry.get('tender', 'N/A')}", body))
    story.append(Paragraph(f"<b>File:</b> {entry['filename']}", body))
    story.append(Paragraph(f"<b>Source URL:</b> {entry['url']}", body))
    story.append(Spacer(1, 0.4 * cm))

    # Preamble
    story.append(Paragraph("SECTION I — INTRODUCTION", heading2))
    story.append(Paragraph(
        f"{entry.get('issuer', 'The issuing authority')} invites sealed tenders from "
        "eligible and experienced contractors / firms for the work / supply described "
        "in this Tender Document. Bidders are advised to read all sections carefully "
        "before submitting their bids.",
        body,
    ))

    # Eligibility Criteria section
    story.append(Paragraph("SECTION II — ELIGIBILITY CRITERIA", heading2))
    story.append(Paragraph(
        "The following eligibility criteria are mandatory. Bids not meeting any "
        "mandatory criterion shall be summarily rejected:",
        body,
    ))
    story.append(Spacer(1, 0.2 * cm))

    if criteria:
        for c in criteria:
            cid = c.get("id", "")
            name = c.get("name", "")
            clause = c.get("source_clause", c.get("description", ""))
            req_docs = ", ".join(c.get("required_documents", []))
            mandatory = "Mandatory" if c.get("is_mandatory") else "Optional"

            # Threshold text
            threshold_str = ""
            tv = c.get("threshold_value")
            tu = c.get("threshold_unit")
            op = c.get("threshold_operator", ">=")
            if tv is not None:
                op_map = {">=": "not less than", "==": "exactly", "<=": "not more than"}
                op_word = op_map.get(op, op)
                if tu == "INR_lakhs":
                    threshold_str = f"  Threshold: {op_word} ₹{tv} Lakhs."
                elif tu == "INR":
                    threshold_str = f"  Threshold: {op_word} ₹{tv:,.0f}."
                else:
                    threshold_str = f"  Threshold: {op_word} {tv} {tu}."

            text = (
                f"<b>{cid}. {name}</b> [{mandatory}]<br/>"
                f"{clause}{threshold_str}<br/>"
                f"<i>Required documents: {req_docs}</i>"
            )
            story.append(Paragraph(text, clause_style))
            story.append(Spacer(1, 0.15 * cm))
    else:
        story.append(Paragraph(
            "Bidder must meet financial, technical, and compliance eligibility as "
            "specified in the complete tender document available at the source URL above.",
            body,
        ))

    # Document checklist
    story.append(Paragraph("SECTION III — DOCUMENTS CHECKLIST", heading2))
    all_docs = []
    seen = set()
    for c in criteria:
        for d in c.get("required_documents", []):
            if d not in seen:
                all_docs.append(d)
                seen.add(d)

    standard_docs = [
        "Tender Acceptance Letter",
        "Integrity Pact (signed)",
        "EMD / Bid Security",
        "GST Registration Certificate",
        "PAN Card",
        "Audited Balance Sheet (last 3 years)",
        "CA Certificate — Average Annual Turnover",
        "Bank Solvency Certificate",
        "ISO 9001:2015 Certificate",
        "Experience / Completion Certificates",
        "Non-Blacklisting Affidavit",
        "Class 3 DSC",
    ]

    combined = list(dict.fromkeys(all_docs + [d for d in standard_docs if d not in seen]))
    for i, d in enumerate(combined, start=1):
        story.append(Paragraph(f"{i}. {d}", clause_style))

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "⚠  PLACEHOLDER DOCUMENT — Fetch the real PDF for production use  ⚠",
        watermark_style,
    ))

    doc.build(story)
    size_kb = os.path.getsize(dest) // 1024
    print(f"  [PLACEHOLDER] Generated {size_kb} KB → {os.path.relpath(dest, PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch TenderAudit seed PDFs")
    parser.add_argument("--force", action="store_true",
                        help="Re-download / re-generate even if file already exists")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== TenderAudit Seed PDF Fetcher ===")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Output dir   : {OUTPUT_DIR}")
    print()

    if not os.path.exists(MANIFEST_PATH):
        print(f"[ERROR] Manifest not found: {MANIFEST_PATH}")
        return 1
    entries = parse_manifest(MANIFEST_PATH)
    if not entries:
        print(f"[ERROR] No entries found in {MANIFEST_PATH}")
        return 1
    print(f"Manifest: {len(entries)} entries found\n")

    # Load ground truth for richer placeholders
    gt_by_filename: dict[str, list] = {}
    if os.path.exists(GROUND_TRUTH_PATH):
        with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
            gt = json.load(f)
        for item in gt:
            fn = item.get("pdf_filename", "")
            gt_by_filename[fn] = item.get("criteria", [])

    real_count = 0
    placeholder_count = 0
    skip_count = 0

    for entry in entries:
        filename = entry["filename"]
        dest = os.path.join(OUTPUT_DIR, filename)
        print(f"[{filename}]")

        if os.path.exists(dest) and os.path.getsize(dest) > 0 and not args.force:
            size_kb = os.path.getsize(dest) // 1024
            print(f"  [SKIP] Already exists ({size_kb} KB). Use --force to re-fetch.")
            skip_count += 1
            print()
            continue

        success = try_download(entry["url"], dest)
        if success:
            real_count += 1
        else:
            criteria = gt_by_filename.get(filename, [])
            build_placeholder(entry, criteria, dest)
            placeholder_count += 1

        print()
        time.sleep(0.5)

    total = len(entries)
    fetched = real_count
    print("=" * 60)
    print(
        f"Done. Downloaded {fetched} / {total - skip_count} real PDFs; "
        f"{placeholder_count} placeholders generated; {skip_count} skipped (already exist)."
    )
    if placeholder_count > 0:
        print(
            "\nTIP: To replace placeholders, download the real PDFs from seed/MANIFEST.md "
            "and drop them into seed/pdfs/ with the exact filenames listed."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
