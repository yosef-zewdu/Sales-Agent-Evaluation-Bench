#!/usr/bin/env python3
"""
Three contamination checks before sealing held_out partition.

1. N-gram overlap: < 8-gram match on input fields between held_out and train tasks
2. Embedding similarity: cosine < 0.85 via numpy TF-IDF (no GPU required)
3. Time-shift: any task referencing a public signal must cite a documentable time window

Outputs contamination_check.json in the repo root.

Usage:
    python generation_scripts/contamination_check.py \
        --train   tenacious_bench_v0.1/train/tasks.jsonl \
        --dev     tenacious_bench_v0.1/dev/tasks.jsonl \
        --held_out tenacious_bench_v0.1/held_out/tasks.jsonl
"""

import json, re, argparse
from collections import Counter
from pathlib import Path

import numpy as np

NGRAM_THRESHOLD = 8
EMBED_THRESHOLD = 0.85
OUTPUT_PATH     = Path("contamination_check.json")

PUBLIC_SIGNAL_KEYWORDS = [
    "crunchbase", "layoffs.fyi", "linkedin", "series a", "series b", "series c",
    "raised", "funding", "layoff", "techcrunch", "glassdoor",
]
TIME_WINDOW_PATTERN = re.compile(
    r"\b(20\d\d-\d{2}(?:-\d{2})?|Q[1-4]\s*20\d\d|\d+\s*days?\s*ago|\d+\s*months?\s*ago"
    r"|last\s+\d+\s*days?|in\s+the\s+last\s+\d+\s*(?:days?|months?|weeks?))\b",
    re.IGNORECASE,
)


