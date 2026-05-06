# TenderAudit — Architecture

## 1. System Overview

> **Status note:** `docs/flow.md` is the canonical reference for the
> prototype implemented today. This architecture document describes the
> pilot/production target. Current implementation: SQLite + local filesystem
> blobs, Chroma, PyMuPDF + Tesseract, filename-based doc-type classification,
> and synchronous FastAPI requests.

TenderAudit is a procurement evaluation pipeline for Indian government tenders: it ingests a tender PDF, extracts eligibility criteria, accepts bidder document bundles, evaluates each bidder against each criterion via retrieval-augmented generation, enforces a no-silent-disqualification invariant at the application layer, and generates a digitally signed audit PDF. The system is built on the same shared-core library as JudgmentFlow; the diverging components are the criterion and evaluation schemas, the RAG engine, the evaluation engine with its hard guard, and the pyHanko signing module.

Every `NotEligible` verdict must carry at least one `Evidence` item with a `{bidder_doc_id, page, bbox, quote}` before it can be persisted. This invariant is enforced by a runtime guard (`no_silent_disqual.py`), not by a prompt instruction. A `NeedsManualReview` verdict is always preferred to a `NotEligible` when evidence is incomplete or ambiguous.

---

## 2. Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TENDER INGEST                                  │
│                                                                     │
│  Officer uploads tender PDF (HTTP multipart)                        │
│                     │                                               │
│                     ▼                                               │
│             pdf_loader.py                                           │
│             ┌────────────────────────────────────────┐              │
│             │  PyMuPDF → digital spans               │              │
│             │  Tesseract today / PaddleOCR-VL target │              │
│             └────────────────────────────────────────┘              │
│                     │                                               │
│             sha256(file) → local blob today / MinIO target          │
│                     │                                               │
│                     ▼                                               │
│             llm_client.py  ←  prompts/criterion_extract.txt         │
│             gpt-4o-2024-08-06 Structured Outputs                    │
│             → [Criterion] (Pydantic, strict=true)                   │
│                     │                                               │
│                     ▼                                               │
│             Officer reviews + approves criteria                     │
│             (edit threshold, type, source_clause)                   │
│                                                                     │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BIDDER INGEST                                   │
│                                                                     │
│  Officer uploads bidder ZIPs (one per bidder)                       │
│                     │                                               │
│                     ▼                                               │
│             For each document in ZIP:                               │
│             pdf_loader.py → spans                                   │
│             chunk today: 400 chars / target: 512 tokens             │
│                     │                                               │
│                     ▼                                               │
│             text-embedding-3-small today / large target             │
│             OR  BAAI/bge-m3 (air-gap)                               │
│             → 1536-dim / 1024-dim vector                            │
│                     │                                               │
│                     ▼                                               │
│             Chroma today / pgvector target                          │
│             {chunk_id, bidder_id, doc_id, page, bbox, text,         │
│              embedding, doc_type}                                   │
│                                                                     │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EVALUATION ENGINE                                 │
│                                                                     │
│  eval_engine.py  — for each (Criterion, Bidder):                    │
│                                                                     │
│  1. Build retrieval query from criterion.threshold + doc_type hint  │
│  2. Chroma top-5 today / pgvector target, doc_type whitelist        │
│  3. LLM (gpt-4o-2024-08-06) compares evidence vs threshold          │
│     → Verdict {Eligible|NotEligible|NeedsManualReview}              │
│     → [Evidence {bidder_doc_id, page, bbox, quote, score}]          │
│                                                                     │
│  Hard verdict rules:                                                │
│  ├── missing required doc → NeedsManualReview (NEVER NotEligible)   │
│  ├── confidence < 0.75 → NeedsManualReview                          │
│  ├── threshold met, conf ≥ 0.85 → Eligible                          │
│  └── threshold not met, conf ≥ 0.85, evidence complete → NotEligible│
│                                                                     │
│                     │                                               │
│                     ▼                                               │
│  no_silent_disqual.py  ←─── HARD GUARD                              │
│  Raises NoSilentDisqualError if:                                    │
│  verdict == NotEligible AND len(evidence) == 0                      │
│                                                                     │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SIGNING + AUDIT                                   │
│                                                                     │
│  sign_pdf.py  (pyHanko PKCS#7)                                      │
│  → signed matrix PDF (bidder × criterion)                           │
│                                                                     │
│  audit/log.py  (SHA-256 hash-chained)                               │
│  → audit_log row for every evaluation event                         │
│                                                                     │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API + UI LAYER                                 │
│                                                                     │
│  FastAPI :8001  ←→  Next.js 15 :3001                                │
│                                                                     │
│  Matrix view: shadcn Table + Badge (green/red/amber per verdict)    │
│  Drill-down: split-pane → bidder PDF bbox + evidence quote          │
│  Signed PDF download button                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Map

| Module | Path | Responsibility |
|---|---|---|
| `pdf_loader` | `api/core/pdf_loader.py` | Implemented today: PyMuPDF digital extraction + Tesseract OCR fallback |
| `ocr_tesseract` | `api/core/ocr_tesseract.py` | Implemented today: pytesseract wrapper |
| `sections` | `api/core/sections.py` | Implemented today: regex eligibility/compliance/documentation classifier |
| `provenance` | `api/core/provenance.py` | Implemented today: quote-to-bbox fuzzy matcher |
| `llm_client` | `api/core/llm_client.py` | Implemented today: OpenAI Structured Outputs client |
| `schemas` | `api/domain/schemas.py` | Implemented today: `Criterion`, `Bidder`, `Evidence`, `Verdict` Pydantic models |
| `prompts/criterion_extract` | `api/domain/prompts/criterion_extract.txt` | Implemented today: system prompt for criterion extraction |
| `prompts/bidder_evaluate` | `api/domain/prompts/bidder_evaluate.txt` | Implemented today: system prompt for per-(criterion, bidder) evaluation |
| `rag` | `api/domain/rag.py` | Implemented today: Chroma chunking, embedding, and similarity search |
| `eval_engine` | `api/domain/eval_engine.py` | Implemented today: per-(criterion, bidder) evaluation loop and verdict logic |
| `no_silent_disqual` | `api/domain/no_silent_disqual.py` | Implemented today: hard guard for empty-evidence disqualification |
| `sign_pdf` | `api/domain/sign_pdf.py` | Implemented today: pyHanko PKCS#7 signing of matrix PDF |
| `audit` | `api/core/audit.py` | Implemented today: SQLite SHA-256 hash chain and `verify_chain()` |
| `routes/tenders` | `api/domain/routes/tenders.py` | Implemented today: CRUD for tenders and criteria |
| `routes/bidders` | `api/domain/routes/bidders.py` | Implemented today: bidder upload, chunk-index, drill-down |
| `routes/audit` | `api/domain/routes/audit.py` | Implemented today: evaluate, matrix, sign, audit routes |
| `ocr_paddle`, `bbox_store`, `minio_client`, `pgvector` | Target modules/services, not present in the prototype tree | Pilot/production upgrades |
| `minio_client` | `api/storage/minio_client.py` | sha256-addressed blob store |
| `PdfViewer` | `web/components/PdfViewer.tsx` | `<Worker>` + `<Viewer>` + highlight plugin |
| `SplitPane` | `web/components/SplitPane.tsx` | `ResizablePanelGroup` horizontal |
| `FieldReview` | `web/components/FieldReview.tsx` | Per-criterion officer review form |
| `MatrixView` | `web/components/MatrixView.tsx` | Bidder × criterion grid; verdict badges |
| `DrillDown` | `web/components/DrillDown.tsx` | Expand cell → evidence list + PDF highlight |
| `AuditTrailDrawer` | `web/components/AuditTrailDrawer.tsx` | Hash-chained log slide-out |

---

## 4. Data Model

```
Tender
├── id: UUID (PK)
├── blob_key: str (sha256 of source PDF)
├── title: str
├── nit_no: str | null             # e.g. "NIT-71"
├── source_url: str | null         # e.g. crpf.gov.in/Upload/Tender/...
├── estimated_cost: decimal | null
├── currency: str default "INR"
├── published_at: date | null
└── created_at: datetime

Criterion
├── id: UUID (PK)
├── tender_id: UUID (FK → Tender)
├── seq: int
├── type: enum(financial, technical, compliance, documentation)
├── description: str
├── threshold: str | null          # e.g. "41.6" (lakh INR)
├── threshold_unit: str | null     # e.g. "lakh_inr", "iso_cert_number"
├── source_clause: str             # verbatim text from tender
├── source_bbox: BboxRecord (FK)
├── doc_type_required: str | null  # e.g. "ca_turnover_cert", "iso_cert"
└── approved: bool

Bidder
├── id: UUID (PK)
├── tender_id: UUID (FK → Tender)
├── name: str
├── bundle_blob_key: str           # sha256 of ZIP
└── indexed_at: datetime | null

BidderDocument
├── id: UUID (PK)
├── bidder_id: UUID (FK → Bidder)
├── blob_key: str
├── filename: str
└── doc_type: str | null           # classified by LLM on ingest

BidderChunk
├── id: UUID (PK)
├── bidder_doc_id: UUID (FK → BidderDocument)
├── page: int
├── bbox: BboxRecord (FK) | null
├── text: str
└── embedding: vector(1536)        # pgvector column

Evidence
├── id: UUID (PK)
├── verdict_id: UUID (FK → Verdict)
├── bidder_doc_id: UUID (FK → BidderDocument)
├── page: int
├── bbox: BboxRecord (FK)
├── quote: str
└── score: float                   # cosine similarity

Verdict
├── id: UUID (PK)
├── tender_id: UUID (FK → Tender)
├── criterion_id: UUID (FK → Criterion)
├── bidder_id: UUID (FK → Bidder)
├── verdict: enum(Eligible, NotEligible, NeedsManualReview)
├── confidence: float
├── explanation: str
├── evidence: [Evidence]           # min 1 if verdict == NotEligible
└── created_at: datetime

BboxRecord
├── id: UUID (PK)
├── doc_blob_key: str
├── page_no: int
├── x0, y0, x1, y1: float         # absolute pixels
├── highlight_top, highlight_left,
│   highlight_width, highlight_height: float  # percentages
```

---

## 5. Storage

### Default (development, implemented today)

- **SQLite** at `data/audit.db` and related local persistence helpers.
- **Local filesystem** at `data/blobs/` with sha256-sharded paths.
- **Chroma** under `data/chroma/` for prototype vector search.

### Production target

- **PostgreSQL 16** with `pgvector` extension. Per Timescale/TigerData benchmark (May 2025): Postgres+pgvector+pgvectorscale delivers 11.4× more throughput than Qdrant at 471.57 QPS on 50M embeddings. At prototype scale (32 bidders × ~50 docs × ~20 chunks = ~32,000 chunks), pgvector is the correct choice.
- **MinIO** for all PDF blobs (tender + bidder documents + signed audit PDF).
- Migration to **Qdrant** is appropriate beyond 50M vectors (production scale with many tenders and bidder archives).

---

## 6. Audit Log Internals

The audit log uses the same SHA-256 hash-chain algorithm as JudgmentFlow. Today it is SQLite-backed; the production target is an INSERT-only PostgreSQL table. The action vocabulary is different:

| Action | Entity type | Triggered by |
|---|---|---|
| `tender.uploaded` | Tender | Officer upload |
| `criterion.extracted` | Criterion | System (LLM extraction) |
| `criterion.approved` | Criterion | Officer approval |
| `criterion.edited` | Criterion | Officer edit |
| `bidder.uploaded` | Bidder | Officer upload |
| `bidder.indexed` | Bidder | System (embedding complete) |
| `verdict.created` | Verdict | System (eval_engine) |
| `verdict.no_silent_disqual_checked` | Verdict | System (guard passed) |
| `matrix_pdf.signed` | Tender | System (pyHanko) |

### Hash chain example row

```json
{
  "ts": "2026-05-04T11:15:22Z",
  "actor": "system:eval_engine",
  "action": "verdict.created",
  "entity_type": "Verdict",
  "entity_id": "c9d1...",
  "payload_json": {
    "tender_id": "a1b2...",
    "criterion_id": "x3y4...",
    "bidder_id": "m5n6...",
    "verdict": "NotEligible",
    "confidence": 0.91,
    "n_evidence": 1,
    "evidence_quote": "Annual turnover: ₹38.2 lakh",
    "threshold": "41.6 lakh INR"
  }
}
```

`verify_chain()` is exposed at `GET /api/tenders/{id}/audit/verify` and called before generating the signed PDF — a broken chain blocks signing.

---

## 7. LLM Call Flow

```
PHASE 1: Criterion Extraction

1. Tender spans → gpt-4o-2024-08-06 Structured Outputs
   Schema: List[Criterion]
   Prompt: criterion_extract.txt
   Rules:
   - Every Criterion MUST cite a verbatim source_clause (≤60 words)
   - type MUST be one of {financial, technical, compliance, documentation}
   - threshold and threshold_unit MUST be numeric/unit pairs where measurable
   - doc_type_required: infer from context (e.g. "ca_turnover_cert", "iso_cert")

PHASE 2: Per-(Criterion, Bidder) Evaluation

For each (criterion, bidder) pair:

1. Build retrieval query
   query = f"{criterion.description} {criterion.threshold} {criterion.doc_type_required}"

2. Chroma similarity search today / pgvector target
   SELECT chunk_id, text, page, bbox, bidder_doc_id, doc_type
   FROM bidder_chunks
   WHERE bidder_id = $1
     AND doc_type = ANY($2)   -- doc_type whitelist from criterion
   ORDER BY embedding <=> $3  -- cosine distance
   LIMIT 5;

3. LLM evaluation
   Model: gpt-4o-2024-08-06
   Prompt: bidder_evaluate.txt
   Input: criterion JSON + top-5 chunks with bbox + bidder_doc_id
   Output: Verdict (Pydantic, strict=true)

4. Hard verdict rules applied in eval_engine.py (NOT in prompt):
   - len(top_k) == 0 → NeedsManualReview
   - doc_type of top_k not in criterion.doc_type_required → NeedsManualReview
   - confidence < 0.75 → NeedsManualReview
   - threshold met AND confidence ≥ 0.85 → Eligible
   - threshold not met AND confidence ≥ 0.85 AND evidence complete → NotEligible

5. no_silent_disqual.py guard
   if verdict.verdict == NotEligible and len(verdict.evidence) == 0:
       raise NoSilentDisqualError(criterion_id, bidder_id)
   # Guard is a runtime check, not a prompt instruction

6. Audit write
   AuditLog row: "verdict.created" + "verdict.no_silent_disqual_checked"
```

---

## 8. Frontend Architecture

### App Router routes

```
web/app/
├── page.tsx                          # Upload tender landing
├── (officer)/
│   └── tender/
│       └── [id]/
│           ├── criteria/page.tsx     # Criterion review screen
│           ├── matrix/page.tsx       # Bidder × criterion matrix
│           └── audit/page.tsx        # Audit trail viewer
└── bidder/
    └── [bidId]/
        └── criterion/
            └── [critId]/
                └── page.tsx         # Evidence drill-down
```

### Key components

**`MatrixView.tsx`** — the hero UI for TenderAudit:
- shadcn `<Table>` with bidders as rows, criteria as columns
- Each cell: `<Badge>` with verdict color (green=Eligible, red=NotEligible, amber=NeedsManualReview)
- Click cell → opens `<DrillDown>` panel or navigates to drill-down route

**`DrillDown.tsx`** — shows for a single (criterion, bidder) verdict:
- Left: `<PdfViewer>` with evidence bbox highlighted (bidder's document)
- Right: evidence quote, verdict explanation, confidence score
- "Request Review" button for `NeedsManualReview` verdicts

**`PdfViewer.tsx`** — identical to JudgmentFlow's component. Accepts `highlights: HighlightArea[]` from evidence bboxes.

**`FieldReview.tsx`** — used in the Criterion Review screen (same component as JudgmentFlow, parameterized for `Criterion` schema).

---

## 9. No-Silent-Disqualification Invariant

This is the single most important technical detail for the IAS/CRPF jury. It is documented here explicitly.

The invariant:

> A `NotEligible` verdict cannot be persisted if `evidence == []`.

Implementation in `no_silent_disqual.py`:

```python
class NoSilentDisqualError(Exception):
    """Raised when a NotEligible verdict has no supporting evidence."""

def check_no_silent_disqual(verdict: Verdict) -> None:
    """
    Call this before any persist operation on a Verdict.
    Raises NoSilentDisqualError if the invariant is violated.
    """
    if verdict.verdict == VerdictEnum.NotEligible:
        if not verdict.evidence or len(verdict.evidence) == 0:
            raise NoSilentDisqualError(
                f"NotEligible verdict for criterion={verdict.criterion_id} "
                f"bidder={verdict.bidder_id} has zero evidence items. "
                f"Set verdict=NeedsManualReview instead."
            )
```

The test in `tests/test_no_silent_disqual.py`:

```python
def test_empty_evidence_raises():
    verdict = Verdict(
        criterion_id=uuid4(),
        bidder_id=uuid4(),
        verdict=VerdictEnum.NotEligible,
        confidence=0.91,
        explanation="Turnover below threshold",
        evidence=[]   # ← violation
    )
    with pytest.raises(NoSilentDisqualError):
        check_no_silent_disqual(verdict)
```

The guard is called in `eval_engine.py` after the LLM returns a verdict and before the matrix is persisted. It cannot be bypassed by a prompt change.

---

## 10. Failure Modes and Graceful Degradation

| Failure | Behavior |
|---|---|
| **OCR returns empty spans on bidder doc** | Document stored as image blob; chunk is created with `text=""` and `embedding=None`; skipped in retrieval. Officer sees a warning: "Document X not indexed — upload text-layer PDF or re-scan." |
| **LLM criterion extraction fails** | Retry up to 3 times. On third failure: criteria list is empty; officer is shown a blank form to enter criteria manually. No evaluation blocked. |
| **LLM evaluation returns NeedsManualReview** | Verdict persisted without hitting the `NoSilentDisqualError` guard. The matrix cell shows amber. The 72-hour representation window is surfaced to the officer in the UI. |
| **`NoSilentDisqualError` raised** | `eval_engine.py` catches the error, logs it to `audit_log` with `action="verdict.silent_disqual_blocked"`, and substitutes `NeedsManualReview` with `explanation="NotEligible verdict blocked: no evidence found. Manual review required."` |
| **Similarity search returns 0 results** | Retrieval query returns empty. Verdict is `NeedsManualReview` regardless of LLM output. Chroma is used today; pgvector is the target. |
| **Audit chain broken** | `GET /api/tenders/{id}/audit/verify` returns `{"chain_valid": false}`. Signing is blocked. Officer sees: "Audit chain integrity failure — signing disabled." |
| **pyHanko signing fails** | Matrix PDF is generated unsigned; a watermark "UNSIGNED — FOR REVIEW ONLY" is stamped on every page. The signed download button is disabled. |
| **MinIO unavailable** | Target only. The prototype writes directly to local `data/blobs/`. |

---

## 11. Trade-offs Taken for the Demo

| Item | Demo State | Production Path |
|---|---|---|
| **Embeddings model** | `text-embedding-3-small` (OpenAI) in the prototype | `BAAI/bge-m3` for air-gap; evaluate `text-embedding-3-large` or a reranker only if quality requires it |
| **Digital signature** | Self-signed PKCS#7 certificate via pyHanko | NIC-issued Class III DSC; certificate chain from NSDG CA |
| **GeM/CPPP integration** | Manual bidder ZIP upload | GeM buyer-side API for tender metadata; NIC IntegrationGateway for bidder bundle download |
| **Bidder document classification** | LLM infers `doc_type` from filename + first 200 words | Fine-tuned classifier on the 18 standard document types (EMD, Integrity Pact, CA cert, ISO cert, etc.) |
| **Two-Bid 72-hour representation** | UI shows amber verdict with "review required" label | Workflow integration: officer sends representation notice; bidder uploads additional docs; re-evaluation triggered |
| **Land-border-country check** (F.No.6/18/2019-PPD) | Criterion extracted from tender text; evaluated as any other criterion | Registry lookup of MHA-notified land-border countries; automatic flag for applicable bidder registration addresses |
| **MSE EMD exemption** (MSE Order 2012) | Not implemented | Bidder uploads Udyam certificate; `eval_engine` applies EMD exemption rule before financial criterion evaluation |
| **Signed PDF audit trail** | SHA-256 chained log viewable in UI | pyHanko long-term validation (LTV) with OCSP stapling for multi-year audit defensibility |

---

## 12. Large-PDF Ingest Pipeline (Production)

### 12.1 Why the demo cannot ship as-is

The prototype's `POST /api/tenders/upload` endpoint is synchronous: the request thread holds the HTTP connection while `pdf_loader.py` runs PyMuPDF/Tesseract across every page, then `llm_client` sends the eligibility text to `gpt-4o-2024-08-06` for criterion extraction, then control returns to the browser. For the 6–14 page CRPF/RITES NITs in the demo corpus this completes in a few seconds and is acceptable.

Real Indian government tenders are different:

| Source | Typical size | Pages |
|---|---|---|
| CPWD construction NIT | 18–35 MB | 180–420 |
| Indian Railways works tender | 22–48 MB | 250–500 |
| AIIMS equipment tender (Tech + Financial bid) | 8–14 MB | 80–160 |
| Defence MoD RFP (with annexures) | 35–50 MB | 400–800 |

End-to-end synchronous time for a 200-page tender PDF: 30–90 seconds (PyMuPDF 4–8s, PaddleOCR-VL 12–60s on image-heavy pages, criterion extraction 8–18s, embedding/persist 4–6s). The browser default 30-second timeout fails before the response arrives. When five officers concurrently upload bidder ZIPs (each containing 15–25 PDFs that fan out to per-page OCR), the API process runs out of worker threads and the whole evaluation queue stalls.

The demo therefore cannot scale beyond demo. The production pipeline below addresses upload, queueing, progress, idempotency, limits, failure semantics, and observability.

### 12.2 Async upload flow

```
Browser                       Backend (FastAPI)              Object Store
   │                               │                            │
   │  POST /api/uploads/init       │                            │
   │  {filename, size_bytes,       │                            │
   │   sha256_client}              │                            │
   ├──────────────────────────────▶│                            │
   │                               │  presign_put(blob_key)     │
   │                               ├──────────────────────────▶ │
   │                               │  ◀── presigned URL ────────│
   │  {upload_url, blob_key,       │                            │
   │   job_id_pending}             │                            │
   │ ◀─────────────────────────────│                            │
   │                                                            │
   │  PUT {upload_url}  (multipart, direct browser → store)     │
   ├───────────────────────────────────────────────────────────▶│
   │                                                            │
   │  POST /api/uploads/complete   │                            │
   │  {blob_key, job_kind:tender}  │                            │
   ├──────────────────────────────▶│                            │
   │                               │  verify sha256 server-side │
   │                               │  enqueue ingest.parse_pdf  │
   │  {job_id}                     │                            │
   │ ◀─────────────────────────────│                            │
```

- Object store: **MinIO** for self-host (NIC private cloud, MeghRaj), **AWS S3** (or AWS GovCloud equivalent) for cloud deployments. Both expose pre-signed PUT URLs with a 15-minute TTL.
- The browser uploads directly to the store; the FastAPI process never streams the bytes. This keeps the API stateless during upload and makes the API horizontally scalable behind nginx/ALB without sticky sessions.
- `POST /api/uploads/complete` is small (<1 KB) and triggers the SHA-256 verification (server-side `head_object` on MinIO returns ETag, full-file rehash is run inside the first Celery stage to confirm).
- The blob key is `sha256(file)` (see section 2). Pre-signed URLs are issued only after the client-claimed sha256 is checked against the dedup table (section 12.6).

### 12.3 Background job queue

- **Celery 5.4** with **Redis 7** broker for self-host. **RQ 1.16** is the simpler-self-host fallback when Celery's beat/canvas features are not needed.
- Workers run in three pools: `ingest` (CPU-bound, PyMuPDF + chunking), `ocr` (GPU-eligible, PaddleOCR-VL), `llm` (I/O-bound, LLM and embedding API calls). Each pool scales independently.

#### Job stages and chaining

Stages are Celery tasks composed with `chain()` and `group()`:

| Stage | Task name | Pool | Parallelism |
|---|---|---|---|
| Parse | `ingest.parse_pdf` | ingest | 1 per doc |
| OCR | `ingest.ocr_page` | ocr | per-page fan-out (group) |
| Chunk + Embed | `ingest.chunk_and_embed` | llm | 1 per doc, batched internally |
| Persist | `ingest.persist` | ingest | 1 per doc |
| Tender-only: extract | `criteria.extract` | llm | 1 per tender |
| Bidder-only: evaluate | `eval.run` | llm | group of (criterion × bidder) |

Tender chain:
```
parse_pdf → group(ocr_page for each image-only page) → chunk_and_embed
         → persist → criteria.extract
```

Bidder chain (one per document in the ZIP):
```
parse_pdf → group(ocr_page ...) → chunk_and_embed → persist
                                                  → eval.run (fanout per criterion)
```

`ingest.parse_pdf` opens the PDF with PyMuPDF, classifies each page as `digital` (text layer present) or `image_only`, and emits a `group` of `ocr_page` subtasks for the latter. Digital pages bypass OCR entirely. Per-page OCR is the unit of parallelism that makes 400-page tenders complete in minutes instead of an hour.

`ingest.chunk_and_embed` calls `chunk(spans, max_tokens=512, overlap=64)` and batches the resulting chunks into embedding requests of size 64 (see 12.7). It uses `text-embedding-3-large` in cloud mode and `BAAI/bge-m3` (served via `text-embeddings-inference` on a single A10/L4) in air-gap mode.

### 12.4 Progress and cancellation

`GET /api/jobs/{job_id}`:
```json
{
  "job_id": "01J...",
  "kind": "tender",
  "stage": "ocr",
  "stage_seq": 2,
  "stage_total": 5,
  "pct": 47.5,
  "eta_s": 38,
  "pages_done": 95,
  "pages_total": 200,
  "started_at": "2026-05-04T11:13:02Z",
  "error": null
}
```

For OCR-heavy documents `pct` is computed as `(pages_done / pages_total)` weighted by stage. The progress writer is the OCR worker itself, which `HSET`s into Redis under `job:{job_id}:progress` after each page completes; the API endpoint reads from Redis (no Postgres write per page).

`POST /api/jobs/{job_id}/cancel` sets `cancel_requested=true` in the job row, then iterates the chain and calls `revoke(task_id, terminate=False)` on every pending task. In-flight tasks check `cancel_requested` between OCR pages and exit cleanly. **Stages already persisted are not rolled back** — a partially-OCRed tender remains queryable; re-running ingest is idempotent on `(blob_key, stage)`.

### 12.5 Notification channels

| Channel | Latency | Use case | Library/Gateway |
|---|---|---|---|
| **WebSocket / SSE** | <1s | In-app live progress, matrix cell updates | FastAPI `WebSocket` route + Redis pub/sub fanout |
| **Email** | 5–60s | "Evaluation complete, sign-ready" digest to officer + reviewer | NIC eMail Gateway (`email.gov.in`) for govt deployments; SMTP relay otherwise |
| **SMS** | 10–90s | High-priority alerts (audit chain broken, evaluation failed, signing blocked) | NIC SMS Gateway (`sms.gov.in`) over the MSDG channel |

The dashboard subscribes via SSE on `GET /api/tenders/{id}/events` and re-renders matrix cells as `verdict.created` events arrive. Email and SMS are emitted from a single `notifications.dispatch` Celery task so audit logging is uniform across channels.

```
Event                              | WS/SSE | Email | SMS
-----------------------------------|--------|-------|-----
job.stage_changed                  |   X    |       |
job.completed (tender)             |   X    |   X   |
job.completed (bidder evaluation)  |   X    |   X   |
job.failed                         |   X    |   X   |  X
audit.chain_broken                 |   X    |   X   |  X
matrix_pdf.signed                  |   X    |   X   |
```

### 12.6 Idempotency and dedup

The blob key is `sha256(file)` (section 2). The dedup table:

```
UploadDedup
├── blob_sha256: char(64) PK
├── first_job_id: ULID
├── kind: enum(tender, bidder_doc)
├── parsed_at: datetime | null
├── chunked_at: datetime | null
└── persisted_at: datetime | null
```

`POST /api/uploads/init` checks `UploadDedup` first. If the sha256 is already present and `persisted_at IS NOT NULL`, the response is `{job_id: <first_job_id>, status: "deduped"}` and no pre-signed URL is issued. The browser short-circuits to the existing matrix.

Re-evaluation against a previously-ingested tender is **explicit** and never implicit:

```
POST /api/tenders/{id}/evaluate?force=true
```

This dispatches a fresh `eval.run` group without re-running `ingest.*` stages. Without `?force=true`, a re-POST returns the existing verdict set with `cached=true`.

### 12.7 Resource limits

Limits are enforced at the API boundary and re-checked at the worker boundary:

| Limit | Value | Enforced at | Error code on breach |
|---|---|---|---|
| Max upload size | 100 MB | Pre-signed URL `Content-Length` constraint | `413 PayloadTooLarge` |
| Max pages per doc | 1000 | `ingest.parse_pdf` after open | `422 PdfTooManyPages` |
| Max docs per bidder ZIP | 50 | ZIP listing in `bidders.uploaded` handler | `422 BundleTooManyDocs` |
| OCR concurrency per worker | 8 | Celery `worker_concurrency=8` on `ocr` pool | queue back-pressure, no error |
| Embedding batch size | 64 chunks | `ingest.chunk_and_embed` | n/a (internal) |
| LLM extraction max input tokens | 120k | `criteria.extract` truncation guard | `422 TenderTooLong` |
| Per-tenant uploads in flight | 10 | Redis counter `tenant:{id}:inflight` | `429 TooManyJobs` |

`PdfTooManyPages` and `TenderTooLong` are surfaced to the officer as inline errors with the exact violated limit; the partial blob is retained for 24 hours so support can investigate.

### 12.8 Failure semantics

Mirrors the table style of section 10. These rows extend, not replace, that table:

| Failure | Behavior |
|---|---|
| **OCR worker crash mid-page** | Celery retries the `ocr_page` task up to 2 times with `countdown=15s`. On third failure, the page is recorded as `text=""` in `BidderChunk` with `ocr_failed=true` and the parent job continues. Officer sees a per-page warning in the document drawer. |
| **Redis broker unavailable** | `POST /api/uploads/complete` writes the job row to a Postgres `job_outbox` table with `status=pending_enqueue` instead of dispatching. A separate `outbox_drainer` Celery beat task (every 30s, runs in the API process via APScheduler when Celery is down) re-attempts dispatch. Uploads are accepted; processing resumes when Redis returns. |
| **Embedding API rate-limited (429)** | `chunk_and_embed` applies exponential backoff: 5s, 15s, 45s, 135s, 300s (capped at 5 minutes), max 5 retries. After the cap, the job is marked `failed_retryable` and the officer can manually re-trigger via `POST /api/jobs/{job_id}/retry`. |
| **LLM `criteria.extract` exceeds 120k context** | Tender is split by section header (regex on `^\d+\.\s+[A-Z]` followed by chapter title heuristic); each section is extracted independently and merged. If the split fails, fall back to `NeedsManualReview` for the whole tender — the officer enters criteria manually (consistent with section 10 row 2). |
| **Pre-signed URL expired before browser PUT** | `POST /api/uploads/complete` checks `HEAD object` and returns `409 UploadExpired`. The frontend re-calls `init` and resumes; no server-side cleanup needed (MinIO lifecycle rule deletes orphans after 24h). |
| **Cancellation race (cancel arrives after persist)** | `cancel` is a no-op for completed stages. The chain stops only at the next un-started stage. If `criteria.extract` already wrote rows, those rows persist and the officer is shown the partial criterion list with a "cancelled" banner. |

### 12.9 Observability

Three layers, all required:

**Structured logs (stdout, JSON)** — One log line per stage transition with fixed keys, ingestible by Loki/CloudWatch without parsers:
```json
{
  "ts": "2026-05-04T11:13:42.118Z",
  "level": "info",
  "service": "tenderaudit-worker",
  "job_id": "01J...",
  "tender_id": "a1b2...",
  "stage": "ocr",
  "event": "stage.completed",
  "duration_ms": 38420,
  "pages_done": 200,
  "ocr_failed_pages": 0
}
```

**Prometheus metrics** — exposed at `/metrics` on each worker:

| Metric | Type | Labels |
|---|---|---|
| `tenderaudit_queue_depth` | gauge | `pool` (ingest/ocr/llm) |
| `tenderaudit_stage_duration_seconds` | histogram | `stage`, `outcome` (success/retry/failed) |
| `tenderaudit_ocr_pages_total` | counter | `outcome` |
| `tenderaudit_embedding_batches_total` | counter | `model`, `outcome` |
| `tenderaudit_llm_tokens_total` | counter | `model`, `phase` (extract/evaluate) |
| `tenderaudit_jobs_inflight` | gauge | `tenant_id`, `kind` |

Grafana dashboard panels: queue depth per pool, p50/p95/p99 stage duration, OCR failure rate, LLM token spend per tenant.

**Audit log entries for async events** — the SHA-256 hash chain (section 6) covers async lifecycle too. Two new actions:

| Action | Triggered by |
|---|---|
| `job.completed` | Final stage of a chain succeeds |
| `job.failed` | Chain exits via `failed` or `failed_retryable` |

These rows include `{job_id, kind, stage_failed_at, retry_count, duration_ms}` in `payload_json`. `verify_chain()` therefore fails if a malicious operator tries to silently drop a failed-job row before the signed PDF is generated — matching the integrity guarantee the synchronous demo already provides.
