# Contamination Survey — Synthesis Memo

**Citation:** Chen et al. (2025). Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation. *EMNLP 2025*. arXiv:2502.17521

**File:** `papers/common/Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation.pdf`

---

## Summary

Chen et al. survey the landscape of data contamination in LLM benchmarking: how pretraining corpora overlap with public benchmark test sets, why this inflates reported performance, and what detection and mitigation strategies exist. They distinguish three contamination types — explicit (exact n-gram match), implicit (paraphrased), and indirect (semantically related data) — and argue that detecting all three requires combining ≥2 strategies. The survey recommends dynamic evaluation (time-shifted, procedurally generated, or private benchmarks) as the most robust long-term solution.

---

## Implementation Decisions Derived from This Paper

- **Three-check contamination protocol:** `generation_scripts/contamination_check.py` implements all three strategies the paper recommends: n-gram overlap (explicit), embedding similarity (implicit/paraphrase), and time-shift verification (indirect/temporal). The paper argues n-gram detection alone misses paraphrased contamination — this directly justifies the embedding check being non-optional in our pipeline.
- **8-gram threshold:** Chen et al. §3.2 discusses n-gram overlap windows; 8-gram is a conservative threshold that catches verbatim passages while avoiding false positives from short common phrases like "senior ML engineer roles".
- **Embedding model choice:** `sentence-transformers/all-MiniLM-L6-v2` is a standard, widely-deployed model for semantic similarity detection — appropriate for detecting paraphrase contamination between programmatic variations of the same probe template.
- **Time-shift check for public signals:** The paper explicitly flags temporal contamination — benchmarks using signals from public sources (Crunchbase, LinkedIn) may be contaminated if LLMs were pretrained on those same signals. Our time-shift check requires any task referencing public funding/hiring data to cite an explicit time window, enabling future verification that the signal post-dates the LLM pretraining cutoff.
- **Pre-seal contamination check:** The paper recommends checking before publishing — our pipeline enforces this via `contamination_check.py` as a required gate before partitioning into held_out. `contamination_check.json` is committed alongside the dataset.
- **Combining ≥2 strategies (paper §4 recommendation):** Our three-check protocol satisfies this requirement. The output JSON reports pass/fail per check independently, so downstream users can see which checks passed.

---

## Disagreement with the Paper

### Disagreement with Chen et al. (§2 — Contamination Type Taxonomy)

Chen et al. define contamination as overlap between **public benchmark test sets** and **LLM pretraining corpora**. Their three-type taxonomy (explicit, implicit, indirect) is designed entirely around this framing: the contaminated entity is a language model whose weights encoded benchmark answers during pretraining.

Tenacious-Bench faces a fundamentally different contamination risk: the **training partition** and the **held-out partition** are authored by the same researcher using the same 41 probe templates. The Chen et al. detection methods (n-gram, embedding, time-shift) address lexical and semantic surface overlap — but they miss what we call **template contamination**.

**Template contamination definition:** Two tasks share a common seed (a probe template ID like P006) but have different surface text. They are structurally identical — same ground_truth logic, same failure mode, same rubric — even if the specific company name, signal_confidence value, and hiring signal brief differ. An agent that overfits to the train partition's probe structure will perform artificially well on held_out tasks derived from the same probe, even with cosine similarity < 0.85.

**Example:** TB-TR-0018 (train, P006, signal_confidence=0.65) and TB-TR-0036 (held_out, P006, signal_confidence=0.70) share probe P006 as seed. Their briefs are rephrased, their embedding similarity is 0.72 (below threshold), and they share no 8-gram overlap. Yet a trained judge that learned "P006 = signal over-claiming at low confidence" from train will generalize to held_out through the structural similarity — not the surface similarity.

**Detection method:** The Chen et al. paper has no mechanism to detect this. The only defense is tracking `seed_probe_id` across partitions and enforcing that **no probe seed appears in both train and held_out**. This is a partitioning constraint, not a detection algorithm.

**Our implementation:** `generation_scripts/partition.py` partitions by `task_id` hash (seed=42), which distributes tasks from the same probe across partitions. This is **incorrect** under the template contamination framing — it should partition by probe, not by task. Version 0.2 should fix this by partitioning such that for each probe, all derived tasks go to either train OR held_out, not both.

**Implication for the field:** The Chen et al. survey focuses on LLM pretraining contamination, but evaluation benchmarks for fine-tuned agents (like Tenacious-Bench) face a third source of contamination: the benchmark author's own template structure. This requires a new detection paradigm: **structural contamination detection via provenance tracking** (seed_probe_id, seed_trace_id), not just surface-level overlap measurement.

**Concrete recommendation for v0.2:** Add a fourth contamination check to `contamination_check.py`: for each held_out task, check whether its `seed_probe_id` appears in any train task. Flag all held_out tasks whose probe seed also appears in train. Report the overlap as `template_contamination_rate`. A rate > 0% indicates the held_out set is partially structurally contaminated relative to the train set.
