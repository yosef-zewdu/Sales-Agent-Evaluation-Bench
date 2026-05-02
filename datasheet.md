# Tenacious-Bench v0.1 — Dataset Documentation

**Sources:** Gebru et al. (2021) §2 (Datasheets for Datasets) + Pushkarna et al. (2022) OFTEn framework

---

## Telescopic Summary (Executive Reader)

Tenacious-Bench v0.1 is a 200–300 task evaluation benchmark for Tenacious Consulting's B2B sales AI agent. It covers 7 failure dimensions identified through 41 production probes that revealed $248,419 in aggregate failure cost. All tasks are synthetic or redacted (no real prospect data), machine-verifiable by `scoring_evaluator.py`, and licensed CC-BY-4.0. The dataset is partitioned 50/30/20 (train/dev/held-out); the held-out set is sealed until the leaderboard is published. Built by Yosef Zewdu as part of 10Academy TRP1 Week 11.

---

## Periscopic Detail (Dataset Consumer)

### 1. Motivation  [Gebru §2.1]

- **Why built:** τ²-Bench retail (pass@1=0.7267) measures task completion on generic synthetic retail tasks. It cannot grade Tenacious-specific B2B sales agent behavior: no ICP classification rules, no signal confidence thresholds, no bench-state constraints, no 120-word cold email cap, no banned-phrase enforcement.
- **Problem scale:** 41 Week 10 production probes across 10 failure categories revealed $248,419 in aggregate annual failure cost. Signal over-claiming alone (P006–P009) costs $34,260/year at a 22% trigger rate.
- **Who built it:** Yosef Zewdu, 10Academy TRP1 Week 11, 2026-04-29.
- **Funding/compute:** 10Academy TRP1 program; Google Colab free T4. Total API budget: ≤$10.
- **Not a replacement for τ²-Bench:** designed as a domain-specific supplement targeting Tenacious failure modes that τ²-Bench cannot detect.

### 2. Composition  [Gebru §2.2]

| Attribute | Value |
|---|---|
| Total tasks (v0.1) | 218 (250 generated → 32 deduped out → 218 final) |
| Dimensions | 7 |
| Partitions | train 109 (50%) / dev 70 (32%) / held_out 39 (18%) |
| Source modes | trace_derived ~30%, programmatic ~30%, multi_llm ~25%, hand_authored ~15% |
| Language | English only |
| Sensitive data | None — all prospect data synthetic or redacted |
| Held-out status | Sealed until leaderboard published |

**7 Dimensions:**

| Dimension | Probe IDs | Description |
|---|---|---|
| signal_grounding | P006–P009, P033–P035 | Agent asserts signals it cannot verify |
| tone_adherence | P013–P016, P039–P040 | Banned phrases, superlatives, >120 words |
| bench_calibration | P010–P012, P041 | Over-promises bench capacity |
| qualification_accuracy | P001–P005, P036–P038 | Pitches wrong ICP segment |
| constraint_judgment | P007, P008 | States low-confidence signals as facts |
| scheduling_hygiene | P026–P028 | Fabricates slots or mishandles timezone |
| escalation_decision | P017–P019 | Fails to flag multi-turn threads for human review |

**Known gaps in v0.1:**
- Multi-thread leakage (P017–P019) coverage is limited — requires multi-turn infrastructure not yet built.
- Scheduling edge cases (P026–P028) partially covered; timezone-edge tasks not yet generated.

### 3. Collection  [Gebru §2.3]

**Four authoring modes:**

| Mode | Script | Source | Target share |
|---|---|---|---|
| Trace-derived | `generation_scripts/trace_derived.py` | `held_out_traces.jsonl` (57 entries from Week 10) | ~30% |
| Programmatic | `generation_scripts/programmatic.py` | `probe_library.py` (41 probes × slot combos) | ~30% |
| Multi-LLM synthesis | `generation_scripts/multi_llm_synthesis.py` | Claude Sonnet 4.6 seeds → DeepSeek V3.2 variations | ~25% |
| Hand-authored adversarial | `generation_scripts/output/hand_authored.jsonl` | 40 manually written edge-case tasks | ~15% |

**Preference leakage rotation policy (per-task):**

