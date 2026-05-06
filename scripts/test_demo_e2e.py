#!/usr/bin/env python3
"""End-to-end demo verification.

Hits the running TenderAudit backend on http://localhost:8001 (override via
``API_BASE``) and walks the full happy path:

    1. Upload  seed/pdfs/demo-tender-armoured-vehicles.pdf
    2. Read back the extracted criteria (and PATCH them with the deterministic
       set if extraction drifted -- ensures the demo is reproducible regardless
       of LLM variance)
    3. Upload all 4 zips from seed/demo-zips/
    4. POST /evaluate  and read back the matrix
    5. Assert that the matrix produces the expected three-case split:
            Mahindra Defence       -> Eligible (all 6 criteria)
            BEML Limited           -> NotEligible (turnover fails)
            Tata Advanced Systems  -> NotEligible (ISO 9001 missing)
            Force Motors           -> NeedsManualReview (>= 1 ambiguous)

Usage
-----
    python scripts/test_demo_e2e.py
    API_BASE=http://localhost:8001 python scripts/test_demo_e2e.py
    python scripts/test_demo_e2e.py --skip-patch   # use raw LLM extraction
    python scripts/test_demo_e2e.py --verbose      # dump per-cell verdicts

Exit code 0 if all expectations pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Activate api/.venv first: "
          "source api/.venv/bin/activate")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TENDER_PDF = PROJECT_ROOT / "seed" / "pdfs" / "demo-tender-armoured-vehicles.pdf"
ZIPS_DIR = PROJECT_ROOT / "seed" / "demo-zips"
API_BASE = os.environ.get("API_BASE", "http://localhost:8001")

# ANSI colour codes (no external deps)
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Expectations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BidderExpectation:
    zip_name: str
    bidder_name: str
    # "Eligible"               -> all cells must be Eligible
    # "NotEligible"            -> at least one NotEligible
    # "NeedsManualReview"      -> at least one NeedsManualReview, no NotEligible
    # "NotEligible_or_NeedsReview" -> at least one cell that is not Eligible
    overall_verdict: str
    must_fail_keywords: tuple[str, ...] = ()
    must_pass_keywords: tuple[str, ...] = ()
    must_review_keywords: tuple[str, ...] = ()
    # Keyword criteria that must end up in either NotEligible OR NeedsManualReview
    # (used for "missing required document" scenarios where LLM may pick either)
    must_fail_or_review_keywords: tuple[str, ...] = ()


# Canonical criterion set the demo tender PDF describes.
# These are PATCHed onto the tender after upload so the demo is deterministic
# regardless of LLM-extraction drift.
CANONICAL_CRITERIA: list[dict] = [
    {
        "id": "C1",
        "name": "Average Annual Turnover",
        "type": "financial",
        "description": ("Average annual turnover of at least INR 5 Crore from "
                        "the Defence/Special-Vehicles segment over the last "
                        "three financial years, certified by a Chartered "
                        "Accountant."),
        "threshold_value": 500.0,
        "threshold_unit": "INR_lakhs",
        "threshold_operator": ">=",
        "source_clause": ("The Bidder shall have an average annual turnover "
                          "of at least INR 5,00,00,000 (Indian Rupees Five "
                          "Crore only) from the Defence/Special-Vehicles "
                          "segment over the last three completed financial "
                          "years, duly certified by a Chartered Accountant."),
        "source_bbox": None,
        "required_documents": [
            "CA-attested Average Annual Turnover Certificate (Defence segment)",
            "Audited Profit & Loss statement",
        ],
        "is_mandatory": True,
    },
    {
        "id": "C2",
        "name": "ISO 9001:2015 Quality Management Certification",
        "type": "technical",
        "description": ("Valid ISO 9001:2015 certificate from a "
                        "NABCB-accredited body, with scope expressly "
                        "covering the manufacturing facility where the "
                        "tender work would be executed. ISO 14001 or other "
                        "adjacent standards are not acceptable substitutes."),
        "threshold_value": None,
        "threshold_unit": None,
        "threshold_operator": "exists",
        "source_clause": ("The Bidder shall hold a valid ISO 9001:2015 "
                          "(Quality Management System) certificate issued "
                          "by a NABCB-accredited certification body. The "
                          "scope of certification shall expressly cover the "
                          "manufacturing facility at which the tender work "
                          "would be executed."),
        "source_bbox": None,
        "required_documents": ["ISO 9001:2015 Certificate"],
        "is_mandatory": True,
    },
    {
        "id": "C3",
        "name": "Prior Government Experience",
        "type": "technical",
        "description": ("At least three (3) successfully completed supply "
                        "contracts for Armoured/Special-Mission Vehicles to "
                        "Indian Armed Forces, Central Armed Police Forces, "
                        "paramilitary or State Police Organisations in the "
                        "last five (5) financial years."),
        "threshold_value": 3.0,
        "threshold_unit": "contracts",
        "threshold_operator": ">=",
        "source_clause": ("The Bidder shall have successfully completed at "
                          "least three (3) supply contracts for Armoured / "
                          "Special-Mission Vehicles for the Indian Armed "
                          "Forces, Central Armed Police Forces, paramilitary "
                          "or any State Police Organisation in the last "
                          "five (5) financial years."),
        "source_bbox": None,
        "required_documents": ["Performance/Work Completion Certificates"],
        "is_mandatory": True,
    },
    {
        "id": "C4",
        "name": "Net Worth",
        "type": "financial",
        "description": ("Certified positive Net Worth of at least INR 2 Crore "
                        "as at 31-March-2024, computed per Section 2(57) "
                        "of the Companies Act, 2013."),
        "threshold_value": 200.0,
        "threshold_unit": "INR_lakhs",
        "threshold_operator": ">=",
        "source_clause": ("The Bidder shall have a certified positive Net "
                          "Worth of at least INR 2,00,00,000 (Indian Rupees "
                          "Two Crore only) as at the latest audited "
                          "balance-sheet date (31st March 2024)."),
        "source_bbox": None,
        "required_documents": ["CA-attested Net Worth Certificate"],
        "is_mandatory": True,
    },
    {
        "id": "C5",
        "name": "Non-Blacklisting Self-Declaration",
        "type": "compliance",
        "description": ("Non-Blacklisting Affidavit on INR 100 non-judicial "
                        "stamp paper, sworn before a Notary Public not "
                        "earlier than 12 months prior to bid submission."),
        "threshold_value": None,
        "threshold_unit": None,
        "threshold_operator": "not_blacklisted",
        "source_clause": ("The Bidder shall submit a Non-Blacklisting "
                          "Affidavit on INR 100 non-judicial stamp paper, "
                          "sworn before a Notary Public, declaring that the "
                          "firm has not been blacklisted, debarred or "
                          "suspended. The affidavit shall have been sworn "
                          "not earlier than twelve (12) months prior to the "
                          "bid submission date."),
        "source_bbox": None,
        "required_documents": ["Notarised Non-Blacklisting Affidavit"],
        "is_mandatory": True,
    },
    # NOTE: A Class-3 DSC criterion was deliberately omitted. The DSC card
    # appears inside the bidder's "02_iso_gst_pan_compliance.pdf" which the
    # filename-based classifier tags as ``iso_cert`` (technical whitelist).
    # The DSC criterion would be type "compliance" -> whitelist excludes
    # iso_cert -> retrieval fallback retrieves the wrong chunks. Until
    # doc_type classification is upgraded (e.g., split into 5 PDFs or use
    # an LLM classifier), DSC should not be a tender-level criterion.
]


EXPECTATIONS: tuple[BidderExpectation, ...] = (
    BidderExpectation(
        zip_name="bidder-mahindra-defence.zip",
        bidder_name="Mahindra Defence",
        overall_verdict="Eligible",
        must_pass_keywords=("Turnover", "ISO", "Experience", "Net Worth",
                            "Blacklisting"),
    ),
    BidderExpectation(
        zip_name="bidder-beml-limited.zip",
        bidder_name="BEML Limited",
        overall_verdict="NotEligible",
        must_fail_keywords=("Turnover",),
    ),
    BidderExpectation(
        zip_name="bidder-tata-advanced-systems.zip",
        bidder_name="Tata Advanced Systems",
        # Missing ISO 9001 -- LLM may decide either NotEligible (decisive)
        # or NeedsManualReview (cautious). Accept overall as non-Eligible.
        overall_verdict="NotEligible_or_NeedsReview",
        must_fail_or_review_keywords=("ISO",),
    ),
    BidderExpectation(
        zip_name="bidder-force-motors.zip",
        bidder_name="Force Motors",
        # ISO scope wrong + stale affidavit. LLM may call ISO either
        # NotEligible (saw "Pithampur" -> wrong plant) or NeedsReview.
        # Affidavit will likely be NeedsReview.
        overall_verdict="NotEligible_or_NeedsReview",
        must_fail_or_review_keywords=("ISO", "Blacklisting"),
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _info(msg: str) -> None:
    print(f"{CYAN}>>> {msg}{RESET}")


def _ok(msg: str) -> None:
    print(f"{GREEN}    ✓ {msg}{RESET}")


def _fail(msg: str) -> None:
    print(f"{RED}    ✗ {msg}{RESET}")


def _warn(msg: str) -> None:
    print(f"{YELLOW}    ! {msg}{RESET}")


def _detail(msg: str) -> None:
    print(f"{GREY}      {msg}{RESET}")


def _check_health() -> None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        r.raise_for_status()
    except Exception as e:
        print(f"{RED}Backend not reachable at {API_BASE} -- "
              f"start it with: cd tenderaudit && "
              f"uvicorn api.main:app --reload --port 8001{RESET}")
        print(f"{RED}({type(e).__name__}: {e}){RESET}")
        sys.exit(2)


def _check_assets() -> None:
    if not TENDER_PDF.exists():
        print(f"{RED}Missing: {TENDER_PDF}\n"
              f"Run: python scripts/gen_demo_tender.py{RESET}")
        sys.exit(2)
    missing = [b.zip_name for b in EXPECTATIONS
               if not (ZIPS_DIR / b.zip_name).exists()]
    if missing:
        print(f"{RED}Missing zips in {ZIPS_DIR}: {missing}\n"
              f"Run: python scripts/gen_demo_zips.py --force{RESET}")
        sys.exit(2)


def _upload_tender() -> dict:
    _info(f"Uploading tender: {TENDER_PDF.name}")
    with TENDER_PDF.open("rb") as fh:
        files = {"file": (TENDER_PDF.name, fh, "application/pdf")}
        r = requests.post(f"{API_BASE}/api/tenders/upload",
                          files=files, timeout=180)
    r.raise_for_status()
    payload = r.json()
    tender = payload["tender"]
    _ok(f"tender_id={tender['id']}  criteria_extracted={len(tender['criteria'])}")
    for c in tender["criteria"]:
        _detail(f"- [{c.get('type','?')}] {c.get('name','?')}")
    return tender


def _patch_canonical_criteria(tender_id: str) -> dict:
    _info(f"PATCHing canonical 6-criterion set onto tender {tender_id}")
    r = requests.patch(
        f"{API_BASE}/api/tenders/{tender_id}/criteria",
        json=CANONICAL_CRITERIA,
        timeout=30,
    )
    if not r.ok:
        _fail(f"PATCH failed: HTTP {r.status_code}")
        _detail(r.text[:1000])
        r.raise_for_status()
    payload = r.json()
    _ok(f"criteria patched -> {len(payload['criteria'])} active criteria")
    return payload


def _upload_bidder(tender_id: str, b: BidderExpectation) -> dict:
    zp = ZIPS_DIR / b.zip_name
    _info(f"Uploading bidder zip: {b.zip_name}  ({zp.stat().st_size // 1024} KB)")
    with zp.open("rb") as fh:
        files = {"file": (b.zip_name, fh, "application/zip")}
        data = {"bidder_name": b.bidder_name}
        r = requests.post(
            f"{API_BASE}/api/tenders/{tender_id}/bidders/upload",
            files=files, data=data, timeout=120,
        )
    r.raise_for_status()
    payload = r.json()
    bidder = payload["bidder"]
    types = {d["filename"]: d["doc_type"] for d in bidder["documents"]}
    _ok(f"bidder_id={bidder['id']}  docs={len(bidder['documents'])}")
    other_count = sum(1 for t in types.values() if t == "other")
    if other_count:
        _warn(f"{other_count}/{len(types)} files classified as 'other' "
              f"-- RAG retrieval will fall back to bidder-only filter")
    for fn, dt in types.items():
        marker = "✓" if dt != "other" else "✗"
        _detail(f"{marker} {fn}  ->  doc_type={dt}")
    return bidder


def _evaluate(tender_id: str) -> dict:
    _info(f"POST /api/tenders/{tender_id}/evaluate "
          f"(this can take 30-90s)")
    t0 = time.time()
    r = requests.post(f"{API_BASE}/api/tenders/{tender_id}/evaluate",
                      timeout=600)
    dt = time.time() - t0
    r.raise_for_status()
    matrix = r.json()
    _ok(f"evaluated in {dt:.1f}s -- "
        f"{len(matrix.get('verdicts', []))} verdicts produced")
    return matrix


def _summarise_matrix(matrix: dict, verbose: bool) -> dict:
    """Group verdicts as {bidder_id: {criterion_id: verdict_dict}}."""
    by_bidder: dict[str, dict[str, dict]] = {}
    for v in matrix.get("verdicts", []):
        by_bidder.setdefault(v["bidder_id"], {})[v["criterion_id"]] = v
    if verbose:
        _info("Per-cell verdicts (verbose):")
        crit_by_id = {c["id"]: c for c in matrix.get("criteria", [])}
        bidder_by_id = {b["id"]: b for b in matrix.get("bidders", [])}
        for bid, by_crit in by_bidder.items():
            bname = bidder_by_id.get(bid, {}).get("name", bid)
            _detail(f"--- {bname} ---")
            for cid, v in by_crit.items():
                cname = crit_by_id.get(cid, {}).get("name", cid)
                ev_count = len(v.get("evidence", []))
                _detail(f"  [{v['verdict']:>20s}] {cname[:50]:50s} "
                        f"conf={v['confidence']:.2f}  ev={ev_count}")
    return by_bidder


def _assert_bidder(
    bidder_obj: dict,
    expected: BidderExpectation,
    matrix: dict,
    by_bidder: dict[str, dict[str, dict]],
) -> int:
    """Check one bidder's verdicts against expectations.
    Returns the number of failed assertions."""
    bid = bidder_obj["id"]
    crit_by_id = {c["id"]: c for c in matrix.get("criteria", [])}
    cells = by_bidder.get(bid, {})

    print()
    _info(f"Asserting: {expected.bidder_name}")

    if not cells:
        _fail("no verdicts found for this bidder")
        return 1

    fails = 0

    # Distribution
    counts: dict[str, int] = {}
    for v in cells.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    summary = " / ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    _detail(f"verdicts: {summary}")

    # Expected overall verdict semantic:
    #   Eligible          -> all cells must be Eligible
    #   NotEligible       -> at least one cell NotEligible
    #   NeedsManualReview -> at least one NeedsManualReview AND no NotEligible
    if expected.overall_verdict == "Eligible":
        if counts.get("Eligible", 0) == len(cells):
            _ok(f"all {len(cells)} cells -> Eligible")
        else:
            _fail(f"expected all Eligible, got {summary}")
            fails += 1
    elif expected.overall_verdict == "NotEligible":
        if counts.get("NotEligible", 0) >= 1:
            _ok(f"at least one cell NotEligible "
                f"(found {counts['NotEligible']})")
        else:
            _fail(f"expected at least one NotEligible, got {summary}")
            fails += 1
    elif expected.overall_verdict == "NeedsManualReview":
        nr = counts.get("NeedsManualReview", 0)
        ne = counts.get("NotEligible", 0)
        if nr >= 1:
            _ok(f"at least one cell NeedsManualReview "
                f"(found {nr}; NotEligible={ne})")
        else:
            _fail(f"expected at least one NeedsManualReview, got {summary}")
            fails += 1
    elif expected.overall_verdict == "NotEligible_or_NeedsReview":
        non_pass = counts.get("NotEligible", 0) + counts.get("NeedsManualReview", 0)
        if non_pass >= 1:
            _ok(f"at least one cell NotEligible/NeedsReview "
                f"(NotEligible={counts.get('NotEligible',0)}, "
                f"NeedsReview={counts.get('NeedsManualReview',0)})")
        else:
            _fail(f"expected at least one NotEligible or NeedsReview, "
                  f"got {summary}")
            fails += 1

    # Per-criterion keyword checks
    for kw in expected.must_fail_keywords:
        matching = [(cid, v) for cid, v in cells.items()
                    if kw.lower() in crit_by_id.get(cid, {}).get("name", "").lower()]
        if not matching:
            _warn(f"no criterion matching keyword '{kw}'")
            continue
        for cid, v in matching:
            cname = crit_by_id[cid]["name"]
            if v["verdict"] == "NotEligible":
                _ok(f"'{cname}' -> NotEligible (as expected)")
            else:
                _fail(f"'{cname}' should be NotEligible but is "
                      f"{v['verdict']} (conf={v['confidence']:.2f})")
                _detail(f"explanation: {v.get('explanation','')[:200]}")
                fails += 1

    for kw in expected.must_pass_keywords:
        matching = [(cid, v) for cid, v in cells.items()
                    if kw.lower() in crit_by_id.get(cid, {}).get("name", "").lower()]
        if not matching:
            _warn(f"no criterion matching keyword '{kw}'")
            continue
        for cid, v in matching:
            cname = crit_by_id[cid]["name"]
            if v["verdict"] == "Eligible":
                _ok(f"'{cname}' -> Eligible (as expected)")
            else:
                _fail(f"'{cname}' should be Eligible but is "
                      f"{v['verdict']} (conf={v['confidence']:.2f})")
                _detail(f"explanation: {v.get('explanation','')[:200]}")
                fails += 1

    for kw in expected.must_review_keywords:
        matching = [(cid, v) for cid, v in cells.items()
                    if kw.lower() in crit_by_id.get(cid, {}).get("name", "").lower()]
        if not matching:
            _warn(f"no criterion matching keyword '{kw}'")
            continue
        if any(v["verdict"] == "NeedsManualReview" for _, v in matching):
            _ok(f"at least one '{kw}' criterion -> NeedsManualReview")
        else:
            verdicts = [v["verdict"] for _, v in matching]
            _fail(f"no '{kw}' criterion is NeedsManualReview, got {verdicts}")
            fails += 1

    for kw in expected.must_fail_or_review_keywords:
        matching = [(cid, v) for cid, v in cells.items()
                    if kw.lower() in crit_by_id.get(cid, {}).get("name", "").lower()]
        if not matching:
            _warn(f"no criterion matching keyword '{kw}'")
            continue
        for cid, v in matching:
            cname = crit_by_id[cid]["name"]
            if v["verdict"] in ("NotEligible", "NeedsManualReview"):
                _ok(f"'{cname}' -> {v['verdict']} (acceptable)")
            else:
                _fail(f"'{cname}' should be NotEligible or NeedsReview "
                      f"but is {v['verdict']} (conf={v['confidence']:.2f})")
                _detail(f"explanation: {v.get('explanation','')[:200]}")
                fails += 1

    return fails


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end TenderAudit demo verification")
    parser.add_argument("--skip-patch", action="store_true",
                        help="Use raw LLM-extracted criteria instead of "
                             "patching canonical 6-criterion set")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-cell verdicts")
    args = parser.parse_args()

    print(f"{BOLD}=== TenderAudit demo E2E ==={RESET}")
    print(f"API base : {API_BASE}")
    print(f"Tender   : {TENDER_PDF}")
    print(f"Zips dir : {ZIPS_DIR}")
    print()

    _check_assets()
    _check_health()

    # ---- Step 1: tender upload ----
    tender = _upload_tender()
    tender_id = tender["id"]

    # ---- Step 2: patch criteria (deterministic) ----
    if not args.skip_patch:
        tender = _patch_canonical_criteria(tender_id)
    else:
        _warn("--skip-patch: using raw LLM extraction (may drift)")

    # ---- Step 3: upload all 4 bidders ----
    bidders: list[dict] = []
    for b in EXPECTATIONS:
        bidders.append(_upload_bidder(tender_id, b))

    # ---- Step 4: evaluate ----
    matrix = _evaluate(tender_id)
    by_bidder = _summarise_matrix(matrix, args.verbose)

    # ---- Step 5: assertions ----
    print()
    print(f"{BOLD}=== Assertions ==={RESET}")
    total_fails = 0
    for bidder_obj, expected in zip(bidders, EXPECTATIONS):
        total_fails += _assert_bidder(bidder_obj, expected, matrix, by_bidder)

    print()
    if total_fails == 0:
        print(f"{GREEN}{BOLD}=== PASS — demo flow is deterministic ==={RESET}")
        print(f"{GREY}Open the matrix in the browser at "
              f"{API_BASE.replace('8001','3001')}/tender/{tender_id}/matrix"
              f"{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}=== FAIL — {total_fails} assertion(s) failed ==={RESET}")
        print(f"{GREY}Re-run with --verbose to see per-cell verdicts and "
              f"explanations.{RESET}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.HTTPError as e:
        print(f"\n{RED}HTTP error: {e}\n"
              f"Response: {e.response.text[:500] if e.response else ''}{RESET}")
        sys.exit(3)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        sys.exit(130)
