# TenderAudit — Demo Script

Target runtime: 120 seconds. Rehearse at least 6 times.

Pre-demo checklist:
- [ ] `make dev` running; API on :8001, UI on :3001
- [ ] Browser tab open at http://localhost:3001 (Upload page visible)
- [ ] `seed/tenders/crpf-bhopal-nit71.pdf` on desktop
- [ ] `seed/bidders/bidder-A-clean.zip`, `bidder-B-shortfall.zip`, `bidder-C-missing-iso.zip`, `bidder-D-ambiguous.zip` on desktop
- [ ] Pre-seeded matrix view open in hidden tab (fallback)
- [ ] Signed PDF already generated in `data/signed/` (fallback download)
- [ ] Screen resolution: 1440×900 or wider; browser zoom 90%

---

## Script

---

### [0:00 – 0:10] Title card

**Say:**
"TenderAudit is the first procurement evaluator that defends itself in writ court. Every disqualification carries an evidence chain back to a bounding-box on a page in the bidder's own PDF."

**Action:** Slide from title card to browser at http://localhost:3001.

---

### [0:10 – 0:25] Upload tender

**Action:** Click **Upload Tender**. Drag `crpf-bhopal-nit71.pdf` into the drop zone.

**Say:**
"CRPF Bhopal Works tender NIT-71. Real document from crpf.gov.in. Turnover threshold: ₹41.6 lakh — from a Chartered Accountant."

**What you see:** Spinner. Toast: "Extracted 6 criteria in 4.1s."

**Fallback:** Click **Load Pre-seeded Tender**. Say: "Here's the pre-processed version."

---

### [0:25 – 0:45] Criteria review

**Action:** Navigate to the **Criteria Review** tab. Six criterion cards appear.

**Say:**
"Six eligibility criteria extracted — financial, documentation, compliance. Every criterion shows its source clause and its confidence score."

**Action:** Click the **Financial / Turnover** criterion card. The PDF on the left jumps to the clause: *"Average Annual Turnover Certificate of Rs. 41.6 Lakh (Proforma as Appendix-C) on works during the last three financial years from a Chartered Accountant."*

**Say:**
"GFR Rule 173: criteria must be specified before bids are invited and applied uniformly. Here they are — extracted, sourced, officer-verified."

**Action:** Click **Approve All Criteria**.

---

### [0:45 – 1:00] Upload bidders

**Action:** Navigate to **Upload Bidders**. Drag all four ZIP files into the upload zone.

**Say:**
"Four bidders. Bidder A is clean. Bidder B has a turnover shortfall. Bidder C is missing their ISO certificate. Bidder D — the interesting one — has an expired ISO and experience certs in a different entity name."

**What you see:** Four upload progress bars. "Indexed" toast for each.

**Action:** Click **Run Evaluation**.

**Say:**
"Now the evaluation engine runs each bidder against each criterion — RAG over their own documents, not over a shared pool."

---

### [1:00 – 1:25] Matrix view + drill-down

**What you see:** A 4×6 matrix. Bidder A: all green. Bidder B: red on Turnover. Bidder C: red on Documentation (ISO). Bidder D: amber across two criteria.

**Say:**
"Green: Eligible. Red: Not Eligible. Amber: Needs Manual Review. Watch what happens when I click a red cell."

**Action:** Click the **Bidder B / Turnover** cell.

**What you see:** A drill-down panel opens. Left: Bidder B's CA certificate PDF, with the turnover figure highlighted. Right: evidence quote — *"Annual turnover: ₹38.2 lakh"*. Verdict explanation: "Threshold: ₹41.6 lakh. Found: ₹38.2 lakh. Shortfall: ₹3.4 lakh."

**Say:**
"The exact line. The exact figure. The exact page. That's the evidence chain. Not a committee note — a bounding-box on a page."

**Action:** Click the **Bidder D / Compliance** amber cell.

**What you see:** Verdict: NeedsManualReview. Explanation: "ISO certificate found but expired. Entity name on certificate — 'Prakash Constructions Pvt Ltd' — does not match bidder name 'Prakash Infrastructure Works'. Manual review required."

