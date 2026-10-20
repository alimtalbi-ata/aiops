# AIOps 2.0 — Deep functional audit and target-driven redesign (2026-10-20)

**Author:** Abdelhalim Talbi  
**Scope:** Branch `feat/core-analysis-quality-v2` / PR #21. Source-level inspection of the Core, Worker, Temporal workflow, Evidence, Intelligence, Policy, SQL migrations, synthetic provider, Compose and release CI.  
**Evidence boundary:** CI proves isolated, **synthetic** integration and immutable-ledger contracts. It does **not** prove real DGX/LLM diagnostic accuracy, qualified real CMDB/RAG connectors, production security or autonomous LIVE remediation.

## 1. Target architecture and actual authority boundaries

```text
 Ingest/API/ITSM/observability
             |
             v
 [CORE] canonical Incident / Run / state / version / audit
             |
             v
 [TEMPORAL] deterministic workflow, retries, idempotent activities
             |
   +---------+--------------+---------------------+
   |                        |                     |
 [TWIN/CMDB]           [EVIDENCE]             [RAG]
 read-only factual     immutable record       trusted scoped retrieval
 topology & change     provenance/time/hash   documents and cases
   |                        |                     |
   +------------------------+---------------------+
                            |
                  [LLM ANALYST — ADVISORY]
                  hypotheses, evidence IDs,
                  alternatives, uncertainty
                            |
                  [LLM CRITIC — INDEPENDENT]
                  unsupported / stale / unsafe /
                  contradictory claims
                            |
                  [DETERMINISTIC VALIDATION]
                  source integrity, freshness,
                  claim coverage, scope, safety
                            |
                   [POLICY / RISK / HITL]
                   no LLM authorization of effects
                            |
                 [FENCING / EFFECT / VERIFY]
                 gated LIVE path — NOT QUALIFIED
                            |
                  [LEARNING / GOLD SET]
                  human-reviewed, verified outcomes
```

Portal, Copilot, Grafana, GLPI and n8n are presentation/integration consumers. They must not become a second source of Run truth. A DEMO or replay is not an authenticated live incident, regardless of visual similarity.

## 2. Findings and remediation status

| Priority | Confirmed gap | Target behavior | Implemented on the feature branch | Remaining proof |
|---|---|---|---|---|
| P0 | Deterministic test provider read `case_id` and chose the expected severity | Fixture labels never enter provider inference; decisions depend on typed evidence | Rewritten rule fixture; removes `case_id` from request; adds metamorphic perturbation tests | Fresh CI evaluation; held-out REAL model later |
| P0 | `DEMO` could return SIMULATE with unvalidated critic or stale evidence | Quality gate applies in every mode; synthetic only relaxes real-effect preconditions | Policy refuses unvalidated, stale, low-confidence or UNKNOWN simulation | Runtime negative scenario tests |
| P0 | Model output could cite stale snapshots as current proof | Only fresh evidence justifies current severity; historical conflicts challenged | Independent evidence integrity/grounding/contradiction module; Analyst and Critic integration | Model-level adversarial red team |
| P0 | Worker Temporal async activity executed blocking HTTP on event loop | Isolate side effects in thread/activities, keep workflow deterministic | Blocking calls dispatched via `asyncio.to_thread`; pure workflow sandbox | Scale/load test, cancel/retry recovery |
| P0 | Event replay could 409 after a successful stage event was committed | Duplicate semantic key returns prior receipt even with stale expected version | Core run-event idempotency check moved ahead of version rejection | Fault-injection across each external side effect |
| P0 | Evidence/Policy APIs lacked internal caller auth | Authenticated internal boundary, missing token fails closed | Constant-time bearer check for Evidence read/write and Policy check | API negative tests, future service-to-service identity |
| P0 | Legacy quick installer embedded a reusable development password | Never include secrets in scripts, source or release artifacts | Installer now delegates to isolated secret-generating bootstrap | Inspect final ZIP and metadata |
| P1 | Evaluation skipped failed cases in metric denominators | A failed/unavailable case must reduce its corresponding score | All cases counted; coverage, stale, contradiction and critic disposition independently gated | Larger balanced corpus and confidence intervals |
| P1 | Confidence remains self-reported by model | Calibration distinct from evidence reliability and diagnostic validity | Contract and deterministic abstention present | External calibration set and expert adjudication |
| P1 | Evidence deduplication relies on payload hash/source | External identity and idempotency proof; no cross-run collisions | Run ID included in synthetic source payloads | Atomic index and replay concurrency tests |
| P1 | Synthetic twin is seeded and mutable, not a fully versioned digital twin | Scenario-isolated, time-travel topology and causal impact | Seeded synthetic topology and scenarios | ACME Twin phase AFTER Core qualification |
| P1 | Copilot currently returns canned inventory/count summaries | Conversational evidence-backed Q&A with sources, uncertainty and follow-up | Existing deterministic Copilot remains intentionally limited | Real Q&A evaluation, permissions and RAG |
| P1 | RAG/CMDB/LIVE adapter paths incomplete | Versioned retrieval/identity and read-only source connectors | LIVE intentionally blocks before synthetic generation | Separate adapter and trust qualification |
| P0 | No qualified LIVE effect runner/PC11K5 end-to-end fence | claim → ownership epoch → preconditions → effect → evidence → verification → reconciliation, rollback | Canonical DB proof tables and guarded proposal/approval APIs | Concurrency, stale-owner, double-claim, partial failure and rollback tests |

