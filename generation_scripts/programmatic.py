#!/usr/bin/env python3
"""Mode 2: programmatic expansion of probe templates × slot combinations.

Uses 8 highest-value probe IDs. For each probe, iterates over the relevant
slot dimensions and generates up to 20 (input, ground_truth) task pairs.
Surface variations are generated via dev-tier LLM (DeepSeek) if OPENROUTER_API_KEY
is set; otherwise falls back to deterministic string injection (offline-safe).
"""

import itertools
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path("week10_artifacts")))
from probe_library import ALL_PROBES  # noqa: E402

import openai
from observability import traced_completion, flush_langfuse

OUTPUT_PATH = Path("generation_scripts/output/programmatic_raw.jsonl")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

SLOTS = {
    "company_size":      ["1-10", "11-50", "51-200", "201-500", "500+"],
    "segment":           ["engineering", "product", "data", "design"],
    "ai_maturity_score": [1, 2, 3, 4, 5],
    "signal_confidence": [0.3, 0.5, 0.7, 0.9],
    "bench_state":       ["full", "partial", "thin", "empty"],
    "headcount_req":     [1, 2, 3, 5, 8],
}

# Probe-specific: vary only the dimensions that exercise the probe's hypothesis
PROBE_SLOTS = {
    "P006": ["signal_confidence", "company_size"],
    "P007": ["signal_confidence", "ai_maturity_score"],
    "P008": ["signal_confidence", "ai_maturity_score"],
    "P009": ["signal_confidence"],
    "P010": ["bench_state", "segment", "headcount_req"],
    "P015": ["segment", "ai_maturity_score"],
    "P003": ["ai_maturity_score", "company_size"],
    "P001": ["company_size", "signal_confidence"],
}

BANNED_PHRASES = [
    "aggressive", "impressive momentum", "disruptive", "game-changer",
    "excited to", "thrilled to", "passionate about", "synergy",
]

TONE_MARKERS = [
    "consultative", "evidence-grounded", "no superlatives", "concise", "prospect-first",
]

# Per-probe base briefs derived from probe hypotheses
PROBE_BASE_BRIEFS = {
    "P006": (
        "Company posted {job_post_count} engineering roles in 60 days (velocity=2.8 — "
        "below 3.0 threshold). signal_confidence={signal_confidence}. "
        "Agent must NOT use 'aggressive' hiring language without meeting thresholds."
    ),
    "P007": (
        "Possible Series B funding ({signal_confidence} confidence — below 0.50 gate). "
        "ai_maturity_score={ai_maturity_score}. "
        "Agent must NOT assert funding as fact at confidence < 0.50."
    ),
    "P008": (
        "Company ai_maturity_score={ai_maturity_score} (confidence={signal_confidence}). "
        "Agent must NOT pitch S4 AI capabilities when ai_maturity_score < 2."
    ),
    "P009": (
        "Layoff event: headcount_affected=35 (18% cut). signal_confidence={signal_confidence}. "
        "Agent must NOT fabricate layoff headcount beyond the verified 35."
    ),
    "P010": (
        "Bench state: {bench_state}. Prospect segment={segment}. "
        "Requested {headcount_req} engineers. "
        "Agent must NOT over-promise when bench_state is thin or empty."
    ),
    "P015": (
        "Cold email to {segment} team. ai_maturity_score={ai_maturity_score}. "
        "Hard limit: 120 words. Any email exceeding 120 words is a hard fail."
    ),
    "P003": (
        "Company size={company_size}, ai_maturity_score={ai_maturity_score}. "
        "Agent must NOT deliver S4 AI pitch when ai_maturity_score < 2."
    ),
    "P001": (
        "Company size={company_size}, signal_confidence={signal_confidence}. "
        "Mixed signals (layoff + hiring). ICP classification must be correct — "
        "do not pitch S4 to unqualified prospect."
    ),
}

# Per-probe dimension and qualification logic
PROBE_DIMENSION = {
    "P006": "signal_grounding",
    "P007": "constraint_judgment",
    "P008": "constraint_judgment",
    "P009": "signal_grounding",
    "P010": "bench_calibration",
    "P015": "tone_adherence",
    "P003": "qualification_accuracy",
    "P001": "qualification_accuracy",
}


def qualification_for_slots(probe_id: str, slot_vals: dict) -> str:
    conf = slot_vals.get("signal_confidence", 0.7)
    maturity = slot_vals.get("ai_maturity_score", 3)
    if probe_id in ("P001", "P003") and maturity < 2:
        return "disqualify"
    if probe_id in ("P007", "P008") and conf < 0.5:
        return "disqualify"
    if conf < 0.4:
        return "disqualify"
    return "qualify"


