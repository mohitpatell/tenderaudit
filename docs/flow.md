# TenderAudit — End-to-End Flow

A self-contained walkthrough of the entire project: what it is, the stack, every API and data type, every page, every backend stage from tender upload to signed audit, what is real versus stubbed, and the production path. Reading this doc alone should be enough to ramp on the codebase.

Companion: `architecture.md` is the structural reference (data model details, audit chain internals, async pipeline design). This doc is the narrative. Skim `architecture.md` §2 (pipeline diagram) and §12 (large-PDF production pipeline) once you finish here.

---

## 1. Project Context

### 1.1 What is TenderAudit

Indian government procurement at scale (CRPF, Railways, AIIMS, MoD, GeM…) involves tenders that ship as 100–500-page PDFs with eligibility clauses scattered across legal-style sections. Bidders respond with ZIP bundles of 10–30 supporting PDFs (turnover certificates, ISO certs, balance sheets, DSC certificates, blacklisting affidavits…). Today, evaluation is manual — an officer reads each bidder's bundle against the tender's clauses and decides Eligible / Not Eligible / Needs Manual Review per criterion. It is slow, inconsistent, hard to audit, and a known source of disputes.

**TenderAudit automates the evaluation matrix while preserving auditability.** It:

1. Ingests a tender PDF and extracts structured eligibility criteria (LLM with Structured Outputs).
2. Ingests bidder ZIPs, indexes every page into a vector store.
3. For each (criterion × bidder) pair, retrieves the most relevant bidder pages via RAG and asks an LLM for a verdict + cited evidence.
4. Enforces a **no-silent-disqualification invariant** at the application layer: a `NotEligible` verdict that lacks evidence is auto-downgraded to `NeedsManualReview`. This is policy code, not a prompt instruction.
5. Records every state change in a SHA-256 hash chain (SQLite-backed) and emits a digitally-signed PDF report at the end.

**Non-goals in the current build:**
- Multi-tenant auth / RBAC (single officer in demo; production design is in `architecture.md`).
- Two-Bid 72-hour representation workflow (UI surfaces amber verdicts; backend automation is a production path item).
- GeM/CPPP API integration (manual upload today; gateway plans documented).
- Land-border-country compliance check (extracted as a regular criterion today; production path adds an MHA registry lookup).

