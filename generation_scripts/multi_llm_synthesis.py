#!/usr/bin/env python3
"""
Mode 3: Multi-LLM synthesis.
Claude Sonnet 4.6 authors 40 hard seeds anchored to failure taxonomy.
DeepSeek V3.2 generates 3 variations per seed.
All LLM calls traced via observability.traced_completion() → cost_log.csv + Langfuse.
Leakage prevention: multi_llm tasks are judged by Qwen3 (judge_filter.py).
"""

import json, os, re, sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import openai
from observability import traced_completion, flush_langfuse

OUTPUT_PATH = Path("generation_scripts/output/multi_llm_raw.jsonl")
SEEDS_PATH  = Path("generation_scripts/output/multi_llm_seeds.jsonl")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

FAILURE_TAXONOMY_SUMMARY = """
Tenacious-Bench targets these 7 failure dimensions:
1. signal_grounding: agent asserts signals it cannot verify (P006, P007, P008, P009)
2. tone_adherence: banned phrases, superlatives, word count >120 (P013, P014, P015)
3. bench_calibration: over-promises bench capacity (P010, P012, P041)
4. qualification_accuracy: pitches wrong ICP segment (P001, P003)
5. constraint_judgment: states low-confidence signals as facts (P007, P008)
6. scheduling_hygiene: fabricates slots or mishandles timezone (P026, P027)
7. escalation_decision: fails to flag multi-turn threads for human review (P017, P019)
"""

SEED_PROMPT = """You are designing evaluation tasks for a B2B sales agent benchmark.
The agent books engineering talent engagements for Tenacious Consulting.

{taxonomy}

Design {n} hard benchmark tasks targeting failure dimensions where subtle errors are easy to miss.
Each task must be:
- Realistic (plausible B2B hiring scenario, specific numbers/dates/signal values)
- Machine-verifiable (ground truth checkable by script, not human judgment)
- Challenging (the failure is non-obvious — not a simple banned-word check)
- Distinct: spread across all 7 dimensions (~5-6 tasks per dimension)

Output a JSON array of tasks, each with EXACTLY these fields:
{{
  "hiring_signal_brief": "...",
  "bench_summary": "...",
  "candidate_output": "...",
  "dimension_tested": "...",
  "failure_type": "...",
  "required_signal_refs": [],
  "banned_phrases": [],
  "required_cta": "calendar_link",
  "correct_qualification": "qualify"
}}

candidate_output must be 50-120 words. Use company names like NexaFlow, Orbis Systems, Vantage Labs, Cortex AI, Stratum Data, Apex Logic, Helix Ops.
"""


def make_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)


def _parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON array from LLM response, stripping code fences."""
    if "```" in raw:
        raw = re.sub(r'```(?:json)?\s*', '', raw).strip()
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
    return []


def generate_seeds(n: int = 40, batch_size: int = 10,
                   model: str = "anthropic/claude-sonnet-4.6") -> list[dict]:
    """Generate hard seeds with Claude Sonnet 4.6 in batches to avoid truncation."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    client = make_client(api_key)

    all_seeds: list[dict] = []
    n_batches = (n + batch_size - 1) // batch_size

    for batch_idx in range(n_batches):
        batch_n = min(batch_size, n - len(all_seeds))
        print(f"  Batch {batch_idx + 1}/{n_batches}: requesting {batch_n} seeds...")
        prompt = SEED_PROMPT.format(taxonomy=FAILURE_TAXONOMY_SUMMARY, n=batch_n)
        resp = traced_completion(
            client=client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            run_name="multi_llm_seed_generation",
            purpose=f"seed_gen batch={batch_idx} n={batch_n}",
            bucket="dataset_authoring",
        )
        raw = resp.choices[0].message.content.strip()
        seeds = _parse_json_array(raw)
        print(f"    Parsed {len(seeds)} seeds from batch {batch_idx + 1}")
        all_seeds.extend(seeds)

    return all_seeds


