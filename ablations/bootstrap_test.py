#!/usr/bin/env python3
"""Paired bootstrap significance test for Tenacious-Bench ablations.

Tests whether the trained judge's pass@1 is significantly better than baseline.
Uses 10,000-sample paired bootstrap (no parametric assumptions needed for pass@1).

Usage:
  # After filling ablation_results.json:
  python ablations/bootstrap_test.py --results ablations/ablation_results.json --alpha 0.05

  # Or pass raw traces directly:
  python ablations/bootstrap_test.py \\
    --baseline-traces ablations/held_out_traces.jsonl \\
    --judge-traces ablations/judge_traces.jsonl \\
    --alpha 0.05
"""

import argparse
import json
import random
from pathlib import Path


def paired_bootstrap(baseline_pass: list, judge_pass: list, n_boot: int = 10000, seed: int = 42) -> dict:
    """
    Paired bootstrap test for H0: judge_pass@1 - baseline_pass@1 = 0.
    Returns observed delta, p-value, and 95% CI.

    Args:
        baseline_pass: List of 0/1 per-task pass indicators (baseline condition).
        judge_pass:    List of 0/1 per-task pass indicators (judge condition).
        n_boot:        Number of bootstrap resamples.
        seed:          Random seed for reproducibility.

    Returns:
        dict with observed_delta, p_value, ci_95, n_tasks, interpretation
    """
    assert len(baseline_pass) == len(judge_pass), "Lists must be same length (paired)"
    n = len(baseline_pass)

    observed_delta = sum(judge_pass) / n - sum(baseline_pass) / n

    rng = random.Random(seed)
    boot_deltas = []
    for _ in range(n_boot):
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        boot_baseline = sum(baseline_pass[i] for i in indices) / n
        boot_judge = sum(judge_pass[i] for i in indices) / n
        boot_deltas.append(boot_judge - boot_baseline)

    # One-sided p-value: P(delta <= 0 | H0)
    p_value = sum(1 for d in boot_deltas if d <= 0) / n_boot

    boot_deltas_sorted = sorted(boot_deltas)
    ci_low = boot_deltas_sorted[int(0.025 * n_boot)]
    ci_high = boot_deltas_sorted[int(0.975 * n_boot)]

    return {
        "n_tasks": n,
        "observed_delta": round(observed_delta, 4),
        "p_value": round(p_value, 4),
        "ci_95": [round(ci_low, 4), round(ci_high, 4)],
        "n_bootstrap": n_boot,
        "seed": seed,
    }


def load_traces(path: str) -> list:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def main():
    parser = argparse.ArgumentParser(description="Paired bootstrap for Tenacious-Bench ablations")
    parser.add_argument("--results", default="ablations/ablation_results.json",
                        help="Path to ablation_results.json (for summary mode)")
    parser.add_argument("--baseline-traces", default="ablations/held_out_traces.jsonl",
                        help="JSONL with per-task baseline pass_at_1 fields")
    parser.add_argument("--judge-traces", default="ablations/judge_traces.jsonl",
                        help="JSONL with per-task judge pass_at_1 fields (created after Colab run)")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--n-boot", type=int, default=10000)
    args = parser.parse_args()

    judge_path = Path(args.judge_traces)
    if not judge_path.exists():
        print(f"[INFO] {args.judge_traces} not found — judge not yet trained.")
        print("Run this script after uploading judge_traces.jsonl from the Colab run.")
        print("\nBaseline-only summary:")
        baseline = load_traces(args.baseline_traces)
        b_pass = [1 if t["pass_at_1"] else 0 for t in baseline]
        print(f"  n={len(b_pass)}, baseline pass@1={sum(b_pass)/len(b_pass):.4f}")
        return

    baseline_traces = load_traces(args.baseline_traces)
    judge_traces = load_traces(args.judge_traces)

    # Align by task_id
    baseline_by_id = {t["task_id"]: t for t in baseline_traces}
    judge_by_id = {t["task_id"]: t for t in judge_traces}
    common_ids = sorted(set(baseline_by_id) & set(judge_by_id))

    if not common_ids:
        print("[ERROR] No common task_ids between baseline and judge traces.")
        return

    b_pass = [1 if baseline_by_id[tid]["pass_at_1"] else 0 for tid in common_ids]
    j_pass = [1 if judge_by_id[tid]["pass_at_1"] else 0 for tid in common_ids]

    result = paired_bootstrap(b_pass, j_pass, n_boot=args.n_boot)

    print(f"\n=== Paired Bootstrap Test (n_boot={args.n_boot}, seed=42) ===")
    print(f"n_tasks       = {result['n_tasks']}")
    print(f"baseline p@1  = {sum(b_pass)/len(b_pass):.4f}")
    print(f"judge p@1     = {sum(j_pass)/len(j_pass):.4f}")
    print(f"observed Δ    = {result['observed_delta']:+.4f}")
    print(f"95% CI        = [{result['ci_95'][0]:+.4f}, {result['ci_95'][1]:+.4f}]")
    print(f"p-value       = {result['p_value']:.4f}")

    sig = result["p_value"] < args.alpha
    print(f"\nSignificant at α={args.alpha}? {'YES ✓' if sig else 'NO ✗'}")
    if not sig:
        print("Delta A criterion NOT met — report honestly, audit training data and pairs.")
    else:
        print(f"Delta A criterion MET — judge improves pass@1 by {result['observed_delta']:+.4f} (p={result['p_value']:.4f})")

    # Update ablation_results.json
    results_path = Path(args.results)
    if results_path.exists():
        data = json.loads(results_path.read_text())
        data["delta_a"]["baseline_tenacious_bench_held_out"] = round(sum(b_pass)/len(b_pass), 4)
        data["delta_a"]["trained_judge_pass_at_1"] = round(sum(j_pass)/len(j_pass), 4)
        data["delta_a"]["delta"] = result["observed_delta"]
        data["delta_a"]["p_value"] = result["p_value"]
        data["delta_a"]["ci_95"] = result["ci_95"]
        data["delta_a"]["significant"] = sig
        results_path.write_text(json.dumps(data, indent=2))
        print(f"\nUpdated {args.results}")


if __name__ == "__main__":
    main()
