import cv2
import numpy as np

from app.preprocess import clean_for_ocr, rotate, skew_angle


def text_image():
    img = np.full((900, 1200), 255, np.uint8)
    for i in range(18):
        cv2.putText(img, "PARACETAMOL 650MG TAB   2   65.00", (60, 80 + i * 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
    return img


def test_deskew_reduces_skew():
    tilted = rotate(text_image(), 6)
    inv = cv2.threshold(tilted, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    a = skew_angle(inv)
    fixed = rotate(tilted, a)
    inv2 = cv2.threshold(fixed, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    assert abs(skew_angle(inv2)) < 1.5


def test_clean_returns_binary_image():
    out = clean_for_ocr(cv2.cvtColor(text_image(), cv2.COLOR_GRAY2BGR))
    assert out.ndim == 2 and set(np.unique(out)) <= {0, 255}