**Engineering interpretation:** The biggest quality hazard was measuring a test server that knew the answer key. Removing label leakage is a prerequisite for a meaningful *integration* quality score, but does not create genuine LLM accuracy. Policy and evidence validation must be deterministic and independent of the model.

## 3. Target behavior for Analyst/Critic

1. **Collect** evidence with source, CI/service identity, observed time, known time, provenance, hash and synthetic/live classification. Duplicate IDs, inconsistent timestamps and caller-forged freshness annotations are invalid input.
2. **Normalize** measurements and distinguish current observations, historical snapshots and assumptions. A historical healthy snapshot is not evidence that the service is currently healthy.
3. **Reason** with versioned Analyst schema: symptom, impact/severity, ranked hypotheses, alternatives, cited evidence IDs, confidence basis, unknowns and explicitly advisory actions.
4. **Challenge** with a separate Critic. Require supported claim checks; detect contradictions and scope/causal jumps; fail closed when evidence is absent or conflicting.
5. **Decide** with a deterministic policy. P1 LIVE must escalate; UNKNOWN cannot authorize LIVE; synthetic modes can only SIMULATE and must not bypass diagnosis quality.
6. **Persist** immutable Analyst, Critic, Policy, action proposal/approval, verification, learning and evaluation records, with content hashes, version and idempotency.
7. **Learn** only from independently verified, human-reviewed, non-synthetic LIVE outcomes. Unreviewed comments or replay data may not become the gold set.

Neither Analyst nor Critic can call an execution tool or authorize a physical effect. Confidence alone is not authorization. An HTTP 200 response is not proof of factual correctness.

## 4. Acceptance/quality matrix (release gates)

