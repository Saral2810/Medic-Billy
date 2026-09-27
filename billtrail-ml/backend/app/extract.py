"""The model step: reads a bill and fills the standard format (app/schemas.py).

Providers
  qwen_local : our fine-tuned Qwen3-VL, served on our GPU by vLLM or Ollama.
               Both expose an OpenAI-compatible /v1/chat/completions endpoint, so we call it with httpx.
  claude     : Anthropic Claude. Used only as the "teacher" that pre-fills training labels and as a
               baseline in the paper. Needs ANTHROPIC_API_KEY and patient consent (data leaves our machine).

Inputs
  images   : list of (bytes, media_type) -> the model reads the picture (extract_mode = vision)
  ocr_text : text from Tesseract/PaddleOCR -> the model only structures text (extract_mode = ocr_text)

INSTRUCTIONS is shared with training/build_dataset.py, so the fine-tuned model is trained on
exactly the prompt it receives in production.
"""
import base64
import json
import re

import httpx

from .config import settings
from .schemas import StandardBill

SCHEMA = """{
 "bill_type": "pharmacy" | "lab" | "hospital",
 "seller": {"name": str, "address": str, "gstin": str, "drug_licence_no": str, "phone": str},
 "invoice": {"number": str, "date": "YYYY-MM-DD"},
 "patient_name": str, "doctor_name": str,
 "items": [{"name": str, "hsn": str, "batch": str, "expiry": "YYYY-MM", "qty": num, "mrp": num, "rate": num, "discount": num, "amount": num}],
 "tax": {"gst_rate": num, "cgst": num, "sgst": num, "igst": num},
 "totals": {"subtotal": num, "discount": num, "taxable_value": num, "total_tax": num, "grand_total": num},
 "confidence": num between 0 and 1,
 "unreadable": [field paths you could not read, like "seller.gstin"]
}"""

INSTRUCTIONS = f"""You are reading one Indian medical bill (pharmacy, lab or hospital). Read it line by line and fill the standard format below.
Rules:
- Copy values exactly as printed. Do NOT correct, guess or invent anything. If a value is missing, faded or unreadable, use null and add its path to "unreadable".
- Dates: invoice date as YYYY-MM-DD (Indian bills print DD/MM/YYYY). Expiry as YYYY-MM (e.g. 08/2028 -> 2028-08).
- Money and quantities as plain numbers, no rupee symbol or commas.
- GSTIN in capitals with no spaces, exactly as printed even if it looks wrong.
- One object in "items" per medicine or service line. "amount" is the line total printed on the bill.
- "confidence" is how sure you are that the whole reading is correct.
Reply with only this JSON, no other text:
{SCHEMA}"""


class ExtractionError(Exception):
    pass


def parse_json(text: str) -> dict:
    """Tolerant parse: whole reply, else a ```json fence, else first '{' to last '}'."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()   # "thinking" models
    for candidate in (text, *(m.group(1) for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.S))):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ExtractionError("Model reply was not valid JSON")


def _prompt(ocr_text: str | None) -> str:
    if ocr_text is not None:
        return INSTRUCTIONS + "\n\nBILL TEXT (from OCR, may contain errors):\n" + ocr_text[:30000]
    return INSTRUCTIONS + "\n\nThe bill is in the attached image(s)."


def _to_bill(reply: str) -> StandardBill:
    data = parse_json(reply)
    if not isinstance(data, dict):
        raise ExtractionError("Model reply was not a JSON object")
    return StandardBill.model_validate(data)


def _qwen(images: list[tuple[bytes, str]], ocr_text: str | None) -> str:
    content = [{"type": "image_url", "image_url": {"url": f"data:{mt};base64,{base64.b64encode(b).decode()}"}}
               for b, mt in images]
    content.append({"type": "text", "text": _prompt(ocr_text)})
    body = {"model": settings.qwen_model, "temperature": 0, "max_tokens": settings.llm_max_tokens,
            "messages": [{"role": "user", "content": content}]}
    try:
        r = httpx.post(f"{settings.qwen_base_url.rstrip('/')}/chat/completions", json=body, timeout=300,
                       headers={"Authorization": f"Bearer {settings.qwen_api_key}"})
    except httpx.HTTPError as e:
        raise ExtractionError(f"Cannot reach the Qwen server at {settings.qwen_base_url}: {e}")
    if r.status_code != 200:
        raise ExtractionError(f"Qwen server error {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"] or ""


def _claude(images: list[tuple[bytes, str]], ocr_text: str | None) -> str:
    import anthropic
    if not settings.anthropic_api_key:
        raise ExtractionError("ANTHROPIC_API_KEY is not set")
    content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(b).decode()}}
               for b, mt in images]
    content.append({"type": "text", "text": _prompt(ocr_text)})
    resp = anthropic.Anthropic(api_key=settings.anthropic_api_key).messages.create(
        model=settings.claude_model, max_tokens=settings.llm_max_tokens, messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in resp.content if b.type == "text")


def model_name(provider: str | None = None) -> str:
    provider = provider or settings.llm_provider
    return settings.qwen_model if provider == "qwen_local" else settings.claude_model


def extract(images: list[tuple[bytes, str]] | None = None, ocr_text: str | None = None,
            provider: str | None = None) -> StandardBill:
    provider = provider or settings.llm_provider
    images = [] if ocr_text is not None else (images or [])
    if not images and ocr_text is None:
        raise ExtractionError("Nothing to read")
    if provider == "qwen_local":
        return _to_bill(_qwen(images, ocr_text))
    if provider == "claude":
        return _to_bill(_claude(images, ocr_text))
    raise ExtractionError(f"Unknown LLM_PROVIDER '{provider}'")
