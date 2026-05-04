# TenderAudit — Compliance Reference

This document covers the five compliance pillars relevant to deploying TenderAudit in a CRPF procurement or central government context, plus the GFR 2017 alignment that is specific to procurement. A checklist at the end distinguishes prototype achievement from pilot requirements.

---

## 1. DPDP Act 2023 + DPDP Rules 2025

### Statutory basis

The **Digital Personal Data Protection Act 2023** received Presidential assent on 11 August 2023. The **DPDP Rules 2025** were notified on **13 November 2025 via Gazette Extraordinary G.S.R. 846(E)**. Hard compliance deadline: **13 May 2027** (18 months). May be shortened to 12 months per Minister Vaishnaw's public statement — build for the earlier deadline.

Penalty cap: **₹250 crore per breach**. No cure period.

### Why bidder documents trigger DPDP

Bidder documents — CA turnover certificates, audited balance sheets, PAN cards, GST certificates, EPFO/ESIC records, Udyam (MSME) registrations, partnership deeds — contain personal data of proprietors, partners, and directors. Processing these documents to evaluate a bid is processing personal data under DPDP §2(t).

### Applicable exemption: §7 Legitimate Use Ground

- **§7(c):** "performance of any function under any law" — procurement under GFR 2017 is a statutory function of the procuring officer
- **§7(b):** where the procurement is triggered by a court order or tribunal direction
- **§7(f):** "employment-related processing" — inapplicable here, but noted for bidder background checks

TenderAudit uses **§7(c)** as the primary ground: processing bidder documents to discharge the statutory procurement obligation under GFR 2017.

### Hard requirements under DPDP

#### §8 — Reasonable Security Safeguards (Immutable Audit Log)

The SHA-256 hash-chained audit log satisfies §8. The `no_silent_disqual.py` guard further ensures that every disqualification has a documented evidence basis — no hidden processing that could constitute unfair data use.

#### Breach Notification — within 72 hours

Procurement files are high-value targets (competitive intelligence). The breach notification path:

1. Detect: audit chain failure, unauthorized access alert, or MinIO policy violation
2. Notify Data Protection Board within 72 hours via prescribed portal
3. Notify affected Data Principals (bidder company representatives) "as soon as practicable"
4. Record all notifications in audit log

Webhook stub: `api/audit/breach.py` with `CERT_IN_WEBHOOK_URL` and `DPBI_WEBHOOK_URL` environment variables.

#### Data Minimization

The `Criterion` schema extracts only eligibility-relevant fields from bidder documents. The RAG retrieval is filtered by `doc_type` whitelist per criterion — the system does not retrieve pages from unrelated documents (e.g., it does not pull from PAN or GST cert when evaluating a turnover criterion).

Bidder documents are stored at the chunk level in pgvector; raw PDFs are retained in MinIO for audit purposes. After the pilot retention period, raw PDFs should be deleted per a documented retention schedule.

#### Right to Correction — §12

The Two-Bid system under GFR Rule 173 provides a **72-hour representation window** after technical disqualification. This maps directly to DPDP §12: the bidder (Data Principal) has the right to have inaccurate data corrected before a final decision. TenderAudit surfaces `NeedsManualReview` verdicts with the 72-hour window in the UI, giving the procuring officer a workflow to re-evaluate after a bidder submits corrected documents.

---

## 2. GIGW 3.0 (2025)

### Standard and legal force

**GIGW 3.0 (2025)** mandates **WCAG 2.1 Level AA** (17 new success criteria over GIGW 2.0). **IS 17802** (BIS, notified 2023) is legally enforceable under the RPwD Amendment Rules 2023. GIGW 3.0 maps to IS 17802.

### How TenderAudit meets GIGW 3.0

**shadcn/ui + Radix UI:** All interactive elements — matrix table cells, evidence drill-down panels, criterion review form — use Radix primitives with correct ARIA roles and keyboard navigation.

**Matrix view accessibility:** The bidder × criterion matrix is implemented as a semantic `<table>` with `<th scope="col">` for criteria headers and `<th scope="row">` for bidder names. Screen readers can navigate cell by cell and announce verdict + confidence.

**Color-only distinction avoided:** Verdict badges use color AND text ("Eligible", "Not Eligible", "Review") AND icon (check, cross, warning triangle) — not color alone. This satisfies WCAG 1.4.1 (Use of Color).

