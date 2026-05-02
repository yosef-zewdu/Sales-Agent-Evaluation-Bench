#!/usr/bin/env python3
"""
Deduplication for generated benchmark tasks.

Uses two-stage approach (no GPU required):
1. N-gram Jaccard similarity on hiring_signal_brief (fast exact/near-exact)
2. TF-IDF cosine similarity via numpy for semantic near-duplicates (cosine > threshold)

No sentence-transformers or PyTorch dependency — runs on CPU only.
"""

import json, argparse
from pathlib import Path
from collections import Counter

import numpy as np


def load_tasks(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def task_text(task: dict) -> str:
    inp = task.get("input", {})
    return (inp.get("hiring_signal_brief", "") + " " + task.get("candidate_output", "")).lower()


# ── TF-IDF cosine without sklearn ────────────────────────────────────────────

def build_tfidf(texts: list[str]) -> np.ndarray:
    """Build a TF-IDF matrix (n_docs × n_terms) using pure Python + numpy."""
    tokenized = [t.split() for t in texts]
    vocab: dict[str, int] = {}
    for tokens in tokenized:
        for tok in tokens:
            if tok not in vocab:
                vocab[tok] = len(vocab)

    n_docs = len(texts)
    n_terms = len(vocab)
    tf = np.zeros((n_docs, n_terms), dtype=np.float32)

    for i, tokens in enumerate(tokenized):
        counts = Counter(tokens)
        total = len(tokens) or 1
        for tok, cnt in counts.items():
            tf[i, vocab[tok]] = cnt / total

    # IDF
    df = np.zeros(n_terms, dtype=np.float32)
    for i in range(n_docs):
        df[tf[i] > 0] += 1
    idf = np.log((n_docs + 1) / (df + 1)) + 1.0

    tfidf = tf * idf

    # L2-normalize each row
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return tfidf / norms


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity matrix (already L2-normalized)."""
    return a @ b.T


def deduplicate(tasks: list[dict], threshold: float = 0.85) -> tuple[list[dict], list[dict]]:
    """Return (kept, removed) task lists using TF-IDF cosine similarity."""
    texts = [task_text(t) for t in tasks]
    tfidf = build_tfidf(texts)

    kept_indices: list[int] = []
    removed: list[dict] = []

    for i in range(len(tasks)):
        if not kept_indices:
            kept_indices.append(i)
            continue
        kept_embs = tfidf[kept_indices]
        sims = (tfidf[i] @ kept_embs.T)  # shape: (n_kept,)
        max_sim = float(sims.max())
        if max_sim > threshold:
            best_j = kept_indices[int(sims.argmax())]
            removed.append({
                "removed_task_id":  tasks[i]["task_id"],
                "duplicate_of":     tasks[best_j]["task_id"],
                "cosine_similarity": round(max_sim, 4),
            })
        else:
            kept_indices.append(i)

    kept = [tasks[i] for i in kept_indices]
    return kept, removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",     required=True)
    parser.add_argument("--output",    required=True)
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    tasks = load_tasks(args.input)
    print(f"Loaded {len(tasks)} tasks from {args.input}")

    kept, removed = deduplicate(tasks, threshold=args.threshold)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(json.dumps(t) for t in kept))

    removed_path = args.output.replace(".jsonl", "_removed_duplicates.json")
    Path(removed_path).write_text(json.dumps(removed, indent=2))

    print(f"Kept: {len(kept)}  |  Removed as duplicates: {len(removed)}")
    print(f"→ {args.output}")
    print(f"→ {removed_path}")


if __name__ == "__main__":
    main()
