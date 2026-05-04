"""Tender eligibility evaluation engine.

For each (criterion, bidder) pair:

1. Retrieve evidence from the bidder's RAG index.
2. Ask the LLM for a verdict (or use a deterministic stub if no API key).
3. Post-populate Evidence.bbox from the retrieved chunk's source span.
4. Run the no-silent-disqualification guard over the entire verdict list.

The guard is a HARD invariant: any code path returning a Verdict that bypasses
:func:`api.domain.no_silent_disqual.enforce` is a bug.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from ..core.llm_client import LLMClient
from . import no_silent_disqual, rag
from .schemas import (
    Bidder,
    Criterion,
    EvaluationMatrix,
    Evidence,
    EvidenceLLM,
    Tender,
    Verdict,
    VerdictLLM,
)

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "bidder_evaluate.txt"


# Type alias for the retrieval function so tests can monkeypatch it cleanly.
RetrieveFn = Callable[[str, Criterion, str, int], list[Evidence]]
EvaluateFn = Callable[[Criterion, Bidder, list[Evidence]], VerdictLLM]


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_evidence_chunks(evidence: list[Evidence]) -> str:
    """Render evidence as a JSON array suitable for the LLM prompt."""
    return json.dumps(
        [
            {
                "bidder_doc_id": e.bidder_doc_id,
                "page": e.page,
                "quote": e.quote,
                "score": round(e.score, 4),
            }
            for e in evidence
        ],
        ensure_ascii=False,
    )


def _llm_evaluate(
    criterion: Criterion,
    bidder: Bidder,
    evidence: list[Evidence],
    *,
    client: Optional[LLMClient] = None,
) -> VerdictLLM:
    llm = client or LLMClient()
    prompt = _load_prompt()
    user_payload = json.dumps(
        {
            "criterion_id": criterion.id,
            "bidder_id": bidder.id,
            "criterion": criterion.model_dump(),
            "bidder_name": bidder.name,
            "evidence_chunks": json.loads(_format_evidence_chunks(evidence)),
        },
        ensure_ascii=False,
    )
    return llm.parse(system=prompt, user=user_payload, response_format=VerdictLLM)


def _stub_evaluate(
    criterion: Criterion,
    bidder: Bidder,
    evidence: list[Evidence],
) -> VerdictLLM:
    """Deterministic offline stub: NeedsManualReview when no evidence, otherwise
    Eligible at low confidence with the top evidence quote echoed back.

    NEVER emits NotEligible — that's the LLM's job. The stub exists only so
    tests / no-key smoke runs can still exercise the pipeline.
    """
    if not evidence:
        return VerdictLLM(
            criterion_id=criterion.id,
            bidder_id=bidder.id,
            verdict="NeedsManualReview",
            confidence=0.5,
            explanation="No evidence retrieved; manual review required.",
            evidence=[],
        )
    top = evidence[0]
    return VerdictLLM(
        criterion_id=criterion.id,
        bidder_id=bidder.id,
        verdict="NeedsManualReview",
        confidence=0.6,
        explanation=(
            f"Stub evaluator (no OPENAI_API_KEY). Top evidence quote: "
            f"\"{top.quote[:120]}\""
        ),
        evidence=[
            EvidenceLLM(bidder_doc_id=top.bidder_doc_id, page=top.page, quote=top.quote)
        ],
    )


def _verdict_from_llm(
    raw: VerdictLLM,
    retrieved: list[Evidence],
) -> Verdict:
    """Build a full Verdict by attaching bbox/score from the retrieved chunks.

    Match LLM-returned evidence to retrieved chunks by ``(bidder_doc_id, quote)``
    using a substring fallback. If no match is found we still emit an Evidence
    record using the LLM's reported page (bbox=0); the guard treats it as
    'has evidence'.
    """
    by_key: dict[tuple[str, str], Evidence] = {
        (e.bidder_doc_id, e.quote): e for e in retrieved
    }
    full_evidence: list[Evidence] = []
    for ev in raw.evidence:
        match = by_key.get((ev.bidder_doc_id, ev.quote))
        if match is None:
            for r in retrieved:
                if r.bidder_doc_id == ev.bidder_doc_id and (
                    ev.quote in r.quote or r.quote in ev.quote
                ):
                    match = r
                    break
        if match is not None:
            full_evidence.append(
                match.model_copy(update={"quote": ev.quote})
            )
        else:
            from .schemas import BBox

            full_evidence.append(
                Evidence(
                    bidder_doc_id=ev.bidder_doc_id,
                    page=ev.page,
                    bbox=BBox(page=ev.page, x0=0, y0=0, x1=0, y1=0),
                    quote=ev.quote,
                    score=0.0,
                )
            )
    return Verdict(
        criterion_id=raw.criterion_id,
        bidder_id=raw.bidder_id,
        verdict=raw.verdict,
        confidence=raw.confidence,
        explanation=raw.explanation,
        evidence=full_evidence,
    )


def evaluate(
    tender: Tender,
    bidders: list[Bidder],
    *,
    retrieve: Optional[RetrieveFn] = None,
    evaluate_pair: Optional[EvaluateFn] = None,
    k: int = 5,
) -> EvaluationMatrix:
    """Build an EvaluationMatrix for ``tender`` x ``bidders``.

    The ``retrieve`` and ``evaluate_pair`` callables are injectable for tests.
    By default they are bound to the live RAG index and LLM client (or to a
    deterministic stub when no ``OPENAI_API_KEY`` is configured).
    """
    retrieve_fn: RetrieveFn = retrieve or rag.retrieve
    use_stub = evaluate_pair is None and not os.getenv("OPENAI_API_KEY")
    evaluate_fn: EvaluateFn = evaluate_pair or (
        _stub_evaluate if use_stub else _llm_evaluate
    )

    raw_verdicts: list[Verdict] = []
    for criterion in tender.criteria:
        for bidder in bidders:
            try:
                evidence = retrieve_fn(tender.id, criterion, bidder.id, k)
            except Exception as e:  # pragma: no cover - defensive
                log.warning("retrieve failed for %s/%s: %s", criterion.id, bidder.id, e)
                evidence = []
            try:
                raw = evaluate_fn(criterion, bidder, evidence)
            except Exception as e:  # pragma: no cover - LLM transient
                log.warning("LLM evaluate failed for %s/%s: %s", criterion.id, bidder.id, e)
                raw = VerdictLLM(
                    criterion_id=criterion.id,
                    bidder_id=bidder.id,
                    verdict="NeedsManualReview",
                    confidence=0.0,
                    explanation=f"Evaluator error: {type(e).__name__}",
                    evidence=[],
                )
            raw_verdicts.append(_verdict_from_llm(raw, evidence))

    # HARD guard: every NotEligible MUST be backed by evidence.
    verdicts = no_silent_disqual.enforce(raw_verdicts)

    return EvaluationMatrix(
        tender_id=tender.id,
        bidders=bidders,
        criteria=tender.criteria,
        verdicts=verdicts,
    )
