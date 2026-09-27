"""Turns images (and PDF pages) into text. Tesseract [Smith 2007] or PaddleOCR [Du et al. 2020]."""
from functools import lru_cache

import cv2
import numpy as np

from .config import settings
from .preprocess import load_image


def to_pages(data: bytes, content_type: str, dpi: int = 300, max_pages: int = 5) -> list[np.ndarray]:
    """Return BGR images, one per page."""
    if content_type == "application/pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        pages = []
        for i in range(min(len(pdf), max_pages)):
            pil = pdf[i].render(scale=dpi / 72).to_pil().convert("RGB")
            pages.append(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
        return pages
    return [load_image(data)]


@lru_cache(maxsize=1)
def _paddle():
    from paddleocr import PaddleOCR          # optional dependency (requirements-paddle.txt)
    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)


def ocr_image(img: np.ndarray) -> str:
    if settings.ocr_engine == "paddle":
        result = _paddle().ocr(img, cls=True) or []
        lines = []
        for page in result:
            # sort boxes top-to-bottom, then left-to-right, so lines read in order
            for box, (text, _conf) in sorted(page or [], key=lambda r: (round(r[0][0][1] / 15), r[0][0][0])):
                lines.append(text)
        return "\n".join(lines)
    import pytesseract
    # psm 6 = "a single uniform block of text", which suits receipts
    return pytesseract.image_to_string(img, lang="eng", config="--psm 6 --oem 1")


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("PNG encode failed")
    return buf.tobytes()
