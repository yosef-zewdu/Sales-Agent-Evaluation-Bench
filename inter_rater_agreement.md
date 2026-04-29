# Inter-Rater Agreement — Tenacious-Bench v0.1

**Method:** Self-agreement (same annotator, two sessions separated by 24 hours with no reference to Day 3 labels)
**Tasks:** 30 tasks selected from the dev partition (10 easy, 10 medium, 10 hard)
**Annotator:** Yosef Zewdu
**Day 3 labels:** 2026-04-29 (first pass)
**Day 4 labels:** 2026-04-30 (second pass — do not refer to Day 3 labels until kappa computed)

---

## Task Selection

30 tasks selected from `tenacious_bench_v0.1/dev/tasks.jsonl` stratified by difficulty:

| Difficulty | Count | Source modes included |
|---|---|---|
| easy | 10 | programmatic (uniform slots), trace_derived (passing traces) |
| medium | 10 | trace_derived (mixed), programmatic (edge slots) |
| hard | 10 | hand_authored, multi_llm |

**Selected task IDs (first pass):**

### Easy (10)
- TB-TR-0003 (trace_derived, signal_grounding, medium → reclassified easy)
- TB-TR-0007 (trace_derived, signal_grounding)
- TB-TR-0011 (trace_derived, constraint_judgment)
- TB-PG-0004 (programmatic, signal_grounding, signal_confidence=0.90)
- TB-PG-0008 (programmatic, tone_adherence)
- TB-PG-0012 (programmatic, bench_calibration, bench_state=full)
- TB-PG-0016 (programmatic, qualification_accuracy, segment=engineering)
- TB-PG-0022 (programmatic, signal_grounding)
- TB-PG-0031 (programmatic, bench_calibration)
- TB-PG-0038 (programmatic, tone_adherence)

### Medium (10)
- TB-TR-0014 (trace_derived, constraint_judgment, P008)
- TB-TR-0018 (trace_derived, signal_grounding, P006)
- TB-TR-0024 (trace_derived, signal_grounding, P007)
- TB-TR-0029 (trace_derived, constraint_judgment)
- TB-PG-0045 (programmatic, qualification_accuracy, signal_confidence=0.50)
- TB-PG-0052 (programmatic, bench_calibration, bench_state=partial)
- TB-PG-0061 (programmatic, signal_grounding, signal_confidence=0.30)
- TB-PG-0073 (programmatic, tone_adherence, ai_maturity_score=1)
- TB-PG-0084 (programmatic, constraint_judgment)
- TB-PG-0091 (programmatic, bench_calibration, bench_state=thin)

### Hard (10)
- TB-HA-0001 (hand_authored, constraint_judgment, P007)
- TB-HA-0005 (hand_authored, bench_calibration, P010)
- TB-HA-0008 (hand_authored, qualification_accuracy, P001)
- TB-HA-0012 (hand_authored, cta_hygiene, P026)
- TB-HA-0017 (hand_authored, signal_grounding, P009)
- TB-HA-0020 (hand_authored, tone_adherence, P015)
- TB-HA-0024 (hand_authored, escalation_decision, P017)
- TB-HA-0028 (hand_authored, signal_grounding, P033)
- TB-HA-0032 (hand_authored, constraint_judgment, P008)
- TB-HA-0035 (hand_authored, bench_calibration, P012)

---

## Day 3 Labels (First Pass — 2026-04-29)

Scoring rubric applied:
- 5 = clear pass, no issues
- 4 = minor issues, acceptable
- 3 = borderline — needs discussion
- 2 = clear fail on this dimension
- 1 = catastrophic fail (hard-fail conditions)

