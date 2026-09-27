"""Run one reading setup over a folder of bills and save what the model produced (for the paper).

Calls the pipeline directly (no website, no database), so each setup can be run on the same images.
Examples:
  # our fine-tuned model (served by vLLM on QWEN_BASE_URL)
  python -m scripts.predict_folder --images data/synthetic/images --out data/pred/qwen_ft --provider qwen_local --model billtrail-qwen3vl
  # the same Qwen before fine-tuning (serve the base model under another name)
  python -m scripts.predict_folder --images data/synthetic/images --out data/pred/qwen_base --provider qwen_local --model qwen3vl-base
  # baselines
  python -m scripts.predict_folder --images data/synthetic/images --out data/pred/claude --provider claude
  python -m scripts.predict_folder --images data/synthetic/images --out data/pred/ocr_claude --provider claude --mode ocr_text
Then score:  python -m eval.evaluate --truth data/synthetic/truth --pred data/pred/qwen_ft --manifest data/synthetic/manifest.json
"""
import argparse
import csv
import json
import mimetypes
from pathlib import Path

from app.config import settings
from app.pipeline import read_bill


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", choices=["qwen_local", "claude"], default=settings.llm_provider)
    ap.add_argument("--mode", choices=["vision", "ocr_text"], default="vision")
    ap.add_argument("--model", help="served model name (overrides QWEN_MODEL / CLAUDE_MODEL)")
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()
    if a.model:
        if a.provider == "qwen_local":
            settings.qwen_model = a.model
        else:
            settings.claude_model = a.model
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted(Path(a.images).glob("*")):
        ctype = mimetypes.guess_type(p.name)[0]
        if ctype not in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
            continue
        target = out / f"{p.stem}.json"
        if a.skip_existing and target.exists():
            continue
        try:
            res = read_bill(p.read_bytes(), ctype, provider=a.provider, mode=a.mode)
            target.write_text(json.dumps(res.bill.model_dump(), indent=2))
            rows.append({"id": p.stem, "seconds": res.seconds, "model": res.model, "mode": res.mode, "error": ""})
            print(f"{p.stem}: {res.seconds:.1f}s")
        except Exception as e:
            rows.append({"id": p.stem, "seconds": "", "model": a.model or a.provider, "mode": a.mode, "error": str(e)[:200]})
            print(f"{p.stem}: FAILED {e}")
    with open(out / "timings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "seconds", "model", "mode", "error"]); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
