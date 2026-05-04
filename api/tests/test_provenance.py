"""Provenance: quote -> bbox lookup with section-bbox fallback."""

from __future__ import annotations

import os
import tempfile

import fitz  # PyMuPDF

from api.core import provenance
from api.core.pdf_loader import load_pdf
from api.domain.schemas import BBox


def _write_pdf(lines: list[str]) -> str:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 72.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18.0
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


def test_quote_to_bbox_exact_hit():
    path = _write_pdf(
        [
            "ELIGIBILITY CRITERIA",
            "Bidder must have minimum annual turnover of INR 50 lakhs.",
        ]
    )
    try:
        document = load_pdf(path)
        bbox = provenance.quote_to_bbox(document, "minimum annual turnover of INR 50 lakhs")
        assert isinstance(bbox, BBox)
        assert bbox.page == 0
        assert bbox.x1 > bbox.x0 and bbox.y1 > bbox.y0
    finally:
        os.unlink(path)


def test_quote_to_bbox_fuzzy_miss_uses_section_fallback():
    path = _write_pdf(
        [
            "ELIGIBILITY CRITERIA",
            "Bidder shall not be blacklisted by any Central / State Government agency.",
        ]
    )
    try:
        document = load_pdf(path)
        # quote that doesn't appear; fuzzy will miss and we fall back to section bbox
        bbox = provenance.quote_to_bbox(
            document,
            "ZZZZZZZZZZ this quote is not in the document QQQQQQQ XYZ123ABC",
        )
        assert isinstance(bbox, BBox)
        assert bbox.page == 0
    finally:
        os.unlink(path)
