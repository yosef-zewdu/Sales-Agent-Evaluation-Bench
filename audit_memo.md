# Audit Memo — Tenacious-Bench v0.1 Gap Analysis

**Date:** 2026-04-29  
**Author:** Yosef Zewdu  
**Word count:** ≤ 600

---

## What τ²-Bench Cannot Answer

τ²-Bench retail (pass@1 = 0.7267 on 150 simulated tasks) grades whether a sales agent completes a task — books a call, sends an email, routes a lead. It says nothing about *how*. There is no Tenacious style guide baked in, no ICP classification rules, no signal-confidence thresholds that gate assertive language, no bench-state constraints that block over-commitment, and no multi-turn FSM isolation checks. A τ²-Bench pass is necessary but not sufficient: an agent can score 1.0 on task completion while fabricating a funding round, exceeding 120 words on a cold email, or pitching an S4 AI-maturity product to a company with `ai_maturity_score = 1`.

---

## Gap 1 — Signal Grounding (Honesty Under Uncertainty)

τ²-Bench grades completion, not factual fidelity to the signal brief. Probes P006 (trigger_rate = 0.28, cost = $8,400) and P007 (trigger_rate = 0.21, cost = $8,820) show the baseline agent asserting hiring momentum and funding confidence at signal_confidence values as low as 0.30 — values where Tenacious policy prohibits assertive language. Probes P008 and P009 extend this to AI-maturity over-claiming and fabricated layoff headcount respectively. These four probes share a root cause: the agent cannot detect when its own output violates a signal-grounding honesty constraint. Traces `tr_be9de76a8a64` and `tr_8e9d88f3e971` confirm this is not a generation failure but a **self-detection failure** — in both traces, a constraint-violating draft reached the `send_email` step undetected and failed only at tool execution (missing field or FSM block), not at the agent's judgment layer.

## Gap 2 — Qualification Accuracy (ICP Rule Enforcement)

τ²-Bench has no concept of ICP classification segments. Probe P001 (cost = $10,560, trigger at ~11%) fires when the agent pitches an S1 unqualified company as high-fit. Probe P003 fires when an S4 "AI-mature" pitch is delivered at `ai_maturity_score < 2`. Probe P036 fires on lookalike misclassification — ICP rules map inputs deterministically (rule-based, not LLM), so a miss here is always a logic error, not a judgment call. No τ²-Bench task tests whether the agent correctly suppresses a pitch based on enriched segment data.

## Gap 3 — Tone Adherence (Hard Style Invariants)

Probe P015 tests the 120-word cold-email hard limit — a Tenacious invariant with no τ²-Bench analogue. Probes P013 and P016 test banned-phrase compliance and tone drift under multi-turn pressure. These cannot be decomposed into completion signals: an email that exceeds 120 words *is* sent (task complete), but the constraint is violated. Trace `tr_3c1d449185b2` (successful execution, policy_allowed = true) establishes the positive baseline — the agent met all tone constraints and routed correctly — while trace `tr_be9de76a8a64` shows tone compliance is not guaranteed in the same session window.

## Gap 4 — Bench Calibration (Capacity Language Gating)

Probe P010 fires when the agent cites an ML headcount exceeding actual bench state. Probe P012 fires when capacity language is used despite `bench_mismatch = True`. τ²-Bench has no bench-state field; its completion tasks never condition outreach content on pipeline capacity. This gap is non-obvious: capacity over-commitment is not a tone failure or a signal failure — it is a separate decision layer that checks whether the agent's *business claims* are consistent with internal bench data, not external signal confidence.

## Gap 5 — Scheduling Hygiene and Multi-Turn Isolation

Probe P026 catches calendar-slot fabrication (offering a time that is not available); probe P027 catches timezone display errors. Probe P017 catches FSM state leaking across MemorySaver keys — a trajectory-level failure invisible to single-turn task graders. Trace `tr_a69fd57f8be3` (segment_2, most recent, 2026-04-27, successful) shows correct FSM isolation; the absence of a cross-thread leak in this trace is the positive ground truth for P017 evaluation.

---

## Conclusion

Tenacious-Bench v0.1 grades all five dimensions above using machine-verifiable scoring with no human in the loop. The benchmark directly targets the gap Week 10 evidence isolates: an agent that completes tasks at 0.7267 pass@1 but mis-scores its own outputs on honesty and domain constraints at $34,260+ per campaign cycle (P006–P009 aggregate). The probe IDs cited — P001, P003, P006, P007, P008, P009, P010, P012, P013, P015, P016, P017, P026, P027, P036 — map directly to the five gap dimensions and establish the grading surface τ²-Bench leaves uncovered.
