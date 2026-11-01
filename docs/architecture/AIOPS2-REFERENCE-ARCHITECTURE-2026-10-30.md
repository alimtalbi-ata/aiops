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
