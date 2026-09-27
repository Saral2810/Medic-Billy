import cv2
import numpy as np

from app import pipeline
from app.schemas import StandardBill


def bill_png():
    img = np.full((1400, 1000, 3), 255, np.uint8)
    for i in range(12):
        cv2.putText(img, "PARACETAMOL 650MG  2  65.00", (40, 80 + i * 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return cv2.imencode(".png", img)[1].tobytes()


def test_model_images_are_prepared_and_shrunk(monkeypatch):
    monkeypatch.setattr(pipeline.settings, "max_image_side", 800)
    imgs = pipeline.model_images(bill_png(), "image/png")
    assert len(imgs) == 1 and imgs[0][1] == "image/png"
    decoded = cv2.imdecode(np.frombuffer(imgs[0][0], np.uint8), cv2.IMREAD_UNCHANGED)
    assert max(decoded.shape[:2]) == 800 and decoded.ndim == 2       # greyscale, not pure black/white


def test_read_bill_vision_mode_sends_images(monkeypatch):
    seen = {}

    def fake_extract(images=None, ocr_text=None, provider=None):
        seen.update(images=images, ocr_text=ocr_text, provider=provider)
        return StandardBill(confidence=0.9)

    monkeypatch.setattr(pipeline, "extract", fake_extract)
    res = pipeline.read_bill(bill_png(), "image/png", provider="qwen_local", mode="vision")
    assert seen["images"] and seen["ocr_text"] is None and res.mode == "vision"


def test_read_bill_ocr_mode_sends_text(monkeypatch):
    seen = {}
    monkeypatch.setattr(pipeline, "extract", lambda images=None, ocr_text=None, provider=None: seen.update(t=ocr_text) or StandardBill())
    pipeline.read_bill(bill_png(), "image/png", provider="claude", mode="ocr_text")
    assert "PARACETAMOL" in seen["t"].upper()
