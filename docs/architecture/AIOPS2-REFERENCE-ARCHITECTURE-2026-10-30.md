# AIOps 2.0 — Reference architecture and enterprise operating model

**Status:** Target architecture / design baseline for the 48-hour convergence.  
**Date:** 2026-10-30. **Scope:** customer-demonstrable, ITIL 4-aligned synthetic enterprise journey; production integrations remain individually qualified.  
**Rule:** this document describes ownership and target contracts. It does not claim that every connector, process, or control is deployed.

## 1. Architecture decision

Converge on one AIOps 2.0 control plane. Do not create a parallel orchestrator, ticket store, evidence store, AI ledger, or operator portal. Reuse the existing Core, Temporal/Worker, Evidence, Twin, Policy, Portal, GLPI, Prometheus/Grafana, RAG and simulator implementations through explicit adapters and versioned contracts.

### Logical planes

| Plane | Primary components | Authority |
|---|---|---|
| Signal and observability | Checkmk (target monitoring authority), Prometheus, Grafana, selected log store/Elastic | Source observations and telemetry; never owns Incident/Run lifecycle |
| Integration and normalization | authenticated source adapters, GLPI adapter, n8n notifications | Validates, timestamps, deduplicates and maps external IDs; no canonical Run state |
| Service control | Core API + PostgreSQL | Sole authority for tenant, Incident, Run, stage, evidence references, decisions and lifecycle transitions |
| Orchestration | Temporal + Worker | Durable workflow execution, retries, timeouts, signals and recovery; no independent business ledger |
| Context and intelligence | Twin/CMDB, Evidence, RAG, Analyst, Critic | Advisory context and sourced evidence; no authorization |
| Governance | Policy, HITL, identity, audit | Deterministic authorization, human decision, fencing and audit; LLM cannot override |
| Execution | isolated simulator now; bounded Ansible/SSH executor only after qualification | Side effects only after independent gates; LIVE remains disabled until release gates pass |
| Experience | Portal / NOC Command Center / Demo Studio / Grafana | Authenticated read models and operator actions through APIs; no direct DB writes |

### Canonical flow

`Monitoring/ITSM → authenticated adapters → Core Incident/Run → Temporal → Evidence + Twin + RAG → Analyst → independent Critic → Policy → HITL → isolated SIMULATE → independent VERIFY → GLPI reconciliation → learning`

The customer journey is anchored to one `tenant_id`, `incident_id`, `run_id`, `service_id`, `ci_id`, `ticket_id`, and immutable evidence/decision references. If a link cannot be proved, expose `UNKNOWN`; never infer a relationship from a title or a synthetic identifier.

## 2. Source-of-truth and data ownership

| Entity | Authoritative owner | Mutability / contract |
|---|---|---|
| Tenant, user, role, service identity | Identity provider + Core authorization projection | Versioned claims; least privilege; tenant isolation |
| CI, service, dependency | GLPI CMDB / governed Twin source | External authority plus Core snapshot, freshness and source reference |
| Incident | Core | Optimistic versioning, idempotent creation, append-only lifecycle events |
| Run and stage | Core for canonical state; Temporal for workflow history | Correlated IDs; durable transitions; Temporal is not a replacement business ledger |
| Evidence | Evidence service | Append-only, hash, source, observed_at, known_at, provenance, freshness, tenant and run binding |
| Analysis / Critique | AI ledger in Core | Immutable input/evidence binding, provider/model/prompt/schema versions, validation state |
| Policy decision | Policy evaluation persisted by Core | Deterministic result, policy version, input hash, reasons and proof snapshot |
| Proposal / Approval | Core HITL ledger | Immutable proposal hash/revision; verified human identity; expiry, nonce and scope |
| Effect / Verification / Reconciliation | executor receipt + Core ledger | Separate effect from approval; independent postcondition evidence; no self-attestation |
| ITSM ticket / Change | GLPI | GLPI remains ticket/CMDB authority; Core stores verified cross-reference and reconciliation |
| Model invocation / evaluation | AI telemetry ledger (target) | Per-call usage, latency, model/prompt/dataset version, cost provenance and evaluation score |

Target canonical identifiers and fields (versioned schemas required): `schema_version`, `tenant_id`, `source`, `source_event_id`, `event_time`, `ingested_at`, `observed_at`, `known_at`, `severity`, `state`, `dedupe_key`, `incident_id`, `run_id`, `service_id`, `ci_id`, `ticket_id`, `evidence_ids`, `mode`, `provenance`, `freshness`, `correlation_status`, `policy_version`, `proposal_hash`, `actor_subject`, `trace_id`.

## 3. ITIL 4 operating model

This is an implementation alignment, not an ITIL certification claim.

| ITIL 4 practice | Platform behavior and customer-visible evidence |
|---|---|
| Monitoring and Event Management | Receive Checkmk/Prometheus events; normalize, dedupe, timestamp, classify; preserve source and acknowledgement separately |
| Incident Management | Create one canonical Incident; P1–P4 priority, impact/urgency, assignment, SLA/OLA timers, escalation and major-incident command |
| Service Desk | N1 intake, acknowledgement, communication, ownership and handover; N2/N3 technical escalation |
| Service Configuration Management | Link CI/service/dependency through GLPI CMDB and Twin; show source and freshness; stale/missing relations are UNKNOWN |
| Problem Management | Cluster recurring incidents, root-cause hypotheses, known error and workaround; link Problem to related Incidents |
| Knowledge Management | Curated runbooks/KB with owner, version, classification, ACL, expiry and citations; retrieval cannot grant authority |
| Change Enablement | Proposed change, risk/impact, implementation and rollback plan, approver roles, maintenance window and post-change review |
| Release Management / Deployment Management | Versioned package, exact commit, manifest/checksums, staged deployment, health checks and tested rollback |
| Service Validation and Testing | Contract/unit/integration/E2E/failure-injection tests with evidence and explicit environment/mode |
| Information Security Management | MFA/SSO, RBAC, tenant fence, secrets management, audit, redaction and security event trail |
| Service Level Management | Service SLO/SLI, SLA/OLA timers, breach/near-breach, availability and business impact |
| Continual Improvement | Post-incident review, verified lessons, action owner/due date, runbook changes and gold-set curation |

### Priority and escalation

Priority is computed from approved impact × urgency rules, not inferred from an LLM. P1 triggers major-incident handling, incident commander, N2/N3 escalation, customer communications and human approval. P2/P3/P4 follow service-specific OLAs and runbooks. The demo must show the calculation inputs and policy version.

### End-to-end enterprise scenario

1. A synthetic Checkmk event reports SAN fabric path degradation.
2. Core correlates the event with the Payments service and CMDB/Twin dependencies; the dependency path must be sourced.
3. A second observation reports payment latency/SLO breach. Core deduplicates and raises a P1 candidate with impact/urgency evidence.
4. N1 acknowledges; N2 investigates; incident commander is assigned for P1. GLPI ticket and Core Incident/Run links are verified, not guessed.
5. Evidence collects current path state, latency, service checks and selected logs. RAG returns only ACL-authorized, versioned runbooks and known errors with citations.
6. Analyst proposes ranked hypotheses and bounded corrective options; independent Critic checks evidence, contradictions, freshness, action safety and missing preconditions.
7. Policy records SIMULATE/ESCALATE/HUMAN_APPROVAL/BLOCK with explicit reasons. No LLM output can alter the policy result.
8. HITL displays proposal hash, CI, risk, evidence, preconditions, expected postconditions, rollback, expiry and verified human identity. Synthetic runs may demonstrate the UX but cannot create real approval authority.
9. The sandbox simulates an allowlisted remediation and records a simulation receipt. No real SSH, sudo, Ansible or GLPI write is implied.
10. Independent verification checks service health and business SLO; reconciliation updates the Core read model and the synthetic GLPI ticket if that connector is part of the test fixture.
11. A Problem/known-error candidate and post-incident review are generated only from verified evidence. A human accepts knowledge changes.

## 4. Safety and trust boundaries

- Core is the only canonical business-state writer; Portal is an API client.
- Temporal signals notify workflows of Core-persisted decisions; they do not authorize effects.
- Evidence and audit are append-only; corrections are superseding records.
- Policy is deterministic and independent of Analyst/Critic.
- Every effect requires proposal hash/revision, verified actor, scope, expiry, current ownership/fencing token, preconditions, idempotency, policy recheck and rollback.
- Execution must be a fixed allowlisted action catalogue; never translate free text into shell commands.
- DEMO/REPLAY/STORY never authorize LIVE. Mark synthetic provenance at every layer.
- Missing, stale, contradictory or untrusted information is `UNKNOWN`, not healthy.
- No cross-tenant retrieval, citation, ticket or evidence link without authorization before retrieval and before display.
- No secrets or raw sensitive prompts in logs, traces, benchmark reports or artifacts.

## 5. Runtime tiers and release gates

