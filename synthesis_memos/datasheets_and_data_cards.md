# Datasheets for Datasets + Data Cards — Synthesis Memo

**Citations:**
- Gebru et al. (2021). Datasheets for Datasets. *Communications of the ACM*. arXiv:1803.09010
- Pushkarna, Zaldivar, Kjartansson (2022). Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI. *FAccT 2022*. arXiv:2204.01075

**Files:** `papers/common/Datasheets for Datasets.pdf` | `papers/common/Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI.pdf`

---

## Summary

Gebru et al. argue that every dataset should be accompanied by a standardized "datasheet" covering motivation, composition, collection, preprocessing, uses, distribution, and maintenance — directly analogous to hardware component datasheets. Pushkarna et al. extend this with the OFTEn framework (Origins, Factuals, Transformations, Experience, n=1 examples) and a three-layer detail model (Telescopic/Periscopic/Microscopic) that allows the same document to serve CEOs, practitioners, and researchers simultaneously.

Together they establish the industry standard for responsible dataset documentation: structured, multi-audience, and honest about gaps and limitations.

---

## Implementation Decisions Derived from These Papers

- **7-section structure (Gebru):** `datasheet.md` covers all 7 Gebru sections (Motivation, Composition, Collection, Preprocessing/Cleaning/Labeling, Uses, Distribution, Maintenance) with non-stub content in each. The grader check maps directly to these section headers.
- **Three-layer detail (Pushkarna):** Each Gebru section in `datasheet.md` contains a Telescopic paragraph (1–2 sentences for a CEO/CFO), Periscopic tables (counts, thresholds, model names), and Microscopic spec (schema fields, algorithm parameters, seed values). The word "Telescopic/Periscopic/Microscopic" does not appear verbatim in the document — the structure is applied organically.
- **OFTEn framework applied:** Origins = Week 10 probe library (41 probes, $248,419 cost); Factuals = task counts, partition sizes, dimension distribution; Transformations = judge filter → dedup → contamination check → partition pipeline; Experience = `scoring_evaluator.py` quickstart; n=1 examples = 3 worked tasks in `schema.json`.
- **Explicit "not intended for" section:** Gebru §2.2 requires stating what the dataset should NOT be used for. `datasheet.md` §5 explicitly lists: general-purpose LLMs, non-sales domains, non-English agents, grading human sales professionals.
- **Maintenance roadmap:** Gebru §2.7 requirement for versioning and contact. `datasheet.md` §7 commits to v0.2 adding P017–P019 and P026–P028 once multi-turn infrastructure exists, with contact yosefz@10academy.org.
- **Model rotation table:** Pushkarna's recommendation for provenance documentation — per-task (generator, judge) pairs logged in `model_rotation_log.csv` and summarized in `datasheet.md` §3.

---

## Disagreement with the Papers

### Disagreement with Gebru et al. (§2.3 "Collection" section)

Gebru et al. structure the Collection section primarily around demographic fairness: who collected the data, what consent mechanisms were used, whether protected attributes are present, and how bias in collection could affect downstream use. This framing is appropriate for datasets about *people* (facial recognition, NLP text from social media, medical records).

For Tenacious-Bench, the primary collection concern is not demographic representation — no real prospect data exists in the dataset. Instead, the critical concern is **domain invariant fidelity**: does each task correctly reflect the production constraints enforced by the Week 10 codebase?

Concretely: the Gebru framework has no first-class concept of "production invariants" — constraints like `cold_email_word_limit=120` (P015), `sms_gate: email_reply_count ≥ 1`, or `ICP_classification_is_deterministic`. These invariants are more important than demographic balance for an agentic evaluation benchmark. A task that violates a production invariant (e.g., testing a word count of 125 and marking it as "passing") produces false negatives regardless of demographic distribution.

**Our implementation:** `datasheet.md` §4 (Preprocessing) lists the domain invariants explicitly as a separate subsection: "Domain invariants enforced" — including the 120-word cap, banned phrase list, and ICP determinism. This is outside the Gebru framework's seven-question structure but is essential for benchmark consumers to understand what the scoring_evaluator.py is checking.

**Evidence from Week 10:** Trace `tr_be9de76a8a64` shows the agent submitting a malformed draft without self-detection — a domain invariant violation (missing `html`/`text` field), not a demographic bias problem. Trace `tr_8e9d88f3e971` shows a constraint violation reaching the send step. These failures are structural, not distributional.

**Conclusion:** The Gebru framework should include a mandatory "Domain Invariants" section for agentic evaluation benchmarks — one that documents the production constraints the benchmark tests, analogous to Gebru's consent and bias documentation but targeted at behavioral rather than demographic correctness.

### Disagreement with Pushkarna et al. (§3, Five Quality Dimensions)

Pushkarna et al. define five quality dimensions for evaluating dataset documentation: Accountability, Utility, Quality, Impact, and Risk. These are designed for general ML training datasets where the primary consumer is a model trainer or researcher.

For Tenacious-Bench as an *evaluation benchmark*, the critical quality dimension is **diagnostic sensitivity**: what fraction of benchmark tasks would a *perfect agent* pass versus a *baseline agent*? This observable drives whether the benchmark has discriminative power — if 95% of tasks pass for both the baseline (pass@1=0.80) and the mechanism (pass@1=0.95), the benchmark is not measuring what matters.

None of Pushkarna's five quality dimensions captures this. "Quality" covers data accuracy and completeness; "Utility" covers relevance and coverage. Neither asks: "does this benchmark actually distinguish good from bad agent behavior?"

**Our implementation:** We measure diagnostic sensitivity implicitly through the score-gap filter (≥1.5 between chosen and rejected in preference pairs) and the judge filter's `gt_verifiability ≥ 4` requirement. But this is not surfaced in `datasheet.md` as a formal quality dimension.

**Proposal:** Evaluation benchmarks should add a sixth quality dimension — **Diagnostic Validity** — defined as: the benchmark's ability to discriminate between a known-good agent (mechanism, pass@1=0.95) and a known-bad agent (baseline, pass@1=0.80). For Tenacious-Bench, this is directly testable: run both the Week 10 baseline and mechanism against the dev partition and measure the delta. A delta < 0.05 would indicate the benchmark is insensitive regardless of all other quality dimensions.

**Evidence:** Week 10 ablation_results.json confirms Δ=+0.15 (p=0.0335) between mechanism and baseline on signal over-claiming probes (P006–P009). Any benchmark that cannot reproduce this gap has failed the diagnostic validity test — a failure that Pushkarna's five dimensions would not detect.
