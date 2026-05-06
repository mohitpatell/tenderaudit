# TenderAudit — Demo Script

Target runtime: 120 seconds. Rehearse at least 6 times.

## Pre-demo checklist

**Local dev:**

- `make dev` running; API on `:8001`, UI on `:3001`
- Browser at [http://localhost:3001](http://localhost:3001) (Upload page visible)
- `OPENAI_API_KEY` set in `api/.env` — extraction + RAG verdicts depend on it

**Or hosted:**

- Web: [https://warm-plateau-98672-f8f1268616c3.herokuapp.com](https://warm-plateau-98672-f8f1268616c3.herokuapp.com)
- API: [https://damp-scrubland-58077-92d7a7c07dd5.herokuapp.com](https://damp-scrubland-58077-92d7a7c07dd5.herokuapp.com) (already wired into the web app)
- First request after idle wakes the dyno (~5–10 s) — open `/` once before demo

**Demo assets on desktop (regenerate with `make demo-zips` and `python scripts/gen_demo_tender.py` if missing):**

- `seed/pdfs/demo-tender-armoured-vehicles.pdf` (the tender)
- All four ZIPs from `seed/demo-zips/`:
  - `bidder-mahindra-defence.zip` (clean — all Eligible)
  - `bidder-beml-limited.zip` (Turnover shortfall — NotEligible)
  - `bidder-tata-advanced-systems.zip` (no ISO 9001 — NotEligible / NeedsReview)
  - `bidder-force-motors.zip` (wrong-plant ISO + stale affidavit — NeedsReview)

**Fallbacks:**

- Pre-seeded matrix view open in a hidden tab (in case live evaluation times out)
- Pre-generated signed PDF in `data/blobs/` (fallback download)
- Screen 1440×900 or wider; browser zoom 90%

---

## Script

### [0:00 – 0:10] Title card

**Say:**
"TenderAudit is the first procurement evaluator that defends itself in writ court. Every disqualification carries an evidence chain back to a bounding-box on a page in the bidder's own PDF. The no-silent-disqualification invariant is enforced at the application layer — no prompt instruction, no LLM-trust assumption."

**Action:** Slide from title card to [http://localhost:3001](http://localhost:3001).

---

### [0:10 – 0:25] Upload tender

**Action:** Drag `demo-tender-armoured-vehicles.pdf` into the upload dropzone on the home page.

**Say:**
"A defence MoD tender for armoured vehicles. Five eligibility criteria — ₹5 Cr defence-segment turnover, ISO 9001:2015 from a NABCB-accredited body, three completed government contracts, ₹2 Cr net worth, and a notarised non-blacklisting affidavit no older than twelve months."

**What you see:** Spinner → toast `Tender extracted in ~6s` → auto-redirect to `/tender/<id>/criteria`.

**Fallback:** Switch to the pre-seeded `/tender/<id>/matrix` tab. Say: "Here's the pre-processed version."

---

### [0:25 – 0:45] Criteria review

**What you see:** Five criterion cards, each showing the verbatim source clause from the tender, type badge (financial / technical / compliance), and threshold.

**Say:**
"Every criterion is extracted with `gpt-4o-2024-08-06` Structured Outputs — schema-validated, not regex-scraped. Every clause shows the exact text the LLM extracted from. GFR Rule 173: criteria must be specified before bids are invited and applied uniformly. Here they are — extracted, sourced, officer-verified."

**Action:** Click **Approve** on each card (or click **Approve all & continue** when the sticky bottom bar appears).

**What you see:** Cards turn green; the "Continue to Bidder Upload" call-to-action activates.

---

### [0:45 – 1:05] Upload bidders (multi-select)

**Action:** Open the file picker. **Hold ⌘ / Ctrl, click all four ZIPs, hit Open** — or drag all four onto the dropzone in one gesture.

**Say:**
"Four bidders, one drop. Mahindra Defence is clean. BEML's defence-segment turnover is ₹3.2 Cr — below the ₹5 Cr threshold. Tata Advanced Systems shipped only ISO 14001, no 9001. Force Motors' ISO covers their Pithampur commercial-vehicle plant — not the Akurdi defence plant where the work would execute — and their non-blacklisting affidavit is 14 months old."

**What you see:** Toast `Added 4 bidder archives`. Four rows in the queue. Click **Run Evaluation**.

**Say:**
"The engine RAG-retrieves each bidder's own pages per criterion, asks `gpt-4o` for a verdict + cited evidence, and writes the matrix. Each criterion-bidder cell is independent — there's no shared pool."

**What you see:** Per-zip upload progress, then `Running evaluation against approved criteria…` → redirect to the matrix.

---

### [1:05 – 1:30] Matrix + drill-down

**What you see:** A 4×5 grid. Mahindra row: all green. BEML row: red on Turnover. Tata row: red/amber on ISO. Force row: amber on ISO and Blacklisting.

**Say:**
"Green — Eligible. Red — Not Eligible. Amber — Needs Manual Review. Watch what happens when I click a red cell."

**Action:** Click the **BEML / Turnover** cell.

**What you see:** Drill-down split-pane. Left: the BEML CA turnover certificate PDF, jumped to the page with a yellow bbox highlight on the certified figure. Right: the LLM rationale citing exact INR figures from the certificate.

**Say:**
"The exact line. The exact figure. The exact page. That's the evidence chain. Not a committee note — a bounding-box on a page in the bidder's own document."

**Action:** Click the **Force Motors / ISO 9001** amber cell.

**What you see:** Verdict `NeedsManualReview`. Evidence quotes the ISO scope: *"Manufacture of Light Commercial Vehicles… at the Pithampur Plant, Madhya Pradesh"*. Rationale: scope does not cover Akurdi defence facility.

**Say:**
"Force Motors gets NeedsManualReview — not NotEligible. The system cannot silently disqualify on ambiguous evidence. The procuring officer sees why, and the production system gives the bidder 72 hours to represent before the verdict is final. That's GFR Rule 173 plus DPDP §12 right-to-correction in code, not in policy."

---

### [1:30 – 1:45] Signed audit PDF + chain inspector

**Action:** From the matrix, click **Generate signed audit PDF**.

**What you see:** Toast `Signed audit PDF generated` → download. Open it. The PDF carries a PKCS#7 signature panel — `Signed by: TenderAudit Demo Signer`.

**Say:**
"A digitally-signed PDF of the entire evaluation. In production, this is signed with a NIC-issued Class III DSC. This document walks into writ court."

**Action:** Open `/data` in a new tab.

**Say:**
"And here's the audit log. Every state change — tender uploaded, criterion approved, bidder uploaded, evaluation run, override, sign — is appended to a SHA-256 hash chain. Click *Verify* — every row's `prev_hash` matches its predecessor. Tamper with one row and verification breaks at that ID."

**Fallback:** If the sign endpoint times out, open the most recent `data/blobs/<sha>.pdf` directly.

---

### [1:45 – 2:00] Closing

**Say:**
"Five guarantees: structured extraction with schema validation, per-bidder RAG with cited evidence, the no-silent-disqualification invariant in code, a hash-chained audit log, and a digitally-signed report. No verdict ships without a bounding-box behind it. The whole stack runs offline behind an air-gap on a CRPF server with vLLM and pgvector — production path is in `docs/airgap_deployment.md`. **TenderAudit — the first procurement evaluator that defends itself in writ court.**"

---

## Fallback Notes


| Step                    | Failure mode                | Fallback action                                                |
| ----------------------- | --------------------------- | -------------------------------------------------------------- |
| Tender upload           | OpenAI timeout / OCR slow   | Switch to the pre-seeded `/tender/<id>/criteria` tab           |
| Criteria not extracted  | LLM schema-validation error | Show pre-seeded criteria; say "extracted from this document"   |
| Bidder indexing slow    | Embedding service lag       | Switch to pre-seeded matrix tab                                |
| Matrix not populating   | Evaluation engine timeout   | Switch to pre-seeded matrix tab                                |
| Drill-down PDF slow     | Blob fetch lag              | Show evidence text only — the right pane carries the narrative |
| Sign endpoint times out | pyHanko / OpenSSL error     | Open the most recent signed `data/blobs/<sha>.pdf` directly    |
| Heroku dyno cold-start  | First request after idle    | Hit `/` once before the demo to wake it (~5–10 s)              |


---

## Technical Notes for Judges Who Ask Questions

**"What is the no-silent-disqualification invariant?"**
A runtime guard in `api/domain/no_silent_disqual.py`, not a prompt instruction. If the evaluation engine attempts to persist a `NotEligible` verdict with zero evidence items, it raises `NoSilentDisqualError` and substitutes `NeedsManualReview`. No code path can bypass it without modifying the guard itself. Tested in `scripts/test_demo_e2e.py` Phase 5.

**"How does the RAG actually work?"**
Each bidder PDF is digitally extracted with PyMuPDF (OCR fallback below 50 words/page via Tesseract), chunked into 400-character overlapping windows, and embedded with `text-embedding-3-small` per page. Chroma persistent store, top-k=5 with a soft `doc_type` whitelist (filename heuristic). Production target: 512-token chunks, `BAAI/bge-m3` embeddings, pgvector. See `docs/architecture.md` §12.

**"Why did Tata get red on ISO and Force get amber?"**
Tata supplied no ISO 9001 at all, only ISO 14001 — the LLM has decisive evidence of absence. Force supplied a valid ISO 9001 from a NABCB body, but the certificate scope is for the Pithampur commercial-vehicle plant, not the Akurdi defence plant. That's a scope-mismatch judgment call, not a documentary defect — exactly the kind of ambiguity the invariant routes to manual review.

**"What if a bidder uploads a forged CA certificate?"**
TenderAudit retrieves and surfaces what the LLM finds. It does not validate documents against external registries. Manual verification of the CA's UDIN against the ICAI portal is the procuring officer's responsibility — the production roadmap in `docs/architecture.md` §12 includes ICAI / NABCB / MCA registry lookups as a separate enrichment pass.

**"Is this DPDP-compliant?"**
§7(c) legitimate-use ground (public procurement under GFR 2017). Immutable audit log (§8). The no-silent-disqualification invariant plus the 72-hour representation window in production maps to §12 right-to-correction. Full detail in `docs/compliance.md`.

**"Why NeedsManualReview instead of NotEligible for missing or ambiguous documents?"**
GFR Rule 173 and the Two-Bid system require bidders an opportunity to explain deficiencies before final disqualification. A `NeedsManualReview` verdict preserves this right; a `NotEligible` verdict closes it. The invariant errs on `NeedsManualReview` when evidence is incomplete — this is the legally defensible default.

**"Can this run in CRPF's air-gapped environment?"**
The prototype calls OpenAI (`gpt-4o`, `text-embedding-3-small`). Air-gap target: Qwen 2.5 32B Q4 via vLLM and BGE-M3 locally; pgvector replaces Chroma; Tesseract is already offline. A Level-1 fallback (no GPU, BM25 keyword retrieval, officer-recorded verdicts, offline-signed PDFs) is documented in `docs/airgap_deployment.md`.

**"What's the audit chain actually verifying?"**  
Every audit row stores `prev_hash`, a canonicalised `payload_json`, and `this_hash = SHA-256(prev_hash || payload_json)`. `GET /api/audit/verify` re-computes every hash and walks the chain — any tamper at row N breaks verification at row N. The chain begins from a deterministic genesis hash; there is no way to insert a row without recomputing every hash that follows.