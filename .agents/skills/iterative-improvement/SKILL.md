---
name: iterative-improvement
description: Autonomous, continuous data-driven optimization loop for IR/RAG systems producing timestamped campaign experiment artifacts in ./experiments/<campaign>/ with tiered fast-failing validation and clean-room data isolation.
disable-model-invocation: true
---

# Iterative Improvement Workflow

An autonomous, data-driven optimization protocol for Information Retrieval and RAG pipelines. The agent systematically drives retrieval metrics toward their empirical performance ceiling across research campaigns, preserving all experiment artifacts in timestamped campaign directories under `./experiments/<campaign_name>/`.

---

## Core Terminology & Architectural Invariants

- **Research Campaign**: A named, isolated optimization track (e.g. `legal_hierarchical_chunking`, `cross_encoder_rerank`) stored under `./experiments/<campaign_name>/` with its own master `ledger.md`.
- **Data Isolation & Clean-Room Boundary**:
  - **Open Dev Split (`data/dev/`)**: Used exclusively for error triage, mechanistic root-cause analysis, and inner-loop hyperparameter tuning.
  - **Sealed Holdout Vault (`data/.holdout_vault/`)**: Contains locked evaluation ground truths. The agent must NEVER inspect, read, or parse vault files via `view_file` or search tools.
- **Coordinated Modular Hypotheses**: Hypotheses target cohesive architectural units (e.g., article-aware document chunkers, cross-encoder rerankers, joint BM25 + dense fusion) rather than isolated single-float micro-tweaks.
- **Document-Structural Invariants**: All algorithmic improvements must exploit universal document properties (e.g., Markdown header hierarchies, PDF layouts, clause boundaries), strictly prohibiting hardcoded query regexes or keyword rules.
- **Tiered Fast-Failing Validation Gates**:
  - **Gate 1 (Inner QA Gate, <1s)**: `./scripts/check.sh` (`ruff`, `ty check`). Must pass with 0 errors before touching data.
  - **Gate 2 (Fast Seeded Sanity Gate, ~3s)**: 25-query sample on dev (`-n 25 --seed 42`). If metrics collapse ($\Delta \text{NDCG} < -0.10$), abort and revert immediately.
  - **Gate 3 (Standard Benchmark Evaluation Gate, capped at $N=100$)**: Evaluates a representative seeded 100-query sample (`-n 100 --seed 42`) across target benchmark datasets to guarantee fast execution without wasting compute.
- **Delta Gate**: Requires positive metric gains ($\Delta \text{NDCG@10} > 0$) on the target domain without regressing baseline performance on other domains.
- **Plateau**: Two consecutive orthogonal architectural iterations yielding $\Delta \text{NDCG@10} \le 0.005$, indicating the empirical ceiling for the active campaign.

---

## Directory & Artifact Structure

All campaign artifacts are isolated under `./experiments/<campaign_name>/`:

```text
experiments/
└── <campaign_name>/                                # e.g. "legal_chunking" or "reranker_tuning"
    ├── ledger.md                                   # Master campaign ledger & metric progression
    ├── iter_000_baseline_<YYYYMMDD_HHMMSS>/
    │   ├── hypothesis.md                           # Baseline architecture definition
    │   ├── report.md                               # Quantitative baseline metrics across datasets
    │   ├── failures.md                             # Categorized error triage from open dev split
    │   ├── predictions/                            # Raw JSONL predictions per dataset (N=100)
    │   └── reports/                                # Structured JSON metric reports per dataset
    └── iter_NNN_<hypothesis_name>_<YYYYMMDD_HHMMSS>/
        ├── hypothesis.md                           # Modular hypothesis, rationale, structural invariant
        ├── report.md                               # Side-by-side metric comparison vs baseline (PROMOTE/REVERT)
        ├── failures.md                             # Remaining error triage driving next iteration
        ├── predictions/                            # Prediction outputs for this run (N=100)
        └── reports/                                # Structured evaluation JSON reports for this run
```

---

## The Autonomous Optimization Steps

### Step 1: Establish Campaign Baseline (Run 0)
1. Define campaign name `CAMPAIGN` and generate timestamp `TS=$(date +%Y%m%d_%H%M%S)`.
2. Create directory `./experiments/${CAMPAIGN}/iter_000_baseline_${TS}/`.
3. Run baseline retrieval on target datasets using $N=100$ seeded queries:
   ```bash
   uv run rag-eval baseline --dataset <name> --split dev -n 100 --seed 42 -p ./experiments/${CAMPAIGN}/iter_000_baseline_${TS}/predictions/<name>_baseline.jsonl
   uv run rag-eval evaluate --dataset <name> --split dev -p ./experiments/${CAMPAIGN}/iter_000_baseline_${TS}/predictions/<name>_baseline.jsonl -r ./experiments/${CAMPAIGN}/iter_000_baseline_${TS}/reports/<name>_eval.json
   ```
4. Write `./experiments/${CAMPAIGN}/iter_000_baseline_${TS}/report.md` and initialize `./experiments/${CAMPAIGN}/ledger.md`.
- **Completion Criterion**: Baseline metrics recorded ($N=100$); campaign ledger initialized.

