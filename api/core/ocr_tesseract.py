"""Tesseract OCR fallback with deskew preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PIL.Image import Image as PILImage


@dataclass(frozen=True)
class OcrSpan:
    text: str
    bbox: tuple[float, float, float, float]
    conf: float
    line_id: int
    page_no: int


def run(page_image: "PILImage", page_no: int = 0) -> list[OcrSpan]:
    """OCR a single page image and return a list of word-level spans.

    Raises
    ------
    RuntimeError
        If the tesseract binary is not installed/found on PATH.
    """
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("install pytesseract: pip install pytesseract") from e

    try:
        deskewed = _deskew(page_image)
    except Exception:  # pragma: no cover
        deskewed = page_image

    try:
        data = pytesseract.image_to_data(deskewed, output_type=Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError("install tesseract-ocr: brew install tesseract") from e

    spans: list[OcrSpan] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        x = float(data["left"][i])
        y = float(data["top"][i])
        w = float(data["width"][i])
        h = float(data["height"][i])
        line_id = int(data.get("line_num", [0] * n)[i])
        spans.append(
            OcrSpan(
                text=text,
                bbox=(x, y, x + w, y + h),
                conf=conf / 100.0,
                line_id=line_id,
                page_no=page_no,
            )
        )
    return spans


def _deskew(image: "PILImage") -> "PILImage":
    """Apply a Hough-transform based deskew. Best-effort; returns original on error."""
    import numpy as np
    import cv2
    from PIL import Image

    arr = np.array(image.convert("L"))
    edges = cv2.Canny(arr, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return image
    angles = []
    for rho_theta in lines[:50]:
        _, theta = rho_theta[0]
        angle = (theta * 180.0 / np.pi) - 90.0
        if -30.0 < angle < 30.0:
            angles.append(angle)
    if not angles:
        return image
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return image
    h, w = arr.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        np.array(image), matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)
    )
    return Image.fromarray(rotated)