| Tier | Purpose | Allowed effects | Required proof |
|---|---|---|---|
| T0 unit/contract | deterministic logic | none | tests, static audit |
| T1 isolated integration | real service processes + ephemeral DB | disposable fixtures only | service integration reports |
| T2 synthetic E2E | customer story in isolated stack | simulator-only effects | exact Run/evidence/ledger receipts |
| T3 deployed read-only | actual deployed services | read-only | timestamped endpoint and redacted response |
| T4 controlled sandbox | isolated executor with approved fixtures | allowlisted sandbox mutations | approval, fencing, effect, verify, rollback |
| T5 LIVE | enterprise production | only explicitly authorized | independent security, identity, policy, executor, recovery and change approval gates |

Current 48-hour target: T2 customer story plus T3 only where actual access/evidence exists. T4/T5 are not implied by green CI. LIVE remediation stays blocked.

## 6. Standards and architecture governance

Use ITIL 4 practice alignment for process design; use versioned API/data contracts, threat modelling, least privilege, auditability, change enablement and rollback for engineering governance. Map controls to ISO/IEC 20000-1 service management, ISO/IEC 27001 information security, ISO/IEC 27017/27018 where cloud/privacy scope applies, and ISO 22301 continuity only after a control-by-control assessment. Do not claim compliance/certification without formal scope, evidence and independent audit.

Architecture changes require: ADR, source-of-truth owner, threat boundary, schema/API version, tests, operational owner, observability, migration/rollback, release manifest and exact qualification evidence.

## ADR-INT-2026-10-31B — current single integration candidate (23:48 Europe/Paris)

The sole clean main-based DEV integration candidate is [#234](https://github.com/alimtalbi-ata/aiops/pull/234) `integration/enterprise-slice-main-20261031-2230`, created from `main@ae7c3e5102b99a66bd7806d602146f1309a9749d`. Historical #201 remains source-only and stale documentary #227 is closed. The first scoped product port is the eight-path ACME synthetic graph/replay contract from #231, not a whole-branch merge. GLPI remains ITSM/CMDB authority when independently qualified; Core owns Incident/Run, Portal requires server-derived actor+tenant exact-Run ACL, and Policy/Temporal cannot authorize LIVE. New candidate exact-head D0 must be requalified; D1/D2 combined and D3/D4 are not qualified. See [integration ADR](../release/AIOPS2-INTEGRATION-CYCLE-2026-10-31-2345.md). RELEASE_STABLE=NO_GO.


## ADR-INT-2026-11-01A — Selective four-owner integration, fail-closed by construction (00:41 Europe/Paris)

The sole DEV candidate remains Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), based on main `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Architect selectively ported ACME Bearer origin pin #236, Portal OIDC callback/identity-only sessions #237, Core read-only xref #233 with installed SQL 009 AI→010 Evidence→011 HITL→012 xref #238, and Policy no-effect #239. Integration code checkpoint `f69b0f7e41ac3d199c8236b09dd8b301b2607176`; no whole historical PR merge.

**Trust ADR:** Portal RS256 identity is not authorization. Core signed synthetic ownership fixtures are not authenticated GLPI authority. The exact Run/Incident/ticket/entity actor+tenant positive ACL remains unqualified and MUST return UNKNOWN/fail-closed. ACME Core Bearer requires an explicitly pinned origin; Policy's public HTTP schema remains exactly state/decision/reason, while internal verdicts prohibit effects. Temporal signal never authorizes action. Only disposable PG16/Chromium tests are permitted; no host/real GLPI/LIVE. D0 integrated CI [#41253703233](https://github.com/alimtalbi-ata/aiops/actions/runs/41253703233) pending at checkpoint; D1/D2/D3/D4 not qualified. Revert focused integration commits in reverse order; discard ephemeral databases.


## ADR-INT-2026-11-01B — Four scoped ports, exact trust boundaries (01:48 CET)

Sole DEV Draft candidate [#234](https://github.com/alimtalbi-ata/aiops/pull/234), main base `ae7c3e5102b99a66bd7806d602146f1309a9749d`, code checkpoint `a44d6aed751b2e4c4cf8ec6e5b00fde29cd1cec3`. Architect selectively copied reviewed exact-head source files from [#240](https://github.com/alimtalbi-ata/aiops/pull/240), [#241](https://github.com/alimtalbi-ata/aiops/pull/241), [#242](https://github.com/alimtalbi-ata/aiops/pull/242), [#243](https://github.com/alimtalbi-ata/aiops/pull/243) in four separate fast-forward commits. No historical PR merge, no main mutation. Final candidate exact-head CI is **PENDING** until the documentary checkpoint is qualified; source CI is not inherited.

ACME site/criticality/blast radius are **synthetic source-pinned estimates**; owner/SLA/OLA/real maintenance and observed impact are UNKNOWN. Portal's OIDC session is **identity only**; exact Run API/HTML remains uniform 503 UNKNOWN with no Core/GLPI fetch before positive actor authorization. Core's independently authenticated GLPI Ticket/Entity/CI readback is a *precondition* for xref VERIFIED, but mocked GLPI HTTP is not real GLPI and does not delegate human actor rights. Policy's no-effect HTTP public contract is unchanged; HITL PG16 5/5 is SQL-model and DR only, not Core claim/ACK or Worker/Temporal restart. The dedicated HITL workflow was adapted to target the candidate PR's `main` base for new exact-head CI. No host, real GLPI write, LIVE or executor.

**Architecture gate:** D0 final exact-head pending; D1 combined disposable and D2 same-SHA browser/API full ITIL story NOT_QUALIFIED; D3 cumulative kit install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. Next contracts: Core actor-bound authorization and independent GLPI readback evidence, Portal positive exact-resource ACL only after Core contract, Policy real disposable Core claim/ACK + Worker restart, ACME Twin source records. Rollback reverse scoped commits #243→#242→#241→#240, discard disposable DB/artifacts; no persistent downgrade validated.


### ADR-INT-2026-11-01C — D0 exact-head source checkout is mandatory

Architect reviewed `.github/workflows/quality.yml` and found all three Quality jobs used bare `actions/checkout@v4`. For `pull_request`, GitHub defaults to the synthetic merge ref, so historical green PR checks **cannot by themselves prove exact source HEAD**, regardless of their job names. Candidate fix `f2bf03f085495348fd80e0acb2a898f9b0b72eb8` pins `github.event.pull_request.head.sha || github.sha`, disables persisted checkout credentials and asserts `git rev-parse HEAD` in each of three jobs. A contract test counts all three guards. Dedicated HITL workflow already pinned exact PR head. **Previous CI remains valid only for its observed checkout revision, not D0 exact-head.** Requalify new candidate and all required checks after this change; no merge to main before D1/D2/D3 gates. Rollback this focused workflow/test commit if broken; do not silently remove head pin.


### Architect cycle — 2026-11-01 02:44 CET — selective integration, NO_GO

SOURCE_REVIEWED: DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft #234 from that base, candidate product checkpoint `7fe177ea165e063a64a80acd22bf4e1a8338b355` (final documentation commit and exact-head CI pending). No whole historical #201/#194/#204 merge. Owner source Drafts all based on prior candidate `d5227f5c3981a53dd2a42d5384dce798cfaf0d33`:

| Owner / source | Exact source HEAD; source CI | Architect selective port / paths | Gate and dependency |
|---|---|---|---|
| Core P0 #246 | `a69e68523b6d690dcb8edbaf8bac57b2e8b8cca0`; [Quality 41260773041](https://github.com/alimtalbi-ata/aiops/actions/runs/41260773041) 3/3; Core 30/30, PG16 installed 3/3 | `5d5f776272f2297f0a2e87cadb1f81c78851422f`; actor_resource_authz, itsm_xref router, Core tests/ADR (5 paths) | IdP introspection mocked; GLPI native human rights, nonce replay ledger and positive ALLOW **not qualified** |
| Portal P0 #245 | `78d0471328268f842e70f5ee5d898cc013b35206`; [Quality 41260115750](https://github.com/alimtalbi-ata/aiops/actions/runs/41260115750) 3/3; Portal 12/12 | `4bcf409c3f2aad27ccaad20ea3cf68dee15b557f`; ACL consumer, tests, OIDC/Core contract (3 paths) | ALLOW-shaped JSON is **not authority**; positive_core_contract_matches remains false, Run 503/UNKNOWN, no upstream |
| Policy/HITL P0 #247 | `dc005302819912f90f32dfc0584ff478fcf756f5`; [Quality 41261752806](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752806) 3/3; [Temporal+PG16 41261752843](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752843) 2/2, Worker 10/10, SQL 5/5 | `b7ab2ab1a5280e98b15805b2d6c7fa9bcac1598e`; Worker pure REJECT adapter, tests, doc, dedicated workflow (4 paths), workflow PR base retargeted to main | No Core claim/ACK HTTP, runtime poller, APPROVE, executor or LIVE; only disposable Temporal Worker restart, no Temporal server restart |
| ACME/Twin P1 #244 | `1c9b6f50c92d43fa893f08bcf0da8964873db4ae`; [Quality 41259232141](https://github.com/alimtalbi-ata/aiops/actions/runs/41259232141) 3/3; catalog 48/48, ACME targeted 85/85 | `7fe177ea165e063a64a80acd22bf4e1a8338b355`; synthetic catalog adversarial tests and provenance doc (2 paths) | Seed 20261018, 18 CI/17 edges, candidate blast radius only; owner/SLA/OLA/Change/real maintenance/observed impact UNKNOWN |

**Decision:** four disjoint, source-reviewed ports to one main-based candidate; all source CI are exact source HEAD, but **do not transfer green by proxy** to the new candidate. New D0 Quality + HITL dedicated runs must check final source HEAD; D1 combined disposable ITIL Event→Incident→Twin→Analyst/Critic→Evidence→HITL→SIMULATE→verification→resolution/reopen NOT_QUALIFIED; D2 browser/API same SHA NOT_QUALIFIED; D3 cumulative kit install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. `#196=FAIL`, provider-reported tokens only, cost UNKNOWN without versioned pricing. No real GLPI/IdP runtime, host or LIVE effects.