| Generator | Judge | Source modes covered | Leakage risk |
|---|---|---|---|
| Claude Sonnet 4.6 | DeepSeek V3.2 | multi_llm seeds | Low |
| DeepSeek V3.2 | Qwen3-235B | multi_llm variations | Low |
| DeepSeek V3.2 | DeepSeek V3.2 | trace_derived, programmatic, hand_authored | Low (no LLM generator for these) |
| N/A (human) | DeepSeek V3.2 | hand_authored | None |
| mixed | Claude Sonnet 4.6 | calibration spot-check (50 tasks) | Acceptable — one-time |

All per-task assignments logged in `generation_scripts/model_rotation_log.csv`.

### 4. Preprocessing / Cleaning / Labeling  [Gebru §2.4]

**Judge filter** (every generated task must pass before entering dataset):
- `input_coherence ≥ 3` — realistic, self-consistent B2B scenario
- `gt_verifiability ≥ 4` — ground truth fully automatable by script
- `rubric_clarity ≥ 3` — unambiguous which dimension is tested
- Bulk judging: DeepSeek V3.2 or Qwen3-235B (source-appropriate per leakage policy)
- Calibration: eval-tier (Claude Sonnet 4.6) spot-checks 50 tasks; Pearson r ≥ 0.80 required

**Deduplication** (`generation_scripts/dedup.py`):
- Cosine similarity < 0.85 on `hiring_signal_brief + candidate_output` TF-IDF vectors
- Method: numpy TF-IDF cosine (CPU-only; no PyTorch dependency)
- Result: 250 → 218 tasks (32 removed)

**Contamination checks** (before sealing held_out):
1. N-gram overlap: < 8-gram on input fields between held_out and train
2. Embedding similarity: cosine < 0.85 (TF-IDF cosine, numpy, CPU-only)
3. Time-shift: public signals (Crunchbase, layoffs.fyi) must cite documentable time windows

**Domain invariants enforced:**
- Cold email hard limit: 120 words (P015 invariant — hard fail above limit)
- Banned phrase list: 8 core phrases (aggressive, impressive momentum, disruptive, game-changer, excited to, thrilled to, passionate about, synergy)

**Inter-rater agreement:**
- 30-task double-label by same annotator (Day 3 + Day 4 without reference)
- Cohen's Kappa target ≥ 0.80 per dimension
- See `inter_rater_agreement.md` for results

### 5. Uses  [Gebru §2.5]

**Intended use:**
- Evaluating B2B sales AI agents on Tenacious-specific quality dimensions
- Preference training data for domain-specific judge/critic models (Path B)
- Diagnostic benchmark: identifying which failure dimensions an agent struggles with

**Not intended for:**
- Evaluating general-purpose LLMs on open-ended tasks
- Non-sales domains or non-Tenacious B2B contexts
- Non-English sales agents
- Grading human sales professionals
- Any use where synthetic prospect data could be mistaken for real prospect information

**Business case:**
- $248,419 aggregate probe cost; signal over-claiming (22% trigger rate, $34,260/year) is the primary target
- A trained judge catching 5pp more constraint violations saves ~$1,700/year at current trigger rates

**Quickstart:**
```bash
# Score a single task
python scoring_evaluator.py --task tenacious_bench_v0.1/dev/tasks.jsonl

# Run contamination check
python generation_scripts/contamination_check.py \
  --train tenacious_bench_v0.1/train/tasks.jsonl \
  --dev   tenacious_bench_v0.1/dev/tasks.jsonl \
  --held_out tenacious_bench_v0.1/held_out/tasks.jsonl
```

### 6. Distribution  [Gebru §2.6]

- **License:** CC-BY-4.0
- **HuggingFace URL:** [to be filled after Session 7 publication]
- **Held-out partition:** released post-leaderboard only; not committed to training scripts
- **Export restrictions:** none
- **Personal data:** none — all prospect data is synthetic or redacted
- **Format:** JSONL (one task per line), schema documented in `schema.json`

### 7. Maintenance  [Gebru §2.7]

- **Versioning policy:** `tenacious_bench_v0.1` → `v0.2` will add:
  - P017–P019 (multi-thread leakage): requires multi-turn conversation infrastructure
  - P026–P028 (scheduling edge cases): timezone-aware scheduling test harness
