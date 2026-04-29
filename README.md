# Tenacious-Bench v0.1 — Sales Agent Evaluation Bench

A domain-specific benchmark and preference-tuned judge for evaluating a Tenacious sales agent against honesty, ICP classification, tone, and constraint-compliance dimensions that τ²-Bench cannot measure.

**TRP1 Challenge Week 11 · Path B: DPO/SimPO/ORPO preference-tuned judge/critic**

---

## Problem Statement

τ²-Bench retail (pass@1 = 0.7267 on 150 simulated tasks) grades whether a sales agent *completes* a task — books a call, sends an email, routes a lead. It says nothing about *how*. An agent can score 1.0 on task completion while:

- Fabricating a funding round (signal over-claiming, P006–P009, trigger_rate ≈ 0.22, cost = $34,260/year)
- Pitching an S4 AI-maturity product to a company with `ai_maturity_score = 1` (ICP misclassification, P001–P005)
- Exceeding the 120-word cold-email hard limit (tone drift, P015)
- Leaking FSM state across prospects (multi-thread leakage, P017–P019)

Tenacious-Bench v0.1 covers all 10 failure categories (41 probes) with machine-verifiable scoring. A LoRA-adapted judge trained via SimPO/ORPO is deployed as a rejection-sampling gate in front of the Week 10 generation pipeline, catching constraint violations at lower per-task cost than the full 3-stage chain.

---

## Current Status (Interim — 2026-04-29)

### Complete (Acts I + II)

| Artifact | Status |
|---|---|
| [audit_memo.md](audit_memo.md) | Done — 600-word gap analysis, 8 probe IDs, 5 trace IDs |
| [schema.json](schema.json) | Done — full task schema with 3 example tasks |
| [scoring_evaluator.py](scoring_evaluator.py) | Done — machine-verifiable scorer, runs against example tasks |
| [methodology.md](methodology.md) | Done — Path B declaration, contamination protocol, partitioning plan |
| [generation_scripts/](generation_scripts/) | Done — all 4 authoring modes implemented |
| [synthesis_memos/](synthesis_memos/) | 2 of 8 memos complete (LLM-as-judge, preference leakage) |
| [cost_log.csv](cost_log.csv) | Tracking — all API charges logged |
| [week10_artifacts/](week10_artifacts/) | Done — symlinked from Conversion-Engine |

### In Progress (Acts III + IV — due Saturday 21:00 UTC)

- `tenacious_bench_v0.1/` — partition pass (train/dev/held-out) pending dedup + contamination gate
- `datasheet.md` — Gebru + Pushkarna full datasheet
- `inter_rater_agreement.md` — 30-task hand-label agreement matrix
- `contamination_check.json` — n-gram + embedding + time-shift results
- `training_data/preference_pairs.jsonl` — 500–1,500 (chosen, rejected) pairs
- `training/` — SimPO/ORPO training script, hyperparams, loss logs
- `ablations/` — Delta A/B/C + cost-Pareto table
- Remaining 6 synthesis memos
- `evidence_graph.json`, `memo.pdf`, blog post, demo video

---

## Setup

**Requirements:**
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

**Install:**

```bash
# With uv (recommended)
uv sync

# Or with pip
pip install -e .
```

**Key runtime dependencies** (see [pyproject.toml](pyproject.toml)):
- `openai` — OpenRouter API calls for multi-LLM synthesis and judge filtering
- `langfuse` — observability for training runs and ablation conditions
- `python-dotenv` — environment variable management

**Environment variables** (create a `.env` file at repo root):
```
OPENROUTER_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## Quickstart

**Validate a task against the schema and run the scorer:**

```bash
# Run scoring evaluator against the built-in example tasks
uv run python scoring_evaluator.py --task schema.json

# Or point at a specific task file
uv run python scoring_evaluator.py --task tenacious_bench_v0.1/dev/example.json
```

**Generate tasks (all 4 authoring modes):**

```bash
# Mode 1: trace-derived tasks from Week 10 execution traces
uv run python generation_scripts/trace_derived.py

# Mode 2: programmatic sweep (41 probes × slot combinations)
uv run python generation_scripts/programmatic.py

