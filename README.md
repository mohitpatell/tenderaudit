# TenderAudit

> The first procurement evaluator that defends itself in writ court.

Extracts eligibility criteria from a government tender, evaluates each bidder against each criterion via RAG over the bidder's own documents, and produces a digitally signed bidder × criterion matrix — with a runtime invariant that every disqualification must cite the page that supports it.

## Live demo

- **Web (UI):** https://warm-plateau-98672-f8f1268616c3.herokuapp.com
- **API:** https://damp-scrubland-58077-92d7a7c07dd5.herokuapp.com (`/health`, `/docs`)

---

## What it does

- Extracts every eligibility criterion (financial, technical, compliance, documentation) from a tender PDF with **bbox source provenance**.
- Officer reviews and corrects criteria before evaluation begins — **no silent criterion injection**.
- Indexes bidder documents into a vector store, then evaluates each (criterion × bidder) pair via retrieval-augmented generation.
- Enforces a hard invariant: a `NotEligible` verdict with no supporting evidence raises an exception **before** it can be persisted. Every disqualification cites a `{bidder_doc_id, page, bbox, quote}`.
- Generates a **PKCS#7-signed** (pyHanko) bidder × criterion matrix PDF — the legally defensible evaluation record.

---

## Why it matters

GFR 2017 Rule 173 requires that eligibility criteria be applied uniformly with a documented basis. Today, a procuring officer who disqualifies a bidder for "insufficient turnover" cannot point to the page of the audited balance sheet that fell short. TenderAudit makes the invariant a property of the application, not the prompt: `no_silent_disqual.enforce()` is a runtime guard. The signed matrix PDF means the officer can walk into writ court with a document that shows exactly what was evaluated, what was found, and who approved it.

---

## Quick start

```bash
git clone <repo> && cd tenderaudit
cp .env.example .env             # set OPENAI_API_KEY=sk-...
make setup && make seed && make dev
open http://localhost:3001
```

Prerequisites: Python 3.11, Node 20, `tesseract` (`brew install tesseract`).

---

## Architecture

```
Tender PDF → criterion extraction (gpt-4o Structured Outputs)
   → officer review → bidder ZIP ingest → embed → pgvector
   → per (criterion, bidder) RAG → Verdict {Eligible | NotEligible | NeedsManualReview}
   → no_silent_disqual guard → pyHanko signed PDF → SHA-256 audit log
```

Production targets PostgreSQL + pgvector, MinIO blob store, and vLLM-served Qwen 2.5 32B / Llama 3.3 70B for air-gapped sites. Embeddings swap to `BAAI/bge-m3` for Indian-language bidder documents. Detail: [docs/architecture.md](docs/architecture.md).

---

## Tech stack

- **Backend:** FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0, Alembic
- **Storage:** SQLite (dev) · PostgreSQL + pgvector + MinIO (prod)
- **OCR:** PyMuPDF 1.24, Tesseract
- **LLM:** `gpt-4o-2024-08-06` Structured Outputs · `gpt-4o-mini` for triage · vLLM + Qwen 2.5 32B for air-gap
- **Embeddings:** `text-embedding-3-large` (cloud) · `BAAI/bge-m3` (air-gap, Indian languages)
- **PDF signing:** pyHanko (PKCS#7); demo uses self-signed cert; production uses NIC Class III DSC
- **Frontend:** Next.js 15 (App Router), shadcn/ui, `@react-pdf-viewer/core`

---

## Compliance & deployment

- **DPDP Act 2023** (§7 legitimate-use under GFR 2017, §8 immutability, §12 right-to-correct) — [docs/compliance.md](docs/compliance.md)
- **GFR 2017 Rule 173** — Two-Bid system, 72-hour representation window surfaced via `NeedsManualReview`
- **GIGW 3.0 / WCAG 2.1 AA** via Radix accessible primitives
- **Air-gap-ready** — Level 1 (no internet) and Level 2 (sovereign GPU). [docs/airgap_deployment.md](docs/airgap_deployment.md)
- **CERT-In Safe-to-Host** scope documented in [docs/compliance.md](docs/compliance.md)

---

## Project structure

```
tenderaudit/
├── api/    FastAPI backend (extractor, eval_engine, no_silent_disqual, RAG, sign_pdf)
├── web/    Next.js 15 frontend (criteria review, matrix, drill-down)
├── seed/   8 tender PDFs + 32 synthetic bidder bundles
├── docs/   architecture · compliance · airgap · demo · pitch
└── data/   SQLite + blobs (gitignored)
```

---

## License & contact

MIT. Seed tenders are public procurement documents (crpf.gov.in, mospi.gov.in, mea.gov.in, stqc.gov.in, eprocure.gov.in). Bidder bundles are synthetic.
Hackathon: **AI for Bharat 2** — Track: GovTech / LegalTech.
