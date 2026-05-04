"""RAG: index 4 chunks, retrieve top-k, assert ranking is correct.

Uses a deterministic in-process embedding function (token Jaccard mapped to a
fixed-dimension dense vector) so the test runs offline without OpenAI.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from typing import Any

import pytest

from api.domain import rag
from api.domain.schemas import BBox, Bidder, BidderDoc, Criterion


VOCAB = [
    "turnover", "lakhs", "iso", "9001", "blacklist", "msme", "gst",
    "audited", "balance", "experience", "completion", "certificate",
]


class _FakeEmbedFn:
    """Deterministic embedder: bag-of-vocab over a fixed vocabulary.

    Same surface as chromadb embedding functions: callable taking a list of
    strings and returning a list of float vectors.
    """

    def __init__(self) -> None:
        self.dim = len(VOCAB)

    def __call__(self, input):  # chromadb v0.5 calls with positional/list arg
        if isinstance(input, str):
            input = [input]
        out: list[list[float]] = []
        for text in input:
            t = (text or "").lower()
            vec = [1.0 if word in t else 0.0 for word in VOCAB]
            # Add a small constant so chroma doesn't choke on all-zero vecs.
            vec.append(0.01)
            out.append(vec)
        return out

    def name(self) -> str:  # chromadb >=0.5 expects a name() classmethod-ish hook
        return "fake-bow"


@pytest.fixture
def isolated_chroma(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="chroma-test-")
    monkeypatch.setenv("CHROMA_DIR", tmp)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RAG_FALLBACK_LOCAL", raising=False)
    rag._reset_client_for_tests()
    monkeypatch.setattr(rag, "_embedding_fn", lambda: _FakeEmbedFn())
    yield tmp
    rag._reset_client_for_tests()
    shutil.rmtree(tmp, ignore_errors=True)


def _bidder() -> Bidder:
    return Bidder(
        id="B1",
        tender_id="T1",
        name="Acme Pvt Ltd",
        documents=[
            BidderDoc(id="d1", bidder_id="B1", filename="ca.pdf",
                      doc_type="ca_turnover_cert", blob_id="b1"),
            BidderDoc(id="d2", bidder_id="B1", filename="iso.pdf",
                      doc_type="iso_cert", blob_id="b2"),
        ],
    )


def _bbox(page: int) -> BBox:
    return BBox(page=page, x0=10, y0=10, x1=200, y1=30)


def test_index_and_retrieve_ranks_correctly(isolated_chroma):
    tender_id = f"t-{uuid.uuid4().hex[:6]}"
    bidder = _bidder()

    pages_by_doc_id = {
        "d1": [
            (0, "audited turnover lakhs balance sheet", _bbox(0)),
            (1, "experience completion certificate", _bbox(1)),
        ],
        "d2": [
            (0, "iso 9001 certificate", _bbox(0)),
            (1, "msme gst", _bbox(1)),
        ],
    }
    n = rag.index_bidder_docs(tender_id, bidder, pages_by_doc_id)
    assert n >= 4

    # Financial criterion: should rank turnover/balance chunk on top.
    fin = Criterion(
        id="C1",
        name="Min annual turnover",
        type="financial",
        description="audited turnover lakhs",
        threshold_operator=">=",
        source_clause="minimum turnover",
        required_documents=["balance sheet"],
    )
    res = rag.retrieve(tender_id, fin, "B1", k=4)
    assert len(res) >= 1
    top = res[0]
    assert "turnover" in top.quote.lower() or "balance" in top.quote.lower()
    # Scope check: financial whitelist filtered to ca/balance docs.
    assert top.bidder_doc_id == "d1"

    # Technical criterion: ISO cert should win.
    tech = Criterion(
        id="C2",
        name="ISO 9001",
        type="technical",
        description="iso 9001 certificate",
        threshold_operator="exists",
        source_clause="must possess ISO 9001",
        required_documents=["ISO 9001 Certificate"],
    )
    res2 = rag.retrieve(tender_id, tech, "B1", k=4)
    assert len(res2) >= 1
    assert "iso" in res2[0].quote.lower()
    assert res2[0].bidder_doc_id == "d2"


def test_retrieve_falls_back_when_whitelist_empty(isolated_chroma):
    """If the doc_type whitelist matches nothing, retrieval must still return."""
    tender_id = f"t-{uuid.uuid4().hex[:6]}"
    bidder = Bidder(
        id="B9",
        tender_id="T9",
        name="Other",
        documents=[
            BidderDoc(id="d9", bidder_id="B9", filename="misc.pdf",
                      doc_type="other", blob_id="b9"),
        ],
    )
    rag.index_bidder_docs(
        tender_id,
        bidder,
        {"d9": [(0, "audited turnover lakhs", _bbox(0))]},
    )
    fin = Criterion(
        id="C1",
        name="Turnover",
        type="financial",
        description="audited turnover lakhs",
        threshold_operator=">=",
        source_clause="turnover",
        required_documents=[],
    )
    res = rag.retrieve(tender_id, fin, "B9", k=3)
    assert len(res) >= 1
    assert res[0].bidder_doc_id == "d9"