# Mode 3: multi-LLM synthesis via OpenRouter
uv run python generation_scripts/multi_llm_synthesis.py

# Filter generated tasks through LLM-as-judge quality gate
uv run python generation_scripts/judge_filter.py

# Dedup + contamination check
uv run python generation_scripts/dedup.py
uv run python generation_scripts/contamination_check.py \
  --train tenacious_bench_v0.1/train/ \
  --dev tenacious_bench_v0.1/dev/ \
  --held_out tenacious_bench_v0.1/held_out/
```

**Build preference pairs and train the judge (Path B):**

```bash
# Build (chosen, rejected) pairs from Week 10 traces + bench tasks
uv run python training_data/prepare_training_data.py \
  --train_partition tenacious_bench_v0.1/train/ \
  --traces week10_artifacts/held_out_traces.jsonl \
  --probes week10_artifacts/probe_library.py \
  --output training_data/preference_pairs.jsonl

# Train the LoRA judge (SimPO/ORPO via Unsloth + TRL)
uv run python training/train_judge.py --config training/hyperparams.yaml

# Run ablations with paired bootstrap significance test
uv run python ablations/bootstrap_test.py \
  --results ablations/ablation_results.json \
  --alpha 0.05
```

---

## Directory Structure

```
sales-agent-evaluation-bench/
├── README.md                        # This file
├── SPECS.md                         # Detailed Path B implementation spec
├── audit_memo.md                    # Act I: 600-word gap audit (τ²-Bench vs Tenacious-Bench)
├── schema.json                      # Act I: Tenacious-Bench task schema (JSON Schema draft-07)
├── scoring_evaluator.py             # Act I: machine-verifiable scorer (no human in loop)
├── methodology.md                   # Path B declaration, partitioning, contamination protocol
├── methodology_rationale.md         # Act III: path rationale citing papers + Week 10 trace IDs
├── cost_log.csv                     # Every API + compute charge (timestamp, bucket, purpose)
├── pyproject.toml                   # Python project config and dependencies
│
├── tenacious_bench_v0.1/
│   ├── train/                       # 50% training partition (sealed from eval scripts)
│   ├── dev/                         # 30% public dev partition
│   └── held_out/                    # 20% sealed held-out (gitignored, released post-leaderboard)
│
├── generation_scripts/
│   ├── trace_derived.py             # Mode 1: tasks extracted from held_out_traces.jsonl
│   ├── programmatic.py              # Mode 2: 41 probe templates × slot-variable sweep
│   ├── multi_llm_synthesis.py       # Mode 3: OpenRouter multi-model synthesis pipeline
│   ├── judge_filter.py              # LLM-as-judge quality gate (pointwise + pairwise)
│   ├── dedup.py                     # Embedding dedup + n-gram overlap check
│   ├── contamination_check.py       # Final contamination verification (n-gram, cosine, time-shift)
│   ├── partition.py                 # 50/30/20 stratified split
│   └── output/                      # Intermediate generation outputs (raw + filtered)
│
├── training_data/
│   ├── preference_pairs.jsonl       # (chosen, rejected) pairs for SimPO/ORPO training
│   └── prepare_training_data.py     # Builds pairs from bench + trace fixes
│
├── training/
│   ├── train_judge.py               # SimPO or ORPO training (Unsloth + TRL)
│   ├── hyperparams.yaml             # Pinned hyperparameters
│   └── training_run.log             # Loss curves + wall time
│
├── ablations/
│   ├── ablation_results.json        # Delta A, B, C + cost-Pareto table
│   ├── held_out_traces.jsonl        # Scoring traces from held-out pass
│   └── bootstrap_test.py           # Paired bootstrap significance test
│
├── synthesis_memos/
│   ├── llm_as_judge_survey.md       # Done — Gu et al. 2024–2025
│   ├── preference_leakage.md        # Done — Li et al. 2025
│   └── [6 more memos pending]       # See Deliverables section below
│
├── week10_artifacts/                # Symlinks into Conversion-Engine (source of truth)
│   ├── probe_library.md             # 41 probes across 10 failure categories
│   ├── probe_library.py             # Parseable Probe dataclass instances
│   ├── failure_taxonomy.md          # 10 failure categories with business costs
│   ├── target_failure_mode.md       # Signal over-claiming root-cause analysis
│   ├── held_out_traces.jsonl        # 57 execution traces for task authoring
│   ├── ablation_results.json        # Baseline/Mechanism/Auto-Opt scores (do not re-run)
│   └── evidence_graph.json          # 16 numeric claims + 7 design decisions → sources
│
└── papers/                          # PDFs for synthesis memo reading list
    ├── common/                      # 4 common papers (all paths)
    └── path-b/                      # 4 Path B papers (DPO, SimPO/ORPO, Prometheus-2, leakage)