- **Contact:** yosefz@10academy.org
- **Erratum policy:** flag issues via GitHub Issues; patch releases tagged `v0.1.x`
- **Deprecation:** no planned deprecation; v0.2 extends rather than replaces v0.1
- **Update cadence:** tied to Tenacious production probe library updates

---

## Microscopic Specification (Researcher)

### Schema Fields

Full schema defined in `schema.json`. Key fields per task:

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Format: `TB-{SOURCE}-{NNNN}` (TR=trace, PG=programmatic, ML=multi_llm, HA=hand_authored) |
| `source_mode` | enum | trace_derived / programmatic / multi_llm / hand_authored |
| `difficulty` | enum | easy / medium / hard |
| `dimension` | string | One of 7 benchmark dimensions |
| `input.hiring_signal_brief` | string | Prospect context: company, signal, confidence, maturity |
| `input.bench_summary` | string | Tenacious bench state: count, skills, availability |
| `input.prior_thread` | string\|null | Prior email thread (null for cold email tasks) |
| `input.prospect_metadata` | object | company, size_band, segment, ai_maturity_score, signal_confidence |
| `candidate_output` | string | Agent output to score (may contain failures) |
| `ground_truth.required_signal_refs` | list[str] | Strings that must appear in output for signal_grounding |
| `ground_truth.banned_phrases` | list[str] | Phrases whose presence is a hard fail |
| `ground_truth.required_cta` | str\|null | "calendar_link" or null |
| `ground_truth.tone_markers` | list[str] | Tone dimensions for LLM tone scoring |
| `ground_truth.correct_qualification` | enum | qualify / disqualify / escalate |
| `rubric` | object | 5 dimensions × {weight, min_pass} |
| `metadata.seed_trace_id` | str\|null | Source trace ID (trace_derived tasks) |
| `metadata.seed_probe_id` | str\|null | Source probe ID |
| `metadata.judge_filter_score` | object\|null | {input_coherence, gt_verifiability, rubric_clarity, judge_model} |
| `metadata.partition` | enum | train / dev / held_out |

### Contamination Check Algorithm

```
1. N-gram: for each held_out task h, for each train task t:
   - Extract 8-grams from h.input + t.input
   - Flag if intersection is non-empty

2. Embedding: encode all tasks with all-MiniLM-L6-v2
   - For each held_out/train pair: cosine_sim(h_emb, t_emb) ≥ 0.85 → flag

3. Time-shift: for each task referencing Crunchbase/layoffs.fyi/LinkedIn/funding:
   - Require explicit date window (regex: YYYY-MM-DD, "in the last N days", "Q[1-4] YYYY")
   - Flag if missing
```

### Partition Logic

```python
h = int(hashlib.md5(f"{seed=42}{task_id}".encode()).hexdigest(), 16) % 100
partition = "train" if h < 50 else "dev" if h < 80 else "held_out"
```

### Rubric Weights

| Dimension | Weight | min_pass (1–5 scale) |
|---|---|---|
| signal_grounding | 0.25 | 3 |
| tone_adherence | 0.25 | 3 |
| bench_calibration | 0.20 | 3 |
| cta_hygiene | 0.15 | 4 |
| qualification_accuracy | 0.15 | 4 |

Total weighted score range: 0.0 – 5.0. Hard fail (score=0.0) if any banned phrase present, CTA missing, or word count >120.

### Model Rotation Log

Per-task `(generator_model, judge_model)` pairs logged in `generation_scripts/model_rotation_log.csv` with columns: `task_id, source_mode, generator_model, judge_model, leakage_risk`.

### Judge Filter Thresholds (derivation)

- `input_coherence ≥ 3`: rejects tasks where the hiring brief is internally contradictory or implausible
- `gt_verifiability ≥ 4` (stricter): a score of 3 implies partial human judgment needed — rejected to maintain machine-verifiability guarantee
- `rubric_clarity ≥ 3`: ensures each task tests one and only one dimension; ambiguous tasks dilute diagnostic value

### Reproducibility

- Partition seed: `seed=42` (hardcoded in `generation_scripts/partition.py`)
- All training/eval scripts log seed in filename: `training_run_seed42.log`
- `requirements.txt` pins all library versions
- `cost_log.csv` records every API call with timestamp, model, tokens, cost
