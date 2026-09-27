import json

import httpx
import pytest

from app import extract as ex
from app.extract import ExtractionError, parse_json


def test_plain_json():
    assert parse_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    assert parse_json('Here you go:\n```json\n{"a": 2}\n```') == {"a": 2}


def test_json_with_sentence():
    assert parse_json('Result: {"a": 3} done') == {"a": 3}


def test_thinking_block_is_ignored():
    assert parse_json('<think>the total is {wrong}</think>{"a": 4}') == {"a": 4}


def test_garbage_raises():
    with pytest.raises(ExtractionError):
        parse_json("no json here")


def test_qwen_provider_sends_openai_style_request(monkeypatch):
    """The Qwen call must be an OpenAI-compatible chat request with the image as a data URL."""
    seen = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        seen["url"], seen["body"] = url, json
        reply = '{"seller": {"name": "Shri Balaji", "gstin": "27AAPFU0939F1ZV"}, "totals": {"grand_total": "₹372.15"}}'
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    monkeypatch.setattr(ex.httpx, "post", fake_post)
    monkeypatch.setattr(ex.settings, "qwen_base_url", "http://gpu:8001/v1")
    bill = ex.extract(images=[(b"PNGDATA", "image/png")], provider="qwen_local")
    assert seen["url"] == "http://gpu:8001/v1/chat/completions"
    parts = seen["body"]["messages"][0]["content"]
    assert parts[0]["type"] == "image_url" and parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[-1]["text"].startswith("You are reading one Indian medical bill")
    assert bill.seller.name == "Shri Balaji" and bill.totals.grand_total == 372.15


def test_qwen_server_down_gives_clear_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(ex.httpx, "post", boom)
    with pytest.raises(ExtractionError, match="Cannot reach the Qwen server"):
        ex.extract(images=[(b"x", "image/png")], provider="qwen_local")
