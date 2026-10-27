# ACME AIOps 2.0 — source-grounded development roadmap

**Date:** 2026-10-27. **Status:** engineering plan from GitHub source inspection, not executed qualification. **Review scope:** main README, Compose, Portal, Core, Copilot, Worker, Policy, Simulator, synthetic E2E, CI quality workflow, continuity docs and draft PR #36. The PR #36 is a large divergent candidate; reuse must be selective. No live environment inspection, no tests executed for this plan.

## 1. Source observations and gaps

| Area | Observed source on main | Gap / risk |
|---|---|---|
| Portal | `app/portal/main.py` offers dashboard, bootstrap, demo launch, Copilot proxy | Bootstrap and demo routes in reviewed main code lack end-user identity/RBAC; PR #36 proposes a separate bootstrap read token, not full SSO |
| Copilot | `app/copilot/main.py` returns fixed summary claims from Core/Twin/Evidence | Not a real question-answering, permission-filtered enterprise RAG; generic source names are not per-claim citations; fixed confidence is not evidence-grounded |
| Temporal Worker | `app/worker/main.py` stages NORMALIZE through LEARN and explicitly blocks LIVE | DEMO stages currently emit generic synthetic PASS evidence and fixed confidence; no verified HITL approval workflow or typed remediation executor; cannot treat stages as real work |
| Policy | `app/policy/main.py` requires evidence freshness, fencing, preconditions and approval for LIVE effects | Need immutable approval binding, role separation, expiration, effect receipt and postchecks in orchestration; preserve P1 escalation |
| Simulator | `app/simulator/main.py` launches synthetic incidents via Core | No rich seeded ACME business journey, deterministic replay oracle or realistic telemetry generator in this reviewed file |
| Compose | Portal/Core/Worker/Twin/Evidence/Policy/Copilot/Simulator/Temporal/GLPI/Prometheus/Grafana defined | Checkmk and Thruk not in reviewed Compose; OTel and pgvector are not proven installed; do not assume integration |
| Synthetic E2E | `tests/synthetic-e2e.sh` on main prints PASS after polling even if run ID never appeared | Fix proposed in draft PR #37; validate, merge separately when reviewed; test actual nonzero failure |
| CI | `.github/workflows/quality.yml` compiles, runs policy/security/static tests, Compose config | No full synthetic Temporal E2E in this workflow; CI success does not qualify runtime |
| PR #36 | ACME fixture/read model, Checkmk/Livestatus offline adapters, NOC wallboard, RAG fixtures, route registry, STAR evidence and tests | Draft, highly divergent, runtime unqualified; selectively port file-level contracts, no bulk merge |

## 2. Delivery strategy: small, independently testable vertical slices

### Gate 0 — stabilize and baseline (P0; 1–2 iterations)
- Freeze canonical Incident/Run/Evidence/Decision schemas, enumerate routes, ownership, tokens and migrations; inspect pending PRs and branch divergence.
- Review PR #37's synthetic run visibility fix, test negative case and decide merge.
- Build a CI synthetic E2E that actually starts the isolated Core/Temporal/Worker stack and checks Run visibility, blocked/failed behavior and append-only evidence.
- **Done when:** tests are deterministic and failures are not falsely PASS; record exact commands, CI URLs and rollback.

### Gate 1 — enterprise data and AI grounding (P0; 2–3 iterations)
- Define `CMDBSnapshot`, `KnowledgeDocument`, `KnowledgeCitation` and `InvestigationHypothesis`; attach source, ACL, product/version, hash, timestamp and validity.
- Reuse PR #36 `demo/rag_ops_fixture_catalog.json` and validation patterns, then add curated licensed official documentation and internal runbooks without copying unauthorized copyrighted content.
- Implement user-scoped read-only retrieval, hybrid keyword/vector evaluation (PostgreSQL FTS first, pgvector conditional), exact citations and abstention; never infer ACME operational facts from vendor docs.
- Replace hardcoded Copilot confidence and generic sources with evidence-based answers; add RBAC, cross-user isolation, injection and missing-proof tests.
- **Done when:** seeded incident questions have correct citations and unauthorized/no-evidence queries disclose nothing.

