#!/usr/bin/env python3
"""Machine-verifiable scoring evaluator for Tenacious-Bench v0.1.

Usage:
  python scoring_evaluator.py --task path/to/task.json
  python scoring_evaluator.py --task path/to/task.json --output "agent output string"
  python scoring_evaluator.py --batch path/to/tasks_dir/  # score all *.json in dir
"""

import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import argparse
import sys
from pathlib import Path
from typing import Optional

# ── global constants ──────────────────────────────────────────────────────────

GLOBAL_BANNED_PHRASES = [
    "aggressive", "impressive momentum", "disruptive", "game-changer",
    "excited to", "thrilled", "passionate about", "synergy",
    "incredible journey", "love to join", "lead the market",
    "funding momentum", "exciting growth",
]

TENACIOUS_TONE_MARKERS = [
    "consultative",
    "evidence-grounded",
    "no superlatives",
    "concise",
    "prospect-first",
]

COLD_EMAIL_WORD_LIMIT = 120  # P015 invariant — hard fail if exceeded


# ── hard-fail checks ──────────────────────────────────────────────────────────

def check_banned_phrases(output: str, banned_list: list) -> tuple:
    """Return (passed: bool, violations: list[str]). passed=False is a hard fail."""
    output_lower = output.lower()
    violations = [p for p in banned_list if p.lower() in output_lower]
    return len(violations) == 0, violations


def check_cta_hygiene(output: str, required_cta: Optional[str]) -> bool:
    """Return True if the CTA requirement is met."""
    if required_cta is None:
        return True
    if required_cta == "calendar_link":
        return bool(re.search(
            r'https?://\S+|cal\.com|calendly\.com|schedule\s+a\s+call|book\s+a\s+time',
            output, re.I
        ))
    return True


def check_word_count(output: str, max_words: int = COLD_EMAIL_WORD_LIMIT) -> tuple:
    """Return (passed: bool, count: int). Cold emails must be ≤120 words (P015)."""
    count = len(output.split())
    return count <= max_words, count


# ── graded checks ─────────────────────────────────────────────────────────────

def check_signal_refs(output: str, required_refs: list) -> float:
    """Return coverage fraction (0.0–1.0) of required signal references."""
    if not required_refs:
        return 1.0
    output_lower = output.lower()
    covered = sum(1 for ref in required_refs if ref.lower() in output_lower)
    return covered / len(required_refs)


def check_qualification(output: str, correct_qualification: str) -> bool:
    """Return True if output is consistent with the expected ICP qualification decision."""
    output_lower = output.lower()
    if correct_qualification == "qualify":
        disqualifiers = ["not a fit", "don't think", "not the right", "pass on", "not interested"]
        return not any(d in output_lower for d in disqualifiers)
    elif correct_qualification == "disqualify":
        # For disqualify tasks the agent output should decline / not pitch
        hard_qualifiers = ["great fit", "perfect match", "would love to", "excited to help"]
        return not any(q in output_lower for q in hard_qualifiers)
    elif correct_qualification == "escalate":
        escalation_signals = [
            "flagging for review", "human review", "need to discuss",
            "complex situation", "escalate",
        ]
        return any(e in output_lower for e in escalation_signals)
    return True


def check_bench_calibration(output: str, bench_summary: str) -> float:
    """
    Return a score 1.0 or 4.0 based on whether the output over-commits given bench state.
    Thin/empty bench: any language guaranteeing a specific headcount is a hard over-commitment.
    """
    bench_lower = bench_summary.lower()
    if "thin" in bench_lower or "empty" in bench_lower:
        over_commitment_patterns = [
            r'\b\d+\s+engineers?\b',  # citing a headcount number
            r'guarantee\b',
            r"definitely have",
            r"we have \d+",
        ]
        output_lower = output.lower()
        for pat in over_commitment_patterns:
            if re.search(pat, output_lower):
                return 1.0
    return 4.0


