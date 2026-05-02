#!/usr/bin/env python3
"""Delta A ablation — baseline pass@1 on held-out partition.

Measures pass@1 of candidate_output in held-out tasks WITHOUT judge intervention.
This establishes the baseline that the trained LoRA judge must beat by ≥ +0.05.

Reference: Week 10 baseline = 0.80 on signal over-claiming probe set.
Target:    Trained judge pass@1 ≥ 0.85 on Tenacious-Bench held-out.

Usage:
  python ablations/run_delta_a.py
  python ablations/run_delta_a.py --held-out tenacious_bench_v0.1/held_out/tasks.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scoring_evaluator import score_task


def run_baseline(held_out_path: str) -> dict:
    tasks = [json.loads(l) for l in Path(held_out_path).read_text().splitlines() if l.strip()]
    print(f"Scoring {len(tasks)} held-out tasks (baseline — no judge intervention)...")

    baseline_scores = []
    traces = []
    for task in tasks:
        result = score_task(task)
        baseline_scores.append(result["total"])
        traces.append({
            "task_id": task["task_id"],
            "score": result["total"],
            "pass_at_1": result["pass_at_1"],
            "hard_fail": result["hard_fail"],
            "hard_fail_reasons": result["hard_fail_reasons"],
            "breakdown": result["breakdown"],
            "condition": "baseline",
            "dimension": task.get("dimension", "unknown"),
        })

    n = len(tasks)
    pass_count = sum(1 for s in baseline_scores if s >= 3.5)
    hard_fail_count = sum(1 for t in traces if t["hard_fail"])
    baseline_pass = pass_count / n
    avg_score = sum(baseline_scores) / n

    print(f"\n=== Baseline Results ===")
    print(f"n={n}, pass@1={baseline_pass:.4f}, avg_score={avg_score:.3f}")
    print(f"hard_fail_rate={hard_fail_count/n:.4f}")
    print(f"Reference: Week 10 baseline = 0.80 on signal over-claiming probe set")
    print(f"Delta A target: trained judge pass@1 ≥ {baseline_pass + 0.05:.4f} (i.e., baseline + 0.05)")

    # Per-dimension breakdown
    from collections import defaultdict
    by_dim = defaultdict(list)
    for t in traces:
        by_dim[t["dimension"]].append(t["pass_at_1"])
    print("\nPer-dimension pass@1:")
    for dim, passes in sorted(by_dim.items()):
        print(f"  {dim}: {sum(passes)/len(passes):.3f}  (n={len(passes)})")

    return {
        "n_tasks": n,
        "pass_at_1": round(baseline_pass, 4),
        "avg_score": round(avg_score, 4),
        "hard_fail_rate": round(hard_fail_count / n, 4),
        "per_dimension": {dim: round(sum(p)/len(p), 4) for dim, p in by_dim.items()},
        "traces": traces,
    }


def save_traces(traces: list, out_path: str):
    Path(out_path).parent.mkdir(exist_ok=True)
    Path(out_path).write_text("\n".join(json.dumps(t) for t in traces))
    print(f"\nTraces saved → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--held-out",
        default="tenacious_bench_v0.1/held_out/tasks.jsonl",
    )
    parser.add_argument(
        "--traces-out",
        default="ablations/held_out_traces.jsonl",
    )
    args = parser.parse_args()

    results = run_baseline(args.held_out)
    save_traces(results["traces"], args.traces_out)

    # Save summary for ablation_results.json
    summary = {
        "condition": "baseline",
        "pass_at_1": results["pass_at_1"],
        "avg_score": results["avg_score"],
        "hard_fail_rate": results["hard_fail_rate"],
        "n_tasks": results["n_tasks"],
        "per_dimension": results["per_dimension"],
    }
    summary_path = Path("ablations/baseline_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary saved → {summary_path}")


if __name__ == "__main__":
    main()