**Focus management:** Opening a drill-down panel moves focus to the panel header; closing it returns focus to the originating matrix cell. This satisfies WCAG 2.4.3 (Focus Order).

**STQC CQW and API mandates:** Same as JudgmentFlow — post-pilot requirements. See checklist below.

---

## 3. CERT-In Safe-to-Host

### Requirement

Mandatory for any application on `*.gov.in` or NIC infrastructure. CERT-In empanelled auditors include WeSecureApp, SecureLayer7, Cereiv, Astra Security.

### VAPT scope for TenderAudit

| Scope item | TenderAudit-specific risks |
|---|---|
| Web application | Bid data leakage between procuring officers; IDOR on bidder documents; XSS in criterion description fields |
| REST API | Evaluation manipulation via forged API requests; unauthorized matrix PDF download |
| File upload | Malicious PDFs with embedded JavaScript (PyMuPDF strips JS but must be verified); ZIP bombs; path traversal via bidder filenames |
| PDF signing | Signature spoofing; certificate chain validation bypass |
| Vector DB | Embedding inversion attacks (inferring bidder document content from stored vectors) |
| Audit log | Privilege escalation to gain UPDATE/DELETE on audit_log table |
| Infrastructure | PostgreSQL access controls; MinIO bucket ACLs; vLLM endpoint exposure |

### Timeline and budget

- Duration: **4–6 weeks**
- Budget: **~₹3–8 lakh**
- Engage after hackathon shortlisting

### Incident reporting

Within **6 hours of detection** per CERT-In April 2022 directive:
- Unauthorized access to bid data
- Audit chain tampering
- Signed PDF forgery
- Extraction of bidder personal/financial data

---

## 4. MeitY Empanelment

### CSP empanelment (MeghRaj)

Empanelled CSPs as of early 2026:

| CSP | Regions in India | Notes |
|---|---|---|
| AWS | Mumbai, Hyderabad | GovCloud not available in India; standard regions are empanelled |
| Microsoft Azure | Central India (Pune), South India (Chennai) | Azure Government not India-specific; use empanelled commercial |
| Google Cloud | Mumbai, Delhi | |
| IBM Cloud | Chennai | |
| E2E Networks | Delhi NCR | Indian-origin CSP |
| Yotta Shakti | Navi Mumbai | NVIDIA H100; BHASHINI-validated; recommended for GPU workloads |
| Tata Communications Vayu | | |

Required ISO certifications: **ISO 27001:2017, ISO 27017:2015, ISO 27018:2019, ISO 20000-1:2018**. Data must remain within India.

### IndiaAI Compute Mission (RFE August 2024)

The MeitY IndiaAI Mission's RFE for AI Compute (August 2024) finalized **10 bidders** for a **10,000 GPU pool** in early 2025. This is the recommended procurement path for GPU rental for Level-2 air-gap deployment. Access via IndiaAI portal under NIC rate card.

---

## 5. GFR 2017 and Procurement Law Alignment

This is the compliance pillar specific to TenderAudit. The system must be aligned with the legal framework governing Indian government procurement.

### GFR 2017 Rule 173 — Eligibility Criteria

Rule 173 requires that eligibility criteria be:
- Specified in the bid document before bids are invited
- Applied uniformly to all bidders
- Documented with reasons for any disqualification

TenderAudit's criterion extraction maps directly to this: every extracted criterion carries a `source_clause` (verbatim from the tender) and a `source_bbox` (page + coordinates). The procuring officer reviews and approves criteria before evaluation — no criteria can be added post-bid-opening.

### GFR 2017 Rule 162 — Single Bid

If only one bid is received after the initial tender, Rule 162 governs whether to re-tender or proceed. TenderAudit records the count of eligible bidders in the matrix summary. If eligible count = 1, the UI flags "Single bid situation — Rule 162 applies" and requires officer confirmation before proceeding to award.

### GFR 2017 Rules 166 & 194 — Emergency Procurement

Emergency procurement under Rules 166 and 194 waives some documentation requirements. TenderAudit's criterion schema includes an `emergency_procurement: bool` flag on the `Tender` model; if true, certain `doc_type_required` fields are marked as optional rather than mandatory.

