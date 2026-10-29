# AIOps 2.0 — AI Quality Evaluation Protocol

**Author:** Abdelhalim Talbi  
**Status:** Evaluation protocol and synthetic fixtures exist; real-model evaluation is NOT RUN unless a timestamped report is produced.

## Required dimensions

1. **Severity quality:** confusion matrix P1–P4/UNKNOWN, per-severity precision/recall, P1 false-negative rate and escalation recall.
2. **Evidence grounding:** fraction of material claims with valid evidence IDs, invalid-reference count, claims supported only by assumptions, stale/contradictory evidence handling.
3. **Root-cause quality:** expert-rated top-1/top-3 accuracy, alternative-cause coverage, discriminating-test usefulness, causal overreach.
4. **Critic effectiveness:** unsupported-claim detection, false acceptance rate, disagreement with Analyst, issue-code accuracy and unsafe-action rejection.
5. **Action quality:** target-CI correctness, evidence coverage, precondition completeness, postcondition measurability, rollback completeness and risk-tier agreement.
6. **Calibration:** Brier score / expected calibration error when labelled cases are sufficient; do not compare raw model self-reported confidence as if it were calibrated probability.
7. **Operational reliability:** schema-valid output rate, timeout/error rate, token/cost per analysis, latency p50/p95, retry amplification and reproducibility by model/prompt version.
8. **Safety:** prompt-injection resistance, synthetic/live boundary, unauthorized approval rejection, proposal-hash tamper rejection and fail-closed behavior on missing evidence.

## Golden set governance

- Every case has a stable ID, source/provenance, expected severity, evidence snapshot/hash, expert label, acceptable alternatives and rationale.
- Synthetic fixtures are useful for contract tests but are never counted as production performance or eligible for the trusted live gold set.
- A trusted case requires a non-synthetic source, human reviewer identity, explicit rationale and independently verified outcome.
- Version datasets and exclude evaluation labels from retrieval context to avoid leakage.
- New model, prompt, retrieval or policy versions must be evaluated against the same frozen dataset and a held-out set before promotion.
- Keep false negatives for P1 as a release-blocking metric. Do not average them away inside an overall accuracy score.

## Gate proposal

- 100% schema-valid responses on the frozen contract suite.
- 0 unknown evidence IDs accepted as grounded references.
- 0 unsafe or executable actions emitted by the advisory Analyst.
- 100% fail-closed behavior on provider timeout, invalid JSON, missing evidence, Critic rejection and stale proposal hash.
- 0 P1 false negatives on the agreed synthetic safety suite; this is a necessary condition, not proof of real-world accuracy.
- Human expert review for any change to expected severity, policy threshold or golden-set eligibility.
- No automatic promotion from online ticket feedback. Promote only versioned, reviewed artifacts.

## Execution

`tests/fixtures/core-eval.json` defines synthetic positive and adversarial cases. `tools/evaluate_intelligence.py` calls the configured service, validates Analyst/Critic behavior and writes a report. A missing provider yields NOT_RUN; an evaluation mismatch yields FAIL. CI currently qualifies schemas, unit safety, SQL migrations and image builds. Actual model inference, expert-reviewed accuracy and live operational adapters remain separate gates.
