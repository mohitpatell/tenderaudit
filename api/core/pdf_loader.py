"""PDF ingestion: digital text via PyMuPDF; OCR fallback for scanned pages.

Loads a PDF into an immutable :class:`Document` of pages and spans. Each span
carries a bbox, text, confidence, line id, and page number — enough to support
quote-to-bbox provenance lookup via :meth:`Document.find_span`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF
from rapidfuzz import fuzz

from .ocr_tesseract import run as ocr_run

OCR_WORD_THRESHOLD = 50
FUZZY_THRESHOLD = 80


@dataclass(frozen=True)
class Span:
    """A single text span (~ word or short phrase) with provenance."""

    text: str
    bbox: tuple[float, float, float, float]
    conf: float
    line_id: int
    page_no: int


@dataclass(frozen=True)
class Page:
    width: float
    height: float
    spans: tuple[Span, ...]
    page_no: int


@dataclass(frozen=True)
class Document:
    """Immutable view of an ingested PDF."""

    pages: tuple[Page, ...] = field(default_factory=tuple)
    source_path: Optional[str] = None

    @property
    def all_spans(self) -> tuple[Span, ...]:
        out: list[Span] = []
        for p in self.pages:
            out.extend(p.spans)
        return tuple(out)

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.all_spans)

    def find_span(self, quote: str, fuzzy: bool = True) -> Optional[Span]:
        """Find the span (or sliding window) whose text best matches ``quote``."""
        if not quote.strip():
            return None
        target = _normalize(quote)
        best: tuple[float, Optional[Span]] = (0.0, None)

        for page in self.pages:
            line_groups: dict[int, list[Span]] = {}
            for s in page.spans:
                line_groups.setdefault(s.line_id, []).append(s)
            for spans in line_groups.values():
                for window_size in range(1, min(len(spans), 40) + 1):
                    for i in range(0, len(spans) - window_size + 1):
                        window = spans[i : i + window_size]
                        text = _normalize(" ".join(s.text for s in window))
                        score = fuzz.partial_ratio(target, text)
                        if score > best[0]:
                            merged = _merge_spans(window)
                            best = (score, merged)
        if not fuzzy:
            return best[1] if best[0] >= 99 else None
        return best[1] if best[0] >= FUZZY_THRESHOLD else None


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _merge_spans(spans: list[Span]) -> Span:
    if len(spans) == 1:
        return spans[0]
    x0 = min(s.bbox[0] for s in spans)
    y0 = min(s.bbox[1] for s in spans)
    x1 = max(s.bbox[2] for s in spans)
    y1 = max(s.bbox[3] for s in spans)
    text = " ".join(s.text for s in spans)
    conf = sum(s.conf for s in spans) / len(spans)
    return Span(
        text=text,
        bbox=(x0, y0, x1, y1),
        conf=conf,
        line_id=spans[0].line_id,
        page_no=spans[0].page_no,
    )


def load_pdf(path: str) -> Document:
    """Load a PDF, returning a :class:`Document` of pages and spans."""
    doc = fitz.open(path)
    pages: list[Page] = []
    try:
        for page_idx, fpage in enumerate(doc):
            spans = _extract_digital(fpage, page_idx)
            if len(spans) < OCR_WORD_THRESHOLD:
                ocr_spans = _ocr_page(fpage, page_idx)
                if len(ocr_spans) > len(spans):
                    spans = ocr_spans
            pages.append(
                Page(
                    width=fpage.rect.width,
                    height=fpage.rect.height,
                    spans=tuple(spans),
                    page_no=page_idx,
                )
            )
    finally:
        doc.close()
    return Document(pages=tuple(pages), source_path=path)


def _extract_digital(fpage: "fitz.Page", page_idx: int) -> list[Span]:
    raw = fpage.get_text("dict")
    spans: list[Span] = []
    line_id = 0
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for s in line.get("spans", []):
                text = (s.get("text") or "").strip()
                if not text:
                    continue
                bbox = tuple(s.get("bbox", (0.0, 0.0, 0.0, 0.0)))
                spans.append(
                    Span(
                        text=text,
                        bbox=bbox,  # type: ignore[arg-type]
                        conf=1.0,
                        line_id=line_id,
                        page_no=page_idx,
                    )
                )
            line_id += 1
    return spans


def _ocr_page(fpage: "fitz.Page", page_idx: int) -> list[Span]:
    try:
        from PIL import Image
        import io

        pix = fpage.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return [
            Span(
                text=s.text,
                bbox=s.bbox,
                conf=s.conf,
                line_id=s.line_id,
                page_no=page_idx,
            )
            for s in ocr_run(img, page_no=page_idx)
        ]
    except RuntimeError:  # pragma: no cover - tesseract missing
        return []
    except Exception:  # pragma: no cover - defensive
        return []
