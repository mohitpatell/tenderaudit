# TenderAudit — Pitch Deck Outline

10 slides. 4–6 lines per slide. IAS officers + sponsor reps + VC observers.

---

## Slide 1: Title

**TenderAudit**
*The first procurement evaluator that defends itself in writ court.*

- AI for Bharat 2 — GovTech Track
- Team: \<team-name\> | Contact: \<email\>
- Demo: http://localhost:3001 (live) or see docs/demo_script.md

---

## Slide 2: The Problem

**Government procurement disqualifications are challenged in writ court. And they lose.**

- GFR 2017 Rule 173 requires eligibility criteria to be specified in the bid document and applied uniformly. In practice: a committee note says "turnover insufficient" with no document reference, no page citation, no figure.
- CRPF Bhopal NIT-71 specifies "Average Annual Turnover Certificate of Rs. 41.6 Lakh from a Chartered Accountant." A bidder at ₹38.2 lakh is disqualified. The bidder files a writ. The procuring officer cannot produce the specific line of the CA certificate that triggered the disqualification.
- The Two-Bid system under GFR Rule 173 requires a 72-hour representation window after technical disqualification. Representation is impossible if the disqualification reason is a spreadsheet cell.
- GeM and CPPP distribute tender PDFs and bidder ZIPs, but neither platform performs criterion-level evaluation or generates a defensible audit record.
- The procuring officer needs an evaluation system that produces courtroom-ready evidence, not a procurement portal.

---

## Slide 3: The Hero Demo

**One tender. Four bidders. One signed, defensible audit PDF.**

[Insert screenshot: 4×6 bidder × criterion matrix — Bidder A all green, Bidder B red on Turnover, Bidder D amber; below, the Bidder B drill-down showing "Annual turnover: ₹38.2 lakh" highlighted in the CA certificate PDF]

- CRPF NIT-71 processed in 4.1 seconds: 6 criteria extracted, sourced to bbox
- Bidder B: NotEligible on turnover — exact figure ₹38.2 lakh vs ₹41.6 lakh threshold, page 3, bbox coordinates recorded
- Bidder D: NeedsManualReview — expired ISO + entity name mismatch — never silently disqualified
- Signed audit PDF downloadable — PKCS#7 signature, NIC Class III DSC in production

---

## Slide 4: How It Works — 5-Step Pipeline

**Tender → Criteria → Index → Evaluate → Sign**

1. **Ingest:** PyMuPDF (digital) + PaddleOCR-VL 1.5 (scanned); sha256 blob addressing in MinIO
2. **Extract:** `gpt-4o-2024-08-06` Structured Outputs → `[Criterion]` Pydantic (strict=true); officer reviews + approves before evaluation begins
3. **Index:** Bidder documents chunked (512 tokens, 64 overlap) → `text-embedding-3-large` → pgvector (11.4× throughput vs Qdrant at 50M vectors per TigerData May 2025 benchmark)
4. **Evaluate:** Per (criterion, bidder): RAG top-5 filtered by doc_type → `gpt-4o-2024-08-06` compares evidence vs threshold → Verdict `{Eligible|NotEligible|NeedsManualReview}` + `[Evidence {bbox, quote}]`
5. **Sign:** `no_silent_disqual.py` hard guard → SHA-256 audit log → pyHanko PKCS#7 signed matrix PDF

---

## Slide 5: The Non-Obvious Technical Detail

**No-silent-disqualification: a runtime invariant, not a prompt instruction.**

- `no_silent_disqual.py` raises `NoSilentDisqualError` if any `NotEligible` verdict has `evidence == []`. This check runs before the verdict can be written to the database. It cannot be bypassed by a prompt change.
- Three verdict types: `Eligible` (conf ≥0.85, threshold met), `NotEligible` (conf ≥0.85, threshold not met, evidence present), `NeedsManualReview` (everything else — missing doc, conf <0.75, expired cert, name mismatch)
- RAG retrieval is filtered by `doc_type` whitelist per criterion: the turnover criterion retrieves only from CA certificates, not from ISO certificates or affidavits — preventing cross-document evidence contamination
- The signed PDF carries the complete evidence chain: every Evidence item records `{bidder_doc_id, page, bbox, quote, cosine_score}`. A reviewing court or audit committee can independently verify every verdict.

---

## Slide 6: Differentiation

**No existing product evaluates government tenders at the criterion level with evidence provenance.**

