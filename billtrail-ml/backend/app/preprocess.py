"""Image cleaning before OCR (OpenCV): shadow removal, denoising, deskewing, binarising."""
import cv2
import numpy as np


def load_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def remove_shadows(gray: np.ndarray) -> np.ndarray:
    """Estimate the background (paper + shadows) and divide it out."""
    background = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 21)
    return cv2.normalize(255 - cv2.absdiff(gray, background), None, 0, 255, cv2.NORM_MINMAX)


def skew_angle(binary_inv: np.ndarray) -> float:
    """Angle (degrees) of the text block; positive = rotated anticlockwise."""
    coords = np.column_stack(np.where(binary_inv > 0))[:, ::-1].astype(np.float32)   # (x, y)
    if len(coords) < 50:
        return 0.0
    (_, _), (w, h), angle = cv2.minAreaRect(coords)
    if w < h:
        angle = angle - 90
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90
    return float(angle)


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def clean_for_ocr(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if gray.shape[1] < 1500:                                   # small phone photos: upscale for OCR
        scale = 1500 / gray.shape[1]
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = remove_shadows(gray)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    binary_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    angle = skew_angle(binary_inv)
    if 0.3 < abs(angle) < 15:
        gray = rotate(gray, angle)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)


def prepare_for_model(img: np.ndarray, max_side: int = 1600) -> np.ndarray:
    """Lighter cleaning for the vision-language model (Qwen3-VL).

    Unlike clean_for_ocr, we do NOT turn the image into pure black-and-white: VLMs read greyscale
    better, and hard thresholding erases faded thermal-paper text. We remove shadows, straighten,
    and shrink very large photos (fewer image tokens = faster, same readability).
    The SAME function is used when building training data, so the model sees identical input
    during training and in the live system.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = remove_shadows(gray)
    binary_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    angle = skew_angle(binary_inv)
    if 0.3 < abs(angle) < 15:
        gray = rotate(gray, angle)
    h, w = gray.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return gray
