# AIOps 2.0 — Reconstruction and Accelerated Execution Plan

**Architecture owner:** Abdelhalim Talbi  
**Execution rule:** one substantial, version-controlled engineering batch per exchange; no routine round trips to the Debian host.  
**Current branch:** `feat/core-analysis-quality-v2`  
**Release policy:** preserve `main`; cumulative kit is publishable only after all required CI gates pass.

## Mission

Reconstruct a reliable AIOps core from the surviving repository and reproducible synthetic fixtures. Optimize for working, measurable software—not preserving weak code for its own sake. Keep the repository as the continuity ledger so ChatGPT conversation-window limits do not become project-memory limits.

The core product is an evidence-grounded incident reasoning and controlled-decision engine. The ACME digital twin is a test fixture and later product layer, not a substitute for real analysis quality.

## Architecture rules

1. **Evidence before explanation.** A claim is either backed by identified evidence, explicitly marked as an assumption, or reported unknown. Every material evidence item has a source, observed time, known time, provenance, mode, and integrity identity.
2. **Analyst and Critic are separate passes.** The Critic must independently challenge causal claims, stale/conflicting evidence, severity, missing preconditions, unsafe actions and unsupported references. A missing or invalid Critic result blocks downstream decisions.
3. **The model never authorizes execution.** LLM output is advisory JSON. Deterministic policy, authorization, immutable proposal hash, approval scope, fencing/ownership and independent postcondition verification remain outside the model.
4. **Fail closed, not silent fallback.** Missing provider, timeout, invalid JSON/schema, absent evidence, stale evidence, conflict, policy failure or incomplete ownership proof cannot become a PASS. Do not manufacture confidence or operational observations.
5. **Mode is a security boundary.** DEMO/REPLAY/STORY evidence is synthetic and cannot authorize LIVE effects or enter the trusted gold set.
6. **One canonical ledger.** Durable run/events/evidence/analysis/critique/policy/proposal/approval/effect/verification/reconciliation/learning records are linked by stable IDs, versioned contracts, idempotency keys and immutable audit.
7. **Replayable decisions.** Persist model/provider/prompt/contract/dataset/policy versions, exact evidence IDs and hashes, and measured outcomes. Re-evaluation must be reproducible from a versioned fixture.
8. **No unverified status claims.** Static checks, unit tests, database migration tests, container builds, deterministic E2E, real-model qualification and production qualification are distinct gates and must be reported separately.

## Work packages and exit criteria

### WP0 — Continuity and repository recovery
- Treat GitHub as the source of truth; every meaningful change, decision, test and blocker lands in a branch/PR.
- Never make speculative claims about the lost server data. Reconstruct from code, migrations, fixtures and verified backups only.
- Keep main protected from exploratory changes; maintain a compact continuity record and architecture decision log.
- Exit: a new session can find the branch, current PR, last CI runs, open blockers and next batch without asking the user to repeat context.

### WP1 — Deterministic core and deployment substrate
- Reconcile Compose, environment templates, health/readiness endpoints, internal network boundaries, dependency ordering and secrets.
- Make install, preflight, migration, status, qualification, backup, restore and package scripts repeatable and idempotent.
- Apply the full migration chain to empty PostgreSQL; upgrade a legacy baseline; rerun migrations; verify checksum drift fails closed.
- Build every app image in CI and retain diagnostics/artifacts on failure.
- Exit: green build and migration/upgrade gates; no production host test required.

### WP2 — Analyst/Critic quality engine
- Version and strictly validate schemas; bound payload sizes, timeouts and retry behavior.
- Require evidence IDs for supported claims; reject unknown references; keep stale/conflicting observations visible.
- Add deterministic fake-provider tests for valid output, malformed output, timeout, empty evidence, invalid references, prompt injection, contradictory telemetry and critic disagreement.
- Add model evaluation dataset and quality gates for severity accuracy, grounding, action safety, injection resistance and contradiction detection.
- Exit: unit/adversarial gates pass; evaluation produces a versioned JSON report for the exact model/prompt; no claim of real-model qualification when only the CI fake provider ran.

