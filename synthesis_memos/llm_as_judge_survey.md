# Synthesis Memo — LLM-as-a-Judge Survey

**Paper:** Gu et al., "A Survey on LLM-as-a-Judge" (2024–2025)  
**Author:** Yosef Zewdu  
**Date:** 2026-04-29

---

## Summary

Gu et al. survey the emerging paradigm of using large language models as automated evaluators. The paper catalogues four evaluation methods — pointwise scoring, yes/no questions, pairwise comparison, and multiple-choice selection — and discusses their tradeoffs (Section 2.1). Pairwise comparison is presented as particularly well-aligned with human judgment: Section 2.1.3 cites empirical work showing that "LLM and human evaluations are more aligned in the context of pairwise comparisons compared to score-based assessments" and that pairwise "outperforms other judging methods in terms of positional consistency." The paper's Section 4.4 experiment summary converts this into a concrete recommendation: for pairwise evaluation tasks, use more powerful LLMs plus two mitigation strategies — position-swapping and majority voting across multiple rounds — to reduce bias. The paper also identifies position bias, verbosity bias, and self-enhancement bias as the dominant failure modes of LLM judges (Section 4.2), and notes that reasoning-enhanced models (o1-mini, Deepseek-R1) do not consistently outperform GPT-4-turbo on alignment tasks.

---

## Design Choice I Disagree With

**Section 4.4's empirical recommendation: apply pairwise comparison + position-swapping + majority voting as the standard evaluation strategy.**

The paper derives this recommendation from experiments on general-purpose benchmarks where quality is a single latent dimension — one response is holistically "better" than another. This framing fits open-ended tasks (explain a concept, write an essay) but breaks down when the evaluation rubric is multi-dimensional, partially rule-based, and includes hard-fail gates.

Tenacious-Bench v0.1 has five rubric dimensions with distinct weights: signal_grounding (0.25), tone_adherence (0.25), bench_calibration (0.20), cta_hygiene (0.15), qualification_accuracy (0.15). Two of these — tone_adherence and qualification_accuracy — contain hard-fail conditions that return 0 regardless of quality on other dimensions: a cold email exceeding 120 words scores 0 on tone_adherence (P015 invariant), and an output asserting S4 ICP fit at ai_maturity_score < 2 scores 0 on qualification_accuracy (P003 invariant). A pairwise judge collapses all five dimensions into a single preference vote, which means it can declare Output A "better" than Output B even when Output A trips a hard-fail gate and Output B does not. The paper's position-swapping and majority-voting mitigations do not fix this: they reduce bias about *which* output is preferred but do not force the judge to apply dimension-specific hard-fail logic.

The direct Week 10 evidence: trace `tr_be9de76a8a64` shows an agent output that failed `send_email` with "Missing `html` or `text` field" — a structural constraint violation. In a pairwise comparison against a verbose but structurally valid output, this malformed draft might still "win" on criteria like conciseness or opening quality. A pointwise evaluator with a hard-fail gate on schema validity returns 0 immediately and correctly. The mechanism constraint_pass = 100% vs. auto-opt constraint_pass = 94% (ablation_results.json) shows that the 6pp gap comes precisely from outputs that pass holistic quality checks but fail on specific constraint dimensions — exactly the failure mode pairwise conflates.

**The correct choice for Tenacious-Bench:** pointwise rubric scoring (1–5 per dimension) with hard-fail gates applied before the LLM judge sees the output. Pairwise comparison is used only in the judge-filter pipeline to choose between near-duplicate candidate tasks, not to score agent outputs.

---

## How I Applied (and Departed From) This Paper

Applied:
- Cross-family judge rotation (generator ≠ judge model family) — Section 5's strongest practical recommendation, directly grounded in self-enhancement bias evidence. Implemented in the rotation table in `methodology.md`.
- Chain-of-thought before score: `scoring_evaluator.py`'s LLM tone-scoring prompt asks the judge to reason per dimension before returning an integer, following the paper's finding that simultaneous explanation + scoring compromises quality (Section 4.4).

Departed:
- Pairwise → pointwise for agent output scoring (rationale above).
- Section 4.4 recommends majority@5 or mean@5 (panel judging) for reliability. For daily dev-tier use this triples per-task LLM cost, which violates the $10 total budget constraint. I use panel judging only for the 50-task calibration spot-check on the eval-tier pass, not bulk scoring.