**Next owner contracts (WIP P0=3):** Core owns source-authenticated GLPI native actor permission and durable nonce/revocation, plus Core-fenced claim/ACK interface; Portal owns an authenticated transport and no-ALLOW-until-qualified exact Run binding, without overlapping Core files; Policy owns a disposable integration test for Core claim/ACK and Worker/Temporal REJECT with zero effects, without wiring poller; ACME owns independently sourced Twin governance facts and a synthetic end-to-end fixture, never invented SLA/OLA. Architect owns shared CI, migrations and candidate promotion. **Rollback:** revert these four focused commits in reverse order ACME→HITL→Portal→Core, remove disposable databases/artifacts; no persistent-data downgrade claimed and no main reset. `RELEASE_STABLE=NO_GO`.

Architecture boundary: the Core preflight's UNKNOWN and Portal's ALLOW-shaped validator are deliberately incompatible with positive access. A verified service xref is never a human GLPI ACL. Worker REJECT signal is notification, not approval or execution. Preserve ITIL 4 authority of GLPI when independently qualified.


## 2026-11-01 03:48 CET architect update

Single Draft #234 now selectively includes Core #250, Worker #251, Portal #249 and ACME #248 (17 non-overlapping source paths). Exact source CI was green; new candidate exact-head CI must be verified separately. See `docs/release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-0348.md` for exact base/head commits, N/N, dependencies, gates, A/B/C/D automation status and revert. GLPI native actor ACL and combined Core+Worker PG16 HTTP remain NOT_QUALIFIED. D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED. No runtime or LIVE. RELEASE_STABLE=NO_GO.

## Architect integration checkpoint — 2026-11-01 04:50 CET (Europe/Paris)

Decision: sole DEV Draft candidate #234, RELEASE_STABLE=NO_GO. No main merge/push, real GLPI write, Debian/SSH, LIVE or executor. Main SHA ae7c3e5102b99a66bd7806d602146f1309a9749d. Candidate after product port 7321d140ae6658c7e7853422f3af7528c59d97b0 (29 ahead / 0 behind, 81 paths).

Selective SOURCE_REVIEWED port, not source-branch merge: ACME #252 HEAD 6914360b032a5a9a36e5470da395a96bd29afbcc (4 paths, 15-stage ITIL plan NOT_EXECUTED); Portal #253 HEAD 8751db0a2459d29fd3cd3d4ff562289dbed5301d (3 paths, Core UNKNOWN wire, no ALLOW); Core #254 HEAD db3ea1185eb3a991dade183ed7c24587d376317a (3 paths, PG16 populated REJECT tests, synthetic owner HMAC); HITL #255 HEAD c8f135d458b4527210431a5ea5f344495e854616 (3 paths, ASGI HTTP/PG16/Temporal test Worker, REJECT only). Thirteen disjoint owner paths selected by pinned blob SHA. Source CI successful on their own heads; candidate new-head CI PENDING.

Contract order: installed 001/004/009 AI/010 Evidence/011 HITL/012 xref -> Core REJECT claim/ACK -> Worker Temporal test Worker -> Portal negative wire -> ACME synthetic planned vertical. Actor+tenant ALLOW blocked on native GLPI User/Profile/Entity rights, independent OIDC-to-GLPI mapping, nonce/revocation and signed-response contract. Fifteen planned steps are NOT_EXECUTED, no runtime E2E claim.

WIP <=3 P0: Portal ACL (Portal paths); Core GLPI rights, durable replay and migrations (Core paths); Policy/HITL Core-Worker REJECT (Worker paths). ACME P1 fixtures/tools. Architect owns shared workflows, release docs, candidate ref. No overlapping owner paths.

Gates: D0 candidate exact-head CI NOT_VERIFIED after port; D1 combined business integration NOT_QUALIFIED; D2 same-SHA browser/API lifecycle NOT_QUALIFIED; D3 semantic kit and install/upgrade/rollback NO_GO; D4 client signoff NOT_ATTESTED. SOURCE_REVIEWED != CI_PASS != INTEGRATION_PASS != RUNTIME_OBSERVED. #196 FAIL; provider-reported tokens only, cost UNKNOWN.

Rollback: revert candidate-only port commit 7321d140ae6658c7e7853422f3af7528c59d97b0 on a fresh branch, rerun exact-head CI. Never rewrite main. Evidence in source PRs #252/#253/#254/#255 and issue #186.


## ADR 2026-11-01 05:48 Europe/Paris — selective four-owner security and synthetic contracts

The sole integration candidate is Draft #234, DEV main base `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Architect copied **exact source blobs** from focused Draft #256 ACME `39eb0a0ad863046d73b531e3fc595766b2cb8231` (4 paths), #257 Portal `78c039c8186ee9725e1d9264d81725cabfb72cab` (3), #258 Core `bcbafb9ee03410b78487bfb9ddb04b2b59ad3925` (9) and #259 Policy `caab0842911f44d59c274cabaf2a667b4d582094` (3) in integration commit `74fe37e67f540e1b1ebc282dc0e8f26f17a8a25d`, without merging any historical branch. New exact-head CI must be requalified; source green does not transfer.

Authority boundary remains: GLPI is authoritative for native human User/Profile/Entity rights and ITSM/CMDB; IdP for subject/delegation; Core for tenant-scoped Run/Incident/Evidence/xref and immutable nonce/JTI ledger; Portal is a denied-by-default consumer; Policy/HITL is REJECT/no-effect; ACME's seven events, correlation and Twin blast radius are synthetic hypotheses, never observed Incident or verified causality. Migration `013_actor_delegation_replay_ledger.sql` follows 009→010→011→012, but is **not** qualified for persistent-data downgrade or release. A synthetic signed ALLOW shape, HMAC mapping, mocked GLPI 200, and loopback TCP gateway close are not runtime authorization or real network partition. D1/D2/D3/D4 remain NO-GO/NOT_QUALIFIED. Revert integration commit if D0 fails; preserve immutable audit data if 013 was ever applied outside disposable tests. No main merge or host/LIVE effects.


## Architect cycle — 2026-11-01 06:45 CET (Europe/Paris)

**Decision:** sole Draft #234, DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; no main promotion. Product integration commit `44f98ab51a21546efa837bb6571afa08b1e7476f` selectively imports 18 disjoint source blobs from four Draft PRs based on candidate `e8328b9f65fcf01addbe1c59b595466f8e48af15`. All four owner source Quality runs 3/3 SUCCESS, plus Policy combined 1/1, **but new integrated HEAD D0 PENDING until its own CI**. SOURCE_REVIEWED is not CI_PASS, INTEGRATION_PASS or RUNTIME_OBSERVED. `RELEASE_STABLE=NO_GO`.

