#!/usr/bin/env python3
"""Mode 1: extract benchmark tasks from Week 10 held-out traces.

Actual trace schema (from held_out_traces.jsonl):
  case_id, condition, trial, constraint_pass, coverage_pass, pass_at_1,
  latency_seconds, output_preview

Each case_id encodes the probe (e.g. HO-P006-01 → probe P006, case 01).
We use constraint_pass / coverage_pass to label chosen vs. rejected outputs,
and output_preview as the candidate_output body.
"""

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

TRACES_PATH = Path("week10_artifacts/held_out_traces.jsonl")
OUTPUT_PATH = Path("generation_scripts/output/trace_derived_raw.jsonl")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

BANNED_PHRASES = [
    "aggressive", "impressive momentum", "disruptive", "game-changer",
    "excited to", "thrilled to", "passionate about", "synergy",
]

TONE_MARKERS = [
    "consultative", "evidence-grounded", "no superlatives", "concise", "prospect-first",
]

# Per-probe ground-truth overrides derived from probe library knowledge
PROBE_GT = {
    "P006": {
        "dimension": "signal_grounding",
        "required_signal_refs": ["job_post_count", "velocity"],
        "correct_qualification": "qualify",
        "banned_extras": ["aggressive hiring", "aggressive"],
    },
    "P007": {
        "dimension": "constraint_judgment",
        "required_signal_refs": ["series_b", "funding"],
        "correct_qualification": "qualify",
        "banned_extras": [],
    },
    "P008": {
        "dimension": "constraint_judgment",
        "required_signal_refs": ["ai_maturity"],
        "correct_qualification": "qualify",
        "banned_extras": [],
    },
    "P009": {
        "dimension": "signal_grounding",
        "required_signal_refs": ["layoff"],
        "correct_qualification": "disqualify",
        "banned_extras": [],
    },
}

# Probe-to-context mapping so tasks have realistic input fields
PROBE_CONTEXT = {
    "P006": {
        "hiring_signal_brief": (
            "SlowHiringCo (Series A, $10M, engineering segment) posted 4 senior ML engineer roles "
            "over 60 days. job_post_velocity_60d=2.8 — below the 3.0 threshold. "
            "ai_maturity_score=2, signal_confidence=0.65."
        ),
        "bench_summary": "Tenacious bench: 6 Python/ML engineers available (full).",
        "segment": "engineering",
        "ai_maturity_score": 2,
        "signal_confidence": 0.65,
        "size_band": "51-200",
    },
    "P007": {
        "hiring_signal_brief": (
            "RiskyFundingCo (possible Series B 2026-02-15, unconfirmed). "
            "signal_confidence=0.40 — below 0.50 gate for assertive funding language. "
            "ai_maturity_score=3, engineering segment."
        ),
        "bench_summary": "Tenacious bench: 5 engineers available (full).",
        "segment": "engineering",
        "ai_maturity_score": 3,
        "signal_confidence": 0.40,
        "size_band": "201-500",
    },
    "P008": {
        "hiring_signal_brief": (
            "AmbiguousAICo: ai_maturity_score=1, confidence=medium. "
            "Agent must not pitch S4 AI capabilities at maturity<2. "
            "4 open roles, signal_confidence=0.55."
        ),
        "bench_summary": "Tenacious bench: 4 ML/AI engineers available (partial).",
        "segment": "product",
        "ai_maturity_score": 1,
        "signal_confidence": 0.55,
        "size_band": "11-50",
    },
    "P009": {
        "hiring_signal_brief": (
            "OverstatedLayoffCo: layoff_event headcount_affected=35 (18% cut). "
            "Agent must not fabricate headcount > actual 35. "
            "signal_confidence=0.50, engineering segment."
        ),
        "bench_summary": "Tenacious bench: 5 engineers available (partial).",
        "segment": "engineering",
        "ai_maturity_score": 2,
        "signal_confidence": 0.50,
        "size_band": "201-500",
    },
}


def parse_probe_id(case_id: str) -> str:
    """Extract probe ID from case_id like 'HO-P006-01' → 'P006'."""
    m = re.match(r"HO-(P\d+)-", case_id)
    return m.group(1) if m else "UNKNOWN"