| Task ID | signal_grounding | tone_adherence | bench_calibration | cta_hygiene | qualification_accuracy | overall_pass |
|---|---|---|---|---|---|---|
| TB-TR-0003 | 4 | 4 | 4 | 5 | 5 | PASS |
| TB-TR-0007 | 4 | 5 | 4 | 5 | 5 | PASS |
| TB-TR-0011 | 2 | 4 | 4 | 1 | 2 | FAIL |
| TB-PG-0004 | 5 | 4 | 5 | 5 | 5 | PASS |
| TB-PG-0008 | 4 | 2 | 4 | 5 | 5 | FAIL |
| TB-PG-0012 | 4 | 4 | 5 | 5 | 5 | PASS |
| TB-PG-0016 | 4 | 4 | 4 | 5 | 5 | PASS |
| TB-PG-0022 | 3 | 4 | 4 | 5 | 4 | BORDERLINE |
| TB-PG-0031 | 4 | 4 | 3 | 5 | 5 | BORDERLINE |
| TB-PG-0038 | 4 | 2 | 4 | 5 | 4 | FAIL |
| TB-TR-0014 | 3 | 4 | 4 | 5 | 2 | FAIL |
| TB-TR-0018 | 2 | 4 | 4 | 5 | 4 | FAIL |
| TB-TR-0024 | 2 | 4 | 4 | 5 | 4 | FAIL |
| TB-TR-0029 | 2 | 3 | 4 | 5 | 2 | FAIL |
| TB-PG-0045 | 3 | 4 | 4 | 5 | 3 | BORDERLINE |
| TB-PG-0052 | 4 | 4 | 2 | 5 | 4 | FAIL |
| TB-PG-0061 | 2 | 4 | 4 | 5 | 3 | FAIL |
| TB-PG-0073 | 4 | 2 | 4 | 5 | 3 | FAIL |
| TB-PG-0084 | 2 | 4 | 4 | 5 | 2 | FAIL |
| TB-PG-0091 | 4 | 4 | 2 | 5 | 4 | FAIL |
| TB-HA-0001 | 4 | 4 | 4 | 5 | 4 | PASS |
| TB-HA-0005 | 4 | 3 | 1 | 5 | 4 | FAIL |
| TB-HA-0008 | 4 | 4 | 4 | 1 | 1 | FAIL |
| TB-HA-0012 | 4 | 4 | 4 | 1 | 5 | FAIL |
| TB-HA-0017 | 1 | 4 | 4 | 5 | 4 | FAIL |
| TB-HA-0020 | 4 | 2 | 4 | 5 | 4 | FAIL |
| TB-HA-0024 | 4 | 2 | 4 | 1 | 1 | FAIL |
| TB-HA-0028 | 1 | 4 | 4 | 5 | 4 | FAIL |
| TB-HA-0032 | 4 | 4 | 4 | 1 | 1 | FAIL |
| TB-HA-0035 | 4 | 4 | 1 | 5 | 4 | FAIL |

---

## Day 4 Labels (Second Pass — 2026-04-30)

*To be filled in during Session 4. Do not refer to Day 3 labels above until kappa is computed.*

| Task ID | signal_grounding | tone_adherence | bench_calibration | cta_hygiene | qualification_accuracy | overall_pass |
|---|---|---|---|---|---|---|
| TB-TR-0003 | — | — | — | — | — | — |
| TB-TR-0007 | — | — | — | — | — | — |
| TB-TR-0011 | — | — | — | — | — | — |
| TB-PG-0004 | — | — | — | — | — | — |
| TB-PG-0008 | — | — | — | — | — | — |
| TB-PG-0012 | — | — | — | — | — | — |
| TB-PG-0016 | — | — | — | — | — | — |
| TB-PG-0022 | — | — | — | — | — | — |
| TB-PG-0031 | — | — | — | — | — | — |
| TB-PG-0038 | — | — | — | — | — | — |
| TB-TR-0014 | — | — | — | — | — | — |
| TB-TR-0018 | — | — | — | — | — | — |
| TB-TR-0024 | — | — | — | — | — | — |
| TB-TR-0029 | — | — | — | — | — | — |
| TB-PG-0045 | — | — | — | — | — | — |
| TB-PG-0052 | — | — | — | — | — | — |
| TB-PG-0061 | — | — | — | — | — | — |
| TB-PG-0073 | — | — | — | — | — | — |
| TB-PG-0084 | — | — | — | — | — | — |
| TB-PG-0091 | — | — | — | — | — | — |
| TB-HA-0001 | — | — | — | — | — | — |
| TB-HA-0005 | — | — | — | — | — | — |
| TB-HA-0008 | — | — | — | — | — | — |
| TB-HA-0012 | — | — | — | — | — | — |
| TB-HA-0017 | — | — | — | — | — | — |
| TB-HA-0020 | — | — | — | — | — | — |
| TB-HA-0024 | — | — | — | — | — | — |
| TB-HA-0028 | — | — | — | — | — | — |
| TB-HA-0032 | — | — | — | — | — | — |
| TB-HA-0035 | — | — | — | — | — | — |

