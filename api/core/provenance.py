"""Quote -> bbox provenance lookup with fuzzy fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ..domain.schemas import BBox
from . import sections as sections_mod

if TYPE_CHECKING:  # pragma: no cover
    from .pdf_loader import Document

log = logging.getLogger(__name__)


def quote_to_bbox(document: "Document", quote: str) -> Optional[BBox]:
    """Resolve a verbatim/quoted phrase to a :class:`BBox`.

    Falls back to the eligibility section bbox if no fuzzy match meets the
    rapidfuzz threshold. Logs a warning on fallback. Returns None for empty
    documents with no spans.
    """
    span = document.find_span(quote, fuzzy=True)
    if span is not None:
        return BBox(
            page=span.page_no,
            x0=span.bbox[0],
            y0=span.bbox[1],
            x1=span.bbox[2],
            y1=span.bbox[3],
        )

    fallback = sections_mod.fallback_section_bbox(document)
    if fallback is None:
        log.warning("quote_to_bbox: no fuzzy match and no section bbox: %r", quote[:80])
        return None

    log.warning("quote_to_bbox: fuzzy miss for %r; using eligibility/body bbox", quote[:80])
    page, x0, y0, x1, y1 = fallback
    return BBox(page=page, x0=x0, y0=y0, x1=x1, y1=y1)