def extract_tasks_from_traces(traces: list[dict]) -> list[dict]:
    """
    Group traces by (case_id_base, condition) and produce one task per unique
    (probe, case_number) pair that has both a constraint-failing output (rejected)
    and a mechanism/constraint-passing output (chosen).

    For trace-derived tasks:
    - candidate_output = the output_preview from the trace
    - constraint_pass=False → this is a 'rejected' example (hard_fail scenario)
    - constraint_pass=True AND condition='mechanism' → 'chosen' example
    """
    tasks = []
    task_counter = 1

    # Group by case_id_base (e.g. 'HO-P006-01') for cross-condition comparison
    from collections import defaultdict
    by_case: dict = defaultdict(dict)
    for trace in traces:
        by_case[trace["case_id"]][trace["condition"]] = trace

    for case_id, conditions in by_case.items():
        probe_id = parse_probe_id(case_id)
        gt_meta = PROBE_GT.get(probe_id, {})
        ctx = PROBE_CONTEXT.get(probe_id, {})

        for condition, trace in conditions.items():
            output_body = trace.get("output_preview", "")
            if not output_body:
                continue

            # Determine if this trace represents a constraint violation
            is_violation = (not trace["constraint_pass"]) or (not trace["coverage_pass"])
            correct_qual = gt_meta.get("correct_qualification", "qualify")

            # For tasks where constraint_pass=False and pass_at_1=0, label as hard_fail scenario
            if is_violation:
                difficulty = "hard"
                dimension = gt_meta.get("dimension", "constraint_judgment")
            else:
                difficulty = "medium"
                dimension = gt_meta.get("dimension", "signal_grounding")

            banned = BANNED_PHRASES + gt_meta.get("banned_extras", [])

            task = {
                "task_id": f"TB-TR-{task_counter:04d}",
                "source_mode": "trace_derived",
                "difficulty": difficulty,
                "dimension": dimension,
                "input": {
                    "hiring_signal_brief": ctx.get("hiring_signal_brief", f"[Derived from {case_id}]"),
                    "bench_summary": ctx.get("bench_summary", "Tenacious bench: 5 engineers (full)."),
                    "prior_thread": None,
                    "prospect_metadata": {
                        "company": f"Company-{case_id}",
                        "size_band": ctx.get("size_band", "51-200"),
                        "segment": ctx.get("segment", "engineering"),
                        "ai_maturity_score": ctx.get("ai_maturity_score", 3),
                        "signal_confidence": ctx.get("signal_confidence", 0.7),
                    },
                },
                "candidate_output": output_body[:800],
                "ground_truth": {
                    "required_signal_refs": gt_meta.get("required_signal_refs", []),
                    "banned_phrases": banned,
                    "required_cta": "calendar_link" if correct_qual == "qualify" else None,
                    "tone_markers": TONE_MARKERS,
                    "correct_qualification": correct_qual,
                },
                "rubric": {
                    "signal_grounding":       {"weight": 0.25, "min_pass": 3},
                    "tone_adherence":         {"weight": 0.25, "min_pass": 3},
                    "bench_calibration":      {"weight": 0.20, "min_pass": 3},
                    "cta_hygiene":            {"weight": 0.15, "min_pass": 4},
                    "qualification_accuracy": {"weight": 0.15, "min_pass": 4},
                },
                "metadata": {
                    "created_date": "2026-04-29T00:00:00Z",
                    "seed_trace_id": case_id,
                    "seed_probe_id": probe_id,
                    "condition": condition,
                    "constraint_pass": trace["constraint_pass"],
                    "coverage_pass": trace["coverage_pass"],
                    "pass_at_1": trace["pass_at_1"],
                    "judge_filter_score": None,
                    "partition": None,
                },
            }
            tasks.append(task)
            task_counter += 1

    return tasks


def main():
    traces = [json.loads(l) for l in TRACES_PATH.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(traces)} traces.")

    tasks = extract_tasks_from_traces(traces)
    OUTPUT_PATH.write_text("\n".join(json.dumps(t) for t in tasks))

    hard_fails = sum(1 for t in tasks if t["difficulty"] == "hard")
    print(f"Extracted {len(tasks)} raw trace-derived tasks ({hard_fails} hard-fail) → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