### Public Procurement (Preference to Make in India) Order 2017

Local content scoring applies to procurement above specified thresholds. The `Criterion` schema supports `type="local_content"` with `threshold` as a percentage. TenderAudit extracts this criterion from the tender if present.

### MSE Order 2012 — MSME Preference

Micro and Small Enterprises are exempt from EMD (Earnest Money Deposit) requirements and receive price preference. TenderAudit detects Udyam certificate in bidder documents (classified as `doc_type="udyam_cert"`) and applies the EMD exemption rule before evaluating the EMD criterion. (Demo: this is noted in the `NeedsManualReview` explanation for Bidder-D who has expired Udyam.)

### Order F.No.6/18/2019-PPD — Land-Border-Country Restriction

Bidders from countries sharing a land border with India (currently Pakistan, China, Bangladesh, Nepal, Myanmar, Bhutan, Afghanistan) must obtain prior security clearance from MHA. TenderAudit extracts this as a mandatory `type="compliance"` criterion from any tender that includes it (all CRPF tenders do). The extracted criterion requires `doc_type="land_border_undertaking"` — the bidder must upload the Land-Border-Country Undertaking form.

### Two-Bid System and 72-Hour Representation Window

CRPF tender clauses specify that bidders disqualified at the technical stage have **72 hours to file a representation**. TenderAudit surfaces this:
- `NeedsManualReview` verdict: shows "72-hour representation window" label
- `NotEligible` verdict: shows the representation deadline (bid opening + 72 hours)
- Officer can trigger "re-evaluation after representation" workflow, which creates a new `Verdict` row with `replaces_verdict_id` pointing to the original

---

## Compliance Checklist

### What the prototype achieves

| Requirement | Status | Implementation |
|---|---|---|
| DPDP §7(c) legitimate-use ground documented | Done | This document |
| Immutable audit log (§8) | Done | SHA-256 hash-chained PostgreSQL, INSERT-only role |
| No-silent-disqualification invariant | Done | `no_silent_disqual.py` runtime guard |
| Right to correction via representation window (§12) | Done | `NeedsManualReview` + 72-hour window in UI |
| Data minimization via doc_type whitelisting | Done | RAG retrieval filtered by `doc_type` |
| 72-hour DPDP breach notification stub | Done | `api/audit/breach.py` |
| WCAG 2.1 AA via shadcn/Radix | Done | Accessible matrix table + drill-down |
| GFR Rule 173 criterion sourcing | Done | `source_clause` + `source_bbox` on every criterion |
| Land-border-country criterion extraction | Done | Extracted from CRPF seed tenders |
| Signed audit PDF (self-signed demo) | Done | pyHanko PKCS#7 |
| Air-gap Level 1 and Level 2 documented | Done | `docs/airgap_deployment.md` |

### What a pilot deployment requires

| Requirement | Action | Owner | Timeline |
|---|---|---|---|
| CERT-In Safe-to-Host certificate | VAPT engagement; ~₹3–8L | Team + auditor | 4–6 weeks post-shortlist |
| STQC CQW certification | GIGW 3.0 + IS 17802 audit | Team + STQC | 4–8 weeks |
| NIC Class III DSC for signed audit PDF | Procure from NIC-accredited CA | Team | Before signing feature launch |
| GeM/CPPP integration | NIC IntegrationGateway connector or GeM buyer API | Team + NIC | After MOU; GeM API access |
| DPDP Data Fiduciary registration | Register with Data Protection Board of India | Legal counsel | Before pilot go-live |
| Data Protection Impact Assessment | Required for systematic processing of bidder personal data | Legal counsel + team | Before CERT-In engagement |
| SSO integration for procuring officer login | Implement per GIGW 3.0 | Team | Before *.gov.in deployment |
| Bidder data retention schedule | Define retention period; implement automated deletion | Team + legal counsel | Before pilot go-live |
| Two-Bid representation workflow | Full re-evaluation trigger post-representation | Team | Before CRPF pilot |
| MSE EMD exemption (Udyam registry lookup) | Integrate Udyam verification API | Team | Phase 2 |
| LTV (Long-Term Validation) for signed PDFs | pyHanko LTV with OCSP stapling or pre-fetched OCSP | Team | Before signed PDF in production |