| Player | What they do | Gap |
|---|---|---|
| SpotDraft ($113M; 1M contracts/yr; $8M Qualcomm Jan 2026) | Enterprise CLM | B2B contracts, not government tenders; no evaluation engine |
| CaseMine | Legal research | Not procurement-oriented |
| Manupatra AI | Legal database | Subscription research; no bidder evaluation |
| Legistify | Enterprise legal management | Corporate; not GFR-aware |
| ProcurementIQ / Bilcrux | Tender intelligence for bidders | Wrong audience — helps bidders find tenders, not officers evaluate them |
| GeM portal | Government marketplace | No criterion evaluation; no audit PDF |

TenderAudit is the first system that maps GFR Rule 173 eligibility criteria to bidder documents at the bounding-box level.

---

## Slide 7: Compliance + Air-Gap

**GFR-aligned. DPDP-ready. CRPF-deployable offline.**

- **DPDP Act 2023 (G.S.R. 846(E), 13 Nov 2025):** §7(c) legitimate-use ground (public procurement under GFR 2017); immutable audit log (§8); 72-hour representation window maps to §12 right to correction; ₹250 cr penalty cap; 13 May 2027 deadline
- **GFR 2017:** Rule 173 (criteria specification); Rule 162 (single-bid flag); Land-Border-Country restriction (F.No.6/18/2019-PPD) extracted as mandatory criterion; MSE EMD exemption (MSE Order 2012) detected from Udyam cert
- **GIGW 3.0:** WCAG 2.1 AA via shadcn/Radix; semantic matrix table for screen readers; IS 17802 mapping
- **CERT-In Safe-to-Host:** VAPT scope documented; ~₹3–8L; 4–6 weeks; 6-hour incident reporting
- **Air-gap Level 1 (CRPF edge sites):** No internet; manual verdicts; offline pyHanko signing; RHEL 8/9
- **Air-gap Level 2 (CRPF HQ Delhi):** vLLM + Qwen 2.5 32B Q4 on A100; BGE-M3 embeddings (32.1% R@1 on 12 Indian languages, arXiv:2601.10205); single `.env` toggle

---

## Slide 8: Pilot Ask

**CRPF procurement cell + GeM integration**

- Target pilot: CRPF Directorate General (HQ Delhi, CGO Complex) — works tenders and stores procurement
- Entry point: A100 GPUs are available at CRPF HQ; Level-2 air-gap deployment is immediately feasible
- GeM integration path: GeM buyer-side API for tender metadata ingestion; manual bidder ZIP upload as Phase 1
- Precedent: CRPF already published 4 tender PDFs used as the TenderAudit seed corpus — procurement office is accessible
- GeM/CPPP do not currently offer public APIs for bidder bundle download — Phase 2 integration via NIC IntegrationGateway or department MOU
- Alternate pilot: any Central Ministry with open CPPP tenders and a willing procuring officer

---

## Slide 9: Market Size

**India GovTech is $90.9M raised — and underserved. The procurement workflow alone is a ₹35 cr ARR opportunity.**

- Grand View Research: India legal-technology market USD 464.6M (2023) → USD 1,253.1M (2030) at **15.2% CAGR**
- India LegalTech: 960 companies; 86 funded; $793M raised cumulatively; 2025: +781% YoY funding (Inventiva, 2026)
- India GovTech: 231 companies; 41 funded; **$90.9M total raised** (Tracxn, Jan 2026) — the procurement tooling segment is almost entirely unaddressed
- Comparable global rounds: Harvey $300M Series D (Sequoia, Feb 2025, $3B); EvenUp $135M Series D (Bain, Oct 2024, $1B)
- TenderAudit wedge: Central Ministry procurement cells (estimate 200+ active CPPP tenders/month) + CRPF + CPWD at ₹15–25L ARR per procurement cell = **₹21–35 cr ARR baseline**
- Expansion: PSUs (ONGC, BHEL, SAIL) → GeM platform integration → ASEAN government procurement (procurement law comparability)

---

## Slide 10: Team + Ask

**We need a CRPF procurement officer and a CERT-In auditor, not a grant.**

- Team: \<name, role\> | \<name, role\> | \<name, role\>
- Built in 14 days using Claude Code and OpenAI gpt-4o-2024-08-06
- Ask: CRPF DG (HQ Delhi) letter of intent for pilot + ₹\<X\>L for CERT-In Safe-to-Host VAPT engagement
- Timeline: 4 weeks to Level-2 air-gap deployment at CRPF HQ → 6 weeks to CERT-In Safe-to-Host → first live tender evaluation
- Long-term: NIC Class III DSC for signed audit PDF → GeM buyer API integration → BGE-M3 embeddings for Hindi-language bidder documents → BHASHINI translation hooks for regional procurement offices