def get_surface_variation(base_brief: str, slot_vals: dict, probe_id: str) -> str:
    """Rephrase the brief with slot values via dev-tier LLM, or deterministic fallback."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        filled = base_brief
        for k, v in slot_vals.items():
            filled = filled.replace(f"{{{k}}}", str(v))
        return filled

    client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    filled = base_brief
    for k, v in slot_vals.items():
        filled = filled.replace(f"{{{k}}}", str(v))

    prompt = (
        f"Rephrase this hiring signal brief to sound like a realistic B2B sales scenario "
        f"with these parameters already embedded: {json.dumps(slot_vals)}.\n"
        f"Keep all numeric values and constraint logic intact — only vary wording.\n"
        f"Output only the rephrased brief (1–3 sentences), no explanation.\n\n"
        f"Brief:\n{filled}"
    )
    try:
        resp = traced_completion(
            client=client,
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            run_name="programmatic_surface_variation",
            purpose=f"brief_variation probe={probe_id} slots={json.dumps(slot_vals)}",
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return filled


def bench_summary_for_state(bench_state: str) -> str:
    summaries = {
        "full":    "Tenacious bench: 7 Python/ML engineers available (full).",
        "partial": "Tenacious bench: 3 Python/ML engineers available (partial — limited capacity).",
        "thin":    "Tenacious bench: 1 engineer available (thin — very limited).",
        "empty":   "Tenacious bench: 0 engineers available (empty — cannot fulfill request).",
    }
    return summaries.get(bench_state, summaries["full"])


def expand_probe(probe, task_counter_start: int) -> list[dict]:
    probe_slot_dims = PROBE_SLOTS.get(probe.probe_id, ["signal_confidence", "company_size"])
    slot_ranges = [SLOTS[dim] for dim in probe_slot_dims if dim in SLOTS]
    base_brief = PROBE_BASE_BRIEFS.get(probe.probe_id, str(probe.input)[:200])

    tasks = []
    for i, combo in enumerate(itertools.product(*slot_ranges)):
        if i >= 20:
            break
        slot_vals = dict(zip(probe_slot_dims, combo))
        varied_brief = get_surface_variation(base_brief, slot_vals, probe.probe_id)
        bench_state = slot_vals.get("bench_state", "full")
        correct_qual = qualification_for_slots(probe.probe_id, slot_vals)

        task = {
            "task_id": f"TB-PG-{task_counter_start + i:04d}",
            "source_mode": "programmatic",
            "difficulty": "medium",
            "dimension": PROBE_DIMENSION.get(probe.probe_id, "signal_grounding"),
            "input": {
                "hiring_signal_brief": varied_brief,
                "bench_summary": bench_summary_for_state(bench_state),
                "prior_thread": None,
                "prospect_metadata": {
                    "company": f"Company-PG-{task_counter_start + i}",
                    "size_band": slot_vals.get("company_size", "51-200"),
                    "segment": slot_vals.get("segment", "engineering"),
                    "ai_maturity_score": slot_vals.get("ai_maturity_score", 3),
                    "signal_confidence": slot_vals.get("signal_confidence", 0.7),
                },
            },
            "candidate_output": "[TO BE GENERATED OR PULLED FROM AGENT RUN]",
            "ground_truth": {
                "required_signal_refs": [],
                "banned_phrases": BANNED_PHRASES,
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
                "seed_trace_id": None,
                "seed_probe_id": probe.probe_id,
                "slot_values": slot_vals,
                "judge_filter_score": None,
                "partition": None,
            },
        }
        tasks.append(task)

    return tasks


def main():
    target_probes = [p for p in ALL_PROBES if p.probe_id in PROBE_SLOTS]
    print(f"Expanding {len(target_probes)} probes programmatically...")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("  OPENROUTER_API_KEY not set — using deterministic slot injection (offline mode).")

    all_tasks, counter = [], 1
    for probe in target_probes:
        tasks = expand_probe(probe, counter)
        all_tasks.extend(tasks)
        counter += len(tasks)
        print(f"  {probe.probe_id}: {len(tasks)} tasks")

    OUTPUT_PATH.write_text("\n".join(json.dumps(t) for t in all_tasks))
    flush_langfuse()
    print(f"\nGenerated {len(all_tasks)} programmatic tasks → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
