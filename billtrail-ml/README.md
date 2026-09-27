# BillTrail — Machine Learning Part

This folder is the **machine learning part** of BillTrail. Its job: teach an open-source vision-language model, **Qwen3-VL**, to read Indian
medical bills and fill in our **standard bill format**, then measure how well it does.

> In the shared `billtrail` repo, keep this file as `docs/ML_README.md` so it doesn't replace the main README.

## Where this fits in the full system

```
Website (frontend team) ─upload─► Backend API ─► queue ─► Worker ─► our fine-tuned Qwen3-VL ─► standard format ─► rule checks ─► database
                                                                      ▲
                                                   everything in this folder builds, tests and measures this model
```

The worker in the full system calls `app/pipeline.py` → `read_bill()`, which is the same code you use here.
So whatever you train and test here plugs straight into the live system.

## What each file does

| File | What it does |
|---|---|
| `backend/app/schemas.py` | **The standard bill format** (seller, invoice, patient, items, tax, totals) |
| `backend/app/extract.py` | **The prompt** (`INSTRUCTIONS`) and the call to the model: `qwen_local` (our Qwen via vLLM/Ollama) or `claude` (teacher / baseline) |
| `backend/app/preprocess.py` | Image cleaning: `prepare_for_model()` for Qwen, `clean_for_ocr()` for the OCR baseline |
| `backend/app/ocr.py` | PDF → page images, and Tesseract / PaddleOCR (baseline only) |
| `backend/app/pipeline.py` | `read_bill()`: one bill file in → standard format out |
| `backend/app/validate.py` | Rule checks (GSTIN check digit, totals, expiry, and more) |
| `backend/app/config.py` | Settings, read from environment variables or `backend/.env` |
| `backend/scripts/make_synthetic_bills.py` | Makes fake bills **with correct answers**: clean, faded, tilted or noisy; ~20% with a planted error |
| `backend/training/build_dataset.py` | Turns bills + answers into train / val / test files for Qwen |
| `backend/training/finetune_qwen3vl.py` | QLoRA fine-tuning with Unsloth (needs an NVIDIA GPU) |
| `backend/training/colab_finetune.ipynb` | The same fine-tuning on a free Colab GPU |
| `backend/scripts/predict_folder.py` | Runs one model setup over a folder of bills and saves its answers |
| `backend/eval/evaluate.py` | Scores those answers: field accuracy, line-item F1, GSTIN validity, review rate |
| `backend/tests/` | 23 automated tests for all of the above |

## Setup (once)

You need Python 3.11. Install Tesseract too if you'll run the OCR baseline (Windows: `winget install -e --id UB-Mannheim.TesseractOCR`).
Then, from inside `backend`:

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements-ml.txt
python -m pytest -q               # should say: 23 passed
```

For fine-tuning, on the GPU machine or Colab only: `pip install -r training/requirements-train.txt`

## The workflow (run everything from inside `backend`)

**1. Make synthetic bills.** This makes 1,000 fake bill images plus a correct-answer file for each.
```bash
python -m scripts.make_synthetic_bills --n 1000 --out data/synthetic
```

**2. Add real bills (optional but important).** Put consented bills, with personal details hidden, in
`data/real/images/`, and the correct answer for each in `data/real/truth/` (same file name, `.json`, same format as
the synthetic answers). An easy way to make the answers: let Claude pre-fill them (step 5 with `--provider claude`),
then check and correct them by hand.

**3. Build the dataset.** Real bills fill the test set first; the model never trains on the test set.
```bash
python -m training.build_dataset --synthetic data/synthetic --real data/real --out data/qwen_dataset
```

**4. Fine-tune** (GPU with about 8 GB+ memory, or Colab with `training/colab_finetune.ipynb`):
```bash
python -m training.finetune_qwen3vl --data data/qwen_dataset --out models/billtrail-qwen3vl --epochs 2
```

**5. Serve the model and test it.** This starts the fine-tuned model as a local server. The prediction script
then sends it every test bill.
```bash
vllm serve models/billtrail-qwen3vl/merged --served-model-name billtrail-qwen3vl --port 8001 --max-model-len 8192
```
Create `backend/.env` with:
```
QWEN_BASE_URL=http://localhost:8001/v1
QWEN_MODEL=billtrail-qwen3vl
ANTHROPIC_API_KEY=          # only for the Claude baseline / teacher
```
Then run each setup on the same test bills:
```bash
python -m scripts.predict_folder --images data/qwen_dataset/test_originals --out data/pred/qwen_ft --provider qwen_local
python -m scripts.predict_folder --images data/qwen_dataset/test_originals --out data/pred/claude  --provider claude
python -m scripts.predict_folder --images data/qwen_dataset/test_originals --out data/pred/ocr_claude --provider claude --mode ocr_text
```
For the "before fine-tuning" row, serve the base model (`vllm serve Qwen/Qwen3-VL-4B-Instruct --served-model-name qwen3vl-base --port 8001`)
and run with `--model qwen3vl-base`.

**6. Score** each setup (this gives the results tables for the paper):
```bash
python -m eval.evaluate --truth data/qwen_dataset/test_truth --pred data/pred/qwen_ft --csv qwen_ft.csv
```

## Some rules (these three files are shared with the rest of the system)

1. **`extract.py` → `INSTRUCTIONS` (the prompt)** and **`preprocess.py` → `prepare_for_model()`**: the model is
   trained on exactly this prompt and this image cleaning, and the live worker uses them too. If you change either,
   **re-train** the model.
2. **`schemas.py` (the standard format)**: the backend saves these fields, and the frontend displays them
   (`frontend/lib/types.ts`). Changing a field name breaks both, so agree with the backend and frontend owners first,
   and note it in your pull request.
3. **Never commit `data/` or `models/`** (already in `.gitignore`). They hold bills, which may be real patient
   data, and multi-GB model files. Share models through Google Drive or Hugging Face (private), never Git.

## Git workflow (shared `billtrail` repo)

Work on the `ml` branch, open a pull request into `main` when a piece is ready, and run `python -m pytest -q`
before every pull request.

```bash
git checkout main && git pull
git checkout -b ml            # first time only; later just: git checkout ml && git merge main
# ...work, then:
git add backend/training backend/scripts backend/eval backend/app backend/tests
git commit -m "Describe what you changed"
git push origin ml            # then open a pull request on GitHub: ml -> main
```

## Good to know

- The fine-tuned model is trained to write `"confidence": null`, because the correct answers have no honest confidence
  value. In the live system, Verified / Needs review for this model is decided by the rule checks.
- The fine-tuning script and vLLM have not been run on a GPU yet. Library options change between versions; if a flag is
  rejected, check the current docs (Unsloth, TRL, vLLM).
- `training/export_verified.py` (exports human-checked real bills from the website) lives in the full repo, because
  it needs the backend running.

