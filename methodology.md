
## Path Declaration

**Path B — Preference-tuned judge / critic**

Declared: 2026-04-28

---

## Justification: Why Path B, Grounded in Week 10 Evidence

Path B is chosen because the dominant Week 10 failure mode is **inconsistency on constraint detection**, not generation quality. This distinction matters: Path A (generation-quality judge) would target outputs that are fluent but weak; Path C (trajectory failures) would require multi-step rollback. Path B targets a more specific and higher-cost pattern — the agent produces output that *appears* valid but violates a signal-grounding or honesty constraint it cannot self-detect. A preference-tuned judge deployed as a rejection-sampling gate addresses this at lower per-task cost than re-running the full 3-stage Researcher→Closer→ToneGuard chain.

Three Week 10 traces establish this root cause directly:

**Trace `tr_be9de76a8a64`** (2026-04-25): The agent produced a malformed cold-email draft. `send_email` failed with "Missing `html` or `text` field." The agent did not flag the draft as invalid before submitting it to the tool — the judgment gate upstream of `send_email` did not fire. This is a constraint-detection miss, not a generation miss: the agent *generated* an output, just not one that met the schema contract. A rejection-sampling judge operating on the draft before the tool call would have caught this.

**Trace `tr_8e9d88f3e971`** (segment_2, intent = interested_positive): A second `send_email` failure — the agent again reached the send step despite a constraint violation. The violation was not detected internally; failure was only surfaced at tool execution. This confirms the pattern from `tr_be9de76a8a64` is systematic, not accidental.

**Trace `tr_a69fd57f8be3`** (segment_2, most recent, 2026-04-27): Successful execution — policy_allowed = true, send_email succeeded. This trace is the positive ground truth: it shows what correct constraint-passing output looks like and anchors the "chosen" side of preference pairs. The contrast between `tr_a69fd57f8be3` and `tr_be9de76a8a64` within the same week, same segment, is direct evidence that the failure is inconsistent self-detection, not consistent generation failure.

The quantitative evidence reinforces this: `ablation_results.json` shows auto-opt constraint_pass = 94% vs. mechanism constraint_pass = 100%. The 6 percentage-point gap is structural — prompt-only enforcement cannot fully replicate the Researcher→Closer boundary that prevents signal over-claiming before the Closer stage sees the input. A trained judge should close this gap at inference cost of a single forward pass rather than a full 3-call chain.

**Paper alignment:**

Gu et al. ("A Survey on LLM-as-a-Judge," 2024–2025) identify *position bias* and *self-enhancement bias* as the two dominant failure modes of zero-shot judges. Both biases are especially acute in domain-specific, rule-dense evaluation contexts — exactly the Tenacious signal-grounding setting, where the judge must apply confidence-threshold gates rather than open-ended quality assessment. Gu et al.'s recommendation for mitigating these biases is to use a **trained judge** (fine-tuned on in-domain preference data) rather than a prompted judge, because training internalizes the rubric rather than relying on in-context rule recitation. This directly supports Path B over a prompt-engineering-only approach.

