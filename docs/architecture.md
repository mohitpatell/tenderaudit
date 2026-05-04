# TenderAudit — Architecture

## 1. System Overview

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
│             │  PaddleOCR-VL → image-only pages       │              │
│             └────────────────────────────────────────┘              │
│                     │                                               │
│             sha256(file) → MinIO blob key                           │
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
│             chunk(spans, max_tokens=512, overlap=64)                │
│                     │                                               │
│                     ▼                                               │
│             text-embedding-3-large (OpenAI)                         │
│             OR  BAAI/bge-m3 (air-gap)                               │
│             → 1536-dim / 1024-dim vector                            │
│                     │                                               │
│                     ▼                                               │
│             pgvector  (chunks table)                                │
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
│  2. pgvector top-5 similarity filtered by doc_type whitelist        │
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
| `pdf_loader` | `api/ingest/pdf_loader.py` | Load PDF, route to digital/OCR, hash, return `Document` |
| `ocr_paddle` | `api/ingest/ocr_paddle.py` | PaddleOCR-VL 1.5 wrapper; preprocess pipeline |
| `preprocess` | `api/ingest/preprocess.py` | grayscale → Otsu → medianBlur → deskew → adaptive contrast |
| `bbox` | `api/provenance/bbox.py` | `Span` dataclass; `find_span(query, fuzzy)` |
| `bbox_store` | `api/provenance/store.py` | Persist spans to PostgreSQL |
| `llm_client` | `api/extract/llm_client.py` | `LLMClient.extract(spans, schema, prompt)` |
| `schemas/tender` | `api/schemas/tender.py` | `Criterion`, `Bidder`, `Evidence`, `Verdict` Pydantic models |
| `prompts/criterion_extract` | `api/prompts/criterion_extract.txt` | System prompt for criterion extraction |
| `prompts/bidder_evaluate` | `api/prompts/bidder_evaluate.txt` | System prompt for per-(criterion, bidder) evaluation |
| `rag` | `api/rag.py` | Chunk + embed bidder docs; pgvector similarity search |
| `eval_engine` | `api/eval_engine.py` | Per-(criterion, bidder) evaluation loop; verdict logic |
| `no_silent_disqual` | `api/no_silent_disqual.py` | Hard guard; raises `NoSilentDisqualError` on empty evidence |
| `sign_pdf` | `api/sign_pdf.py` | pyHanko PKCS#7 signing of matrix PDF |
| `audit/log` | `api/audit/log.py` | Append-only write; `verify_chain()` |
| `routes/tenders` | `api/routes/tenders.py` | CRUD for tenders and criteria |
| `routes/bidders` | `api/routes/bidders.py` | Bidder upload, chunk-index, evaluation trigger |
| `routes/audit` | `api/routes/audit.py` | `GET /audit/{tender_id}` + chain verification |
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

### Default (development)

- **SQLite** at `data/tenderaudit.db`.
- **Local filesystem** at `data/blobs/` with sha256-sharded paths.
- **pgvector** (in-process via `sqlite-vec` extension) for prototype vector search.

### Production

- **PostgreSQL 16** with `pgvector` extension. Per Timescale/TigerData benchmark (May 2025): Postgres+pgvector+pgvectorscale delivers 11.4× more throughput than Qdrant at 471.57 QPS on 50M embeddings. At prototype scale (32 bidders × ~50 docs × ~20 chunks = ~32,000 chunks), pgvector is the correct choice.
- **MinIO** for all PDF blobs (tender + bidder documents + signed audit PDF).
- Migration to **Qdrant** is appropriate beyond 50M vectors (production scale with many tenders and bidder archives).

---

## 6. Audit Log Internals

The audit log is identical in schema and algorithm to JudgmentFlow's (SHA-256 hash chain, INSERT-only PostgreSQL role, `verify_chain()`). The action vocabulary is different:

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

2. pgvector similarity search
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

The guard is called in `eval_engine.py` after the LLM returns a verdict and before `db.add(verdict)`. It cannot be bypassed by a prompt change.

---

## 10. Failure Modes and Graceful Degradation

| Failure | Behavior |
|---|---|
| **OCR returns empty spans on bidder doc** | Document stored as image blob; chunk is created with `text=""` and `embedding=None`; skipped in retrieval. Officer sees a warning: "Document X not indexed — upload text-layer PDF or re-scan." |
| **LLM criterion extraction fails** | Retry up to 3 times. On third failure: criteria list is empty; officer is shown a blank form to enter criteria manually. No evaluation blocked. |
| **LLM evaluation returns NeedsManualReview** | Verdict persisted without hitting the `NoSilentDisqualError` guard. The matrix cell shows amber. The 72-hour representation window is surfaced to the officer in the UI. |
| **`NoSilentDisqualError` raised** | `eval_engine.py` catches the error, logs it to `audit_log` with `action="verdict.silent_disqual_blocked"`, and substitutes `NeedsManualReview` with `explanation="NotEligible verdict blocked: no evidence found. Manual review required."` |
| **pgvector similarity returns 0 results** | Retrieval query returns empty. Verdict is `NeedsManualReview` regardless of LLM output. |
| **Audit chain broken** | `GET /api/tenders/{id}/audit/verify` returns `{"chain_valid": false}`. Signing is blocked. Officer sees: "Audit chain integrity failure — signing disabled." |
| **pyHanko signing fails** | Matrix PDF is generated unsigned; a watermark "UNSIGNED — FOR REVIEW ONLY" is stamped on every page. The signed download button is disabled. |
| **MinIO unavailable** | Fallback to local `data/blobs/`; background retry every 60 seconds. |

---

## 11. Trade-offs Taken for the Demo

| Item | Demo State | Production Path |
|---|---|---|
| **Embeddings model** | `text-embedding-3-large` (OpenAI) | `BAAI/bge-m3` for air-gap; `multilingual-e5-large-instruct` as primary per arXiv:2601.10205 |
| **Digital signature** | Self-signed PKCS#7 certificate via pyHanko | NIC-issued Class III DSC; certificate chain from NSDG CA |
| **GeM/CPPP integration** | Manual bidder ZIP upload | GeM buyer-side API for tender metadata; NIC IntegrationGateway for bidder bundle download |
| **Bidder document classification** | LLM infers `doc_type` from filename + first 200 words | Fine-tuned classifier on the 18 standard document types (EMD, Integrity Pact, CA cert, ISO cert, etc.) |
| **Two-Bid 72-hour representation** | UI shows amber verdict with "review required" label | Workflow integration: officer sends representation notice; bidder uploads additional docs; re-evaluation triggered |
| **Land-border-country check** (F.No.6/18/2019-PPD) | Criterion extracted from tender text; evaluated as any other criterion | Registry lookup of MHA-notified land-border countries; automatic flag for applicable bidder registration addresses |
| **MSE EMD exemption** (MSE Order 2012) | Not implemented | Bidder uploads Udyam certificate; `eval_engine` applies EMD exemption rule before financial criterion evaluation |
| **Signed PDF audit trail** | SHA-256 chained log viewable in UI | pyHanko long-term validation (LTV) with OCSP stapling for multi-year audit defensibility |