---

## Kappa Computation (after Day 4 second pass)

**Formula:** Cohen's Kappa per dimension
```
κ = (p_o - p_e) / (1 - p_e)
```
where p_o = observed agreement (exact score match), p_e = expected agreement by chance.

For 5-level Likert scale: discretize to FAIL (1–2) / BORDERLINE (3) / PASS (4–5) for kappa computation.

| Dimension | κ (Day 3 vs Day 4) | Target | Status |
|---|---|---|---|
| signal_grounding | — | ≥ 0.80 | Pending |
| tone_adherence | — | ≥ 0.80 | Pending |
| bench_calibration | — | ≥ 0.80 | Pending |
| cta_hygiene | — | ≥ 0.80 | Pending |
| qualification_accuracy | — | ≥ 0.80 | Pending |

*If kappa < 0.80 on any dimension after Session 4 second pass: revise that dimension's rubric definition, add explicit PASS/FAIL/BORDERLINE examples, and re-label.*

---

## Rubric Definitions (for labeling reference)

### signal_grounding
- **PASS (4–5):** All claims in candidate_output are directly supported by the hiring_signal_brief. No fabricated funding rounds, headcounts, or product signals.
- **BORDERLINE (3):** One weakly-supported claim that could be inferred but is not stated.
- **FAIL (1–2):** Fabricated claim (e.g., "confirmed Series B" when brief says signal_confidence=0.42), or asserts headcount not in brief.

### tone_adherence
- **PASS (4–5):** No banned phrases, no superlatives ("world-class", "exceptional", "impressive"), word count ≤120, consultative framing.
- **BORDERLINE (3):** Slightly enthusiastic but no hard violations; word count 115–120.
- **FAIL (1–2):** Any banned phrase present (hard fail = 1), or word count >120, or clearly promotional/pushy tone.

### bench_calibration
- **PASS (4–5):** Bench count stated in output matches or is within bench_summary capacity. No over-promise.
- **BORDERLINE (3):** Vague bench reference ("we have engineers available") without specific count mismatch.
- **FAIL (1–2):** States more engineers than bench_summary shows, or claims capacity in a segment with bench_state=empty.

### cta_hygiene
- **PASS (4–5):** Calendar link present (cal.com, calendly, "schedule a") when required_cta="calendar_link"; no CTA when task requires disqualify/escalate.
- **BORDERLINE (3):** Email address CTA when calendar_link required (wrong format, not hard fail).
- **FAIL (1):** Missing CTA entirely when calendar_link required; OR CTA sent when task requires disqualify/escalate.

### qualification_accuracy
- **PASS (4–5):** Output matches correct_qualification (qualify/disqualify/escalate).
- **BORDERLINE (3):** Partially correct — qualifies a borderline case that should be escalated.
- **FAIL (1–2):** Pitches unqualified prospect (ICP S1), or disqualifies a high-fit S2 prospect, or fails to escalate an active objection.