### Gate 2 — HITL + safe remediation laboratory (P0; 2–3 iterations)
- Versioned typed `RemediationProposal`, `HumanDecision`, `ExecutionReceipt` and `VerificationResult` contracts; action/CI/parameter hash, role, expiration, single-use approval and append-only audit.
- Human approve/reject/clarify/revise flows through Core/Portal/Temporal; Policy independently validates exact action, fencing, freshness and role separation.
- Catalog sandbox Ansible, shell/Python, CLI and REST recipes, with dry-run, bounded timeouts, idempotency, rollback/compensation and technical + business postchecks; **no free-form LLM command execution**.
- **Done when:** rejected, expired, modified and replayed approvals have zero effects; postcheck failure never resolves the Run; LIVE remains blocked until separately qualified.

### Gate 3 — realistic ACME twin and NOC (P1; 2–3 iterations)
- Select a deterministic ERP/payments scenario with sites, hosts, SAN, DB, service graph, users, workload, alert and telemetry sequence; isolate ground truth from investigator.
- Selectively adapt PR #36 `app/portal/acme_fixture_contract.py`, `app/portal/acme_impact_read_model.py`, `demo/noc_checkmk_export.py`, `demo/noc_livestatus_import.py` and NOC wallboard tests.
- Validate real Checkmk edition/version and Thruk-compatible backend via read-only spike; only then choose deployment topology and credential scope.
- **Done when:** one incident traces from monitoring to CMDB impact and Portal with explicit synthetic provenance and verified mapping.

### Gate 4 — Golden Demo, Evidence Studio and release (P1; 2 iterations)
- End-to-end seeded flow: alert → Core → AI cited diagnosis → operator clarification/rejection/approval → sandbox recipe → postchecks → GLPI reconciliation → evidence package and replay.
- Adapt PR #36 STAR evidence capture and offline qualification contracts; include negative tests and browser/API evidence; do not use fake success screenshots.
- **Done when:** clean install/upgrade/rollback on isolated environment and deterministic E2E pass, with manifest, source SHA and qualification level; production remains NO-GO pending separate approval.

## 3. Explicit dependencies and non-goals

- No new control plane, duplicate Run writer, Kafka, Kubernetes, Elasticsearch or dedicated vector DB unless measured necessity.
- Do not deploy PR #36's candidate ZIP or blindly merge its divergent branch. Extract narrow files only after contract comparison.
- No Checkmk↔Thruk compatibility assertion before version/adapter test. No claims of real RAG, SSO, HITL or LIVE remediation from the reviewed main sources.
- Secrets in vault/environment, never in Git. Keep DEMO/REPLAY/STORY segregated from LIVE networks/credentials.
- Maintain five continuity docs, decision log, component reuse matrix, and per-schedule run logs on branch/PR.

## 4. Suggested PR breakdown and acceptance

1. `test: fail-closed synthetic visibility + CI E2E` — review PR #37, add failing negative fixtures.
2. `feat: canonical evidence and CMDB citation contracts` — source ACL and provenance unit/contract tests.
3. `feat: enterprise-only Copilot retrieval` — authorization, exact citations, abstention and injection tests.
4. `feat: HITL decision state machine` — race, expiry, revocation and audit tests.
5. `feat: sandbox remediation catalog` — typed recipes, effect receipt, postcheck and rollback tests.
6. `feat: ACME scenario and NOC adapter` — deterministic Checkmk/Livestatus fixture tests, separate compatibility spike.
7. `feat: auditable Golden Demo` — E2E technical/business verification and evidence replay.

**Ownership:** one PR per bounded slice, Core owns state; Temporal owns workflow; Policy owns authorization; Portal renders; adapters only integrate. Each PR must include source SHA, exact tests and non-run tests, migration/rollback notes, risks, and documentation updates.

## 5. Known unresolved issues

- PR #36 large divergence and unqualified runtime; PR #37 and PR #39 draft pending review.
- Main Copilot does not satisfy internal-only question answering with ACL/citations.
- Main DEMO stages create generic synthetic success markers; no real remediation execution verified.
- Portal end-user authentication and HITL approval semantics incomplete in inspected code.
- Checkmk/Thruk deployment compatibility and actual Debian environment unverified.
- No full-stack synthetic E2E in reviewed main quality workflow.
- **No tests or runtime actions performed during this roadmap-only review.**
