# Methodology Rationale — Path B (SimPO Judge)

**Author:** Yosef Zewdu  
**Date:** 2026-04-30  
**Path:** B — SimPO preference-tuned judge deployed as a rollback gate

---

## Why Path B

The dominant failure mode from Week 10 was **inconsistency on signal over-claiming**: the 3-stage chain (Researcher→Closer→ToneGuard) raised pass@1 from 0.80 to 0.95 on signal over-claiming probes — but the agent still cannot reliably detect when an output violates honesty constraints without running the full 3-stage chain. Three execution traces make this concrete:

**Trace `tr_be9de76a8a64`** (send_email failure — "Missing `html` or `text` field"): the agent produced a malformed draft and did not self-detect the generation failure before attempting to send. This shows the agent cannot reliably validate its own output structure, let alone its semantic content.

**Trace `tr_8e9d88f3e971`** (segment_2, intent=interested_positive, send_email failure): the agent triggered the send_email tool on a segment_2 prospect without detecting that its outreach violated the signal_confidence gate (confidence=0.40, below the 0.50 threshold for assertive funding language). The constraint violation was not caught before the send attempt.

**Trace `tr_3c1d449185b2`** (segment_1, policy_allowed=True, send_email success via staff_sink): success trace — the kill switch defaulted to STAFF_SINK (not a live send), which is why no damage occurred. This illustrates that the current system's safety net is the infrastructure kill switch, not a semantic constraint check by the agent itself.

These three traces together show that:
1. The agent produces constraint-violating drafts at a non-trivial rate.
2. The current constraint enforcement is structural (kill switch → STAFF_SINK, ToneGuard in the chain) rather than semantic.
3. A trained judge deployed as a rollback gate would catch constraint violations before they reach the send step, at lower per-task cost than running the full 3-call Researcher invocation.

Supporting ablation evidence from `ablation_results.json`:
- Mechanism `constraint_pass` = 100% vs. auto_opt = 94%: structural separation (3-stage chain) catches 6pp more constraint violations than prompt-only enforcement.
- Mechanism vs. Baseline Δ = +0.15 (p=0.0335): the structural separation is statistically significant.
- A trained judge should capture this 6pp gap without the full 3-call overhead — the goal is to deploy the *learned discriminative behavior* of the mechanism as a lightweight rollback layer.

**Cost argument:** `target_failure_mode.md` documents signal over-claiming (P006–P009) as the highest-cost failure cluster: aggregate $34,260 at average trigger_rate=0.22. P006 alone (trigger_rate=0.28, cost=$8,400) and P007 (trigger_rate=0.21, cost=$8,820) are the two highest-frequency probes. Baseline pass@1=0.80 means 20% of outreach on these probes produces violating outputs — at 22% trigger_rate, this equates to a non-trivial direct cost rate. A trained judge that catches these violations at near-zero marginal cost (one forward pass through a 0.5B–2B LoRA) justifies the training investment.

---

## Why SimPO over ORPO

SimPO (Meng et al., NeurIPS 2024) is selected over ORPO (Hong et al., EMNLP 2024) for three reasons grounded in the Tenacious-Bench domain:

**1. Length normalization is required for cold-email judging.** The Tenacious cold-email hard invariant (P015) caps all outputs at 120 words. SimPO's length-normalized reward `r(x,y) = (β/|y|) · log p_θ(y|x)` evaluates quality on a per-token basis, preventing the judge from learning to prefer longer outputs solely because they accumulate more log-probability mass. Without length normalization (as in ORPO's odds ratio loss), a judge trained on cold emails would systematically reward outputs approaching the 120-word cap, conflating verbosity with quality. SimPO's γ parameter (target margin) further ensures that chosen/rejected pairs with insufficient quality gap contribute near-zero gradient — this mirrors the score-gap filter ≥1.5 at the training-data level (motivated by DPO §4 implicit reward margin analysis, Rafailov et al., NeurIPS 2023).

**2. ORPO's SFT loss is redundant for instruction-tuned backbones.** ORPO adds negative log-likelihood loss over chosen outputs to provide the SFT warm-up that base models need for preference alignment. The Tenacious-Bench backbone (Qwen2.5-0.5B-Instruct or 1.5B-Instruct) is already instruction-tuned — applying ORPO's NLL loss over chosen outputs risks degrading the existing instruction-following format without providing alignment benefit. SimPO is purely a preference optimizer and does not modify the base distribution.

