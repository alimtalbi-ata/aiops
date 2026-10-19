# AIOps 2.0 — Decision, Remediation and Learning Architecture

**Author:** Abdelhalim Talbi  
**Status:** Target contract for implementation and qualification.

## Core principle

The trusted system is versioned evidence, deterministic policy, durable workflow state and verified outcomes—not the LLM alone. The analyst proposes; the critic challenges; policy decides which disposition is permitted; a human approves when required; an executor performs only a bounded allowlisted action; verification/reconciliation decides whether the intended effect actually occurred.

## State separation

Never conflate these records:
1. Incident — what was reported and normalized.
2. Run — one durable processing attempt with mode, version and idempotency.
3. Evidence — immutable observation with provenance, freshness and integrity.
4. Analysis — versioned analyst output.
5. Critique — independent validation/challenge.
6. Policy decision — deterministic result plus policy version and evaluated-input hash.
7. Proposal — intended action, risk, target, preconditions, expected result, verification and rollback plan.
8. Approval — identity, role, action hash, scope, expiry and decision.
9. Effect — actual side effect or explicit no-effect/failure.
10. Verification — evidence collected after the effect.
11. Reconciliation — comparison of intended and actual state.
12. Learning case — reviewed linkage of evidence, hypotheses, human correction and verified outcome.

Each record has stable ID, timestamps, schema version, correlation IDs and append-only audit history where appropriate.

## Confidence is not authority

Keep separate fields for source reliability, evidence quality/coverage, analyst confidence, critic confidence and calibration quality. Policy uses explicit proofs for freshness, fencing, preconditions and approval. Confidence cannot compensate for missing proof.

## Proposed action contract

A proposal includes action ID/version, target CI identity and authoritative source, allowlisted command and risk tier, supporting evidence references, preconditions/freshness, impact scope/blast radius, expected effect and measurable postconditions, idempotency key, concurrency/ownership/fencing token, approval requirement, dry-run result, rollback plan and preconditions, timeout/retry budget and stop conditions.

A proposal is not an execution request. Execution requires a separate command referencing the immutable approved proposal hash. Any change to action, target, scope or preconditions invalidates approval.

## PC11K5 invariant chain

Claim → fencing/ownership → preconditions → effect → evidence → reconciliation.

Claim/fencing prevents duplicate or stale owners. Preconditions are rechecked immediately before effect. The effect is idempotent or has a compensating transaction. Evidence describes the actual result, not expected output. Reconciliation determines whether intended state is true. Failed verification stops further actions; recovery/rollback is separately authorized. A command exit code alone never means success.

## Learning loop

1. Capture source/evidence IDs and exact prompt/model/policy/retrieval versions.
2. Store analyst and critic outputs without overwriting previous revisions.
3. Capture human decision and reason, including disagreement.
4. Observe outcome through a trusted adapter and label verification strength.
5. Exclude unverified or synthetic outcomes from trusted production truth.
6. Create a curated case with expected facts, alternatives, counter-evidence and safety disposition.
7. Run regression against candidate prompt/model/retrieval/policy.
8. Deploy in shadow/replay first; compare to current release and preserve rollback.
9. Monitor drift, failure distribution, evidence gaps and human overrides.

The system must not rewrite its own policy, silently fine-tune from raw tickets or convert its prior unverified recommendation into ground truth.

## Delivery phases

### Phase A — Core qualification
- Freeze canonical schemas and service ownership.
- Test incident/run lifecycle, optimistic concurrency, idempotency, append-only events/evidence and audit.
- Test analyst/critic output, grounding and failure/timeout behavior.
- Test policy against P1, missing/stale/conflicting evidence, unknown severity, invalid critic, absent approval, invalid fencing, duplicate command and replay.
- Build an offline gold set and evaluation harness.
- Keep LIVE blocked while adapters are unavailable/unqualified.
- Use local/CI containers and synthetic fixtures; no production-server experiments for this phase.

### Phase B — Adapter qualification
- Read-only CMDB, monitoring, logs/metrics/traces, change and RAG adapters.
- Contract tests for auth, freshness, provenance, timeout and rate limits.
- Temporal worker restart/replay, retries, duplicate delivery, partial failure and recovery.
- GLPI/HITL approval binding, expiry, resume and audit.
- Observability of every workflow stage.

### Phase C — ACME digital twin
Only after Phase A gates pass:
- Versioned CI/service/dependency graph with valid-time and known-time facts.
- Explicit topology provenance, confidence and freshness.
- Failure/capacity/latency/replication scenarios and dependency impact analysis.
- Calibration against known incidents; uncertainty surfaced to operators.
- Isolated simulator network and explicit DEMO/REPLAY mode.
- No direct writes from the twin into canonical production state.

### Phase D — Demo and video
- Reproducible seeded scenario with known expected results.
- Synthetic labels on every screen/API event.
- Scripted path: alert → evidence → analyst → critic → policy → human approval → simulated effect → verification → learning.
- Capture real UI screenshots only from a running build; label fixtures/mockups clearly.
- Repeatable recording script and reset procedure; never imply simulation is live production.
