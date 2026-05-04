# TenderAudit

> The first procurement evaluator that defends itself in writ court.

![Demo placeholder — insert asciicast or screenshot here](docs/assets/demo-placeholder.png)

---

## What it does

- Ingests a government tender PDF and extracts every eligibility criterion (financial, technical, compliance, documentation) as a structured JSON record with its exact source bounding-box.
- Allows the procuring officer to review and correct every criterion before evaluation begins — no silent criterion injection.
- Accepts bidder document bundles (ZIP), embeds and indexes every page, and evaluates each bidder against each criterion via retrieval-augmented generation (RAG) over the bidder's own uploaded documents.
- Enforces a hard runtime invariant: a `NotEligible` verdict with zero supporting evidence items raises an exception before it can be persisted. Every disqualification must cite a bbox on a page in the bidder's PDF.
- Generates a digitally signed (PKCS#7 via pyHanko) bidder × criterion matrix PDF that constitutes the legally defensible evaluation record.

---

## Why it matters

Public procurement disqualifications are challenged in writ court when the disqualification reason cannot be traced to the evidence. GFR 2017 Rule 173 requires that eligibility criteria be specified in the bid document and applied uniformly. The CRPF Bhopal Works NIT-71 (https://crpf.gov.in/Upload/Tender/832082025-481.pdf) specifies "Average Annual Turnover Certificate of Rs. 41.6 Lakh... from a Chartered Accountant" — if a bidder is disqualified for not meeting that threshold, the procuring officer must produce the exact page of the audited balance sheet that fell short. Current practice: a committee meeting note says "turnover insufficient" with no document reference.

TenderAudit enforces a no-silent-disqualification invariant at the application layer, not in the prompt. The `no_silent_disqual.py` guard raises a runtime exception if any `NotEligible` verdict reaches the database without at least one `Evidence` item carrying a `{bidder_doc_id, page, bbox, quote}`. The signed audit PDF means the procuring officer can walk into writ court with a document that shows exactly what was evaluated, what was found, and who approved it.

The Two-Bid system under GFR Rule 173 also gives bidders a 72-hour representation window after technical disqualification. TenderAudit's `NeedsManualReview` verdict and per-criterion evidence trail make that representation process tractable for the first time.

---

## Quick start (60 seconds)

```bash
# Prerequisites: Python 3.11, Node 20, Docker (optional), tesseract (brew install tesseract)
git clone <this-repo>
cd tenderaudit
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-...
make setup        # ~3 min: installs Python venv + npm deps + embeddings model
make seed         # downloads tender PDFs + generates 4 synthetic bidder bundles
make dev          # starts api on :8001 + web on :3001
open http://localhost:3001
```

If Docker is available:

```bash
docker compose up --build
open http://localhost:3001
```

The seed step places 8 government tender PDFs and 32 synthetic bidder bundles (4 per tender: Bidder-A clean/eligible, Bidder-B turnover shortfall, Bidder-C missing ISO, Bidder-D ambiguous/expired certs) in `seed/`. See [`seed/README.md`](seed/README.md) for corpus details.

---

## Architecture

```
Tender PDF (officer upload)
        │
        ▼
  [pdf_loader.py]
  PyMuPDF → digital spans
  PaddleOCR-VL → image-only pages
        │
        ▼
  [llm_client.py]  ←  criterion_extract.txt prompt
  gpt-4o-2024-08-06 Structured Outputs
  → [Criterion] (Pydantic, strict=true)
        │
        ▼
  Officer review screen
  (edit / approve criteria)
        │
        ▼
  Bidder ZIPs (officer upload)
  → chunk → embed (text-embedding-3-large)
  → pgvector store
        │
        ▼
  [eval_engine.py] per (criterion, bidder)
  → RAG top-5 → LLM compare vs threshold
  → Verdict {Eligible|NotEligible|NeedsManualReview}
        │
        ▼
  [no_silent_disqual.py]
  Hard guard: NotEligible requires evidence[]
        │
        ▼
  [sign_pdf.py]  (pyHanko PKCS#7)
  Signed matrix PDF
        │
        ▼
  [audit/log.py]
  SHA-256 hash-chained audit row
        │
        ▼
  FastAPI :8001  ←→  Next.js :3001
  Matrix view + drill-down UI
```

Detailed: see [docs/architecture.md](docs/architecture.md).

---

## Demo flow (3 min)

1. Open http://localhost:3001. Click **Upload Tender**.
2. Drop `seed/tenders/crpf-bhopal-nit71.pdf` (NIT-71, turnover threshold ₹41.6 lakh).
3. A toast confirms "Extracted 6 criteria in ~4s." Navigate to the **Criteria Review** screen.
4. The criteria list shows: Financial (turnover ₹41.6L), Documentation (CA certificate), Compliance (non-blacklisting affidavit), etc. Click criterion #1 → PDF jumps to the source clause.
5. Click **Approve All Criteria**. Navigate to **Upload Bidders**.
6. Upload `seed/bidders/bidder-A-clean.zip`, `bidder-B-shortfall.zip`, `bidder-C-missing-iso.zip`, `bidder-D-ambiguous.zip`.
7. Click **Run Evaluation**. The 4×6 matrix populates: Bidder-A all green, Bidder-B red on turnover, Bidder-C red on documentation, Bidder-D amber (NeedsManualReview) on compliance.
8. Click the Bidder-B / Turnover cell (red). The drill-down shows: retrieved evidence page from Bidder-B's CA certificate → "Annual turnover: ₹38.2 lakh" — below the ₹41.6 lakh threshold. Exact bbox highlighted.
9. Click **Download Signed Audit PDF**. The signed PDF opens; the signature panel is visible.

Full script: [docs/demo_script.md](docs/demo_script.md).

---

## Differentiation

| Player | What they do | Why they are not TenderAudit |
|---|---|---|
| **SpotDraft** ($113M raised; $8M Qualcomm Ventures Jan 2026 extension; 1M contracts/year) | Enterprise CLM, on-device VerifAI | B2B contracts, not government procurement. No bidder evaluation engine. No signed audit PDF. |
| **CaseMine** | Legal research / case discovery | Research tool. No tender or procurement workflow. |
| **Manupatra AI** | Legal database + AI search | Subscription research product. No evaluation pipeline. |
| **Legistify** | Enterprise legal management | Mid-market corporate. No GFR-aware procurement logic. |
| **ProcurementIQ / Bilcrux** | Tender intelligence for bidders | Audience mismatch — helps bidders find tenders, not officers evaluate them. |
| **GeM portal** | Government marketplace | Does not perform criterion-level evaluation or audit PDF generation. |

---

## Compliance

- **DPDP Act 2023 / Rules 2025 (G.S.R. 846(E), notified 13 Nov 2025):** Bidder documents contain personal/corporate data. §7 legitimate-use ground (public procurement under GFR 2017) applies. Immutable audit log (§8). Right-to-correct via officer review screen (§12). 72-hour breach notification webhook stub. Penalty cap: ₹250 crore per breach. Compliance deadline: 13 May 2027 (may be shortened to 12 months per Minister Vaishnaw's public statement).
- **GIGW 3.0 (2025):** WCAG 2.1 AA via shadcn/Radix. IS 17802 mapping documented. STQC CQW certification required before `*.gov.in` deployment.
- **CERT-In Safe-to-Host:** VAPT scope documented; budget ~₹3–8 lakh; timeline 4–6 weeks. Incident reporting within 6 hours per April 2022 CERT-In directive.
- **GFR 2017 Alignment:** Criterion extraction maps to Rule 173 (eligibility); Two-Bid system 72-hour representation window surfaced via `NeedsManualReview` verdict; land-border-country restriction (Order F.No.6/18/2019-PPD) is a mandatory criterion field.

Full detail: [docs/compliance.md](docs/compliance.md).

---

## Air-gap deployment

**Level 1** (no internet egress): all Python dependencies bundled; LLM calls skipped; officer manually reviews extracted criteria and fills evaluation notes. Runs on RHEL 8/9 with no external network access — matches CRPF edge-site reality. **Level 2** (sovereign GPU): vLLM serves Qwen 2.5 32B Q4 / Gemma 3 27B Q4 / Llama 3.3 70B Q4 on a local GPU; toggle via `LLM_BACKEND=vllm` + `VLLM_BASE_URL=http://localhost:8004/v1`. CRPF HQ Delhi GPUs (available at CGO Complex) support Level 2; edge sites remain Level 1.

Embeddings: swap `text-embedding-3-large` for `BAAI/bge-m3` (BGE-M3 leads Indian-language reverse retrieval at 32.1% R@1 across 12 Indian languages per arXiv:2601.10205).

Full guide: [docs/airgap_deployment.md](docs/airgap_deployment.md).

---

## Tech stack

- **Runtime:** Python 3.11, Node 20
- **API:** FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0, Alembic
- **Storage:** SQLite (default dev), PostgreSQL + pgvector (production), MinIO (blob store, sha256-addressed)
- **OCR:** PyMuPDF 1.24 (digital pages), PaddleOCR-VL 1.5 (image-only pages)
- **LLM:** `gpt-4o-2024-08-06` with Structured Outputs (`response_format: {type: "json_schema", strict: true}`); `gpt-4o-mini-2024-07-18` for triage
- **Embeddings:** `text-embedding-3-large` (prototype); `BAAI/bge-m3` (air-gap production)
- **Vector DB:** pgvector on PostgreSQL (prototype); Qdrant for >50M vectors (production scale)
- **Air-gap LLM:** vLLM + Qwen 2.5 32B / Gemma 3 27B / Llama 3.3 70B (Q4_K_M)
- **PDF signing:** pyHanko (PKCS#7); demo uses self-signed cert; production uses NIC-issued Class III DSC
- **Frontend:** Next.js 15 (App Router), shadcn/ui, Radix UI, `@react-pdf-viewer/core` + `@react-pdf-viewer/highlight`, react-resizable-panels

---

## Roadmap

- **Pilot:** CRPF (Delhi HQ) procurement cell for works tender evaluation. GeM buyer-side API integration for tender metadata ingestion.
- **CERT-In Safe-to-Host:** Engage empanelled auditor; ~4–6 weeks.
- **NIC-issued Class III DSC:** Replace self-signed cert in `sign_pdf.py` for production audit PDF validity.
- **BHASHINI translation hooks:** Enable Hindi-language tender UI and Devanagari-mixed document processing.
- **BGE-M3 embeddings:** Replace `text-embedding-3-large` for air-gap deployments and Indian-language bidder documents.
- **STQC CQW + GIGW 3.0 audit:** Required before `*.gov.in` deployment.

---

## Project structure

```
tenderaudit/
├── api/            FastAPI backend (main.py, schemas/, routes/, prompts/, eval_engine.py,
│                   no_silent_disqual.py, rag.py, sign_pdf.py)
├── web/            Next.js 15 frontend (criteria review, matrix view, drill-down)
├── seed/           8 tender PDFs + 32 synthetic bidder bundles (4 per tender)
├── scripts/        Setup utilities (install deps, download models, gen_bidder_bundle.py)
├── docs/           Architecture, compliance, air-gap, demo script, pitch outline
│   ├── architecture.md
│   ├── airgap_deployment.md
│   ├── compliance.md
│   ├── demo_script.md
│   └── pitch_outline.md
└── data/           Runtime artifacts — SQLite DB, MinIO blobs (gitignored)
```

---

## License

MIT. Seed tender PDFs are public procurement documents sourced from crpf.gov.in, mospi.gov.in, mea.gov.in, stqc.gov.in, and eprocure.gov.in. Synthetic bidder bundles are entirely fabricated.

---

## Contact

Hackathon submission: AI for Bharat 2 — Team \<team-name\>
Contact: \<your-email@example.com\>
Track: GovTech / LegalTech