def load_tasks(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def task_input_text(task: dict) -> str:
    inp = task.get("input", {})
    return (inp.get("hiring_signal_brief", "") + " " + inp.get("bench_summary", "")).strip()


def get_ngrams(text: str, n: int) -> set[str]:
    tokens = text.lower().split()
    return {" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)}


# ── Check 1: N-gram overlap ───────────────────────────────────────────────────

def check_ngram(train_tasks: list[dict], held_tasks: list[dict],
                n: int = NGRAM_THRESHOLD) -> dict:
    flagged = []
    train_ngrams = {t["task_id"]: get_ngrams(task_input_text(t), n) for t in train_tasks}

    for ht in held_tasks:
        held_ng = get_ngrams(task_input_text(ht), n)
        for tid, tr_ng in train_ngrams.items():
            overlap = held_ng & tr_ng
            if overlap:
                flagged.append({
                    "held_task_id":  ht["task_id"],
                    "train_task_id": tid,
                    "overlapping_ngrams": list(overlap)[:5],
                })

    return {
        "passed":        len(flagged) == 0,
        "threshold":     f"{n}-gram",
        "flagged_pairs": flagged,
    }


# ── Check 2: TF-IDF cosine similarity (CPU-only, no sentence-transformers) ────

def build_tfidf(texts: list[str]) -> np.ndarray:
    tokenized = [t.lower().split() for t in texts]
    vocab: dict[str, int] = {}
    for tokens in tokenized:
        for tok in tokens:
            if tok not in vocab:
                vocab[tok] = len(vocab)

    n_docs, n_terms = len(texts), len(vocab)
    tf = np.zeros((n_docs, n_terms), dtype=np.float32)
    for i, tokens in enumerate(tokenized):
        counts = Counter(tokens)
        total = len(tokens) or 1
        for tok, cnt in counts.items():
            tf[i, vocab[tok]] = cnt / total

    df = np.zeros(n_terms, dtype=np.float32)
    for i in range(n_docs):
        df[tf[i] > 0] += 1
    idf = np.log((n_docs + 1) / (df + 1)) + 1.0

    tfidf = tf * idf
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return tfidf / norms


def check_embedding(train_tasks: list[dict], held_tasks: list[dict],
                    threshold: float = EMBED_THRESHOLD) -> dict:
    if not train_tasks or not held_tasks:
        return {
            "passed": True, "threshold": threshold,
            "model": "tfidf-cosine (numpy, CPU-only)",
            "flagged_pairs": [], "note": "empty partition — skipped",
        }

    all_texts   = [task_input_text(t) for t in train_tasks + held_tasks]
    all_tfidf   = build_tfidf(all_texts)
    train_embs  = all_tfidf[:len(train_tasks)]
    held_embs   = all_tfidf[len(train_tasks):]

    sim_matrix = held_embs @ train_embs.T   # (n_held × n_train)

    flagged = []
    for hi, ht in enumerate(held_tasks):
        for ti, tt in enumerate(train_tasks):
            sim = float(sim_matrix[hi, ti])
            if sim >= threshold:
                flagged.append({
                    "held_task_id":  ht["task_id"],
                    "train_task_id": tt["task_id"],
                    "cosine_similarity": round(sim, 4),
                })

    return {
        "passed":        len(flagged) == 0,
        "threshold":     threshold,
        "model":         "tfidf-cosine (numpy, CPU-only)",
        "flagged_pairs": flagged,
    }


# ── Check 3: Time-shift verification ─────────────────────────────────────────

def check_timeshift(all_tasks: list[dict]) -> dict:
    flagged, verified = [], []
    for task in all_tasks:
        brief = task.get("input", {}).get("hiring_signal_brief", "").lower()
        if not any(kw in brief for kw in PUBLIC_SIGNAL_KEYWORDS):
            continue
        if TIME_WINDOW_PATTERN.search(brief):
            verified.append(task["task_id"])
        else:
            flagged.append({
                "task_id": task["task_id"],
                "reason":  "public signal reference without documentable time window",
                "brief_excerpt": brief[:120],
            })

    return {
        "passed":                       len(flagged) == 0,
        "public_signal_tasks_found":    len(verified) + len(flagged),
        "public_signal_tasks_verified": len(verified),
        "flagged_tasks":                flagged,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def build_remediation(ngram: dict, embed: dict, timeshift: dict) -> list[str]:
    actions = []
    if not ngram["passed"]:
        actions.append(
            f"N-gram: {len(ngram['flagged_pairs'])} held_out tasks share ≥{NGRAM_THRESHOLD}-gram "
            "with train. Rephrase or replace the flagged held_out tasks."
        )
    if not embed["passed"]:
        actions.append(
            f"Embedding: {len(embed['flagged_pairs'])} held_out tasks have cosine ≥{EMBED_THRESHOLD} "
            "with train. Increase paraphrase distance or replace."
        )
    if not timeshift["passed"]:
        actions.append(
            f"Time-shift: {len(timeshift['flagged_tasks'])} tasks reference public signals "
            "without a documentable time window. Add explicit date ranges."
        )
    return actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train",      required=True)
    parser.add_argument("--dev",        required=True)
    parser.add_argument("--held_out",   required=True)
    parser.add_argument("--train_pairs", default=None,
                        help="Optional: preference_pairs.jsonl to check against held_out")
    args = parser.parse_args()

    print("Loading tasks...")
    train_tasks = load_tasks(args.train)
    dev_tasks   = load_tasks(args.dev)
    held_tasks  = load_tasks(args.held_out)
    all_tasks   = train_tasks + dev_tasks + held_tasks
    print(f"  Train: {len(train_tasks)}  Dev: {len(dev_tasks)}  Held-out: {len(held_tasks)}")

    print("\nCheck 1: N-gram overlap (8-gram)...")
    ngram_result = check_ngram(train_tasks, held_tasks)
    n_pairs = len(ngram_result["flagged_pairs"])
    print(f"  → {'PASS' if ngram_result['passed'] else 'FAIL (' + str(n_pairs) + ' pairs)'}")

    print("\nCheck 2: TF-IDF cosine similarity (cosine < 0.85)...")
    embed_result = check_embedding(train_tasks, held_tasks)
    e_pairs = len(embed_result["flagged_pairs"])
    print(f"  → {'PASS' if embed_result['passed'] else 'FAIL (' + str(e_pairs) + ' pairs)'}")

    print("\nCheck 3: Time-shift verification...")
    timeshift_result = check_timeshift(all_tasks)
    t_tasks = len(timeshift_result["flagged_tasks"])
    print(f"  → {'PASS' if timeshift_result['passed'] else 'FAIL (' + str(t_tasks) + ' tasks)'}")

    remediation  = build_remediation(ngram_result, embed_result, timeshift_result)
    overall_pass = ngram_result["passed"] and embed_result["passed"] and timeshift_result["passed"]

    result = {
        "overall_pass":    overall_pass,
        "ngram_check":     ngram_result,
        "embedding_check": embed_result,
        "timeshift_check": timeshift_result,
        "remediation":     remediation,
        "task_counts": {
            "train":    len(train_tasks),
            "dev":      len(dev_tasks),
            "held_out": len(held_tasks),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\n{'ALL CHECKS PASS' if overall_pass else 'SOME CHECKS FAILED'}")
    print(f"→ {OUTPUT_PATH}")
    if remediation:
        print("\nRemediation needed:")
        for r in remediation:
            print(f"  • {r}")


if __name__ == "__main__":
    main()
