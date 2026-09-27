"""Build the fine-tuning dataset for Qwen3-VL from synthetic and real bills.

Each example = the prepared bill image(s) + the exact production prompt + the correct JSON answer.
Images go through app.pipeline.model_images(), the same cleaning the live worker uses, so the model
is trained on exactly what it will see.

Split rules (report Section 7.3):
  * the TEST set is filled with REAL bills first and is never used for training;
  * validation is a random slice of the rest.
Outputs in --out:
  train.jsonl, val.jsonl, test.jsonl   one example per line: {"id", "source", "images": [...], "prompt", "answer"}
  images/                              prepared PNGs
  test_originals/, test_truth/         the untouched test files + answers, for scripts.predict_folder and eval.evaluate

Usage:
  python -m training.build_dataset --synthetic data/synthetic --real data/real --out data/qwen_dataset --test 0.15 --val 0.1
"""
import argparse
import json
import mimetypes
import random
import shutil
from pathlib import Path

from app.extract import INSTRUCTIONS
from app.pipeline import model_images

PROMPT = INSTRUCTIONS + "\n\nThe bill is in the attached image(s)."


def target_answer(truth: dict) -> str:
    """The answer the model learns to write.
    confidence is left null: the ground truth has no honest confidence value, and teaching a constant would make
    the number meaningless. The rule checks decide Verified / Needs review for the fine-tuned model."""
    t = {k: v for k, v in truth.items() if k not in ("confidence", "unreadable")}
    t["confidence"] = None
    t["unreadable"] = []
    return json.dumps(t, ensure_ascii=False)


def collect(folder: Path | None, source: str) -> list[dict]:
    if not folder:
        return []
    items = []
    for truth_path in sorted((folder / "truth").glob("*.json")):
        matches = [p for p in (folder / "images").glob(truth_path.stem + ".*")]
        if matches:
            items.append({"id": f"{source}_{truth_path.stem}", "source": source, "file": matches[0],
                          "truth": json.loads(truth_path.read_text())})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", type=Path)
    ap.add_argument("--real", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/qwen_dataset"))
    ap.add_argument("--test", type=float, default=0.15)
    ap.add_argument("--val", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    real, synth = collect(a.real, "real"), collect(a.synthetic, "synthetic")
    rng.shuffle(real); rng.shuffle(synth)
    total = len(real) + len(synth)
    if not total:
        raise SystemExit("No examples found. Expected <folder>/images and <folder>/truth.")
    n_test, n_val = round(total * a.test), round(total * a.val)
    pool = real + synth                                  # real bills first -> they fill the test set first
    test, rest = pool[:n_test], pool[n_test:]
    rng.shuffle(rest)
    val, train = rest[:n_val], rest[n_val:]

    out = a.out
    for d in ("images", "test_originals", "test_truth"):
        (out / d).mkdir(parents=True, exist_ok=True)
    for name, split in (("train", train), ("val", val), ("test", test)):
        with open(out / f"{name}.jsonl", "w") as f:
            for ex in split:
                ctype = mimetypes.guess_type(ex["file"].name)[0] or "image/png"
                paths = []
                for i, (png, _) in enumerate(model_images(ex["file"].read_bytes(), ctype)):
                    p = out / "images" / f"{ex['id']}_p{i}.png"
                    p.write_bytes(png)
                    paths.append(str(p.relative_to(out)))
                f.write(json.dumps({"id": ex["id"], "source": ex["source"], "images": paths,
                                    "prompt": PROMPT, "answer": target_answer(ex["truth"])}, ensure_ascii=False) + "\n")
                if name == "test":
                    shutil.copy(ex["file"], out / "test_originals" / f"{ex['id']}{ex['file'].suffix}")
                    (out / "test_truth" / f"{ex['id']}.json").write_text(json.dumps(ex["truth"], indent=2))
    count = lambda s, src: sum(e["source"] == src for e in s)
    for name, split in (("train", train), ("val", val), ("test", test)):
        print(f"{name:5s}: {len(split):4d}  (real {count(split, 'real')}, synthetic {count(split, 'synthetic')})")
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