| Owner / WIP | Source HEAD and exact source CI | Port / contract | Blocker / next |
|---|---|---|---|
| 1 ACME/Twin P1 | #260 `86c024b3174fdafbd6f9caab02c994494f89cd09`, Quality [41275176879](https://github.com/alimtalbi-ata/aiops/actions/runs/41275176879) 3/3; 117/117 targeted | 3 paths, local synthetic test-partition ingestion/dedup, seven events, pinned SAN→Payments reverse graph, seed 20261018 | Partition labels NOT tenants; no Core Incident/Run/Evidence receipts. Next: tenant-authenticated disposable ingestion adapter contract; preserve no-effect |
| 2 Portal P0 | #261 `195dce15e297d3899e1468ceeea189a54c649e0d`, Quality [41275956099](https://github.com/alimtalbi-ata/aiops/actions/runs/41275956099) 3/3; Chromium 12/12 | 3 paths, disposable TLS Chromium/API negative ACL 401/503, revoked/replay/cross-tenant, no Core fetch | Native GLPI actor+tenant ALLOW absent. Next: exact actor-resource delegated rights evidence and non-leaking negative UX, no positive read |
| 3 Core P0 | #262 `a3b476daca767d753c96657feaa5c865d1721a7c`, Quality [41276788868](https://github.com/alimtalbi-ata/aiops/actions/runs/41276788868) 3/3; installed 009→013 PG16 13/13 | 9 paths, native GLPI rights preflight and durable 013 issuer/JTI/nonce replay consume; UNKNOWN-only | No independently observed IdP/GLPI native actor rights; populated COPY restore is not full archive/upgrade/downgrade. Next: independent synthetic-service contract and full 009→013 sandbox restore without deleting audit |
| 4 Policy/HITL P0 | #263 `3ce13e2674ed18fce66a86c19004bcd0b9a61c2b`, Quality [41277445682](https://github.com/alimtalbi-ata/aiops/actions/runs/41277445682) 3/3 + combined [41277445680](https://github.com/alimtalbi-ata/aiops/actions/runs/41277445680) 1/1; combined 5/5 + DR 5/5 | 3 paths, independent disposable Core TCP process, persistent Temporal dev server SQLite restart, Worker REJECT, gateway-close-after-ACK | Not actual packet loss, not real GLPI or IncidentWorkflow. Next: exact tenant/lease fencing under restart with zero effects |

**Order/dependencies:** IdP delegation + native GLPI User/Profile/Entity/Ticket rights → Core exact tenant/Run/Incident/xref and durable 013 consume → Portal signed actor-resource response (currently always UNKNOWN) → Policy REJECT notification only → ACME synthetic Event/Incident projection. Migration order `001→004→009 AI→010 Evidence→011 HITL→012 xref→013 actor replay`; preserve immutable audit. No parallel owner edits to shared Quality, migration ordinals, candidate branch or release docs. Architect owns integration and CI.

**Gates:** D0 integrated exact-head CI PENDING after port; D1 partial disposable REJECT only, full ITIL business NOT_QUALIFIED; D2 same-SHA full browser/API ITIL NOT_QUALIFIED (negative Portal test alone not sufficient); D3 cumulative kit semantic integrity and clean install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. #196 benchmark FAIL, provider-reported tokens only, cost UNKNOWN. No GLPI real write, host/SSH/sudo, executor, LIVE or production. **Rollback:** revert focused integration commit `44f98ab51a21546efa837bb6571afa08b1e7476f` on candidate with a new commit, rerun exact-head CI; retain all 013 audit tables/rows outside disposable; never force-push/reset main.


## Architect integration checkpoint — 2026-11-01 07:44 CET (Europe/Paris)