**3. Key SimPO hyperparameters are domain-appropriate.** The SimPO paper reports β=2.5, γ=0.5, lr=5e-7 as the best-performing configuration (§3, Appendix). For Tenacious-Bench, with cold emails capped at 120 words (short sequences, low denominator in length normalization), β=2.5 provides sufficient reward scaling without over-amplifying length penalties for very short outputs.

---

## Preference Pair Construction

Preference pairs are constructed following Prometheus 2's domain-rubric paradigm (Kim et al., 2024, §3.3), adapted for Tenacious-Bench's machine-verifiable scoring:

**Rejected outputs:** candidate_output fields from train tasks that trigger hard-fail conditions (banned phrases, missing CTA, word count violation) or score ≤ 3.0 on `scoring_evaluator.py`. These correspond to baseline agent outputs on signal over-claiming probes (P006–P009). All rejected outputs are from the Week 10 3-stage chain run at baseline condition (no mechanism structural separation).

**Chosen outputs:** rewrites generated by `deepseek/deepseek-chat` (DeepSeek family) that pass all hard-fail checks and score ≥ 4.0 on `scoring_evaluator.py`. Preference leakage prevention (Li et al., 2025): chosen rewrites use DeepSeek family; the trained judge backbone is Qwen family; dev-tier quality filtering uses heuristic scoring. No model family overlap at any authoring DAG node.

**Score-gap filter (≥1.5):** pairs where `chosen_score − rejected_score < 1.5` are discarded. This is motivated by the DPO §4 gradient analysis (Rafailov et al., NeurIPS 2023): pairs where chosen ≈ rejected in quality produce near-zero implicit reward gradient. For SimPO, the analogous effect is that pairs near the margin γ contribute near-zero loss decrease. High-quality pairs with gap ≥ 1.5 represent unambiguous discriminations that the judge must learn: a 0.0-score output (hard fail: banned phrase + missing CTA) vs. a 4.5-score output (all checks pass, verified signal reference, consultative tone).

**Quality over quantity:** Prometheus 2 uses 100K direct + 200K pairwise training pairs (§3.3). Tenacious-Bench targets 500–1,500 pairs. The paper's core finding — that 1K custom evaluation criteria outperform generic helpfulness rubric — justifies this compression. Our 5 Tenacious rubric dimensions (`signal_grounding`, `tone_adherence`, `bench_calibration`, `cta_hygiene`, `qualification_accuracy`) implement this insight: the judge learns domain-specific discriminations, not general helpfulness. Supporting evidence: LIMA §3 (Zhou et al., 2023) shows 1,000 high-quality samples sufficient for instruction following alignment — similar volume suffices for domain-specific judge training when rubric clarity is high.

---

## Why Signal Over-Claiming as Target Dimension

Signal over-claiming (P006–P009) is the primary training target for five reasons:

1. **Highest cost-frequency product:** P006 trigger_rate=0.28 × $8,400 direct cost; P007 trigger_rate=0.21 × $8,820; P008 trigger_rate=0.24. Aggregate $34,260 at avg trigger_rate=0.22 — the highest cost-frequency product in the failure taxonomy (`target_failure_mode.md`).

2. **Largest Mechanism vs. Baseline gap:** The 3-stage chain's +0.15 improvement (p=0.0335) over baseline is concentrated on signal over-claiming probes. The mechanism's structural separation of fact extraction (Researcher) from phrasing (Closer) is the mechanism of improvement. The trained judge should replicate this structural separation as a learned discriminator.

3. **Root cause is structural, not prompt-engineering:** `target_failure_mode.md` documents that signal over-claiming arises because the baseline agent's phrasing step has no explicit gate between "what signals are verified" and "what language is used to describe them." Prompt engineering alone (auto_opt, pass@1=0.89) cannot fully solve this — mechanism constraint_pass=100% vs. auto_opt=94% confirms the 6pp residual. A trained judge that has learned to detect signal fabrication will catch cases that slip through prompt-level constraints.

4. **Probes P006–P009 are the richest source of training pairs:** all four probes produce outputs that fail on `signal_grounding` (fabricated signal claims) while passing on other dimensions (tone, CTA, bench). This creates clean, unambiguous preference pairs where the discrimination is purely on the target dimension.

5. **Low false-negative rate on hard-fail outputs:** the 120-word limit and banned-phrase checks are binary — they produce score=0.0 unconditionally. Signal over-claiming failures produce score=0.0–2.5 (depending on how many other dimensions pass), giving a richer range of rejected scores and more informative training gradient.
