# AIOps 2.0 — Core Implementation Gap Analysis

**Author:** Abdelhalim Talbi  
**Source reviewed:** GitHub main branch files as of 2026-10-19. This is static source inspection, not runtime qualification.

## Confirmed source observations

1. The current Copilot module is not an LLM Analyst/Critic implementation. Its query handler calls the Core dashboard, Twin summary and Evidence API, then constructs a fixed text answer with fixed confidence values. This is a deterministic status summary and must not be described as model-driven diagnosis.
2. The Worker declares workflow stages including DGX_ANALYST and DGX_CRITIC, but the reviewed Worker code explicitly documents that qualified LIVE evidence/CMDB/RAG/analyst/critic/remediation adapters are absent. LIVE stage execution is blocked and emits an adapter-unavailable event instead of manufacturing evidence.
3. The Policy API has deterministic inputs for mode, command, severity, confidence, evidence count, critic validation, redundancy, freshness, preconditions, fencing and approval. Its existing safety tests cover P1, missing evidence, missing fencing, missing approval and synthetic-mode behavior.
4. The database migrations already provide runs, ordered run events, append-only evidence, gates, command receipts, stage state, checkpoints, API audit, topology nodes/edges/facts, incidents, observations, changes, impact assessments, scenarios and demo artifacts.
5. The migrations reviewed do not show explicit normalized records for Analyst output, Critic output, proposal versions, approval bindings, execution effects, post-effect verification/reconciliation or curated learning/evaluation cases. Some state may currently be embedded in run event JSON; that must be confirmed by mapping all reads/writes before changing schema.
6. The repository already has a broad Compose stack, installer/preflight, static audit, policy tests, runtime contract checks, qualification and synthetic E2E scripts. Existing continuity notes state that full container/runtime qualification and synthetic E2E were not yet established at the last recorded review.

## Required engineering work in order

### A. Freeze contracts before wiring models
- Add versioned JSON Schemas for Analyst and Critic outputs.
- Add schema validators and evidence-ID reference validation.
- Distinguish provider confidence, evidence quality, analyst confidence and critic confidence.
- Make provider timeout, malformed JSON, schema mismatch and unavailable critic explicit states; never synthesize a successful answer.

### B. Implement an isolated model adapter
- OpenAI-compatible endpoint configurable for the local model server.
- Separate Analyst and Critic calls; temperature zero for reproducibility where supported.
- Strict timeout/retry limits, response size limits and no arbitrary model tools.
- Redact secrets and unneeded personal data.
- No provider configured means a clear degraded/unavailable response, not a fallback fixed confidence.
- Add unit/contract tests with a deterministic fake provider. Keep actual inference tests optional and separately labelled.

### C. Ground analysis in evidence
- Every material claim carries evidence IDs or is marked assumption.
- Validate that cited IDs are present in the supplied ledger.
- Preserve contradictory, stale and unavailable source results.
- Record source identity, observed time, known time, freshness rule, integrity hash and synthetic/live mode.
- Require the Critic to challenge claims, alternatives, severity and action preconditions.

### D. Extend the canonical decision ledger only after mapping existing persistence
- Inspect all Core/Worker/Policy/Evidence/Copilot DB reads and writes.
- Produce an explicit entity-to-table mapping and API contract map.
- If required data cannot be represented reliably in current run events/gates, add an additive migration for analysis records, critiques, policy decisions, proposal versions, approvals, effect receipts, verification/reconciliation and reviewed learning cases.
- Include schema versions, parent revisions, actor, timestamps, idempotency and evidence references.
- Design an explicit upgrade path; PostgreSQL initdb scripts alone do not migrate an already initialized volume.

### E. Validate locally/CI before server deployment
- Python compile/static checks and deterministic unit tests.
- Analyst/Critic schema contract tests with valid and invalid fixtures.
- Evidence reference, stale evidence, contradictions, missing evidence and prompt-injection fixtures.
- Policy regression tests and seeded adversarial tests.
- Disposable PostgreSQL migration-from-empty and migration-upgrade tests.
- Container build and isolated synthetic E2E in CI.
- Publish exact workflow run and artifacts. Do not test on the production Debian server in this phase.

## Exit criteria for Phase A

The Core is ready to be considered qualified only when the analyst and critic are real provider-backed components (or explicitly declared unavailable), structured outputs are validated and evidence-grounded, deterministic policy tests pass, data persistence is durable and auditable, migration tests pass, failure cases are covered, and CI produces a reproducible report. Until then, keep LIVE effects disabled.

The ACME twin feature expansion, demonstration polish and video recording are Phase C/D activities after the core exit criteria; existing seed topology can remain available for isolated tests but is not proof of twin accuracy.
