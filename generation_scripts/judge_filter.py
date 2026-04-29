#!/usr/bin/env python3
"""
LLM-as-a-judge quality filter for generated tasks.

Applies pointwise scoring on 3 dimensions; keeps tasks passing all thresholds.
Leakage prevention: generator ≠ judge per source_mode.
  - trace_derived / programmatic → DeepSeek V3.2 judge
  - multi_llm (Claude seeds)     → Qwen3 judge
  - hand_authored                → DeepSeek V3.2 judge

Falls back to heuristic scoring when OPENROUTER_API_KEY is not set.
Every live API call is traced in Langfuse with exact token counts and cost
written to cost_log.csv via observability.traced_completion().
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import openai
from observability import traced_completion, flush_langfuse

THRESHOLDS = {
    "input_coherence": 3,
    "gt_verifiability": 4,
    "rubric_clarity": 3,
}

JUDGE_MODEL_BY_SOURCE = {
    "trace_derived": "deepseek/deepseek-chat",
    "programmatic":  "deepseek/deepseek-chat",
    "multi_llm":     "qwen/qwen3-235b-a22b",
    "hand_authored": "deepseek/deepseek-chat",
}


def heuristic_score(task: dict) -> dict:
    """Offline fallback: score by checking structural completeness."""
    inp = task.get("input", {})
    gt = task.get("ground_truth", {})

    coherence = 4 if inp.get("hiring_signal_brief") and len(inp["hiring_signal_brief"]) > 30 else 2
    verifiability = 4 if (
        gt.get("banned_phrases") and gt.get("correct_qualification")
    ) else 2
    # Programmatic tasks are templates; rubric clarity is judged by dimension + ground_truth,
    # not by candidate_output (which is intentionally a placeholder until agent runs).
    cand = task.get("candidate_output", "")
    source_mode = task.get("source_mode", "")
    if source_mode == "programmatic":
        clarity = 4 if task.get("dimension") else 2
    else:
        clarity = 2 if "[TO BE GENERATED" in cand or "[AGENT OUTPUT MISSING" in cand else 4

    return {
        "input_coherence": coherence,
        "gt_verifiability": verifiability,
        "rubric_clarity": clarity,
        "reason": "heuristic (offline)",
        "judge_model": "heuristic",
    }


def judge_task(task: dict, client: openai.OpenAI | None) -> dict:
    if client is None:
        return heuristic_score(task)

    source_mode = task.get("source_mode", "programmatic")
    model = JUDGE_MODEL_BY_SOURCE.get(source_mode, "deepseek/deepseek-chat")

    # Truncate task for prompt — avoid huge token bills
    task_preview = {
        "task_id": task.get("task_id"),
        "source_mode": source_mode,
        "dimension": task.get("dimension"),
        "input": task.get("input", {}),
        "candidate_output": task.get("candidate_output", "")[:300],
        "ground_truth": task.get("ground_truth", {}),
    }

    prompt = f"""You are evaluating a benchmark task for a B2B sales-agent evaluation suite.
Score on three dimensions (1–5 each).

Task (truncated):
{json.dumps(task_preview, indent=2)[:1800]}

Score these:
1. input_coherence (1–5): Does the hiring signal brief form a realistic, coherent B2B scenario?
2. gt_verifiability (1–5): Can the ground_truth be checked automatically by a script with no human judgment?
3. rubric_clarity (1–5): Is it unambiguous which quality dimension this task is testing?

Respond with ONLY valid JSON:
{{"input_coherence": N, "gt_verifiability": N, "rubric_clarity": N, "reason": "one sentence"}}"""

    try:
        resp = traced_completion(
            client=client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            run_name="judge_filter",
            purpose=f"pointwise_judge task={task.get('task_id')} source={source_mode}",
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw)
    except Exception as e:
        scores = {
            "input_coherence": 3,
            "gt_verifiability": 3,
            "rubric_clarity": 3,
            "reason": f"parse error: {e}",
        }

    scores["judge_model"] = model
    return scores


def passes_filter(scores: dict) -> bool:
    return all(scores.get(dim, 0) >= threshold for dim, threshold in THRESHOLDS.items())


def main(input_files: list[str], output_path: str):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        print("Using OpenRouter (dev-tier) for judging.")
    else:
        client = None
        print("OPENROUTER_API_KEY not set — using heuristic scoring (offline mode).")

    all_tasks = []
    for f in input_files:
        lines = [l for l in Path(f).read_text().splitlines() if l.strip()]
        all_tasks.extend(json.loads(l) for l in lines)

    print(f"Filtering {len(all_tasks)} tasks...")
    passed, failed = [], []

    for i, task in enumerate(all_tasks):
        scores = judge_task(task, client)
        task["metadata"]["judge_filter_score"] = {
            "input_coherence":  scores["input_coherence"],
            "gt_verifiability": scores["gt_verifiability"],
            "rubric_clarity":   scores["rubric_clarity"],
            "judge_model":      scores.get("judge_model", "unknown"),
            "reason":           scores.get("reason", ""),
        }
        if passes_filter(scores):
            passed.append(task)
        else:
            failed.append({"task_id": task["task_id"], "scores": scores})

        if (i + 1) % 50 == 0:
            print(f"  Scored {i + 1}/{len(all_tasks)} ...")

    Path(output_path).write_text("\n".join(json.dumps(t) for t in passed))
    rejected_path = output_path.replace(".jsonl", "_rejected.json")
    Path(rejected_path).write_text(json.dumps(failed, indent=2))

    flush_langfuse()

    print(f"\nPassed: {len(passed)}  |  Rejected: {len(failed)}")
    print(f"→ {output_path}")
    print(f"→ {rejected_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: judge_filter.py <input1.jsonl> [input2.jsonl ...] <output.jsonl>")
        sys.exit(1)
    inputs = sys.argv[1:-1]
    output = sys.argv[-1]
    main(inputs, output)