def llm_tone_score(output: str, tone_markers: list, model: str = "deepseek/deepseek-chat") -> list:
    """
    Score output on each tone marker (1–5 each) using a dev-tier LLM via OpenRouter.
    Falls back to a heuristic if OPENROUTER_API_KEY is not set.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return _heuristic_tone_score(output, tone_markers)

    try:
        import openai
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        scores = []
        for marker in tone_markers:
            prompt = (
                f"Score the following sales email on the tone dimension '{marker}' from 1 (poor) to 5 (excellent).\n"
                f"Reply with ONLY a single integer 1-5.\n\n"
                f"Email:\n{output}"
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
            )
            raw = resp.choices[0].message.content.strip()
            try:
                scores.append(max(1, min(5, int(raw))))
            except ValueError:
                scores.append(3)
        return scores
    except Exception as e:
        print(f"[WARNING] LLM tone scoring failed ({e}). Using heuristic fallback.", file=sys.stderr)
        return _heuristic_tone_score(output, tone_markers)


def _heuristic_tone_score(output: str, tone_markers: list) -> list:
    """
    Rule-based tone scoring for offline / CI use.
    Each marker gets 1–5 based on simple surface features.
    """
    output_lower = output.lower()
    word_count = len(output.split())

    scores = []
    for marker in tone_markers:
        if marker == "concise":
            if word_count <= 80:
                scores.append(5)
            elif word_count <= 120:
                scores.append(4)
            elif word_count <= 160:
                scores.append(3)
            else:
                scores.append(1)
        elif marker == "no superlatives":
            superlatives = ["best", "greatest", "most", "incredible", "amazing", "fantastic", "thrilled", "excited"]
            hits = sum(1 for s in superlatives if s in output_lower)
            scores.append(max(1, 5 - hits))
        elif marker == "evidence-grounded":
            evidence_signals = [
                r'\d+\s+role', r'\d+\s+engineer', r'\$\d+', r'raised', r'series [a-d]',
                r'\d+\s+days?', r'\d+\s+months?', r'crunchbase', r'linkedin',
            ]
            hits = sum(1 for p in evidence_signals if re.search(p, output_lower))
            scores.append(min(5, 2 + hits))
        elif marker == "consultative":
            consultative_signals = ["worth a", "would it make sense", "curious if", "open to", "happy to"]
            hits = sum(1 for s in consultative_signals if s in output_lower)
            pitch_blast = ["we can help", "we have the solution", "our product", "our platform"]
            misses = sum(1 for s in pitch_blast if s in output_lower)
            scores.append(max(1, min(5, 3 + hits - misses)))
        elif marker == "prospect-first":
            i_statements = len(re.findall(r'\bI\b|\bwe\b|\bour\b', output))
            you_statements = len(re.findall(r'\byou\b|\byour\b', output_lower))
            if you_statements > i_statements:
                scores.append(5)
            elif you_statements == i_statements:
                scores.append(3)
            else:
                scores.append(2)
        else:
            scores.append(3)

    return scores


# ── main scoring function ─────────────────────────────────────────────────────

def score_task(task: dict, agent_output: Optional[str] = None, tone_model: str = "deepseek/deepseek-chat") -> dict:
    """
    Score a Tenacious-Bench task.

    Args:
        task: Full task dict matching schema.json.
        agent_output: If provided, scores this string. Otherwise scores task["candidate_output"].
        tone_model: OpenRouter model slug for tone scoring (dev-tier only).

    Returns:
        {
          "total": float,           # weighted score 0.0–5.0
          "breakdown": dict,        # per-dimension scores
          "hard_fail": bool,
          "hard_fail_reasons": list,
          "pass_at_1": bool         # True if total >= 3.5 and no hard fail
        }
    """
    output = agent_output if agent_output is not None else task["candidate_output"]
    gt = task["ground_truth"]
    rubric = task["rubric"]
    is_cold_email = task["input"].get("prior_thread") is None

    hard_fail_reasons = []

    # ── hard fails ────────────────────────────────────────────────────────────

    # Merge task-level banned phrases with global list (deduplicated)
    combined_banned = list({
        p.lower() for p in (gt.get("banned_phrases", []) + GLOBAL_BANNED_PHRASES)
    })
    phrases_ok, violations = check_banned_phrases(output, combined_banned)
    if not phrases_ok:
        hard_fail_reasons.append(f"Banned phrases detected: {violations}")

    cta_ok = check_cta_hygiene(output, gt.get("required_cta"))
    if not cta_ok:
        hard_fail_reasons.append("Missing required CTA (calendar_link)")

    if is_cold_email:
        wc_ok, wc = check_word_count(output)
        if not wc_ok:
            hard_fail_reasons.append(f"Cold email exceeds {COLD_EMAIL_WORD_LIMIT}-word limit: {wc} words (P015)")

    if hard_fail_reasons:
        return {
            "total": 0.0,
            "breakdown": {},
            "hard_fail": True,
            "hard_fail_reasons": hard_fail_reasons,
            "pass_at_1": False,
        }

    # ── graded dimensions ─────────────────────────────────────────────────────

    signal_raw = check_signal_refs(output, gt.get("required_signal_refs", []))
    signal_score = round(signal_raw * 5, 2)  # scale 0–1 → 1–5

    tone_scores = llm_tone_score(output, gt.get("tone_markers", TENACIOUS_TONE_MARKERS), model=tone_model)
    tone_avg = round(sum(tone_scores) / len(tone_scores), 2) if tone_scores else 3.0

    qual_ok = check_qualification(output, gt.get("correct_qualification", "qualify"))
    qual_score = 5.0 if qual_ok else 1.0

    bench_score = check_bench_calibration(output, task["input"].get("bench_summary", ""))

    breakdown = {
        "signal_grounding":       signal_score,
        "tone_adherence":         tone_avg,
        "bench_calibration":      bench_score,
        "cta_hygiene":            5.0,  # already passed hard check above
        "qualification_accuracy": qual_score,
    }

    weights = {k: rubric[k]["weight"] for k in rubric if k in breakdown}
    total = round(sum(breakdown[dim] * weights.get(dim, 0) for dim in breakdown), 3)

    return {
        "total": total,
        "breakdown": breakdown,
        "hard_fail": False,
        "hard_fail_reasons": [],
        "pass_at_1": total >= 3.5,
    }


# ── batch scoring ─────────────────────────────────────────────────────────────

def score_batch(tasks_dir: str, tone_model: str = "deepseek/deepseek-chat") -> dict:
    """Score all *.json task files in a directory. Returns aggregate stats."""
    results = []
    for path in sorted(Path(tasks_dir).glob("*.json")):
        task = json.loads(path.read_text())
        # Schema files contain an "examples" array — skip them
        if "examples" in task and "$schema" in task:
            for example in task.get("examples", []):
                r = score_task(example, tone_model=tone_model)
                r["task_id"] = example.get("task_id", str(path))
                results.append(r)
            continue
        r = score_task(task, tone_model=tone_model)
        r["task_id"] = task.get("task_id", str(path))
        results.append(r)

    if not results:
        return {"error": f"No tasks found in {tasks_dir}"}

    pass_count = sum(1 for r in results if r["pass_at_1"])
    hard_fail_count = sum(1 for r in results if r["hard_fail"])
    avg_total = round(sum(r["total"] for r in results) / len(results), 3)

    return {
        "n_tasks": len(results),
        "pass_at_1": round(pass_count / len(results), 4),
        "hard_fail_rate": round(hard_fail_count / len(results), 4),
        "avg_total_score": avg_total,
        "per_task": results,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tenacious-Bench v0.1 scoring evaluator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Path to a single task JSON file")
    group.add_argument("--batch", help="Path to a directory of task JSON files")
    parser.add_argument("--output", default=None, help="Agent output string (overrides candidate_output in task)")
    parser.add_argument("--tone-model", default="deepseek/deepseek-chat",
                        help="OpenRouter model slug for tone scoring (default: deepseek/deepseek-chat)")
    args = parser.parse_args()

    if args.task:
        task_path = Path(args.task)
        if not task_path.exists():
            print(f"Error: {task_path} not found", file=sys.stderr)
            sys.exit(1)
        raw = json.loads(task_path.read_text())
        # If the file is the schema (has $schema key and examples array), score the examples
        if "$schema" in raw and "examples" in raw:
            print(f"Detected schema file with {len(raw['examples'])} examples — scoring all examples.\n")
            for example in raw["examples"]:
                result = score_task(example, args.output, tone_model=args.tone_model)
                print(f"Task {example['task_id']}:")
                print(json.dumps(result, indent=2))
                print()
        else:
            result = score_task(raw, args.output, tone_model=args.tone_model)
            print(json.dumps(result, indent=2))
    else:
        result = score_batch(args.batch, tone_model=args.tone_model)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
