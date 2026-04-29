#!/usr/bin/env python3
"""
Embedding-based deduplication for generated benchmark tasks.
Removes tasks with cosine similarity > threshold (default 0.85) using
sentence-transformers/all-MiniLM-L6-v2 embeddings on the hiring_signal_brief field.
"""

import json, argparse
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_tasks(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def deduplicate(tasks: list[dict], threshold: float = 0.85) -> tuple[list[dict], list[dict]]:
    """Return (kept, removed) task lists."""
    model = SentenceTransformer(MODEL_NAME)

    texts = [
        t["input"].get("hiring_signal_brief", "") + " " + t.get("candidate_output", "")
        for t in tasks
    ]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    kept_indices: list[int] = []
    removed: list[dict] = []

    for i, task in enumerate(tasks):
        duplicate = False
        for j in kept_indices:
            sim = cosine_sim(embeddings[i], embeddings[j])
            if sim > threshold:
                duplicate = True
                removed.append({
                    "removed_task_id": task["task_id"],
                    "duplicate_of": tasks[j]["task_id"],
                    "cosine_similarity": round(sim, 4),
                })
                break
        if not duplicate:
            kept_indices.append(i)

    kept = [tasks[i] for i in kept_indices]
    return kept, removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",     required=True, help="Input JSONL path")
    parser.add_argument("--output",    required=True, help="Output JSONL path (deduplicated)")
    parser.add_argument("--threshold", type=float, default=0.85, help="Cosine similarity threshold")
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