**Sole candidate:** Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`; refreshed main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (compare identical at read); pre-port candidate `f93a55cebdef017d979e43bba47f08126963048d`. Architect copied **14 reviewed, non-overlapping source Git blobs** into focused candidate commit `ba3e3f39e1097599b9a9a5a91831a0f62cf4a58a` without merging source histories. **D0 exact integrated HEAD CI PENDING until new HEAD logs checked.** No main merge.

| Owner | Source branch/HEAD → Draft PR | Source exact-head CI | Delta and next task |
|---|---|---|---|
| 1/5 ACME/Twin P1 | `feat/acme-itil-replay-verifier-20261101-0700` `3c52fc8688a73144f0ad1544dec28c3e199bbd7f` → [#264](https://github.com/alimtalbi-ata/aiops/pull/264), base `f93a55ce` | [Quality 41279214271](https://github.com/alimtalbi-ata/aiops/actions/runs/41279214271) 3/3; 127/127 targeted | 3 paths: 15-stage offline synthetic verifier + 10 adversarial tests; next: fixture-to-Core readback adapter **only when** real source receipts exist; otherwise emit NOT_EXECUTED |
| 2/5 Portal P0 | `feat/portal-core-tcp-unknown-20261101-0714` `e64ab649f5dba5b3135d4723afdc1da9b0ec4a29` → [#265](https://github.com/alimtalbi-ata/aiops/pull/265), base `f93a55ce` | [Quality 41280139388](https://github.com/alimtalbi-ata/aiops/actions/runs/41280139388) 3/3; Chromium 14/14, consumer 22/22 | 3 paths: independent test-only HTTPS Core UNKNOWN and deny parity; next: server-side fail-closed Core authorization consumer integration, no synthetic ALLOW |
| 3/5 Core P0 | `feat/core-actor-disposable-sources-pg16-archive-20261101-0720` `b3f8a229a2f60d9a72bfaaac2ec225d8bc7cd746` → [#266](https://github.com/alimtalbi-ata/aiops/pull/266), base `f93a55ce` | [Quality 41281162897](https://github.com/alimtalbi-ata/aiops/actions/runs/41281162897) 3/3; Core 75/75, installed PG16 14/14 | 5 paths: independent loopback IdP/map/GLPI mock, PG16 custom dump/restore populated 009→013; next: same-major PG16 client and independently TLS-validated native authority, audit preservation |
| 4/5 Policy/HITL P0 | `feat/p0-worker-multiworker-lease-temporal-restart-20261101-0734` `16d1f3c4236b4a0bbdf6bda22c09ad04fd5bda81` → [#267](https://github.com/alimtalbi-ata/aiops/pull/267), base `f93a55ce` | [Quality 41281513857](https://github.com/alimtalbi-ata/aiops/actions/runs/41281513857) 3/3; [combined 41281513844](https://github.com/alimtalbi-ata/aiops/actions/runs/41281513844) 1/1, 6/6 | 3 paths: two Worker lease race + Temporal server restart, REJECT only; next: adversarial stale lease/ACK replay across separate worker processes, no effect |

**Architecture/reuse review:** no new schema migration or GLPI writer; Core actor stays UNKNOWN despite successful mocked source preflight, Portal does not grant a read on 200 UNKNOWN, Policy never emits APPROVE, ACME projections are not observed ITIL receipts. PG16 restore uses PG18 client generated SQL with only `SET transaction_timeout = 0;` removed; same-major PG16-client restore remains unqualified. Worker gateway-close is injected, not physical packet loss. 013 JTI/nonce/revocation audit is immutable. All four source PRs are Draft, stacked on #234, retained for provenance; no #201/#194 wholesale merge, no automatic green→release inference. Source CI qualification does **not** transfer to candidate.

**Gates:** SOURCE_REVIEWED focused diffs and filenames; source CI_PASS as linked; candidate INTEGRATION_PASS **PENDING exact HEAD**; RUNTIME_OBSERVED only disposable CI after qualification; full ACME Event→Incident→Twin→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→verify→resolution/reopen NOT_VERIFIED; D3 cumulative kit NO_GO; D4 client sign-off NOT_ATTESTED; #196 benchmark FAIL, cost UNKNOWN. **RELEASE_STABLE=NO_GO.** Rollback: revert focused port `ba3e3f39e1097599b9a9a5a91831a0f62cf4a58a` with a new commit, preserve 013 audit data, rerun exact-head CI; no reset/force-push/main mutation. No host/SSH/sudo, real GLPI write, LIVE executor or deployed runtime claims.


## 7. ADR addendum — 2026-11-01 08:48 CET

Selective integration on sole Draft #234 preserves a strict distinction between test-only source evidence and runtime authority. ACME offline receipt requirements cannot become Core/GLPI/Evidence receipts; Portal's independent TLS Core 200 UNKNOWN is never a positive read; native TLS IdP/mapping/GLPI preflight does not grant human authorization; Worker two-process REJECT fencing is a disposable test, not production exactly-once. Core's same-major PG16 archive test remains unqualified (14 PASS / 1 SKIP) and was deliberately **not** ported. Keep actor authorization UNKNOWN and release NO_GO. Detailed evidence and rollback are in [cycle ADR](../release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-0848.md).


## Architect selective integration — 2026-11-01 09:41 CET (Europe/Paris)

**Decision:** keep sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234) on `integration/enterprise-slice-main-20261031-2230`, base current `main=ae7c3e5102b99a66bd7806d602146f1309a9749d` (40 ahead/0 behind before port). Reviewed four focused source Draft diffs and exact changed paths, ported **12 non-overlapping Git blob paths** in product commit `b354c44f26a26a5567b3cf57e0a7d3aa6cf64968` without their branch histories; Core dedicated PG16 workflow trigger adapted to include `main` so the integration PR can qualify its exact HEAD. **New candidate CI is PENDING** until the final docs HEAD is checked. Prior candidate `6a8c9bca` [7/7](https://github.com/alimtalbi-ata/aiops/actions/runs/41286401487) does not qualify this port. No merge to main.

| Owner / priority | Source Draft HEAD | Source exact-head checks | Imported scope / blocker | Next task |
|---|---|---|---|---|
| ACME/Twin P1 | #272 `8ce1c26ef284166c42770d81b58b1c30b5810677` | Quality [41287105440](https://github.com/alimtalbi-ata/aiops/actions/runs/41287105440) 3/3, 148/148 targeted | 3 ACME paths; offline probe only; actor/tenant binding UNKNOWN | Core independently authenticated seven-event binding; ACME may only validate a real readback, never invent receipts |
| Portal/GLPI P0 | #273 `2c2cda0a6dfcbf526bca491338dd40e9054aba7a` | Quality [41288065952](https://github.com/alimtalbi-ata/aiops/actions/runs/41288065952) 3/3, consumer 22/22, Chromium 18/18 | 3 Portal paths; session recheck and Core negative TLS; positive ALLOW prohibited | Native GLPI profile/entity ACL + signed Core response required; test revocation and no browser bearer |
| Core/NOC P0 | #274 `308bf92c311b7f8b07c8bb9f51adc64e8b3ff903` | Dedicated [41288738108](https://github.com/alimtalbi-ata/aiops/actions/runs/41288738108) 1/1 no SKIP, Quality [41288738180](https://github.com/alimtalbi-ata/aiops/actions/runs/41288738180) 3/3 | 3 Core paths; native PG16 16.15 archive/restore 001/004/009–013, audit preserved | Core actor+tenant+source hash readback contract, no positive human authority without independent GLPI |
| Policy/HITL P0 | #275 `2d44dd25eab684104b43cf704d6bb8aef227617f` | Dedicated [41289152239](https://github.com/alimtalbi-ata/aiops/actions/runs/41289152239) 1/1 (8/8 + DR 5/5), Quality [41289152249](https://github.com/alimtalbi-ata/aiops/actions/runs/41289152249) 3/3 | 3 Worker paths; two tenant-scoped synthetic principals, two OS restarts, REJECT-only | Continue isolated ACK/lease replay adversarial checks; no approval/effect/LIVE |

**SOURCE_REVIEWED:** 12 selected source paths; source CI_PASS as linked; new candidate **INTEGRATION_PASS not yet attested**. **RUNTIME_OBSERVED** only disposable CI at source HEAD, no client or Debian deployment. **NOT_VERIFIED:** canonical ACME seven-event Incident/Run actor+tenant+source hash linkage; 15 ITIL stages/6 checkpoints remain NOT_EXECUTED; GLPI native human rights, positive ALLOW, actual Analyst/Critic/Evidence/Policy/HITL/SIMULATE/verify/reopen journey, physical partition, cumulative install/upgrade/rollback, customer signoff. Native PG16 same-major restore is now qualified at **source** only; requalify at integration HEAD. Policy synthetic HMAC and gateway-close are not real OIDC/GLPI authority or physical packet loss. No new migration, GLPI writer or duplicate ledger; 013 audit rows must remain immutable. **D0 PENDING, D1 partial REJECT only, D2 NOT_VERIFIED, D3 NO_GO, D4 NOT_ATTESTED; RELEASE_STABLE=NO_GO.**

**Order/rollback:** #272→#273→#274→#275 selective blobs already combined in one candidate commit; do not merge Draft source PRs or historical #201/#194. For failure, revert product `b354c44f26a26a5567b3cf57e0a7d3aa6cf64968` and its docs commit via *new* commits on #234; rerun exact-head CI, preserve 013 audit and main history, no force-push/reset. Main promotion requires current mergeability, exact HEAD checks, D1/D2/D3/D4 evidence and explicit GO; otherwise keep Draft. No SSH/sudo/host, real GLPI write, LIVE executor or external mutation.


## 2026-11-01 10:40 CET — architect cycle 11: focused integration, authority still UNKNOWN

**Decision:** sole candidate [Draft #234](https://github.com/alimtalbi-ata/aiops/pull/234) based on main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (42 ahead/0 behind *before* this cycle). Prior candidate HEAD `5d06311c6bc53d6d60c54483f485acfa5df8eba8`; focused product commit `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf` imports 14 source file blobs from four Drafts without histories, migration or 013 audit change. New docs commit and **new exact-head CI pending at writing**; prior 8/8 on `5d06311c` does not qualify the new HEAD. No main merge. ADR: [cycle 10:40](../release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-1040.md).

| Team / WIP | Source PR / exact HEAD | Source qualification | Integrated paths and next contract |
|---|---|---|---|
| ACME/Twin P1 | [#276](https://github.com/alimtalbi-ata/aiops/pull/276) `d54be9fe6babe3d60568363d5515e59e6487cda3` | [Quality 41291051671](https://github.com/alimtalbi-ata/aiops/actions/runs/41291051671) 3/3, 160/160 targeted | 3 ACME paths; seven-event SHA shape TEST_ONLY remains UNAVAILABLE, 15 stages/6 checkpoints NOT_EXECUTED. Next: integrate *independently authenticated* Core actor/tenant Incident/Run readback with seven immutable event links in disposable E2E, no invented IDs |
| Portal/GLPI P0 | [#277](https://github.com/alimtalbi-ata/aiops/pull/277) `34115ff47009f7085b3223f90c9feeb9abc3b336` | [Quality 41292392857](https://github.com/alimtalbi-ata/aiops/actions/runs/41292392857) 3/3; Chromium 19/19, consumer 22/22, OIDC 12/12 | 2 Portal paths; 15 re-signed negative variants, valid offline RSA shape never grants ALLOW. Next: native human GLPI User/Profile/Entity permission readback + Core signer/nonce contract, no positive UI until independently attested |
| Core/NOC/CMDB P0 | [#278](https://github.com/alimtalbi-ata/aiops/pull/278) `f8ce7dc7cd8d24decef19847de8720939e6bb745` | [Quality 41292933631](https://github.com/alimtalbi-ata/aiops/actions/runs/41292933631) 3/3; Core 91/91, xref 20/20, PG16 installed 14/14 | 6 Core paths; pinned HTTPS actor/tenant/Run/source event hash preflight before nonce; still 200 UNKNOWN. Next: independently sourced canonical seven-event readback + real native human GLPI authority on disposable stack; do not create parallel CMDB |
| Policy/HITL/Temporal P0 | [#279](https://github.com/alimtalbi-ata/aiops/pull/279) `6c4a8bb03534088355864c1ff41b39e173c2be6a` | [Quality 41293262077](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262077) 3/3; [combined 41293262009](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262009) 1/1, 8/8 + DR 5/5 | 3 Worker paths; two persisted Temporal server restarts/four Worker PIDs, REJECT-only. DEAD is CI SQL-injected, not runtime API; gateway close != physical packet loss. Next: Core-owned runtime DEAD transition/ACK lease fencing without effects |

**SOURCE_REVIEWED** 14 source paths and relevant patches, no overlapping team files; **CI_PASS** at four *source* exact HEADs only at authoring; **INTEGRATION_PASS** pending new candidate exact-head CI; **RUNTIME_OBSERVED** disposable PG16/Temporal/Chromium only, not customer/deployment; **NOT_VERIFIED** independent IdP/GLPI human ALLOW, canonical Core seven-event binding, real ticket/CI readback, full Event→Incident→Twin→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→VERIFY→resolve/reopen, D2 role UX, D3 cumulative clean install/upgrade/rollback, D4 signoff. No runtime positive actor authorization. D0 pending, D1 partial negative REJECT only, D2/D3/D4 NO_GO, **RELEASE_STABLE=NO_GO**.

**Migration/rollback/merge:** no new migration; preserve 001/004/009→013, PG16 16.15 and append-only audit 013. The Worker DEAD fault is disposable SQL injection, not a data migration. Source PRs remain Draft, stacked on former candidate HEAD; never merge their histories or historical #201/#194. Revert the new docs commit then product `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf` via fresh candidate commits, rerun all exact-head checks and retain 013 ledger. Main is unchanged; promotion only via merge commit PR with expected exact SHA, green checks, D1/D2/D3/D4 and GO. No SSH/sudo/Docker socket, real GLPI writes, LIVE or host validation.


## 2026-11-01 11:43 CET — architect selective integration cycle: independent authority remains unqualified

**Single candidate:** [Draft #234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`, main independently checked at `ae7c3e5102b99a66bd7806d602146f1309a9749d` (0 behind before port). Previous candidate HEAD `ab06b95bca2caeffdc4757d671a83700930c8267` had D0 8/8 on [Quality 41294253563](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253563), [native PG16 41294253688](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253688), [combined 41294253489](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253489), [Worker DR 41294253549](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253549), [outbox 41294253557](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253557). Those results **do not** qualify the new HEAD.

**Focused selective product port** `7a1e344313a94335c93fdafd0929c4063e673640`: 13 distinct exact Git blobs, four source Drafts stacked on the prior #234, without their historical commits. No migrations, schema/runtime write, 013 audit mutation, LIVE, host, or real GLPI access.