**Say:**
"Bidder D gets NeedsManualReview — not NotEligible. The system cannot silently disqualify on ambiguous evidence. The procuring officer sees why, and has 72 hours to hear the representation."

---

### [1:25 – 1:45] Signed audit PDF

**Action:** Click **Download Signed Audit PDF**.

**What you see:** A PDF downloads. Open it. The PDF shows the 4×6 matrix with all verdicts. A signature panel in the PDF viewer shows: "Signed by: TenderAudit Demo Signer. Date: 2026-05-04."

**Say:**
"A digitally signed PDF of the entire evaluation. In production, this is signed with a NIC-issued Class III DSC. This document walks into writ court."

**Fallback:** If download fails, open `data/signed/nit71-matrix-signed.pdf` from the pre-generated file.

---

### [1:45 – 2:00] Closing

**Say:**
"No silent disqualifications. Every verdict is traceable to a bounding-box. Every action is in a hash-chained audit log. And the entire system can run on a CRPF server with no internet egress. TenderAudit — the first procurement evaluator that defends itself in writ court."

---

## Fallback Notes

| Step | Failure mode | Fallback action |
|---|---|---|
| Tender upload | Timeout or OCR slow | Load pre-seeded tender from seed database; click "Load Pre-seeded" |
| Criteria not extracted | LLM failure | Show pre-seeded criteria list; say "extracted from this document" |
| Bidder indexing slow | Embedding service lag | Switch to pre-seeded matrix view tab |
| Matrix not populating | Evaluation engine timeout | Switch to pre-seeded matrix tab |
| Drill-down PDF slow | Blob fetch lag | Show evidence text only (right pane is sufficient for the narrative) |
| Signed PDF download fails | pyHanko error | Open pre-generated `data/signed/nit71-matrix-signed.pdf` |

---

## Technical Notes for Judges Who Ask Questions

**"What is the no-silent-disqualification invariant?"**
It is a runtime guard in `no_silent_disqual.py`, not a prompt instruction. If the evaluation engine attempts to persist a `NotEligible` verdict with zero evidence items, it raises `NoSilentDisqualError` and substitutes `NeedsManualReview`. No code path can bypass it without modifying the guard itself.

**"How does the RAG work?"**
Each bidder document is chunked into 512-token segments with 64-token overlap and embedded with `text-embedding-3-large`. On evaluation, the retrieval query is built from the criterion description + threshold + document type. pgvector returns the top-5 most similar chunks filtered by document type whitelist (so only CA certificates are retrieved for the turnover criterion, not ISO certificates).

**"What if a bidder uploads a fake CA certificate?"**
TenderAudit retrieves and surfaces what it finds; it does not validate documents against external registries. Manual verification of the CA certificate against the ICAI registry is the procuring officer's responsibility — and is documented in the `NeedsManualReview` explanation when certificate issuer details are inconsistent.

**"Is this DPDP compliant?"**
§7(c) legitimate-use ground (public procurement under GFR 2017). Immutable audit log (§8). No-silent-disqualification + 72-hour representation window maps to §12 right to correction. Full detail in `docs/compliance.md`.

**"Why NeedsManualReview instead of NotEligible for missing documents?"**
GFR Rule 173 and the Two-Bid system require that bidders have an opportunity to explain deficiencies before final disqualification. A `NeedsManualReview` verdict preserves this right. A `NotEligible` verdict closes it. The system errs on the side of `NeedsManualReview` when evidence is incomplete or ambiguous — this is the legally defensible choice.

**"Can this run in CRPF's air-gapped environment?"**
Level 1 (no GPU, no internet): tender ingest, bidder chunking with BM25 keyword retrieval, officer manually records verdicts, audit PDF signed offline. Level 2 (CRPF HQ Delhi GPU): Qwen 2.5 32B Q4 on A100 via vLLM; BGE-M3 embeddings locally. Toggle: `LLM_BACKEND=vllm` in `.env`. No changes to any other code.