| Gate | CI synthetic acceptance | Future real-model acceptance |
|---|---|---|
| Contract | All Analyst/Critic JSON outputs schema-valid; malformed output blocks | Version-pinned prompt/provider/dataset and recorded errors |
| Grounding | Zero accepted unknown evidence IDs; current severity cites fresh proof | Expert-rated claim precision and factual consistency |
| Abstention | Missing/stale evidence and disagreement cause BLOCK/ENRICH | P1 false-negative target set and expert-reviewed risk policy |
| Security | Untrusted log text is treated as data; advisory-only actions; auth negatives | Larger OWASP LLM threat suite, service identity, threat modeling |
| Temporal | Durable workflow completes synthetic scenario with zero real effects | Crash/retry/replay/failover/parallel run stress tests |
| Database | Empty migration, legacy upgrade, immutable triggers, replay receipts | Backup restore, schema drift and failure recovery |
| Remediation | P1 LIVE blocked; no LIVE adapter registered | Stale fencing epoch, duplicate owner, rollback and human approval tests |
| Evaluation | All fixtures scored; scenario labels blinded; failed cases not discarded | Held-out gold set; calibration/false-negative/confidence intervals |
| Release | One cumulative ZIP, portable SHA-256 and embedded qualification reports | Deployment qualification on isolated Debian host, approved cutover plan |

A five-case CI fixture suite is deliberately a **small smoke/adversarial set**, not a statistically meaningful production benchmark. Do not represent its score as a real-world accuracy percentage.

## 5. Accelerated delivery work packages

**V2.1 — Critical Core hardening (current focus)**  
Independent evidence checks, blind synthetic provider, fault-tolerant Temporal activity execution, authenticated APIs, fail-closed Policy and immutable evaluation reporting. Must pass every CI gate and produce a cumulative kit. No real effects.

**V2.2 — Trusted intelligence and read-only adapters**  
Connect an explicit real OpenAI-compatible model; label model/prompt/data versions. Add constrained RAG with source-citation verification and document-poisoning tests; read-only storage/SAN and observability adapters; CMDB identity normalization; risk-aware evidence reconciliation. Real-model gate separate from CI fixture result.

**V2.3 — HITL, fencing and controlled remediation design**  
Implement proposal risk classification and approver identity/role separation, leases and ownership epochs, precondition snapshot hashes, effect idempotency keys, verification, reconciliation and rollback. Start with read-only/simulator effect targets. LIVE remains OFF until independently qualified.

**V2.4 — ACME digital twin and chaos qualification**  
Versioned infrastructure/service graph; SAN multipath, block/NAS arrays, virtualization, applications and dependency impact; seeded deterministic Chaos campaigns with replay and comparable campaigns; performance, causal validation and UI timelines.

**V2.5 — Product demo and operational readiness**  
Human-centered console, interactive evidence Q&A, observability KPIs, narrated storyboards, real (not fabricated) UI snapshots, captured video and separate deployment/operations qualification.

## 6. Operational/deployment principles

- GitHub is the source of truth: branch + PR, tracked migrations/configs/tests/scripts/manifest/docs. Never infer functionality from historical Docker names or incomplete host inventories.
- One isolated deployment into `/home/aiops` with unique Compose project/volume/network prefix and loopback-bound web ports. No `/in` or `/out` staging directories.
- One installer, deterministic preflight, local random secrets, health wait, migrations, synthetic E2E, collected sanitized reports. Failure is explicit and non-zero; no silent fallback.
- Do not overwrite legacy runtime, restart missing-image containers, prune volumes, or automate a cutover.
- Protected `main` remains unchanged until tests and review support merging. CI artifacts qualify an exact commit, not future changes.

## 7. Explicit unresolved questions

- Which real DGX-hosted model(s), model quantization, endpoint and context budget will be qualified? Must be pinned before benchmark.
- What are the CMDB and observability data source authorities and refresh SLAs? No live values may be invented.
- What is the acceptable false-negative ceiling for P1, by fault family and site? Requires human operational signoff.
- Which remediation actions are initially permissible, and under what dual approval/fencing protections? Default none.
- Which enterprise-grade real incident histories can be shared for expert-reviewed qualification without exposing secrets/PII? Synthetic fixtures alone are insufficient.

**Current release conclusion:** Source implementation and isolated CI can qualify the synthetic Core baseline only. Real-model performance, full RAG/CMDB, ACME twin accuracy and LIVE auto-remediation are explicitly out of scope until their own evidence-driven gates pass.