| Owner / priority | Source HEAD, exact source CI | 13-path port and next contract |
|---|---|---|
| ACME/Twin P1 | [#280](https://github.com/alimtalbi-ata/aiops/pull/280) `98617bb5e0bb248bb81d1bb71112a5c9cbb18e7f`; [Quality 41295561991](https://github.com/alimtalbi-ata/aiops/actions/runs/41295561991) 3/3, targeted 170/170 | 3 paths: seven full-event SHA256 vs Core v1 single `source_payload_hash` is **not** same hash domain. Next: jointly specify canonical serialization with Core; offline fixtures must remain UNAVAILABLE |
| Portal/GLPI P0 | [#281](https://github.com/alimtalbi-ata/aiops/pull/281) `7cd75b6d9ebbf707f80e19dea9b967ccd30fe485`; [Quality 41296693871](https://github.com/alimtalbi-ata/aiops/actions/runs/41296693871) 3/3, consumer 24/24, Chromium/API 43/43 | 4 paths: disposable signed Core + separate native-shaped GLPI human session, negative only; signer and actual native rights not attested. Next: independently sourced IdP/GLPI human User/Profile/Entity/Ticket rights, signer key rotation and revocation |
| Core/NOC/CMDB P0 | [#282](https://github.com/alimtalbi-ata/aiops/pull/282) `9590980f2d273a3cea33ebf0cf68fa03306c7c13`; [PG16 TLS 41297372938](https://github.com/alimtalbi-ata/aiops/actions/runs/41297372938) 1/1 (6/6), [Quality 41297372946](https://github.com/alimtalbi-ata/aiops/actions/runs/41297372946) 3/3 | 3 paths: synthetic PG16 seven-event readback on 001/004/009–013, **test-only** hash domain, no Core runtime seven-event API. Next: Core-owned canonical signed seven-event readback and audited terminal DEAD contract; avoid parallel CMDB |
| Policy/HITL/Temporal P0 | [#283](https://github.com/alimtalbi-ata/aiops/pull/283) `0074f91a25bec7d616eb2ece152b26cafd93c65c`; [combined 41297520143](https://github.com/alimtalbi-ata/aiops/actions/runs/41297520143) 1/1 (9/9 + DR 5/5), [Quality 41297520120](https://github.com/alimtalbi-ata/aiops/actions/runs/41297520120) 3/3 | 3 paths: actual Core claim after eighth lease stays LEASED attempts=8, **not DEAD**; existing DEAD is SQL injected. Next: Worker-only negative contract tests against Core-owned audited runtime DEAD; no APPROVE/effect |

**Architecture decisions:** no promotion from signed synthetic Core ALLOW or GLPI-shaped fixture to human authorization; independent issuer, tenant/actor/Run/ticket/entity, nonce/JTI and 013 ledger are mandatory. ACME full-event and Core source-payload hash domains differ; no seven-event Core runtime binding or verified blast radius. Worker retry exhaustion lacks runtime terminal transition. Temporal signal is notification only. Keep all 15 ITIL stages and six checkpoints NOT_EXECUTED until real synthetic disposable end-to-end receipts.

**Truth labels:** SOURCE_REVIEWED 13 source patches/blobs; CI_PASS four independent source exact HEADs; INTEGRATION_PASS **PENDING** on new candidate HEAD; RUNTIME_OBSERVED only disposable CI sources; NOT_VERIFIED actual human IdP/GLPI rights, Core seven-event production API, D1 complete ITIL chain, D2 operator role journey, D3 cumulative kit install/upgrade/rollback, D4 customer signoff. **RELEASE_STABLE=NO_GO**, keep #234 Draft, main unchanged. No merge despite source green. Revert new docs commit and focused product commit `7a1e344313a94335c93fdafd0929c4063e673640` using new candidate commits, rerun exact-head CI, never reset/force-push or delete 013 audit; main promotion only after D0–D4, expected_head_sha and explicit GO.


## 2026-11-01 12:34 CET — ADR: source preflight ≠ human authorization; host reporter ≠ release

The sole Draft #234 selectively ports #284/#285/#287/#288 in product commit `d3099158201e600d3e62ef7ea58a2366608a92c8` (14 blobs, no schema changes). Core's `aiops.core-canonical-seven-source-binding.v1` is a read-only **negative precondition** using independent HTTPS and disposable PG16; it does not authorize Portal read, grant GLPI native human rights or establish ACME seven full-event hash equivalence. IdP→GLPI signed fixtures remain synthetic, 503 UNKNOWN; a Worker exhausted lease remains LEASED attempts=8, not Core runtime DEAD. A positive human authorization requires independently verified IdP subject, native GLPI User/Profile/Entity/Ticket rights, source-owned Run/Incident, durable revocation/nonce and Core authority, with immutable audit. No parallel GLPI/CMDB, Incident/Run or receipt store.

Existing SRV-DEB-05 read-only reporter publishes canonical `ops/debian-reports/SRV-DEB-05/latest.json` on `ops/debian-runtime-reports`; 2026-11-01 11:29 UTC collection reports 61 containers, 53 running/8 exited, 22 healthy/38 no-healthcheck/1 unhealthy. Healthy rebuild Portal != independently verified operator service; exited/unhealthy rollback container != active outage. #286's additional observer is duplicative and must not be installed/merged wholesale. Host schedule has no SSH access; `deploy/aiops2-stable` is protected by **voluntary** no-push rule because its poller deploys on SHA change. Exact-head source CI cannot qualify the combined #234 head; release remains NO_GO. Details and rollback: [cycle record](../release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-1234.md).


## 2026-11-01 13:42 CET — 8h sprint integration: four exact-head receipt lots

**Sole Draft #234** base main `ae7c3e5102b99a66bd7806d602146f1309a9749d`, prior HEAD `bbe95d9894df13ab910c2b99ccb3d09ec32aa678`; source Drafts #289 `d55049cfc5627db5006667f05d459762002f1012` (ACME P1), #290 `b929bd8b0058c7f2e5a023631de14eae4db15aeb` (Portal P0), #291 `5514ce77728bfd7bf0ce6a1ccf3a6b9a2a9c946d` (Core P0), #292 `df978fc28d0d776e364d83dea587a8d82683f722` (Worker/Policy P0). The architect selectively imports **13 exact Git blob SHAs** (4+2+4+3) without merging source histories, touching migrations, creating a parallel authority or changing main/deploy. Combined new HEAD **CI pending until exact SHA qualification**; previous #234 10/10 is NOT transferable. All source PRs remain Draft.

**Source CI_PASS:** #289 [Quality 41304723889](https://github.com/alimtalbi-ata/aiops/actions/runs/41304723889) 3/3, ACME targeted 193/193 (156 catalogue+22 locator+12 SAN fixture+3 overrides); #290 [Quality 41305414476](https://github.com/alimtalbi-ata/aiops/actions/runs/41305414476) 3/3, Portal browser/API 51/51; #291 [Core PG16/TLS 41306396835](https://github.com/alimtalbi-ata/aiops/actions/runs/41306396835) 1/1 12/12 + [Quality 41306396816](https://github.com/alimtalbi-ata/aiops/actions/runs/41306396816) 3/3; #292 [combined PG16/Temporal 41306864067](https://github.com/alimtalbi-ata/aiops/actions/runs/41306864067) 1/1 10/10 + DR 5/5 and [Quality 41306864394](https://github.com/alimtalbi-ata/aiops/actions/runs/41306864394) 3/3. Source green is not integration runtime evidence.

**ADR/security:** ACME three SHA256 domains are distinct and **not Core runtime equivalence**; its 15 ITIL stages/six checkpoints remain NOT_EXECUTED. Portal's IdP/GLPI and signer/nonce tests are synthetic negative-only (503 UNKNOWN, revoked 401); no real human GLPI rights or positive ALLOW. Core seven-event informational receipt follows disposable TLS+PG16 readback but is nonportable, unsigned and UNKNOWN-only, with immutable migration 013 replay ledger preserved. Worker receipt observes two REJECT outbox events **LEASED attempts=8** across three disposable Temporal server generations, 0 signals/effects/APPROVE; DEAD remains missing in Core runtime (older SQL injection is not runtime). No GLPI write, executor, LIVE or host access.

**Debian runtime evidence:** canonical [latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) collected **2026-11-01 12:39:01 UTC (13:39 CET)**, 61 containers, 53 running/8 exited, 22 healthy/38 no-healthcheck/1 unhealthy. Rebuild Portal/Core running healthy; rollback historical exited/unhealthy does not prove active outage. GitHub reporter publication observed, automatic cron invocation NOT_TESTED. #286 duplicate observer stays Draft; no deploy/aiops2-stable push or Docker/volume change.

**Gates:** SOURCE_REVIEWED=13 source blobs and patches; CI_PASS=source exact-head only; INTEGRATION_PASS=PENDING new candidate SHA; RUNTIME_OBSERVED=disposable CI PG16/Temporal/Portal and read-only published host report only; NOT_VERIFIED=real human IdP/GLPI authorization, ACME→Core full-event equality, Core runtime DEAD, full ITIL E2E, D3 cumulative kit/rollback, customer validation. **RELEASE_STABLE=NO_GO**, #234 Draft, main unchanged. **Rollback:** revert only this selective candidate commit via new PR commit, requalify exact HEAD; preserve migrations 009–013, immutable 013 audit, Docker volumes and main history.


## 2026-11-01 15:21 CET — single-stack 7777 decision and Core 014 selective integration

**Decision:** sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), main `ae7c3e5102b99a66bd7806d602146f1309a9749d` unchanged. The architect selectively ports **five Core-owned exact blobs** from Draft [#295](https://github.com/alimtalbi-ata/aiops/pull/295) HEAD `f4c177f4415f0ae0f1b5f2162e687b25dbdbc64e`: handler, migration **014**, PG16 test, dedicated workflow, ADR. Source [Core terminal PG16 #41315653226](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653226) 1/1 SUCCESS, **12/12** adversarial tests; [native recovery #41315653322](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653322) 1/1 SUCCESS with 001/004/009→014 archive restore; source Quality [#41315653230](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653230) 3/3 SUCCESS. **Candidate new HEAD CI is PENDING; old candidate 10/10 does not transfer.** Worker [#296](https://github.com/alimtalbi-ata/aiops/pull/296) negative route-absent test is **not ported** before a new positive integration test on 014. All source PRs stay Draft; no PR merge.

**Host snapshot:** [GitHub latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) `2026-11-01T14:19:01.751858+00:00` = 15:19 CET, **61 total / 53 running / 8 exited**, rebuild Portal/Core running healthy; historical rollback portal exited/unhealthy. Loopback **17777 reachable**, **host TCP 7777 NOT_VERIFIED** (no PortBindings, proxy, ss, firewall, TLS/Host or public HTTP proof). **One existing stack** is target; no second portal/Compose project. See [consolidation plan](../operations/AIOPS2-SRV-DEB-05-SINGLE-STACK-7777-PLAN-2026-11-01.md) and [non-deployable manifest](../../ops/debian/compose.canonical.plan.yml) with KEEP/MIGRATE/STOP-LATER/UNKNOWN and host read-only evidence gates. #286 duplicate observer remains Draft. No host SSH/Docker execution, stop, migration, GLPI write, LIVE, volumes change or deploy branch push.

**WIP:** Portal P0 [#298](https://github.com/alimtalbi-ata/aiops/pull/298) HEAD `0a527ce265ad107651b7db9c2ca255ed5f38ff77`, Quality [#41315561070](https://github.com/alimtalbi-ata/aiops/actions/runs/41315561070) 3/3, 55/55 negative, **7777 host unknown**; Core P0 #295 12/12+restore, integrated candidate requalification pending; Worker/Policy P0 #296 HEAD `a96111982d43accdb9dc7cede2f1c466fab70baa`, combined [#41311898721](https://github.com/alimtalbi-ata/aiops/actions/runs/41311898721) 11/11+DR 5/5, negative 404 only, positive 014 not integrated; ACME P1 #297 HEAD `a4daed17b6452ca6179f9007780700ee9a795429`, Quality [#41314428648](https://github.com/alimtalbi-ata/aiops/actions/runs/41314428648) 3/3, 210/210 synthetic. Actor/tenant/GLPI native rights, Core signer, full ACME ITIL 15 stages/6 checkpoints and 7777 host remain **NOT_VERIFIED**. **RELEASE_STABLE=NO_GO**.

**Rollback:** revert the new selective candidate commit (Core 014 code + docs) by a forward commit, never DROP 013/014 or delete immutable audit; preserve existing volumes, images, backup and `main` history. Requalify new exact HEAD before any merge; no deploy.


## 2026-11-01 16:14 CET — Core 014 Worker qualification

Core owns terminal REJECT to DEAD and immutable 013/014 audit. Candidate #234 selectively imports Worker #299 positive PG16/Temporal tests, source CI 41316946503 (1/1 positive + 5/5 DR) and Quality 41316946593 (3/3). Candidate exact-head CI must requalify. Main-based workflow excludes raw PG16 archive uploads. No real GLPI approval or host changes. Host TCP 7777 NOT_VERIFIED; loopback 17777 is different. RELEASE_STABLE=NO_GO.


## 2026-11-01 16:25 CET — canonical Core and Portal OIDC fence

Core #302 fixes a critical integration gap: the terminal /dead handler existed but was not mounted on canonical core.main.app. Four focused files were imported into Draft #234; disposable source PG16 canonical HTTP 14/14 and native restore passed. Portal #301 rejects invalid/revoked OIDC cookie downgrade to viewer bearer, requires HTTPS same-Origin and preserves 503 UNKNOWN for unqualified Run; source Chromium/API 54/54 passed. Neither synthetic test proves human GLPI rights, Debian 7777 reachability or a full ITIL incident journey. Candidate exact-head requalification required; RELEASE_STABLE=NO_GO.

## 2026-11-01 17:18 CET — Integrated negative authority, canonical DEAD gateway, Portal duplicate cookie

Sole Draft #234 selectively reuses source Draft #303 (canonical Core TCP /dead gateway-close replay with persisted Temporal restart, 2 Core-owned immutable 014 receipts), #304 (seven ACME local SHA-domain negative fixture, Core PG16 authority UNAVAILABLE) and #305 (duplicate OIDC cookie rejection and HTTP/HTTPS Origin coherence). The Worker workflow also targets main-based candidate PRs to require exact-head PG16 tests. Source heads e9812307647bd455bf9e8c66aaebb5523d900020, 20f6d5da4ee151510dd854b9a90ad1ba50f6433a, fb9089256e901764a86a8e137dde88391589152a. Source CI success is not integrated-head CI; requalification pending. No second Core authority, no GLPI write, no LIVE, no host action. Real GLPI human rights, signed Core authority, seven-event persisted Core equality, 15-stage ITIL journey and Debian TCP 7777 remain NOT_VERIFIED. RELEASE_STABLE=NO_GO.


## Architect integration cycle — 2026-11-01 18:19 CET (source qualification; new exact-head CI pending)

- Single Draft integration PR [#234](https://github.com/alimtalbi-ata/aiops/pull/234); pre-port candidate `e484f2e17bf4c72e4c5319e2e92f32430b4ec3b0`, verified DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (62 ahead / 0 behind). New candidate HEAD and its exact CI must be read from GitHub after this commit. **Do not transfer the old 10/10 CI to the new HEAD.** No main merge, no host write.
- **SOURCE_REVIEWED:** 14 exact Git blobs selectively imported from four independent focused Drafts, not their branch histories: Core [#306](https://github.com/alimtalbi-ata/aiops/pull/306) `73967f349057e852ad5329852804d7412a3ac753` (3 Core test/workflow/ADR paths, base `5045dfa0` but both preexisting paths blob-identical on current candidate); Worker [#307](https://github.com/alimtalbi-ata/aiops/pull/307) `a9e1a56c7030b38f9a3a0079f073d5a0a6c848fa` (3 paths); ACME [#308](https://github.com/alimtalbi-ata/aiops/pull/308) `3368e068919b938898966ad16117e0daf06eecb2` (4 paths); Portal [#309](https://github.com/alimtalbi-ata/aiops/pull/309) `5b5d0960ed092c69068fd1e4f1a9ca72ff435b73` (4 paths). Source PRs are Draft and remain unmerged. No migrations or new persistent stack.
- **Source CI_PASS only:** Core [#41325667604](https://github.com/alimtalbi-ata/aiops/actions/runs/41325667604) 15/15 PG16, Quality [#41325667635](https://github.com/alimtalbi-ata/aiops/actions/runs/41325667635) 3/3; Worker [#41326736739](https://github.com/alimtalbi-ata/aiops/actions/runs/41326736739) 2/2 + DR 5/5, Quality [#41326736701](https://github.com/alimtalbi-ata/aiops/actions/runs/41326736701) 3/3; ACME [#41329857661](https://github.com/alimtalbi-ata/aiops/actions/runs/41329857661) Quality 3/3, targeted 210/210; Portal [#41330094178](https://github.com/alimtalbi-ata/aiops/actions/runs/41330094178) Quality 3/3, browser/API 58/58. These qualify **source heads only**. New combined exact-head CI, PG16 009–014 DR, Chromium/Portal and ACME/Worker interplay remain **NOT_VERIFIED** until GitHub Actions completes.
- **Contracts:** Core post-DEAD credential/permission/provenance revocation returns 401/403/UNKNOWN without rewriting immutable 014; Worker 18 concurrent post-DEAD HTTP retries/ACK/claim after persisted Temporal restart remain REJECT/zero effects; ACME consumes only untrusted seven-event offline readback as UNKNOWN, 15 ITIL stages and six checkpoints NOT_EXECUTED; Portal refuses split Cookie headers and forged GLPI rights, pins HTTPS callback :7777 (never :17777), 401/503 fail-closed. These are disposable synthetic tests, not native human GLPI authority or host listener evidence.
- **RUNTIME_REPORTED, not new runtime test:** GitHub `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected_at `2026-11-01T17:14:01.198403+00:00` (18:14 CET), 61 containers / 53 running / 8 exited; `aiops2-rebuild-portal` healthy, `aiops2-portal-candidate-web-20261029` running/no healthcheck, rollback exited/unhealthy. Host TCP **7777 NOT_VERIFIED**; report lacks complete PortBindings, reverse proxy, firewall and traffic ownership. No host migration/stop performed.
- **Gate:** D0 integrated CI pending, D1 partial REJECT-only, D2 15-stage operator/GLPI HITL NOT_VERIFIED, D3 cumulative kit NO_GO, D4 human signoff NOT_ATTESTED. **RELEASE_STABLE=NO_GO.** Retain single DEV stack target `aiops2-rebuild-*`, classify duplicates UNKNOWN pending read-only mapping, no Docker/volume deletion or `deploy/aiops2-stable` push.
- **Rollback:** forward-revert only this 14-blob + three-document commit on the integration branch, then requalify exact new HEAD; never rewrite main, drop migrations 009–014, immutable 013/014 audits, DB or Docker volumes. If promotion is ever approved, merge via PR with exact expected HEAD and separately planned revert.
- **Next:** recheck all exact-head GitHub Actions; Core independently authenticated seven-event PG16 actor/tenant/Run proof, Portal GLPI native human authorization + 7777 host attestation, Worker concurrency stress boundary, ACME complete authorized ITIL scenario. Three P0 (Core, Portal, Worker), ACME P1. 


## Architect cycle — 2026-11-01 19:2x Europe/Paris (selective source port; D0 requalification pending)

- **Base:** main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft #234 previous exact HEAD `e6381a6d7e8e088add37e6e28e9fde9ef543a9ff` (63 ahead/0 behind). New integration HEAD must be re-read and exact-head CI requalified after this commit; source CI cannot be transferred. No direct source PR merge, no main/deploy merge.
- **Core #310** `df845f9ea800c6956d96f3911e720e044ad2af2c`: 3 Core paths, PG16/TLS 14/14 and zero SKIP [#41336002970](https://github.com/alimtalbi-ata/aiops/actions/runs/41336002970), Quality 3/3 [#41336003122](https://github.com/alimtalbi-ata/aiops/actions/runs/41336003122); stale/expired independent transport evidence -> UNKNOWN, immutable 013/014 + native PG16 restore; synthetic 014 fixture not a runtime /dead.
- **Worker #311** `2ec1aef8952ea98ca69626ee8a4daf52f5303ed9`: 3 Worker paths, canonical 2/2 + revocation 1/1 + PG16 DR 5/5 [#41332063971](https://github.com/alimtalbi-ata/aiops/actions/runs/41332063971), Quality 3/3 [#41332063977](https://github.com/alimtalbi-ata/aiops/actions/runs/41332063977); CI-only proof withdrawal, Core 012 immutable trigger preserved, gateway close injected, physical partition NOT_TESTED.
- **ACME #312** `e1c5d1a7efeef318ac85c9b48e8110442237cc35`: 4 ACME paths, targeted 220/220, Quality 3/3 [#41334336181](https://github.com/alimtalbi-ata/aiops/actions/runs/41334336181); 7 synthetic events, 15 stages and six checkpoints NOT_EXECUTED/UNKNOWN, no positive ALLOW.
- **Portal #313** `e250bb8c16c50254f5ce0a22b7258cc4b0dc38c3`: 2 Portal paths, browser/API 59/59, Host/OIDC 8/8, Quality 3/3 [#41335292014](https://github.com/alimtalbi-ata/aiops/actions/runs/41335292014); forged human GLPI rights fail closed, 7777 contract not host verification, 17777 distinct.
- **Architecture/ownership:** only selected 12 exact Git blobs from these four source Drafts, no source history merge and no schema migration. Core owns authenticated source binding, Portal owns human GLPI visibility gate, Worker owns no-effect retry fencing, ACME owns offline ITIL replay. No new parallel ITSM/CMDB or persistent host stack. D0 integrated CI PENDING until exact HEAD run; D1 partial negative-only; D2/D3/D4 NO_GO. SOURCE_REVIEWED on diffs, source CI_PASS, INTEGRATION_PASS NOT_VERIFIED, RUNTIME_OBSERVED only through GitHub Debian reporter, not current candidate runtime.
- **Debian read-only** `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected `2026-11-01T18:19:01.241861+00:00`, 61 containers (53 running, 8 exited). `aiops2-rebuild-portal` healthy, candidate portal also running. Host TCP 7777 NOT_VERIFIED (only 17777 loopback probe). Keep canonical rebuild services; parallel groups UNKNOWN until digest, Compose labels, network/port bindings, traffic, DB ownership, volumes, backups and rollback inspected. No STOP, prune, down -v, new stack or deploy/aiops2-stable change.
- **Rollback:** forward-revert this selective port on #234 (12 source paths and these docs), preserve immutable Core 013/014 audit, database/host volumes and history. Re-run exact-head CI after revert. **RELEASE_STABLE=NO_GO.**


## Architect cycle — 2026-11-01 20:19 CET — ACME/Portal focused source integration

- **Refs before port:** DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234) `466cc80e7d1c651ad48791cbbfa7ac7fc6d1c6c6`, 64 ahead / 0 behind. New exact candidate SHA/CI MUST be requalified; old [D0 10/10 workflows, 13/13 jobs](https://github.com/alimtalbi-ata/aiops/issues/186#issuecomment-6562045016) applies only to old SHA. No main merge.
- **ACME/Twin P1 [#314](https://github.com/alimtalbi-ata/aiops/pull/314)** source `31367d1451a1a74ec3d1332d152e23e1d2044582`, 5 paths, [Quality #41339765432](https://github.com/alimtalbi-ata/aiops/actions/runs/41339765432) 3/3 and **230/230** targeted. Synthetic offline seven-event local/Core-shaped hash matrix; independent **TEST_ONLY_UNTRUSTED_NOT_PG16** vector never confers authority; actual Core PG16 hashes null, all 15 ITIL stages + 6 checkpoints NOT_EXECUTED. No real Incident/Run/GLPI/Evidence/HITL IDs.
- **Portal/GLPI P0 [#315](https://github.com/alimtalbi-ata/aiops/pull/315)** source `c308b7bcb31029887e42656364cd7fae520792d4`, 2 paths, [Quality #41340603232](https://github.com/alimtalbi-ata/aiops/actions/runs/41340603232) 3/3, **60/60 browser/API**, **10/10 native mock**, **24/24 consumer**. Two separate disposable TLS mock peers; seven native GLPI READ/READMY negatives, six Core signature/expiry/tenant/nonce negatives; synthetic signed ALLOW + mock READ remains 503 UNKNOWN, revoked OIDC 401. Human native GLPI READ independently NOT_ATTESTED.
- **Debian:** user/operator attests *local* `aiops2-rebuild-portal` running/healthy, `0.0.0.0:7777->777` and `/health` HTTP 200 JSON `external_port=7777`: **7777 LOCAL OPERATOR_VERIFIED**, not independently schedule-observed; external TLS/SSO/GLPI E2E, traffic, uniqueness remain NOT_VERIFIED. [GitHub reporter latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) collected `2026-11-01T19:14:01.516272+00:00`, **61 total / 53 running / 8 exited**; `aiops2-portal-candidate-web-20261029` still running; 17777 probe false, 7777 absent. Reporter lacks PortBindings/digests/Compose labels/traffic/volume ownership; no host change. Keep rebuild canonical, classify duplicate UNKNOWN pending read-only mapping, backup and rollback, no STOP.
- **Ownership:** Core P0 independent seven-event PG16 actor/tenant/Run+013/014 audit; Portal P0 native human GLPI trust; Worker P0 post-DEAD concurrent no-effect; ACME P1 honest offline ITIL comparison. Only 7 selected source Git blobs plus these 3 docs, no source history, migration or cross-owner files.
- **Truth/gates:** SOURCE_REVIEWED=2 PR diffs, source CI_PASS=2/2, new integrated D0 CI_PENDING; INTEGRATION_PASS=NOT_VERIFIED until new exact-head jobs. RUNTIME_OBSERVED=operator-local 7777 + published reporter only, NOT new code. D1 partial negative-only; D2 GLPI HITL/ITIL full journey NO_GO, D3 cumulative kit NO_GO, D4 client signoff NOT_ATTESTED; **RELEASE_STABLE=NO_GO**. No deploy/aiops2-stable push, SSH/Docker, GLPI write, LIVE, new persistent stack, DB/volume deletion.
- **Rollback:** forward-revert only this focused candidate commit, rerun exact-head CI, preserve Core 013/014 immutable audit, Docker volumes and main history; no force-push/reset.
