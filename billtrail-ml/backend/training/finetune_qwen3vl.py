"""Fine-tune Qwen3-VL on our bills with QLoRA (Unsloth). Needs an NVIDIA GPU (about 8 GB+ for the 4B model).
Runs on a local GPU or on a free Colab / Kaggle GPU (see training/colab_finetune.ipynb).

What happens (report Section 7.2):
  * the base model is loaded in 4-bit (the "Q" in QLoRA) to save memory;
  * small LoRA add-on layers are attached and ONLY those are trained;
  * each example = bill image(s) + production prompt -> correct JSON;
  * we save (a) the small LoRA adapter and (b) a merged 16-bit model that vLLM can serve directly.

Usage:
  pip install -r training/requirements-train.txt
  python -m training.finetune_qwen3vl --data data/qwen_dataset --out models/billtrail-qwen3vl --epochs 2
Serve it:
  vllm serve models/billtrail-qwen3vl/merged --served-model-name billtrail-qwen3vl --max-model-len 8192
"""
import argparse
import json
from pathlib import Path

from PIL import Image


def load_split(data: Path, name: str) -> list[dict]:
    rows = []
    for line in open(data / f"{name}.jsonl"):
        ex = json.loads(line)
        content = [{"type": "image", "image": Image.open(data / p).convert("RGB")} for p in ex["images"]]
        content.append({"type": "text", "text": ex["prompt"]})
        rows.append({"messages": [{"role": "user", "content": content},
                                  {"role": "assistant", "content": [{"type": "text", "text": ex["answer"]}]}]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/qwen_dataset"))
    ap.add_argument("--base", default="unsloth/Qwen3-VL-4B-Instruct")
    ap.add_argument("--out", type=Path, default=Path("models/billtrail-qwen3vl"))
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=6144)
    a = ap.parse_args()

    # imported here so the rest of the repo works without a GPU
    from unsloth import FastVisionModel
    from unsloth.trainer import UnslothVisionDataCollator
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastVisionModel.from_pretrained(a.base, load_in_4bit=True, use_gradient_checkpointing="unsloth")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,       # bills have unusual layouts and faded print: let the vision side adapt too
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=a.rank, lora_alpha=a.rank, lora_dropout=0, bias="none", random_state=3407,
    )
    train, val = load_split(a.data, "train"), load_split(a.data, "val")
    print(f"train {len(train)} examples, val {len(val)} examples")

    FastVisionModel.for_training(model)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        train_dataset=train, eval_dataset=val or None,
        args=SFTConfig(
            per_device_train_batch_size=a.batch, gradient_accumulation_steps=a.grad_accum,
            num_train_epochs=a.epochs, learning_rate=a.lr, warmup_ratio=0.05, lr_scheduler_type="cosine",
            optim="adamw_8bit", weight_decay=0.01, logging_steps=5,
            eval_strategy="epoch" if val else "no", save_strategy="epoch",
            output_dir=str(a.out / "checkpoints"), seed=3407, report_to="none",
            remove_unused_columns=False, dataset_text_field="", dataset_kwargs={"skip_prepare_dataset": True},
            max_length=a.max_len,
        ),
    )
    stats = trainer.train()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "train_stats.json").write_text(json.dumps(stats.metrics, indent=2))
    model.save_pretrained(str(a.out / "lora_adapter"))
    tokenizer.save_pretrained(str(a.out / "lora_adapter"))
    model.save_pretrained_merged(str(a.out / "merged"), tokenizer, save_method="merged_16bit")
    print(f"Saved adapter to {a.out / 'lora_adapter'} and merged model to {a.out / 'merged'}")


if __name__ == "__main__":
    main()
