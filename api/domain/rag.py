"""RAG over bidder documents using chromadb (in-process, persistent).

One collection per tender (``bidders_{tender_id}``). Each chunk:

- text: 300-500 char sliding window with 50-char overlap
- metadata: ``bidder_id, bidder_doc_id, page, bbox_serialized, doc_type``

Embeddings:

- Default: OpenAI ``text-embedding-3-small``
- Fallback (gated by env ``RAG_FALLBACK_LOCAL=1``):
  ``SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2')``
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .schemas import BBox, Bidder, BidderDoc, Criterion, Evidence

log = logging.getLogger(__name__)

CHROMA_DIR_DEFAULT = "./data/chroma"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

# Doc-type whitelists by criterion type. Used as a soft retrieval filter.
DOC_TYPE_WHITELIST: dict[str, list[str]] = {
    "financial": ["ca_turnover_cert", "balance_sheet", "audited_financials", "itr"],
    "technical": [
        "experience_cert",
        "work_order",
        "completion_cert",
        "iso_cert",
        "oem_letter",
        "aerb_cert",
    ],
    "compliance": [
        "blacklist_undertaking",
        "epfo_cert",
        "esic_cert",
        "gst_cert",
        "msme_cert",
        "integrity_pact",
    ],
    "documentation": [],
}


@dataclass(frozen=True)
class _Chunk:
    text: str
    bidder_id: str
    bidder_doc_id: str
    page: int
    bbox: BBox
    doc_type: Optional[str]


# ---------------------------------------------------------------------------
# Chroma client + embedding function helpers
# ---------------------------------------------------------------------------


_CLIENT: Any = None


def _get_client() -> Any:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    import chromadb  # local import keeps test collection time low

    persist_dir = os.getenv("CHROMA_DIR", CHROMA_DIR_DEFAULT)
    os.makedirs(persist_dir, exist_ok=True)
    _CLIENT = chromadb.PersistentClient(path=persist_dir)
    return _CLIENT


def _reset_client_for_tests() -> None:
    """Reset the in-process chroma client (test helper)."""
    global _CLIENT
    _CLIENT = None


def _embedding_fn() -> Any:
    """Resolve the embedding function based on env vars.

    - If ``OPENAI_API_KEY`` is set, use OpenAI ``text-embedding-3-small``.
    - Else if ``RAG_FALLBACK_LOCAL=1``, use SentenceTransformer all-MiniLM-L6-v2.
    - Else return None — chroma will use its default (built-in) embedder.
    """
    try:
        from chromadb.utils import embedding_functions
    except ImportError:  # pragma: no cover
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            )
        except Exception:  # pragma: no cover - constructor failure
            log.warning("OpenAIEmbeddingFunction init failed; falling through")

    if os.getenv("RAG_FALLBACK_LOCAL") == "1":
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
            )
        except Exception:  # pragma: no cover
            log.warning("SentenceTransformer fallback failed; using chroma default")

    return None  # chroma default


def _collection(tender_id: str) -> Any:
    name = f"bidders_{tender_id}"
    client = _get_client()
    ef = _embedding_fn()
    if ef is None:
        return client.get_or_create_collection(name=name)
    return client.get_or_create_collection(name=name, embedding_function=ef)


# ---------------------------------------------------------------------------
# Chunking + indexing
# ---------------------------------------------------------------------------


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window chunks at character boundaries (with overlap)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _serialize_bbox(b: BBox) -> str:
    return json.dumps({"page": b.page, "x0": b.x0, "y0": b.y0, "x1": b.x1, "y1": b.y1})


def _deserialize_bbox(s: str) -> BBox:
    raw = json.loads(s)
    return BBox(**raw)


def index_bidder_docs(
    tender_id: str,
    bidder: Bidder,
    pages_by_doc_id: dict[str, list[tuple[int, str, BBox]]],
) -> int:
    """Index pre-extracted page text for one bidder.

    ``pages_by_doc_id[doc_id]`` is a list of ``(page_no, page_text, page_bbox)``
    tuples — typically the union bbox of all spans on that page. We chunk the
    page text and attach the page bbox as a coarse provenance hook (the eval
    engine post-populates a finer bbox via ``core.provenance.quote_to_bbox``).

    Returns the number of chunks written.
    """
    coll = _collection(tender_id)
    docs_by_id: dict[str, BidderDoc] = {d.id: d for d in bidder.documents}
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for doc_id, page_items in pages_by_doc_id.items():
        bd = docs_by_id.get(doc_id)
        doc_type = bd.doc_type if bd else None
        for page_no, page_text, page_bbox in page_items:
            for chunk in _chunk_text(page_text):
                ids.append(uuid.uuid4().hex)
                documents.append(chunk)
                metadatas.append(
                    {
                        "bidder_id": bidder.id,
                        "bidder_doc_id": doc_id,
                        "page": int(page_no),
                        "bbox_serialized": _serialize_bbox(page_bbox),
                        "doc_type": doc_type or "",
                    }
                )
    if not ids:
        return 0
    coll.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def _build_query(criterion: Criterion) -> str:
    parts: list[str] = [criterion.name, criterion.description]
    if criterion.required_documents:
        parts.extend(criterion.required_documents)
    return " | ".join(p for p in parts if p)


def retrieve(
    tender_id: str,
    criterion: Criterion,
    bidder_id: str,
    k: int = 5,
) -> list[Evidence]:
    """Retrieve top-k evidence chunks for a (criterion, bidder) pair.

    Filters by ``bidder_id``. Tries doc_type whitelist first (for financial /
    technical / compliance criteria); falls back to no doc_type filter if zero
    results.
    """
    coll = _collection(tender_id)
    query = _build_query(criterion)
    whitelist = DOC_TYPE_WHITELIST.get(criterion.type, [])

    where_strict: dict[str, Any] = {"bidder_id": bidder_id}
    if whitelist:
        where_strict = {
            "$and": [
                {"bidder_id": bidder_id},
                {"doc_type": {"$in": whitelist}},
            ]
        }

    res = _query(coll, query, k, where_strict)
    if not res or not res.get("ids") or not res["ids"][0]:
        res = _query(coll, query, k, {"bidder_id": bidder_id})

    return _to_evidence(res)


def _query(coll: Any, query: str, k: int, where: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        return coll.query(query_texts=[query], n_results=k, where=where)
    except Exception as e:  # pragma: no cover - chroma can throw on empty coll
        log.warning("chroma query failed (where=%s): %s", where, e)
        return None


def _to_evidence(res: Optional[dict[str, Any]]) -> list[Evidence]:
    if not res or not res.get("ids") or not res["ids"][0]:
        return []
    out: list[Evidence] = []
    ids = res["ids"][0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0] if res.get("distances") else [0.0] * len(ids)
    for i, _hit_id in enumerate(ids):
        text = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else 0.0
        try:
            bbox = _deserialize_bbox(meta.get("bbox_serialized", ""))
        except Exception:
            bbox = BBox(page=int(meta.get("page", 0)), x0=0, y0=0, x1=0, y1=0)
        # similarity ~ 1 - distance (chroma cosine distance is in [0, 2])
        score = max(0.0, 1.0 - float(dist))
        out.append(
            Evidence(
                bidder_doc_id=str(meta.get("bidder_doc_id", "")),
                page=int(meta.get("page", 0)),
                bbox=bbox,
                quote=text,
                score=score,
            )
        )
    return out
