"""Smoke tests for the PDF loader.

Generates a minimal in-memory PDF (PyMuPDF) so the test runs offline without
a sample fixture. Verifies that:

- ``load_pdf`` parses the synthetic PDF into pages and spans
- ``Document.full_text`` contains the inserted text
- ``find_span`` returns a non-None Span for an exact substring
"""

from __future__ import annotations

import os
import tempfile

import fitz  # PyMuPDF

from api.core.pdf_loader import Document, Span, load_pdf


def _write_synthetic_pdf(text_lines: list[str]) -> str:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    y = 72.0
    for line in text_lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18.0
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


def test_load_pdf_basic():
    path = _write_synthetic_pdf(
        [
            "NOTICE INVITING TENDER",
            "NIT NO 2024/CRPF/123",
            "ELIGIBILITY CRITERIA",
            "Bidder must have minimum average annual turnover of INR 50 lakhs",
            "for the last three financial years.",
        ]
    )
    try:
        document: Document = load_pdf(path)
        assert len(document.pages) == 1
        assert len(document.all_spans) > 0
        text = document.full_text.lower()
        assert "eligibility" in text
        assert "turnover" in text
    finally:
        os.unlink(path)


def test_find_span_exact_match():
    path = _write_synthetic_pdf(
        [
            "ELIGIBILITY CRITERIA",
            "Bidder must have minimum average annual turnover of INR 50 lakhs",
        ]
    )
    try:
        document = load_pdf(path)
        span: Span | None = document.find_span("annual turnover", fuzzy=True)
        assert span is not None
        assert "turnover" in span.text.lower()
    finally:
        os.unlink(path)


def test_find_span_returns_none_for_empty_quote():
    path = _write_synthetic_pdf(["Hello world"])
    try:
        document = load_pdf(path)
        assert document.find_span("", fuzzy=True) is None
        assert document.find_span("   ", fuzzy=True) is None
    finally:
        os.unlink(path)