### 1.2 Stack at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (officer)                                          │
│  ─────────────────                                          │
│  Next.js 15 App Router · React 19 · Tailwind · shadcn/ui    │
│  Pages under web/app/ — see §1.3                            │
└─────────────┬───────────────────────────────────────────────┘
              │  fetch /api/proxy/*
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Next.js API proxy (web/app/api/proxy/[...path]/route.ts)   │
│  Forwards every method+path verbatim to API_URL             │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI on :8001 (api/main.py)                             │
│  ─────────────────                                          │
│  Routes: tenders, bidders, audit (in api/domain/routes/)    │
│  Core:   pdf_loader, ocr_tesseract, sections, provenance,   │
│          llm_client, storage, audit                         │
│  Domain: criterion_extractor, eval_engine, rag,             │
│          no_silent_disqual, sign_pdf                        │
│  State:  app.state dicts (in-memory; see §2)                │
│  Persistent: data/blobs/, data/audit.db, data/chroma/       │
└─────────┬─────────┬─────────┬───────────────────────────────┘
          │         │         │
          ▼         ▼         ▼
       OpenAI   Tesseract  Chroma (local)
       (gpt-4o,
        embed-3-small)
```

| Layer | Tech | File |
|---|---|---|
| Frontend | Next.js 15, React 19, Tailwind, shadcn/ui, sonner | `web/` |
| Frontend → backend bridge | Next.js Route Handler, transparent proxy | `web/app/api/proxy/[...path]/route.ts` |
| Backend HTTP | FastAPI + uvicorn | `api/main.py` |
| PDF text | PyMuPDF (`fitz`) | `api/core/pdf_loader.py` |
| OCR fallback | Tesseract via `pytesseract` | `api/core/ocr_tesseract.py` |
| LLM client | `openai` SDK (Structured Outputs) | `api/core/llm_client.py` |
| Vector store | Chroma (persistent, in-process) | `api/domain/rag.py` |
| Audit chain | SQLite + `hashlib.sha256` | `api/core/audit.py` |
| PDF signing | pyHanko + `cryptography` | `api/domain/sign_pdf.py` |

### 1.3 Frontend Pages

| Path | File | Purpose | Backend calls |
|---|---|---|---|
| `/` | `web/app/page.tsx` | Landing — drop tender PDF | `POST /api/tenders/upload` |
| `/data` | `web/app/data/page.tsx` | Stored data + audit hash chain inspector | `GET /api/tenders`, `GET /api/audit`, `GET /api/audit/verify` |
| `/tender/[id]/criteria` | `web/app/(officer)/tender/[id]/criteria/page.tsx` | Review LLM-extracted criteria, approve each | `GET /api/tenders/{id}`, `POST /api/tenders/{id}/criteria/approve` |
| `/tender/[id]/upload-bidders` | `web/app/(officer)/tender/[id]/upload-bidders/page.tsx` | Drop bidder ZIPs, run evaluation | `POST /api/tenders/{id}/bidders/upload` (per zip), `POST /api/tenders/{id}/evaluate` |
| `/tender/[id]/matrix` | `web/app/(officer)/tender/[id]/matrix/page.tsx` | Evaluation matrix grid (bidders × criteria) | `GET /api/tenders/{id}/matrix` |
| `/bidder/[bidId]/criterion/[critId]` | `web/app/(officer)/bidder/[bidId]/criterion/[critId]/page.tsx` | Drill-down: original PDF + bbox highlight + override form | `GET /api/bidders/{id}/criterion/{cid}`, `POST /api/audit` |

Layouts: `web/app/(officer)/layout.tsx` wraps the officer-only routes with the sidebar and toaster.

### 1.4 API Surface

All backend routes live under `api/domain/routes/`. Browser hits `/api/proxy/<path>`; the proxy forwards `<path>` verbatim to FastAPI on `:8001`.

| Method | Path | Handler | Purpose |
|---|---|---|---|
| POST | `/api/tenders/upload` | `tenders.upload_tender` | Upload tender PDF; parse + LLM-extract criteria; return `{tender, blob_id}` |
| GET | `/api/tenders` | `tenders.list_tenders` | List tenders with summary counts (criteria, bidders, verdicts) |
| GET | `/api/tenders/{id}` | `tenders.get_tender` | Single tender + criteria |
| PATCH | `/api/tenders/{id}/criteria` | `tenders.patch_criteria` | Replace the criteria array (used for officer edits — currently not wired in UI) |
| GET | `/api/tenders/{id}/bidders` | `tenders.list_bidders` | List bidder summaries for a tender |
| POST | `/api/tenders/{id}/bidders/upload` | `bidders.upload_bidder` | Upload one bidder ZIP; extract PDFs; index into RAG |
| GET | `/api/bidders/{bidder_id}/criterion/{cid}` | `bidders.drill_down` | Verdict + evidence + doc blob ids for the drill-down page |
| POST | `/api/tenders/{id}/evaluate` | `audit.evaluate_tender` | Run RAG + LLM verdict for every (criterion × bidder); persist matrix |
| GET | `/api/tenders/{id}/matrix` | `audit.get_matrix` | Return the persisted matrix; 404 if not yet evaluated |
| POST | `/api/tenders/{id}/sign` | `audit.sign_tender` | Build + PKCS#7-sign the audit PDF; return blob id |
| GET | `/api/audit?limit=N` | `audit.list_audit` | Paginated audit log rows |
| GET | `/api/audit/verify` | `audit.verify_audit` | Walk the SHA-256 chain; return `{valid, broken_at}` |
| POST | `/api/audit` | `audit_routes` | Append override / arbitrary audit row (used by drill-down override) |
| GET | `/files/{blob_id}` | `main.get_blob` | Stream the original PDF bytes from `data/blobs/` (used by iframe + download) |
| GET | `/health` | `main.health` | Liveness probe |

### 1.5 Core Data Model

Defined in `api/domain/schemas.py` (Pydantic) and mirrored on the frontend in `web/lib/types.ts`.

| Type | Key fields | Notes |
|---|---|---|
| `Tender` | `id`, `title`, `issuer`, `nit_number`, `estimated_value`, `criteria: list[Criterion]` | The tender object the LLM extraction populates |
| `Criterion` | `id`, `name`, `type` (`financial`/`technical`/`compliance`/`documentation`), `description`, `threshold_value`, `threshold_unit`, `threshold_operator` (`>=`/`<=`/`==`/`exists`/`not_blacklisted`), `source_clause`, `source_bbox`, `required_documents`, `is_mandatory` | One row in the criteria column header. `source_clause` is the verbatim quote from the tender PDF. `source_bbox` is the page rectangle covering it. |
| `Bidder` | `id`, `tender_id`, `name`, `documents: list[BidderDoc]` | One bidder = one ZIP = N documents |
| `BidderDoc` | `id`, `bidder_id`, `filename`, `doc_type` (e.g. `iso_cert`, `balance_sheet`), `blob_id` | `doc_type` is filename-keyword today |
| `Evidence` | `bidder_doc_id`, `page`, `bbox`, `quote`, `score` | One Evidence record = one chunk pulled by RAG. `bbox` is the page rectangle for highlighting. `score` is cosine similarity. |
| `Verdict` | `criterion_id`, `bidder_id`, `verdict` (`Eligible`/`NotEligible`/`NeedsManualReview`), `confidence` (0–1), `explanation`, `evidence: list[Evidence]` | One row in the matrix grid. Every `NotEligible` is guaranteed by `no_silent_disqual.enforce` to have ≥ 1 evidence record. |
| `EvaluationMatrix` | `tender_id`, `bidders`, `criteria`, `verdicts` | What the matrix page renders. |
| `BBox` | `page`, `x0`, `y0`, `x1`, `y1` | PDF user-space rectangle, used by `/files/{blob_id}` overlay |
| Audit row | `id`, `ts`, `actor`, `action`, `entity_type`, `entity_id`, `payload_json`, `prev_hash`, `this_hash` | SHA-256 chained; `this_hash = sha256(prev_hash || canonical_json(payload))` |

`VerdictLLM` and `EvidenceLLM` are slimmer copies the LLM is asked to emit (no bbox/score — those are reattached server-side).

### 1.6 Demo Assets

| Path | What |
|---|---|
| `seed/pdfs/*.pdf` | 8 real Indian govt tender PDFs (340 KB – 4.7 MB), e.g. `crpf-1-gem-checklist.pdf`, `crpf-2-bhopal-nit71.pdf`. Use any of these for the tender upload. |
| `seed/bidders/<tender>/<profile>/*.pdf` | Original 12-PDF bidder bundles (1 page each, ~3 KB) generated by `scripts/gen_bidder_bundle.py`. Older artifacts; not used in the current demo flow. |
| `seed/demo-zips/*.zip` | **The 4 demo ZIPs the live demo uploads.** 4 PDFs each, 4-5 dense pages per PDF. Names + profiles below. |
| `seed/ground_truth.json` | Hand-curated expected verdicts; intended for evaluation harness. |
| `scripts/gen_demo_zips.py` | Regenerator for `seed/demo-zips/` if the firm details need changes. |

The 4 demo zips:

| ZIP | Firm | Designed verdict pattern |
|---|---|---|
| `bidder-mahindra-defence.zip` | Mahindra Defence Systems Pvt. Ltd. (Mumbai) | Clean — passes every criterion |
| `bidder-beml-limited.zip` | BEML Limited (Bangalore) | Turnover shortfall — defence-segment turnover ₹3.21 Cr explicitly stated, below ₹5 Cr threshold |
| `bidder-tata-advanced-systems.zip` | Tata Advanced Systems Ltd. (Hyderabad) | Missing ISO 9001 — only ISO 14001 environmental cert in the bundle |
| `bidder-force-motors.zip` | Force Motors Ltd. (Pune) | Ambiguous — ISO valid for wrong plant; net worth ₹2.18 Cr borderline; non-blacklisting affidavit 14 months stale |

Each PDF inside is realistic Indian formatting: distinct CIN/GSTIN/PAN, INR amounts in lakh-crore notation, signed CA letterheads, plausible dates.

---

## 2. Where Things Live

| Concern | Location | Persistence |
|---|---|---|
| Frontend dev server | `tenderaudit/web/` on `:3001` (`npm run dev`) | n/a |
| Backend dev server | `tenderaudit/api/` on `:8001` (`uvicorn api.main:app --reload`) | n/a |
| Tender object (parsed criteria, title, NIT, issuer) | `app.state.tenders[tender_id]` | **In-memory only** — lost on restart |
| Bidder objects (per tender) | `app.state.bidders[tender_id][bidder_id]` | In-memory only |
| Evaluation matrix | `app.state.matrices[tender_id]` | In-memory only |
| Blob → bytes (uploaded PDFs, signed PDFs) | Filesystem at `data/blobs/<sha256>` | Persistent |
| Audit hash chain | SQLite at `data/audit.db` | Persistent |
| RAG vector store | Chroma persistent at `data/chroma/` | Persistent |
| Frontend ↔ backend bridge | Next.js proxy `app/api/proxy/[...path]/route.ts` → `API_URL=http://localhost:8001` | n/a |

---

## 3. Tender Upload

**Trigger:** officer drops a tender PDF on the landing page (`web/app/page.tsx`).

**Frontend call:** `POST /api/proxy/api/tenders/upload` (multipart/form-data, field `file`).

**Backend handler:** `api/domain/routes/tenders.py:upload_tender`.

### What runs, in order

1. **Read bytes.** `await file.read()` — single buffer; no streaming. Hard-coded refusal on empty body.

2. **Persist blob.** `core.storage.put_bytes(raw, filename, content_type)` writes to `data/blobs/<sha256(raw)>` and returns a `BlobMeta` with `blob_id = sha256(raw)`. Re-uploading the same file is automatically deduped at the FS level.

3. **Parse the PDF.** `core.pdf_loader.load_pdf(tmp_path)`. Per page:
   - PyMuPDF (`fitz`) extracts digital text spans (each with bbox, line id, word confidence, page number) via `page.get_text("dict")`.
   - If the page yields fewer than `OCR_WORD_THRESHOLD = 50` words, the page is rasterized and routed to **Tesseract** (`core/ocr_tesseract.py`) for OCR. OCR spans get `conf` from Tesseract's per-word confidence.
   - Result is an immutable `Document(pages=tuple[Page], source_path)`.
   - **No LLM here.** Pure deterministic text extraction.

4. **Extract criteria.** `domain.criterion_extractor.extract(document, ...)`:
   - `_eligibility_text(document)` first runs `core.sections.classify(document)` — a heuristic that labels each span as `eligibility` / `compliance` / `documentation` / `boilerplate` based on regex patterns (e.g. `re.search(r"eligib|qualification|turnover|net worth", text)`). The eligibility/compliance/documentation spans are concatenated; if none match, the full doc text is used.
   - That text + the prompt at `api/domain/prompts/criterion_extract.txt` go to `LLMClient.parse(system=prompt, user=text, response_format=CriterionExtractionResult)`.
   - **Model:** `gpt-4o-2024-08-06` (env `OPENAI_MODEL`), **OpenAI Structured Outputs** mode — the response is JSON-schema-constrained at the API layer to match the `CriterionExtractionResult` Pydantic model. The result is each `Criterion` with `name`, `type`, `threshold_value`, `threshold_unit`, `threshold_operator`, `source_clause`, `required_documents`, `is_mandatory`.
   - `_attach_bboxes` then walks the criteria, calls `core.provenance.quote_to_bbox(document, c.source_clause)` per item: rapidfuzz fuzzy match (≥ 80 token-set ratio) of the LLM-returned quote against document spans → returns the matching span's bbox. If no match meets the threshold, falls back to the eligibility section's union bbox; logs a warning either way.
   - **Stub fallback:** if `OPENAI_API_KEY` is unset OR the LLM call raises, `extract_stub` returns a single placeholder `Criterion(name="Stub criterion", description="Auto-generated stub (no OPENAI_API_KEY)…", is_mandatory=True)`. The upload route never crashes because of LLM failure.

5. **Allocate `tender_id`.** `uuid.uuid4().hex[:12]` (12 hex chars, ~48 bits — fine for demo, would be UUIDv7 with a DB primary key in prod).

6. **Persist into in-memory state.** `state.tenders[tender_id] = tender` and `state.tender_blob[tender_id] = blob_id`. **No database.**

7. **Audit log.** `core.audit.append(conn, action="tender.upload", entity_type="tender", entity_id=tender_id, payload={"blob_id": ..., "criteria_count": ...})` writes one row to SQLite. The row's `this_hash = sha256(prev_hash || canonical_json(payload))`, forming a tamper-evident chain. Verifiable by `GET /api/audit/verify`.

8. **Response.** `{"tender": {...full criteria...}, "blob_id": "<sha256>"}`.

### Frontend reaction

- Landing page receives `id`, toasts, navigates to `/tender/{id}/criteria`.
- Criteria page calls `getTender(id)` → renders the LLM-extracted criteria. The officer can click "Approve" on each card. **The approve buttons currently only mutate React state** (`setApproved(...)`); there is no backend write. The "All approved → upload bidders" gate is a UI gate. (See §10 — this is one of the listed gaps.)

### Status table

| Step | State today | Production gap |
|---|---|---|
| PDF parse (digital + OCR) | **Real**, deterministic | Add PaddleOCR-VL for layout-aware OCR; current Tesseract loses tables |
| Section classification | Heuristic regex | Either keep heuristic (cheap and stable) or replace with a trained classifier |
| Criterion extraction | **Real LLM** when `OPENAI_API_KEY` set; stub otherwise | Add prompt versioning, golden tests, eval harness against `seed/ground_truth.json` |
| Criteria approval | **Real per-card approval** | `POST /api/tenders/{id}/criteria/approve` flips `criterion.approved` and audit-logs it; bulk edit persistence still uses `PATCH /api/tenders/{id}/criteria` |
| Persistence | In-memory dict | Postgres + SQLAlchemy; restart safety |
| Tender id | 12-hex uuid | UUIDv7 with monotonic ordering |

---

## 4. Criteria Review

**Page:** `web/app/(officer)/tender/[id]/criteria/page.tsx`.

What it does:

- `getTender(id)` to fetch criteria.
- Renders one `CriterionCard` per criterion with name, threshold, source-clause quote, mandatory flag.
- Officer clicks "Approve" on each → optimistic local `Set<criterion_id>` plus `POST /api/tenders/{id}/criteria/approve`.
- Officer can edit threshold/operator/source via a modal — also local-only (calls `handleUpdate`, does not POST).
- "Continue" button gated on `approved.size === criteria.length`.

**Remaining gap:**

- Approval is persisted and audit-logged. Edits made in the UI modal are still local-only; if the officer refreshes before a `PATCH /api/tenders/{id}/criteria` save path is wired, edits are lost.

---

## 5. Bidder Bundle Upload

**Trigger:** upload-bidders page (`tender/[id]/upload-bidders/page.tsx`). Officer drops one or more ZIP files; clicks "Run Evaluation".

The page now (after the recent rewire) iterates and **actually calls the backend** for each ZIP.

**Frontend call (per ZIP):** `POST /api/proxy/api/tenders/{id}/bidders/upload` (multipart, fields: `file` = the ZIP, `bidder_name` = derived from filename).

**Backend handler:** `api/domain/routes/bidders.py:upload_bidder`.

### What runs, in order, per ZIP

1. **Verify tender exists.** 404 if `tender_id not in state.tenders`.

2. **Read raw bytes** of the ZIP into memory. (Synchronous read — fine for demo; production needs streaming + size limits.)

3. **Allocate `bidder_id`** = `uuid.uuid4().hex[:12]`.

4. **Extract members.** `_extract_zip(raw)`:
   - `zipfile.ZipFile(io.BytesIO(raw))` — purely stdlib, no shell `unzip`.
   - Iterates `namelist()`, skips directories and any file not ending in `.pdf`.
   - Yields `(member_name, pdf_bytes)` tuples, all in memory.
   - Bad zip → `HTTPException 400 invalid zip`.

5. **For each PDF inside the ZIP:**
   - `storage.put_bytes(pdf_bytes, filename=member_name, ...)` → blob with `blob_id = sha256(pdf_bytes)`.
   - **Doc-type classification.** `_classify_doc_type(member_name)`: hard-coded keyword match against the filename (e.g. `"iso"` → `"iso_cert"`, `"turnover"` → `"ca_turnover_cert"`, `"balance"` → `"balance_sheet"`, …, else `"other"`). The code itself comments this as: *"Cheap filename-based classification. Real systems would do this via LLM."*
   - Build a `BidderDoc(id, bidder_id, filename, doc_type, blob_id)` Pydantic record.
   - Call `_load_pages_for_indexing(pdf_bytes)` — same `pdf_loader.load_pdf` path as the tender upload, returning `[(page_no, page_text, page_bbox)]`. Page bbox is the union of all spans on that page.

6. **Index into RAG.** `domain.rag.index_bidder_docs(tender_id, bidder, pages_by_doc_id)`:
   - Open/get a Chroma collection named `bidders_{tender_id}` from `data/chroma/`.
   - For each page, `_chunk_text(page_text, size=400, overlap=50)` — sliding-window character chunks (not token-aware).
   - For each chunk, append:
     - `documents`: the chunk text
     - `metadatas`: `{bidder_id, bidder_doc_id, page, bbox_serialized, doc_type}` (bbox flattened to JSON because Chroma metadata is scalar-only)
     - `ids`: `uuid.uuid4().hex` per chunk
   - One bulk `collection.add(...)` per bidder. Chroma calls the embedding function:
     - **If `OPENAI_API_KEY` is set:** `OpenAIEmbeddingFunction(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))` → 1536-dim vectors.
     - **Else if `RAG_FALLBACK_LOCAL=1`:** `SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")` → 384-dim, runs locally, no network.
     - **Else:** Chroma's built-in default embedder (`all-MiniLM-L6-v2` under the hood) — same model, different code path.

7. **Register the `Bidder`.** `state.bidders.setdefault(tender_id, {})[bidder_id] = bidder`. In-memory dict.

8. **Audit log entry.** `action="bidder.upload"`, `payload={tender_id, doc_count}`.

9. **Response.** `{"bidder": {...}}`.

### What gets text-extracted vs not

- **Born-digital PDFs (the 4 demo zips):** PyMuPDF reads the text layer directly. Fast, exact.
- **Scanned PDFs (real govt bidder bundles often are):** Pages with < 50 words from PyMuPDF route to Tesseract. OCR confidence is per-word; bboxes are still produced. No layout/table extraction — Tesseract returns flat reading order.
- **Image-only pages with figures/tables:** Tables get linearized into noisy text. This is a real issue for production (CA turnover certs are tables) — see "Production gaps" below.

### Status table

| Step | State today | Production gap |
|---|---|---|
| ZIP extraction | **Real**, stdlib | Stream extract + per-file size cap; reject zip-bombs |
| PDF text + OCR | **Real**, PyMuPDF + Tesseract | PaddleOCR-VL for table-aware extraction; per-page parallel OCR via Celery |
| Doc-type classification | **Filename keyword** (hardcoded) | LLM classifier on filename + first 200 words; labeled training set on the 18 GeM document types |
| Chunking | 400-char sliding window, 50 overlap | Token-aware (tiktoken) chunking; honor sentence/paragraph boundaries; 512-token chunks with 64 overlap to match `text-embedding-3-large` context |
| Embeddings | **Real OpenAI** `text-embedding-3-small` (1536-dim) when key set; SentenceTransformer fallback otherwise | Air-gap deployments: `BAAI/bge-m3` (1024-dim) on GPU; same embedder for index + query |
| RAG store | Chroma persistent, on-disk | pgvector inside Postgres (single source of truth); HNSW index |
| Persistence (bidder objects) | In-memory dict | Postgres |
| Upload semantics | Synchronous (request blocks until indexing done) | See `architecture.md` §12 — pre-signed PUT, async Celery job, progress endpoint |

---

## 6. Evaluation

**Trigger:** the upload-bidders page calls `POST /api/proxy/api/tenders/{id}/evaluate` after all ZIPs are uploaded.

**Backend handler:** `api/domain/routes/audit.py:evaluate_tender`.

### What runs

1. **Validate state.** Fetch `tender = state.tenders[id]`; build `bidders = list(state.bidders[id].values())`. 404 if no tender, 400 if no bidders.

2. **Call `eval_engine.evaluate(tender, bidders)`** (`api/domain/eval_engine.py`).

3. **Per (criterion × bidder) pair** — i.e. 6 × 4 = 24 calls for our demo:
   - **Retrieve.** `rag.retrieve(tender_id, criterion, bidder_id, k=5)`:
     - Embed `f"{criterion.name} {criterion.description}"` using the *same* embedding function the bidder docs were indexed with (cosine similarity is meaningless across different embedders).
     - Apply soft filter via Chroma `where={"bidder_id": bidder_id, "doc_type": {"$in": DOC_TYPE_WHITELIST[criterion.type]}}` (e.g. financial criteria preferentially pull from `ca_turnover_cert`/`balance_sheet`/`audited_financials`/`itr`). If the filter returns fewer than `k` chunks, retry without it.
     - Top-k results become a `list[Evidence]` with `{bidder_doc_id, page, bbox (deserialized from metadata), quote (chunk text), score (cosine similarity)}`.

   - **Evaluate.** `_llm_evaluate(criterion, bidder, evidence)`:
     - Loads the prompt at `api/domain/prompts/bidder_evaluate.txt`.
     - Builds a JSON user payload: `{criterion_id, bidder_id, criterion: {...full Criterion dump...}, bidder_name, evidence_chunks: [{bidder_doc_id, page, quote, score}]}`.
     - **Model:** `gpt-4o-2024-08-06`, **Structured Outputs** mode, `response_format=VerdictLLM`. The schema constrains the response to `{criterion_id, bidder_id, verdict: "Eligible"|"NotEligible"|"NeedsManualReview", confidence: 0..1, explanation: str, evidence: [{bidder_doc_id, page, quote}]}`.
     - **Stub fallback:** if no `OPENAI_API_KEY`, `_stub_evaluate` returns `NeedsManualReview` for every pair. The stub *never* emits `NotEligible` — that responsibility belongs to the LLM, and the no-silent-disqual guard would fire on a stub-emitted `NotEligible` with empty evidence anyway.

   - **Reattach bbox.** `_verdict_from_llm(raw, retrieved)`: the LLM only sees `(bidder_doc_id, page, quote)`; the engine matches each LLM-cited evidence quote back to the retrieved chunk by `(bidder_doc_id, quote)` exact key, falling through to substring match. The matched chunk's bbox is attached. If no match (LLM hallucinated a quote not in retrieval), an Evidence record is still emitted with `bbox=(0,0,0,0)` and `score=0.0`. The verdict is preserved but flagged for the no-silent-disqual guard.

4. **No-silent-disqualification guard.** `no_silent_disqual.enforce(raw_verdicts)` walks every verdict; for each `NotEligible`, asserts `len(evidence) >= 1`. On violation, the verdict is rewritten to `NeedsManualReview` with explanation `"NotEligible verdict blocked: no evidence found. Manual review required."`. **This invariant is enforced at the application layer, not by the prompt.**

5. **Build `EvaluationMatrix`** = `{tender_id, bidders, criteria, verdicts}`. Persist `state.matrices[tender_id] = matrix`.

6. **Audit log.** `action="tender.evaluate"`, `payload={bidder_count, criteria_count, verdict_count}`.

7. **Response.** Full matrix JSON.

### Status table

| Step | State today | Production gap |
|---|---|---|
| Retrieval | **Real** Chroma cosine, top-k=5, doc-type whitelist filter | pgvector HNSW; query-time reranker (e.g. Cohere Rerank or `bge-reranker-v2-m3`) on top-20 → top-5 |
| Verdict generation | **Real LLM** when key set; stub returns 100% Manual Review otherwise | Same model, plus a self-consistency check (3 samples, majority vote) on borderline confidence |
| No-silent-disqual guard | **Real**, hard-coded invariant with passing tests | Same in prod — this is a policy invariant, not demo scaffolding |
| Bbox reattachment | **Real**, exact + substring fallback | Token-level alignment for OCR'd pages where the chunk text is noisy |
| Concurrency | Sequential per-pair LLM calls | `asyncio.gather` + per-bidder semaphore; OpenAI batch API for bulk eval |
| Caching | None — re-evaluation re-pays the LLM cost | Cache by `(prompt_hash, evidence_hashes, model)` → skip identical pairs; reuse across re-runs |

---

## 7. Matrix Display + Drill-Down

**Frontend:** `tender/[id]/matrix/page.tsx`.

- On mount: `getMatrix(id)` → `GET /api/proxy/api/tenders/{id}/matrix` → backend returns `state.matrices[id]` or 404.
- After the recent rewire, **404 returns `null`** (not mock); UI shows the empty state with "Upload Bidders" CTA.
- The previous behavior (silently substituting `MOCK_MATRIX` for any error) is removed. The mock is now reachable only via the literal id `"mock"` in `getTender`/`getMatrix` — used only by direct dev navigation, not by the demo flow.
- Matrix render: `MatrixGrid` component places bidders on rows, criteria on columns; each cell is colored by verdict (green/amber/red) and shows confidence as a horizontal bar.

**Drill-down (`/bidder/{bidderId}/criterion/{critId}`):**

- Calls `GET /api/proxy/api/bidders/{bidder_id}/criterion/{cid}` (`api/domain/routes/bidders.py:drill_down`).
- Returns the matched verdict + `{doc_id: blob_id}` for the bidder's documents.
- Frontend uses the blob_ids to embed the original PDF via `<iframe src="/api/proxy/files/{blob_id}">` and overlays bbox highlights from `verdict.evidence[i].bbox` on the named page. **This is the "show the original PDF we referred for this" feature** — the bbox lookup chain is real, not faked.

---

## 8. Override + Sign

**Override (officer disagrees with verdict):** `POST /api/audit` with `{tender_id, bidder_id, criterion_id, verdict, justification}`. Currently this only writes an audit row (`action="audit.override"`) — it does **not** mutate the matrix. The override is recorded for the chain of custody but the displayed verdict won't change. Production needs a separate `state.matrices[id].verdicts[k].override_chain` field that the UI surfaces.

**Sign (`POST /api/tenders/{id}/sign`):**

- Verifies a matrix exists.
- Builds a PDF report with the matrix, every verdict, every evidence quote, and the audit chain root hash.
- Calls `pyHanko sign_evaluation(matrix, out_path, chain_root=audit.db)` → embeds a PKCS#7 signature using a self-signed cert in `data/certs/` (demo-grade). Production: NIC-issued Class III DSC.
- Stores the signed PDF as a blob; logs `action="tender.sign"`.
- Returns `{blob_id, ...}` — the frontend offers it as a download.

---

## 9. Data + Audit Page

**Page:** `web/app/data/page.tsx`.

- `listTenders()` → `GET /api/tenders` → real backend list (uses `state.tenders`).
- `listAllAudit()` → `GET /api/audit?limit=200` → real audit rows.
- `verifyAuditChain()` → `GET /api/audit/verify` → returns `{valid, broken_at}` after walking the SHA-256 chain.

This page is fully real today. It's the cleanest proof-point in the demo that nothing is hardcoded — every entry corresponds to an actual `audit.append` call somewhere in the pipeline. **Show this page first** in the demo to establish that there is no precomputed state, then upload tender + bidders and refresh to show new rows appearing.

---

## 10. Hardcoded / Mock Surfaces (Remaining)

| Surface | Location | Trigger | Risk in demo |
|---|---|---|---|
| `MOCK_TENDER`, `MOCK_MATRIX` | `web/lib/mock.ts` | Returned by `getTender("mock")` / `getMatrix("mock")` only | None as long as you never navigate to `/tender/mock/...` |
| `MOCK_BIDDERS`, `MOCK_VERDICTS` | `web/lib/mock.ts` | Same — only via id `"mock"` | None |
| Doc-type classifier | `api/domain/routes/bidders.py:_classify_doc_type` | Filename keyword | Wrong `doc_type` weakens the RAG whitelist filter, but retrieval still works (whitelist is soft) |
| Criteria edit persistence | UI only | When editing fields in the modal | Page refresh loses edits; approvals are persisted |
| Override doesn't mutate matrix | `api/domain/routes/audit.py` POST `/api/audit` | Always | If you demo override, the cell color won't change — only the audit row appears |
| LLM stub when key absent | `extract_stub`, `_stub_evaluate` | When `OPENAI_API_KEY` is not set | All cells become Manual Review; no Pass/Fail spread |

---

## 11. Models + External Services Today

| Capability | Model / library | When called | Cost driver |
|---|---|---|---|
| PDF digital text | PyMuPDF (`fitz`) | Tender + every bidder PDF, on upload | None (local) |
| OCR | Tesseract via `pytesseract` | Pages with < 50 PyMuPDF words | None (local) |
| Section classification | Regex heuristic | Once per tender | None |
| Criterion extraction | OpenAI `gpt-4o-2024-08-06` Structured Outputs | Once per tender upload | ~1k input tokens (eligibility section), ~500 output tokens. ≈ $0.01 per tender. |
| Embeddings (index) | OpenAI `text-embedding-3-small` (1536-dim) | Once per page chunk per bidder | ~$0.02 per 1M tokens. A 4-PDF / 15-page bidder ≈ 4k tokens ≈ $0.0001. |
| Embeddings (query) | Same model, same env var | Once per (criterion, bidder) pair | Trivial — criterion text is short |
| Verdict generation | OpenAI `gpt-4o-2024-08-06` Structured Outputs | Once per (criterion × bidder) | ~1.5k input tokens (criterion + 5 evidence chunks), ~300 output tokens. ≈ $0.02 per cell. 24 cells ≈ $0.50 per evaluation. |
| Quote → bbox | rapidfuzz | After every LLM verdict | None |
| PDF signing | pyHanko + cryptography | Once per "Sign" click | None |
| Audit chain | `hashlib.sha256` + sqlite3 | Every state-changing endpoint | None |

**Total LLM cost per demo tender (full pipeline, 4 bidders, 6 criteria):** ~$0.51 + a few cents for embeddings. Comfortably free-tier.

**Required env vars:** `OPENAI_API_KEY`. Optional: `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_FALLBACK_LOCAL=1`, `LLM_BACKEND=openai|vllm`, `AUDIT_DB`, `BLOB_ROOT`.

---

## 12. Production Path (Summary)

The full async/scale design is in `architecture.md` §12. The deltas that matter most for going from "demo on a laptop" to "deploy at NIC":

1. **Persistence.** Replace the three `app.state` dicts with Postgres tables (`tenders`, `bidders`, `bidder_docs`, `criteria`, `verdicts`, `evidence`, `audit_log`). The audit chain stays in its own table with a hash trigger.

2. **Async ingest.** Pre-signed PUT to MinIO/S3, then enqueue Celery jobs for parse → OCR (per-page parallel) → chunk → embed → persist → criteria-extract (tender) or evaluate (bidder). Browser polls or subscribes to job status via SSE/WebSocket. NIC eMail/SMS Gateway notifications on completion.

3. **Air-gap LLM path.** Swap `LLM_BACKEND=openai` for `LLM_BACKEND=vllm` pointed at a self-hosted Llama-3.1-70B / Qwen-2.5-72B behind an OpenAI-compatible gateway. Embeddings: `BAAI/bge-m3` on the same GPU.

4. **Doc-type classifier.** Replace filename heuristic with a small fine-tuned classifier (DistilBERT or a 1.5B LLM with structured outputs) over the GeM document taxonomy. Cite labeled examples per type.

5. **OCR upgrade.** Tesseract → PaddleOCR-VL for layout-aware extraction (preserves table structure, which matters for CA turnover certificates, audited balance sheets, work-order tables).

6. **Caching.** Memoize `(prompt_hash, evidence_hashes, model)` → verdict so re-evaluation skips already-computed pairs; same for criterion extraction by tender file hash.

7. **Override + representation workflow.** Officer override mutates the verdict row (with audit entry); 72-hour bidder representation window opens via a notification; bidder uploads supplementary docs; auto-re-evaluation against just the affected (criterion × bidder) cells.

8. **Signing chain.** Replace self-signed PKCS#7 cert with NIC-issued Class III DSC + LTV (long-term validation) via OCSP stapling, so signed audit PDFs remain verifiable years after issuance.

9. **Observability.** Per-job structured logs to Loki, Prometheus metrics for queue depth + stage durations, audit log entries for async events (`job.start`, `job.complete`, `job.fail`).

10. **Security.** Bidder PDFs may contain sensitive data (financials, GST/PAN); add at-rest encryption on MinIO, IAM-bounded pre-signed URLs with short TTLs, redaction of PAN/GSTIN in logs.

---

## 13. Demo Run Order

1. `cd tenderaudit && uvicorn api.main:app --reload --port 8001` — confirm `OPENAI_API_KEY` in `.env`.
2. `cd tenderaudit/web && npm run dev` (port 3001).
3. Open `/data` first to show "no tenders, no audit rows" — proof there is no hidden state.
4. Land on `/`, upload a real tender PDF (any of `seed/pdfs/*.pdf`). Wait for criteria extraction (~3-8s).
5. On the criteria page, walk through the LLM-extracted criteria and approve all. Avoid demoing threshold edits unless you also explain that edit persistence is still a production gap.
6. On upload-bidders, drag in the 4 zips from `seed/demo-zips/`. Watch the live progress bar (per-zip upload then "Running evaluation…").
7. Land on the matrix — every cell is now a real LLM verdict against the just-indexed bidder pages. Click any cell → drill-down shows the original PDF page with the bbox highlight from RAG retrieval. Open `/data` again to show the new audit rows.
8. Click "Generate signed audit" → downloads a real PKCS#7-signed PDF with the matrix + chain root.
