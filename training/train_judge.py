#!/usr/bin/env python3
"""SimPO training script for Tenacious-Judge LoRA adapter.

Designed to run on Google Colab T4 (free) or RunPod 4090.
Algorithm: SimPO (reference-free, no separate ref model needed — lower VRAM than DPO).
Backbone: Qwen/Qwen2.5-0.5B-Instruct (upgrade to 1.5B if kill condition triggers).

Kill condition (SimPO §2.3):
  If epoch-1 loss has not dropped 10% from step-0 loss, stop immediately.
  Root cause: check score-gap distribution (mean gap must be > 2.0).

Usage:
  # Install deps first:
  pip install unsloth trl datasets peft transformers accelerate bitsandbytes -q
  # Then:
  python train_judge.py --config training/hyperparams.yaml [--pairs training_data/preference_pairs.jsonl]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_pairs(pairs_path: str) -> list:
    pairs = [json.loads(l) for l in open(pairs_path) if l.strip()]
    gaps = [p["score_gap"] for p in pairs]
    mean_gap = sum(gaps) / len(gaps)
    log.info(f"Loaded {len(pairs)} preference pairs — mean_gap={mean_gap:.2f}, min={min(gaps):.2f}, max={max(gaps):.2f}")
    if mean_gap < 2.0:
        log.error(
            f"KILL CONDITION PRE-CHECK: mean score_gap={mean_gap:.2f} < 2.0. "
            "Pairs are too noisy — adding compute will not fix this. "
            "Audit training_data/preference_pairs.jsonl and tighten the score-gap filter."
        )
        sys.exit(1)
    return pairs


def check_format(pairs: list):
    for i, p in enumerate(pairs[:3]):
        assert "prompt" in p and "chosen" in p and "rejected" in p, \
            f"Pair {i} missing required fields. Got: {list(p.keys())}"
    log.info("Format check OK — all required fields present (prompt, chosen, rejected)")


def build_dataset(pairs: list, seed: int):
    from datasets import Dataset
    rows = [{"prompt": p["prompt"], "chosen": p["chosen"], "rejected": p["rejected"]} for p in pairs]
    ds = Dataset.from_list(rows)
    ds = ds.train_test_split(test_size=0.1, seed=seed)
    log.info(f"Dataset split — train={len(ds['train'])}, eval={len(ds['test'])}")
    return ds


def build_model(cfg: dict):
    from unsloth import FastLanguageModel
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["backbone"],
        max_seq_length=cfg["max_seq_length"],
        load_in_4bit=False,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["target_modules"],
        bias="none",
        use_gradient_checkpointing=True,
        random_state=cfg["seed"],
    )
    log.info(f"Model loaded: {cfg['backbone']} + LoRA r={cfg['lora_r']}")
    return model, tokenizer


def train(cfg: dict, ds, model, tokenizer):
    from trl import SimPOTrainer, SimPOConfig

    simpo_cfg = SimPOConfig(
        output_dir=cfg["output_dir"],
        num_train_epochs=cfg["num_epochs"],
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["gradient_accumulation_steps"],
        learning_rate=cfg["learning_rate"],
        warmup_ratio=cfg["warmup_ratio"],
        fp16=(cfg["precision"] == "fp16"),
        bf16=(cfg["precision"] == "bf16"),
        seed=cfg["seed"],
        logging_steps=cfg["log_steps"],
        save_strategy=cfg["save_strategy"],
        eval_strategy="epoch",
        push_to_hub=cfg.get("push_to_hub", False),
        hub_model_id=cfg.get("hub_model_id", ""),
        report_to="none",
    )

    trainer = SimPOTrainer(
        model=model,
        args=simpo_cfg,
        train_dataset=ds["train"],
        eval_dataset=ds["test"],
        tokenizer=tokenizer,
    )

    log.info("Starting training...")
    trainer.train()

    # Kill condition check after epoch 1
    log_history = trainer.state.log_history
    losses = [e["loss"] for e in log_history if "loss" in e]
    if len(losses) >= 2:
        initial_loss = losses[0]
        # Find loss after ~first third of training (approx epoch 1 checkpoint)
        ep1_idx = max(1, len(losses) // cfg["num_epochs"])
        ep1_loss = losses[ep1_idx]
        pct_drop = (initial_loss - ep1_loss) / initial_loss if initial_loss > 0 else 0
        log.info(f"Loss at step 0: {initial_loss:.4f}, after epoch 1: {ep1_loss:.4f}, drop={pct_drop*100:.1f}%")
        if pct_drop < 0.10:
            log.warning(
                "KILL CONDITION: loss did not decrease 10% by epoch 1. "
                "Check score-gap distribution and chat template. "
                "Consider increasing lora_r to 32."
            )

    return trainer


def save_log(trainer, output_path: str):
    log_history = trainer.state.log_history
    Path(output_path).write_text(json.dumps(log_history, indent=2))
    losses = [e.get("loss") for e in log_history if "loss" in e]
    log.info(f"Training complete. Loss history (sampled): {losses[:5]} ... {losses[-3:]}")
    log.info(f"Log saved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="training/hyperparams.yaml")
    parser.add_argument("--pairs", default="training_data/preference_pairs.jsonl")
    parser.add_argument("--log-output", default="training/training_run.log")
    args = parser.parse_args()

    cfg = load_config(args.config)
    pairs = load_pairs(args.pairs)
    check_format(pairs)

    import random
    random.seed(cfg["seed"])

    ds = build_dataset(pairs, cfg["seed"])
    model, tokenizer = build_model(cfg)
    trainer = train(cfg, ds, model, tokenizer)
    save_log(trainer, args.log_output)


if __name__ == "__main__":
    main()
