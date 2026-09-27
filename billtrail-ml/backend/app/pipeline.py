"""Read one bill file end to end: pages -> cleaning -> (OCR) -> model -> StandardBill.

Used by the worker (live system), scripts/predict_folder.py (experiments) and
training/build_dataset.py (same image preparation for training data).
No database here: this runs on the GPU machine.
"""
import time
from dataclasses import dataclass

from .config import settings
from .extract import extract, model_name
from .ocr import encode_png, ocr_image, to_pages
from .preprocess import clean_for_ocr, prepare_for_model
from .schemas import StandardBill


@dataclass
class ReadResult:
    bill: StandardBill
    mode: str
    model: str
    ocr_text: str | None
    seconds: float


def model_images(data: bytes, content_type: str) -> list[tuple[bytes, str]]:
    """The exact images the vision model sees (also used to build training data)."""
    pages = to_pages(data, content_type, max_pages=settings.max_pages)
    return [(encode_png(prepare_for_model(p, settings.max_image_side)), "image/png") for p in pages]


def read_bill(data: bytes, content_type: str, provider: str | None = None, mode: str | None = None) -> ReadResult:
    provider = provider or settings.llm_provider
    mode = mode or settings.extract_mode
    t0 = time.perf_counter()
    ocr_text = None
    if mode == "ocr_text":
        pages = to_pages(data, content_type, max_pages=settings.max_pages)
        ocr_text = "\n\n--- next page ---\n\n".join(ocr_image(clean_for_ocr(p)) for p in pages)
        bill = extract(ocr_text=ocr_text, provider=provider)
    else:
        bill = extract(images=model_images(data, content_type), provider=provider)
    return ReadResult(bill=bill, mode=mode, model=model_name(provider), ocr_text=ocr_text,
                      seconds=round(time.perf_counter() - t0, 2))
