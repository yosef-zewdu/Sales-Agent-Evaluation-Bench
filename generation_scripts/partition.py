#!/usr/bin/env python3
"""
Partition deduplicated tasks into train/dev/held_out splits.
Split: 50% train / 30% dev / 20% held_out using MD5 hash of task_id (seed=42).
Ensures reproducibility — same task_id always maps to the same partition.
"""

import json, hashlib, argparse
from pathlib import Path


def partition_tasks(
    input_path: str,
    train_path: str,
    dev_path: str,
    held_out_path: str,
    seed: int = 42,
) -> None:
    tasks = [json.loads(l) for l in Path(input_path).read_text().splitlines() if l.strip()]
    train, dev, held = [], [], []

    for task in tasks:
        h = int(hashlib.md5(f"{seed}{task['task_id']}".encode()).hexdigest(), 16) % 100
        task["metadata"]["partition"] = "train" if h < 50 else "dev" if h < 80 else "held_out"
        if h < 50:
            train.append(task)
        elif h < 80:
            dev.append(task)
        else:
            held.append(task)

    for path, bucket in [(train_path, train), (dev_path, dev), (held_out_path, held)]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(json.dumps(t) for t in bucket))

    total = len(tasks)
    print(f"Train: {len(train)} ({len(train)/total:.0%})  |  "
          f"Dev: {len(dev)} ({len(dev)/total:.0%})  |  "
          f"Held-out: {len(held)} ({len(held)/total:.0%})")
    print(f"→ {train_path}")
    print(f"→ {dev_path}")
    print(f"→ {held_out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",     required=True)
    parser.add_argument("--train",     required=True)
    parser.add_argument("--dev",       required=True)
    parser.add_argument("--held_out",  required=True)
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    partition_tasks(args.input, args.train, args.dev, args.held_out, seed=args.seed)


if __name__ == "__main__":
    main()