Li et al. ("Preference Leakage: A Contamination Problem in LLM-as-a-Judge," 2025) show that when generator and judge share a model family, win-rates inflate by 6–14pp due to stylistic self-similarity and shared RLHF biases. For Tenacious-Bench, this contamination risk is present at *authoring* time — the rewriting model that produces "chosen" outputs must come from a different family than the judge backbone. Path B makes this rotation policy enforceable because the judge backbone is pinned (Qwen 3.5 0.8B or 2B LoRA), so the generator rotation table can be defined precisely. A prompt-only judge (Path A's fallback option) would require re-specifying the rotation policy every time the judge prompt changed, creating a maintenance gap. Li et al.'s findings therefore support Path B's architecture as more contamination-resistant than a prompt-only equivalent.

The match between evidence and path is not asserted — it is argued as follows: the failure mode is *inconsistency* (same-segment, same-week traces diverge on constraint compliance); inconsistency is not fixed by better generation prompts (auto-opt shows this — it improves to 89% but hits a ceiling at 94% constraint_pass); the structural source of inconsistency is missing a pre-send judgment gate; Path B provides that gate as a trained component rather than a prompted one, which Gu et al. show is more reliable for rule-dense evaluation and Li et al. show is more contamination-resistant when the generator and judge rotation is pinned.

---

## Partitioning Protocol

The dataset is split 50% train / 30% dev / 20% held-out using deterministic task_id hashing (seed = 42). The hash is computed over the canonical task_id string; the split boundary is `hash(task_id, seed=42) % 100`, with 0–49 → train, 50–79 → dev, 80–99 → held-out.

**Why deterministic hashing rather than random shuffling:** random shuffling can be reproduced only if the full dataset ordering is known at split time, which creates a subtle contamination risk if tasks are added or reordered during authoring. Hash-based splits are order-invariant — a task's partition assignment is fixed by its ID, not by when it was added. This matters for Tenacious-Bench because tasks are authored across four modes (trace-derived, programmatic, multi-LLM synthesis, hand-authored adversarial) on different days.

**Stratification by failure-mode category:** within each partition, tasks are stratified by the primary probe category they test (ICP Misclassification, Signal Over-Claiming, Bench Over-Commitment, Tone Drift, Multi-Thread Leakage, Cost Pathology, Dual-Control Coordination, Scheduling Edge Cases, Signal Reliability, Gap Over-Claiming). Each of the 10 categories must be represented in the train, dev, and held-out partitions in approximately its natural frequency. This serves two purposes. First, it prevents the held-out partition from being accidentally dominated by a single failure mode (e.g., all Scheduling Edge Cases in held-out), which would make Delta A unstable — a judge that happens to be strong on scheduling but weak on signal over-claiming would show inflated or deflated Delta A depending on which mode dominates the held-out. Second, it ensures the train partition contains positive and negative examples of every failure mode, which is required for the preference-tuned judge to generalize across the full probe surface rather than overfitting to the most frequent mode (Signal Over-Claiming, P006–P009).

The **held-out partition is sealed** after contamination checks pass: not committed to any training or dev-eval script, gitignored by pattern `tenacious_bench_v0.1/held_out/`. Tasks are released only after the leaderboard pass. The dev partition is public and used for iterative rubric calibration.

---

## Contamination-Check Results

Three checks were run before sealing the held-out partition, using `generation_scripts/contamination_check.py`.

**Check 1 — N-gram overlap (< 8-gram threshold on input fields):**  
Candidate held-out tasks were compared against all train and dev tasks using 8-gram sliding window overlap on the `input_context` and `task_description` fields. Of 62 candidate held-out tasks, **4 flagged** for 8-gram overlap above threshold. Inspection showed all 4 were programmatic-sweep tasks generated from the same probe template (P006) with identical slot values — they were near-duplicates of train tasks differing only in the prospect name slot. Resolution: all 4 were rewritten with distinct signal-confidence and bench-state combinations before re-checking. Final pass: 0 flagged above threshold.

**Check 2 — Embedding similarity (cosine < 0.85 threshold):**  
All tasks were embedded using `sentence-transformers/all-MiniLM-L6-v2`. Cosine similarity was computed between every held-out candidate and every train/dev task. **7 pairs** exceeded the 0.85 threshold. Of these, 5 were the same 4 programmatic duplicates already caught by Check 1 (plus one additional variation); the remaining 2 were multi-LLM synthesis tasks from different probe categories (P012 and P019) that had converged to nearly identical phrasing of the capacity-commitment setup. Resolution: the P012 and P019 near-duplicates were dropped from held-out and replaced with hand-authored adversarial variants targeting the same probes. Final pass: 0 pairs above 0.85 cosine similarity after revision.

**Check 3 — Time-shift verification:**  
Tasks that reference public signals (hiring activity, funding rounds, layoff events) must anchor to a documentable time window. All 12 held-out tasks referencing public signals were audited against the signal dates in the source traces (`held_out_traces.jsonl`). **2 tasks** referenced a "recent funding round" without a datable anchor, creating a time-shift ambiguity — a future eval run could interpret "recent" relative to a different reference date. Resolution: both tasks were updated to reference a specific signal window (e.g., "Series B announced 2026-Q1") derived from trace `tr_a69fd57f8be3` and its companion enrichment fields. Final pass: all 12 public-signal tasks have datable anchors.

All three checks passed. Final held-out partition: 62 tasks (20.1% of total 308 tasks), stratified across all 10 probe categories.

---

## Preference Leakage Rotation Policy

| Generator model   | Judge model        | Used for                     |
|-------------------|--------------------|------------------------------|
| Claude Sonnet 4.6 | DeepSeek V3.2      | Seed authoring → bulk judge  |
| DeepSeek V3.2     | Qwen3-Next-80B     | Variation → variation judge  |
| Qwen3-Next-80B    | DeepSeek V3.2      | Bulk tasks → quality filter  |

Rule: generator_model_family ≠ judge_model_family for every (task_id, generator, judge) triple.  
Per-task assignments committed in `generation_scripts/model_rotation_log.csv`.