```

---

## Key Artifacts

| Artifact | Description | Link |
|---|---|---|
| Audit memo | Gap analysis: what τ²-Bench cannot measure and why | [audit_memo.md](audit_memo.md) |
| Task schema | JSON Schema for every Tenacious-Bench task | [schema.json](schema.json) |
| Scorer | Machine-verifiable Python scorer | [scoring_evaluator.py](scoring_evaluator.py) |
| Methodology | Path B declaration, partitioning, leakage controls | [methodology.md](methodology.md) |
| LLM-as-judge memo | Synthesis of Gu et al. judge survey | [synthesis_memos/llm_as_judge_survey.md](synthesis_memos/llm_as_judge_survey.md) |
| Preference leakage memo | Synthesis of Li et al. 2025 | [synthesis_memos/preference_leakage.md](synthesis_memos/preference_leakage.md) |
| Week 10 probes | 41 probes, 10 categories, parseable Python | [week10_artifacts/probe_library.py](week10_artifacts/probe_library.py) |
| Week 10 traces | 57 execution traces (source of rejected preference pairs) | [week10_artifacts/held_out_traces.jsonl](week10_artifacts/held_out_traces.jsonl) |

---

## Baseline Numbers (from Week 10 — do not re-derive)

| Metric | Value |
|---|---|
| τ²-Bench retail pass@1 | 0.7267 (95% CI: [0.6504, 0.7917]) |
| Mechanism pass@1 (signal over-claiming probes) | 0.95 (95% CI: [0.90, 0.99]) |
| Baseline pass@1 (same probe set) | 0.80 (95% CI: [0.72, 0.87]) |
| Mechanism vs. Baseline Δ | +0.15, p=0.0335 |
| Signal over-claiming cost (P006–P009) | $34,260/year, trigger_rate=0.22 |
| Avg cost per task | $0.0199 |

**Delta A target for trained judge:** ≥ +0.05 over baseline (0.80 → ≥ 0.85) on Tenacious-Bench held-out, p < 0.05 paired bootstrap.

---

## What's Next (Acts III + IV)

1. **Partition + seal held-out** — run all 3 contamination checks (n-gram, embedding cosine, time-shift), then gitignore `tenacious_bench_v0.1/held_out/`
2. **Datasheet + inter-rater agreement** — Gebru + Pushkarna full datasheet; 30-task hand-label matrix
3. **Preference pairs** — extract rejected outputs from P006–P009 traces; rewrite chosen side using different model family (preference leakage prevention)
4. **Train judge** — SimPO or ORPO on Qwen 3.5 0.8B/2B backbone via Unsloth; max 90-minute wall time on Colab T4
5. **Ablations** — Delta A (vs. baseline), Delta B (vs. prompt-only judge), Delta C (vs. τ²-Bench retail)
6. **Remaining synthesis memos** — 6 memos: synthetic data best practices, datasheets, contamination survey, DPO, SimPO/ORPO, Prometheus-2
7. **Evidence graph, memo.pdf, blog post, demo video**

---

## Budget

Total budget: **$10**. Dev-tier models (OpenRouter Qwen3/DeepSeek) on Days 2–3 only. Eval-tier (Claude Sonnet 4.6) reserved for the final held-out pass. All charges logged to [cost_log.csv](cost_log.csv).

---

## License

Dataset: CC-BY-4.0. Code: MIT.
