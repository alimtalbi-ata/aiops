# AIOps 2.0 — Core AI Analysis Quality Contract

**Author:** Abdelhalim Talbi  
**Status:** Architecture and acceptance contract; runtime implementation must be mapped and tested against it.

## 1. Design rule

The model is an evidence interpreter and proposal generator, not an authority. It must never invent observations, access production systems implicitly, approve its own actions, or override deterministic policy. Analyst and critic are separate logical roles with separate prompts, schemas, inputs and recorded outputs. Using one provider initially is acceptable, but outputs must remain independently validated.

## 2. Trust-boundary pipeline

1. Ingest: authenticate source, assign stable IDs, timestamps and idempotency key.
2. Normalize: map to canonical Incident/Run while preserving source identity and original fields.
3. Resolve context: CMDB/service relationships and recent changes, each with source, observed-at, known-at and freshness.
4. Acquire evidence only through allowlisted adapters with bounded timeouts and size limits.
5. Append evidence records with provenance, integrity hash, source timestamps, quality metadata and LIVE/DEMO/REPLAY/STORY marker.
6. Analyst generates hypotheses grounded only in supplied evidence.
7. Critic challenges coverage, temporal validity, contradictions, causal leaps, missing context and action safety.
8. Deterministic policy validates schema, severity floors, freshness, preconditions, ownership/fencing, approval and command allowlist.
9. Disposition is OBSERVE, ENRICH, ESCALATE, HUMAN_APPROVAL or a separately authorized execution path.
10. Verify and reconcile actual state after any authorized effect.
11. Learn from reviewed outcomes as new versioned records; never rewrite old evidence or decisions.

## 3. Analyst output contract

Each result must validate against a versioned JSON Schema and include:
- contract_version, analysis_id, incident_id, run_id, mode, created_at;
- classification and severity with rationale;
- hypotheses with IDs, statement, confidence, supporting and contradicting evidence IDs, assumptions;
- alternatives and discriminating tests;
- timeline entries referencing evidence IDs and timestamps;
- impact assessment with affected CI/service references and uncertainty;
- recommended actions with action ID, intent, risk tier, target, preconditions, expected effect, verification, rollback, required approval and advisory-only status;
- missing_information, unknowns and contradictions;
- confidence breakdown, limitations, model/provider/prompt/schema versions.

A confidence number without supporting evidence and calibration context is not a quality claim. Missing data must never be converted to a negative observation.

## 4. Critic output contract

The critic receives the incident, normalized context, evidence ledger and analyst result. It must not merely restate or endorse the analyst. It returns:
- validated boolean;
- issues classified as unsupported_claim, stale_evidence, contradiction, missing_precondition, causal_leap, schema_error, severity_mismatch, unsafe_action or scope_violation;
- claim checks linking each material claim to supporting/contradicting evidence IDs;
- additional evidence needed, unsafe actions and safe observations;
- corrected severity or null, with rationale;
- diagnostic confidence and explicit limitations;
- final recommendation restricted to the allowed disposition enum.

The critic cannot invent evidence IDs or claim to have queried an adapter. Missing, malformed, timed-out or failed critic output means validation is false.

## 5. Evidence quality dimensions

Keep dimensions separate rather than collapsing them into one opaque score:
- provenance: authenticated source and adapter identity;
- integrity: canonical payload hash and immutable record identity;
- freshness: source-specific TTL and event-time/known-time checks;
- relevance: relation to claim, CI and service;
- independence: multiple signals must be genuinely independent, not copied;
- completeness: expected sources checked, skipped or unavailable;
- consistency: agreement and temporal ordering across sources;
- mode: LIVE, DEMO, REPLAY or STORY propagated end to end;
- confidence: source/adapter confidence separate from model confidence.

Contradictory and stale evidence remains visible. Fusion preserves originals and records algorithm/version.

## 6. Deterministic safety gate

Policy is ordinary versioned code, never prompt-only safety. Minimum rules:
- P1 always ESCALATE; no confidence override.
- Missing, malformed, stale or contradictory critical evidence yields UNKNOWN, BLOCKED or HUMAN_APPROVAL as appropriate.
- Analyst schema failure, critic failure, timeout or refusal cannot pass the gate.
- LIVE cannot use synthetic evidence or demo shortcuts.
- Every action must be allowlisted and have validated target identity, ownership/fencing, preconditions, idempotency key and bounded scope.
- High-risk effects require explicit human approval bound to action hash, target, run, expiry and approver identity.
- Approval cannot be reused for a changed action or target.
- Model output never directly invokes shell, SQL, SSH, arbitrary URL, tool or remediation endpoint.
- Side effects require before/after evidence, verification and reconciliation. Rollback is a new guarded action.
- LIVE remains blocked where real adapters are not qualified.

## 7. Evaluation and quality gates

Build a versioned gold set for storage/SAN, servers, databases, network, capacity, latency, multipath, replication lag, cascades, false positives, contradictory signals, missing telemetry, stale CMDB and adversarial payloads. Split by incident family/time to prevent near-duplicate leakage.

Track:
- severity macro-F1 and P1 recall;
- root-cause top-k accuracy and evidence-supported claim rate;
- unsupported-claim rate and contradiction detection recall;
- calibration (Brier score/ECE when sample size permits);
- critic defect catch rate and false-positive rate;
- disposition precision/recall by severity;
- unsafe-action proposal and policy-bypass rates (target zero);
- evidence freshness/coverage, abstention correctness and usefulness of missing-information requests;
- analyst/critic latency, token/cost, retries/timeouts;
- human override rate and verified remediation outcomes;
- regression rate on previously accepted cases.

Report sample size and confidence intervals. Curated examples alone do not establish general accuracy.

Release gates require schema and policy tests; P1/missing/stale/conflicting evidence, critic failure, provider timeout, duplicate event, replay and partial-failure coverage; no unsafe bypass in adversarial tests; comparison with previous gold-set results; and explicit failed/skipped/not-run tests. Runtime qualification is separate from static/unit checks.

## 8. Prompt injection and isolation

Treat incident descriptions, logs, tickets, runbooks, CMDB text and retrieved documents as untrusted data, not instructions. Ignore embedded requests to reveal secrets, change policy or execute actions. Retrieval cannot elevate privileges. Redact secrets and unnecessary personal data before model calls. Tool access uses narrow adapters with server-side authorization, allowlists, timeout and audit. A model never receives database superuser credentials or unrestricted execution access.

## 9. Capitalization and learning

Store analyst result, critic result, evidence references, policy version, final disposition, human corrections and verified outcome as immutable linked records. Corrections create a new revision with parent ID and actor/time. Distinguish observed, human-asserted, inferred, synthetic and verified operational outcomes.

Only reviewed, provenance-complete cases enter the trusted gold set. No online self-training from raw incidents. Promote prompt/model/retrieval changes through offline evaluation, regression, shadow/replay, approval and versioned release with rollback.

## 10. Acceptance checklist

- [ ] Analyst and critic contracts are schema-validated and versioned.
- [ ] Every material diagnosis claim links to evidence IDs or is marked assumption.
- [ ] Missing/stale/conflicting evidence produces explicit unknowns.
- [ ] Critic failure blocks high-impact disposition.
- [ ] Policy is independent of model text.
- [ ] Synthetic/live provenance is enforced end to end.
- [ ] Proposed, approved, executed and verified actions are distinct.
- [ ] Audit is append-only and replayable.
- [ ] Offline benchmark and adversarial regression report exists.
- [ ] LIVE remains blocked until real adapters and end-to-end safety qualification pass.
