"""Regex-based layout-section classification for Indian government tender PDFs.

Returns a list of ``(label, span_indices)`` tuples covering the full document.
Labels: ``cover_page, eligibility, technical_specs, financial, formats,
annexures, body``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .pdf_loader import Document

SectionLabel = str

SECTION_PATTERNS: list[tuple[SectionLabel, re.Pattern[str]]] = [
    (
        "cover_page",
        re.compile(
            r"\b(NIT\s*NO|TENDER\s+NOTICE|NOTICE\s+INVITING\s+TENDER|REQUEST\s+FOR\s+PROPOSAL|RFP)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "eligibility",
        re.compile(
            r"\b(ELIGIBILITY\s+CRITERIA|ELIGIBILITY|QUALIFYING\s+CRITERIA|"
            r"PRE[-\s]QUALIFICATION|GENERAL\s+CONDITIONS|MINIMUM\s+QUALIFYING)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "technical_specs",
        re.compile(
            r"\b(TECHNICAL\s+SPECIFICATION|SCOPE\s+OF\s+WORK|"
            r"TECHNICAL\s+REQUIREMENTS|SCHEDULE\s+OF\s+REQUIREMENTS)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "financial",
        re.compile(
            r"\b(FINANCIAL\s+BID|PRICE\s+BID|PRICE\s+SCHEDULE|"
            r"BILL\s+OF\s+QUANTIT|BOQ|EARNEST\s+MONEY)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "formats",
        re.compile(
            r"\b(FORMAT|FORM\s+NO|FORM[-\s]?[A-Z0-9]+|UNDERTAKING|DECLARATION)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "annexures",
        re.compile(r"\b(ANNEXURE|APPENDIX|SCHEDULE\s+[IVX]+)\b", re.IGNORECASE),
    ),
]


def classify(document: "Document") -> list[tuple[SectionLabel, list[int]]]:
    """Classify each span into a layout section label.

    Strategy: walk spans in order, switching section label whenever a header
    regex matches in a small look-back window. Spans with no detected header
    are tagged ``body`` (or carry the previously assigned label).
    """
    spans = list(document.all_spans)
    if not spans:
        return []

    labels: list[SectionLabel] = ["body"] * len(spans)
    current: SectionLabel = "body"
    for i in range(len(spans)):
        window_start = max(0, i - 6)
        ctx = " ".join(s.text for s in spans[window_start : i + 1])
        for label, pat in SECTION_PATTERNS:
            if pat.search(ctx):
                current = label
                break
        labels[i] = current

    return _group(labels)


def _group(labels: list[SectionLabel]) -> list[tuple[SectionLabel, list[int]]]:
    out: list[tuple[SectionLabel, list[int]]] = []
    if not labels:
        return out
    current = labels[0]
    indices = [0]
    for i in range(1, len(labels)):
        if labels[i] == current:
            indices.append(i)
        else:
            out.append((current, indices))
            current = labels[i]
            indices = [i]
    out.append((current, indices))
    return out


def eligibility_bbox(document: "Document"):
    """Return the bounding bbox covering eligibility-section spans, or None.

    Tuple ``(page, x0, y0, x1, y1)``. If the eligibility section crosses pages,
    the page of the first eligibility span is used; the bbox is the union of
    eligibility spans on that page.
    """
    sections = classify(document)
    spans = list(document.all_spans)
    elig = [i for label, idxs in sections if label == "eligibility" for i in idxs]
    if not elig:
        return None
    first_page = spans[elig[0]].page_no
    same_page = [spans[i] for i in elig if spans[i].page_no == first_page]
    if not same_page:
        return None
    x0 = min(s.bbox[0] for s in same_page)
    y0 = min(s.bbox[1] for s in same_page)
    x1 = max(s.bbox[2] for s in same_page)
    y1 = max(s.bbox[3] for s in same_page)
    return (first_page, x0, y0, x1, y1)


# Backwards-compat alias used by provenance.py fallback path.
def fallback_section_bbox(document: "Document"):
    """Best-effort fallback bbox: prefer eligibility, otherwise body's first page."""
    eb = eligibility_bbox(document)
    if eb is not None:
        return eb
    spans = list(document.all_spans)
    if not spans:
        return None
    page = spans[0].page_no
    same_page = [s for s in spans if s.page_no == page]
    x0 = min(s.bbox[0] for s in same_page)
    y0 = min(s.bbox[1] for s in same_page)
    x1 = max(s.bbox[2] for s in same_page)
    y1 = max(s.bbox[3] for s in same_page)
    return (page, x0, y0, x1, y1)