### WP3 — Temporal workflow integration
- Test actual orchestration from incident/run creation through NORMALIZE → evidence → Analyst → Critic → Policy.
- Verify idempotency under activity retry, worker restart, timeout after remote commit, stale run versions and repeated launch.
- Prove P1 escalation blocks before effects; prove unavailable Analyst/Critic blocks; prove DEMO cannot create real effect receipts.
- Record stage events and the exact analysis/critique/policy IDs; include evidence-linked diagnostics in reports.
- Exit: isolated Docker Compose E2E passes repeatedly and produces a machine-readable qualification artifact.

### WP4 — Decision lifecycle and safe remediation
- Model each action as an immutable, hash-bound proposal with target CI, risk, evidence, preconditions, measurable postconditions and rollback/compensation.
- Bind human approval to exact proposal hash, target, action, scope, expiry and nonce; critical operations require two distinct required roles.
- Use qualified adapters only. Record an effect receipt before interpreting the outcome; verify independently and reconcile desired/current state.
- Preserve partial/unknown effects and require compensation or human intervention rather than claiming success.
- Exit: database and API tests cover allowed and forbidden transitions, duplicate approval/replay, expired approval, hash tampering, stale ownership/fencing and partial effects.

### WP5 — Learning and quality improvement
- Capture analyst/critic outputs, human feedback, false positives/negatives, verified outcomes and corrective actions as versioned cases.
- Keep synthetic data separate from real operational cases. Gold-set eligibility requires live/non-synthetic provenance, human review, verified outcome and evidence links.
- Add evaluation run records containing dataset hash, provider/model/prompt/policy versions, sample counts, metrics, thresholds and artifacts.
- Do not silently train online from raw tickets. Learning means curated retrieval/evaluation first; model training or prompt promotion only after review and regression gates.
- Exit: one verified case can be traced from incident through analysis, decision, effect/verification and curated learning record; synthetic gold-set insertion is blocked by database constraints.

### WP6 — Deployment kit and operator handoff
- Generate one cumulative, versioned ZIP containing the entire source, Compose stack, env template, scripts, migrations, tests, docs, manifest, SHA-256 list and the successful runtime qualification report.
- Keep secrets, local .env files, runtime database data, backups and unreviewed raw logs out of the kit.
- Package only after unit/static gates, image builds, fresh-database migration, legacy upgrade, runtime E2E and report checks all pass.
- Exit: ZIP checksum validates; a clean isolated environment can follow the documented install/qualification flow without manual file repair.

### WP7 — ACME digital twin, demo and video (after core exit)
- Expand topology, bi-temporal facts, service dependencies, fault scenarios, expected impact, recovery and replay determinism only after the core gates pass.
- Compare two campaigns with the same seed; show evidence, uncertainty, stage timing, policy reasoning, HITL, effects and verification.
- Video must be recorded from a successfully qualified run. Label synthetic data and distinguish real captures from mockups.
- Exit: demo scenario is repeatable from a clean stack, all displayed claims map to run/evidence records, and the demo does not imply live execution.

## Automated quality scorecard

| Gate | Required result before cumulative release |
|---|---|
| Python compile + unit/contract/adversarial tests | PASS |
| Static security/secret/SQL audit | PASS |
| Compose model validation + every image build | PASS |
| Empty database migration chain | PASS |
| Legacy database upgrade + migration rerun/checksum checks | PASS |
| Ledger immutability and forbidden transition tests | PASS |
| Temporal deterministic-provider E2E | PASS |
| Runtime JSON report | PASS, includes expected P1 block and zero effects |
| Model evaluation | Separate report; real model only when provider is configured |
| Package manifest and SHA-256 verification | PASS |
| Live/production qualification | Explicitly NOT QUALIFIED until separately approved and run |

## Execution discipline

- Batch changes across code, tests, SQL, Compose, scripts and docs when they belong to the same work package.
- Prefer CI and disposable containers over user-server experiments. Do not ask the user to run a command unless it provides information unavailable from source/CI or is required for an environment-specific acceptance test.
- Never merge a PR or enable LIVE remediation without explicit approval.
- On a failed CI run, read the failing job log, correct the root cause, add a regression test and rerun the full relevant gates.
- Each release candidate must state: code changes, tests actually run, test outcomes, remaining gaps, exact branch/commit/PR, and the versioned kit artifact link.