### Step 2: Open Dev Error Triage & Root-Cause Diagnosis
1. Extract missed queries from the active baseline predictions on `data/dev/`.
2. Perform mechanistic root-cause diagnosis on 3–5 representative failure traces:
   - **Fractured Chunk Boundary**: Key entities, clauses, or conditions split across character boundaries.
   - **Lexical/IDF Dilution**: Repeated boilerplate text overpowering distinctive domain terms.
   - **Semantic/Topical Confusion**: Embedding model prioritizing general topical similarity over exact legal/factual conditions.
3. Identify the dominant structural bottleneck across the dataset.
- **Completion Criterion**: Dominant structural failure mechanism diagnosed with concrete document traces.

### Step 3: Formulate Coordinated Modular Hypothesis & Mutate Code
1. Formulate a testable modular hypothesis addressing the dominant structural failure mechanism.
2. Generate timestamp `TS=$(date +%Y%m%d_%H%M%S)` and create `./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/`.
3. Write `./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/hypothesis.md` documenting:
   - Target structural failure mode
   - Coordinated code components to modify
   - Clean-room verification (zero query-specific hardcoding, zero holdout vault access)
4. Apply codebase modifications.
5. **Gate 1 Execution**: Run `./scripts/check.sh`. If any linter, typecheck, or test error occurs, fix it immediately in-turn until `./scripts/check.sh` exits with code 0.
- **Completion Criterion**: `hypothesis.md` written; Gate 1 passes cleanly (<1s).

### Step 4: Tiered Controlled Benchmarking
1. **Gate 2 (Fast Sanity Check, ~3s)**:
   Run 25-query sample on target dataset:
   ```bash
   uv run rag-eval baseline --dataset <target> --split dev -n 25 --seed 42 -p ./scratch/gate2_pred.jsonl
   uv run rag-eval evaluate --dataset <target> --split dev -p ./scratch/gate2_pred.jsonl -r ./scratch/gate2_eval.json
   ```
   If metrics show catastrophic regression ($\Delta \text{NDCG@10} < -0.10$), abort and revert immediately.
2. **Gate 3 (Standard 100-Query Benchmark)**:
   Execute the 100-query benchmark suite across all target datasets:
   ```bash
   uv run rag-eval baseline --dataset <name> --split dev -n 100 --seed 42 -p ./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/predictions/<name>.jsonl
   uv run rag-eval evaluate --dataset <name> --split dev -p ./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/predictions/<name>.jsonl -r ./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/reports/<name>_eval.json
   ```
3. Calculate metric deltas against active reference baseline:
   $$\Delta \text{Metric} = \text{Metric}_{\text{new}} - \text{Metric}_{\text{baseline}}$$
4. Write `./experiments/${CAMPAIGN}/iter_NNN_<name>_${TS}/report.md` with side-by-side metric tables and delta columns.
- **Completion Criterion**: `report.md` written with complete $\Delta \text{NDCG@10}$, $\Delta \text{MRR@10}$, and $\Delta \text{Hit@10}$.

### Step 5: Delta Gate Decision & Promotion / Rollback
1. Evaluate results against the **Delta Gate**:
   - **Pass ($\Delta \text{NDCG@10} > 0$ without cross-domain regression)**: Mark as **PROMOTE**; retain changes as the new active baseline.
   - **Fail ($\Delta \text{NDCG@10} \le 0$ or significant cross-domain regression)**: Mark as **REVERT**; immediately revert code changes to previous baseline state.
2. Document decision in `report.md` and append entry to `./experiments/${CAMPAIGN}/ledger.md`.
- **Completion Criterion**: Decision recorded in campaign ledger; codebase state matches decision.

### Step 6: Empirical Ceiling Check & Continuation
1. Check for the **Plateau**: Verify if 2 consecutive orthogonal optimization iterations yielded $\Delta \text{NDCG@10} \le 0.005$.
2. If ceiling reached: Document formal termination in `./experiments/${CAMPAIGN}/ledger.md` and conclude.
3. If ceiling NOT reached: Immediately proceed to Step 2 for the next iteration cycle.
- **Completion Criterion**: Formal termination if plateau verified; otherwise, next iteration loop launched immediately.

---

## Anti-Exploitation & Data-Leakage Guardrails

1. **Zero Holdout Vault Peeking**: Never inspect, read, or parse files in `data/.holdout_vault/`. All triage and diagnosis must happen on `data/dev/`.
2. **Document-Structural Invariants Only**: Never hardcode rules for specific query IDs or test string keywords (e.g. `if "Article 5" in text:`). Logic must generalize universally to unseen documents.
3. **Cross-Domain Generalization**: Modifications targeting a specific domain (e.g., CUAD legal) must not degrade performance on other domains (SciFact, QASPER, FiQA).
4. **Single-Path File Persistence**: All systems must persist predictions to disk (`.jsonl`) before evaluation. In-memory ephemeral evaluation is strictly forbidden.
