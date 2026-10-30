# AIOps 2.0 — Reuse and convergence register

**Baseline:** GitHub inventory on 2026-10-30.  
**Purpose:** direct existing work to one target architecture; prevent parallel implementations and unreviewed promotions.  
**Evidence labels:** SOURCE_REVIEWED, CI_REPORTED, RUNTIME_REPORTED, NOT_VERIFIED. PR body claims are recorded as claims until independently rechecked against the exact current head.

## 1. Open work inventory

| Item | Observed state | Direction |
|---|---|---|
| #185 ACME integrated candidate | Open draft; 72 files, +10,233/-72. PR body reports prior 6/6 quality jobs, other qualification workflows, 8/8 source blob checks and deployment-kit checks. It explicitly says DEMO_LOCAL=GO and RELEASE_STABLE=NO_GO. | Use as the primary scenario/convergence candidate; inspect exact head and current CI before selective promotion. Do not merge the large diff as a unit without ownership/transport review. |
| #190 INGEST and Demo Studio artefacts | Open, non-draft. Body reports a previous syntax error and follow-up mock corrections; latest stated head requires full CI. | Re-run exact-head CI; prioritize if still failing the visible run/artefact consistency bug. |
| #192 Portal HITL inbox + GLPI read-only Copilot | Open draft; +448/-3, 7 files. Read-only proposal inbox and GLPI ticket context. | Reuse read-only surfaces and ticket adapter; align to verified identity and Core contract before exposing decisions. |
| #193 guarded GLPI→Copilot→HITL fastpath | Open draft; +243, 2 files. Creates PROPOSED record only for constrained synthetic LOW-risk action. | Reuse only after #192/#194 contracts align; proposal creation is not approval or execution. |
| #194 Temporal HITL / OIDC / outbox | Open draft; +1,572/-10, 17 files. Previous exact head `1fade3e` had all observed CI jobs green. | Reuse Core OIDC verifier, transactional decision outbox and LIVE-only Temporal barrier. Portal OIDC session integration and full runtime failure-injection remain gaps. |
| #188 scheduled qualification + Debian runtime smoke | Open non-draft. Daily full quality schedule plus 15-minute read-only smoke on repository-scoped self-hosted runner. | Preferred schedule candidate after review. It is inactive until merged to default branch and runner installed/online. |
| #189 scheduled quality checks | Open non-draft. Adds a two-hour quality cron and manual dispatch. | Duplicate with #188. Do not activate both; consolidate schedule definition and close/supersede only after owner review. |
| #187 Loki/Tempo/OTel | Open draft, 7 files, +322; explicitly untested on Debian. | Defer new stack until resource/retention/security/rollback review. Use existing Prometheus/Grafana and add instrumentation first. |
| #146 / #153 Debian auto-deploy / stable poller | Open drafts; 15-minute portal auto-deploy and 5-minute stable poller proposals. Not tested on Debian. | No automatic deployment in the 48h window. Require exact transport map, protected release branch, backup, rollback, health and applied SHA proof. |
| #177 Portal P0 UI | Open draft. Its body records historical Policy and Runtime E2E failures plus a deployer transport gap. | Do not promote whole branch. Selectively reuse tested routes/UI only after current CI and package-transport coverage. |
| #59 architecture + 12-week roadmap | Open draft; architecture/HLD and schedule are explicitly proposed and not runtime proof. | Keep as long-term program backlog; this 48h plan is a vertical slice and does not replace it. |

## 2. Existing components to reuse

| Capability | Source candidates | Reuse mode | Required validation |
|---|---|---|---|
| Canonical Run/Incident and stage ledger | Core API + PostgreSQL migrations | Reuse as single authority | schema chain, tenant scope, optimistic version, idempotency |
| Durable orchestration | Temporal/Worker | Reuse | retry, replay, restart, timeout, outbox signal delivery |
| ACME SAN→Payments scenario | Twin, simulator, Golden Payment fixture, PR #185 and existing locator | Adapt behind canonical source-backed relationship contract | exact CI edges, impact direction, source freshness, deterministic replay |
| Portal operator journey | Demo Studio V2, NOC/Timeline, PR #177/#190 | Selective reuse | routes, auth, no stale/foreign Run fallback, packaged source completeness |
| AI evidence ledger | Analysis/Critic/Policy records | Reuse | immutable evidence-set hash, provider/model/prompt versions, validated output |
| AI evaluation | `tools/evaluate_ai_core.py`, `eval/ai-core-cases.json`, `tests/test_ai_eval_harness.py` on HITL candidate branch | Port selectively | exact dependency and API compatibility; add usage/latency telemetry |
| Evidence | Evidence API + read-only refs + bundle auditor | Reuse | hash, provenance, freshness, source identity, tenant/run binding |
| Twin | ACME topology and impact read models | Reuse/adapt | source-backed graph, no fabricated edges, unknown stale state |
| GLPI | read-only adapter, ticket/run context, ITSM correlation branches | Adapt | authenticated read, canonical IDs, idempotency, reconciliation |
| Policy/HITL | Policy SIMULATE, proposal ledger, sandbox receipts, OIDC/outbox branch | Reuse and harden | role separation, immutable hash/scope, lease recovery, Policy recheck |
| Observability | Prometheus/Grafana already in Compose | Reuse | instrument Core/Worker/AI stage metrics; no duplicate collection |
| Debian release | existing install/upgrade/package/rollback scripts | Reuse | clean install, source transport, ownership fence, checksum, rollback |

## 3. Anti-duplication rules

- No second Run store, orchestration engine, AI ledger, Evidence repository, GLPI client, Portal shell or monitoring stack without ADR and measured need.
- PRs touching the same module are sequenced, not stacked blindly. In particular, reconcile Core `main.py`, Portal `main.py`, Worker `main.py`, migrations and Compose before merge.
- A PR is not a source of truth until its exact head SHA, diff, tests and current CI are reviewed.
- A prior green SHA does not qualify a newer head.
- Source/CI qualification does not prove Debian deployment. Runtime claims require timestamped, read-only evidence from the actual host.
- Historical V1/V145 directories are candidates, not deployable components. Inspect code, contracts, dependencies, tests and runtime ownership before reuse.

## 4. Integration order

1. Freeze scenario IDs and canonical contract versions.
2. Selectively converge #185 scenario and read models.
3. Resolve #190 stage/artefact correctness.
4. Align #192/#193 Portal/GLPI read context with #194 Core HITL/OIDC/outbox contract.
5. Add AI usage/latency telemetry to the existing evaluation harness.
6. Converge schedule #188 vs #189; leave Debian auto-deploy #146/#153 disabled.
7. Produce one cumulative package only after exact-head CI, artifact checksum and install/rollback gates.