def generate_variations(seed: dict, seed_idx: int, n: int = 3,
                        model: str = "deepseek/deepseek-chat") -> list[dict]:
    """Generate variations of a seed using DeepSeek (different family from Claude seeds)."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    client = make_client(api_key)

    prompt = (
        f"Generate {n} variations of this benchmark task. Keep the dimension_tested and failure_type the same.\n"
        f"Vary: company size, segment (engineering/product/data/design), signal confidence values, and specific signal details.\n"
        f"Output a JSON array of {n} tasks with the same fields as the input.\n\n"
        f"Input task:\n{json.dumps(seed, indent=2)}"
    )

    resp = traced_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
        run_name="multi_llm_variation",
        purpose=f"variation seed_idx={seed_idx} dim={seed.get('dimension_tested', 'unknown')}",
        bucket="dataset_authoring",
    )
    raw = resp.choices[0].message.content.strip()
    return _parse_json_array(raw) or [seed]


def seeds_to_tasks(seeds: list[dict], start_id: int) -> list[dict]:
    """Convert raw seed dicts to full task schema."""
    BANNED_PHRASES = [
        "aggressive", "impressive momentum", "disruptive", "game-changer",
        "excited to", "thrilled to", "passionate about", "synergy",
    ]
    TONE_MARKERS = ["consultative", "evidence-grounded", "no superlatives", "concise", "prospect-first"]

    tasks = []
    for i, s in enumerate(seeds):
        brief = s.get("hiring_signal_brief", "")
        company_guess = brief.split()[0] if brief else f"Company-ML-{start_id + i}"

        task = {
            "task_id": f"TB-ML-{start_id + i:04d}",
            "source_mode": "multi_llm",
            "difficulty": "hard",
            "dimension": s.get("dimension_tested", "signal_grounding"),
            "input": {
                "hiring_signal_brief": brief,
                "bench_summary": s.get("bench_summary", "Tenacious bench: 7 Python/ML engineers available (full)."),
                "prior_thread": None,
                "prospect_metadata": {
                    "company": company_guess[:30],
                    "size_band": "51-200",
                    "segment": "engineering",
                    "ai_maturity_score": 3,
                    "signal_confidence": 0.7,
                },
            },
            "candidate_output": s.get("candidate_output", ""),
            "ground_truth": {
                "required_signal_refs": s.get("required_signal_refs", []),
                "banned_phrases": list(set(s.get("banned_phrases", []) + BANNED_PHRASES)),
                "required_cta": s.get("required_cta", "calendar_link"),
                "tone_markers": TONE_MARKERS,
                "correct_qualification": s.get("correct_qualification", "qualify"),
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
                "seed_probe_id": None,
                "failure_type": s.get("failure_type", ""),
                "judge_filter_score": None,
                "partition": None,
            },
        }
        tasks.append(task)
    return tasks


def main():
    print("Step 1: Generating seeds with Claude Sonnet 4.6...")
    seeds = generate_seeds(n=40)
    if not seeds:
        print("  WARNING: No seeds generated — check API key or model availability")
        return
    SEEDS_PATH.write_text("\n".join(json.dumps(s) for s in seeds))
    print(f"  Generated {len(seeds)} seeds")

    print("Step 2: Generating variations with DeepSeek V3.2...")
    all_variants = []
    for idx, seed in enumerate(seeds):
        dim = seed.get("dimension_tested", "?")
        print(f"  Seed {idx + 1}/{len(seeds)}: {dim}")
        variants = generate_variations(seed, seed_idx=idx, n=3)
        all_variants.extend(variants)
    print(f"  Generated {len(all_variants)} total (seeds + variations)")

    print("Step 3: Converting to task schema...")
    tasks = seeds_to_tasks(all_variants, start_id=1)

    OUTPUT_PATH.write_text("\n".join(json.dumps(t) for t in tasks))
    print(f"  Wrote {len(tasks)} raw multi-LLM tasks → {OUTPUT_PATH}")
    print("\nNext: run judge_filter.py on this output (use Qwen judge, NOT Claude)")

    flush_langfuse()


if __name__ == "__main__":
    main()
