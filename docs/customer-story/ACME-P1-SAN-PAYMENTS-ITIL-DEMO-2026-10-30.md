# Customer demonstration — P1 Payments incident caused by SAN path degradation

**Scenario:** ACME synthetic enterprise. **Mode:** DEMO / synthetic only.  
**Purpose:** demonstrate operational realism and traceability; this is not a real customer incident or production integration.

## Customer-facing narrative

At 09:42, monitoring raises a critical event on the SAN fabric serving Payments. A service-level observation then shows payment latency above the agreed SLO. The NOC does not jump directly to remediation: it validates the affected service and CI path, checks current and contradictory evidence, correlates related events, and escalates as a P1 candidate.

The operator sees one incident timeline rather than separate dashboards with unrelated IDs. N1 acknowledges and owns communication; N2 investigates storage/network evidence; N3 validates the service dependency and runbook. The incident commander is assigned under the P1 major-incident process. GLPI provides the ticket and CMDB reference when an authenticated lookup confirms them.

The AI Analyst ranks hypotheses and recommends bounded diagnostic/corrective options with evidence citations. The Critic independently challenges unsupported claims, stale measurements, contradictory paths and unsafe actions. Policy evaluates the structured proposal. If approval is required, the HITL view shows who is authorized, what CI/action/scope is proposed, why it is needed, the preconditions, expected postconditions, expiry and rollback plan.

The demonstration then executes only a synthetic simulation in the isolated lab. It records what would have changed, but it does not SSH to a server, run sudo, alter a real SAN, close a real GLPI ticket or authorize LIVE remediation. A separate verification step evaluates the simulated postconditions. The operator closes the loop with a synthetic ticket update, Problem candidate, post-incident review and knowledge improvement.

## What the client should see

1. NOC cockpit with source freshness, P1 priority rationale and service impact.
2. Canonical Incident/Run IDs and event timeline with timestamps.
3. Twin path SAN → storage → Payments, each edge sourced and freshness-labelled.
4. Evidence cards with source, observed_at, known_at, hash and provenance.
5. Analyst hypotheses and alternative explanations with citations.
6. Critic disposition, objections and missing evidence.
7. Policy decision, risk, reason codes and approval requirement.
8. HITL proposal hash, actor roles, expiry, scope and rollback.
9. SIMULATE receipt, before/after hypothesis and explicit no-effect boundary.
10. Independent verification, reconciliation, GLPI ticket link and PIR/Problem candidate.

## Narration rules

- Say "synthetic" at the beginning and keep the marker visible.
- Never claim Checkmk, GLPI, CMDB, SSO, RAG, model or executor is connected unless the current run provides evidence.
- Never use a confidence score as a calibrated probability unless calibration has been validated.
- Show UNKNOWN and explain the missing source instead of filling the gap.
- Distinguish recommendation, approval, effect, verification and ticket closure.
- A successful simulation is not a production remediation success.

## Rehearsal checklist

- [ ] Exact scenario fixture/version/hash recorded.
- [ ] Incident and Run IDs verified through Core API.
- [ ] Twin edges sourced; unsupported edges shown UNKNOWN.
- [ ] Ticket ID read from GLPI and mapped to same Run, or shown UNKNOWN.
- [ ] Evidence refs match Analyst/Critic and run events.
- [ ] Critic and Policy negative paths demonstrated.
- [ ] HITL approval identity verified or demo-only simulated identity labelled.
- [ ] No-effect simulator receipt confirmed; effect_receipts count remains zero.
- [ ] Verification uses independent fixture observations.
- [ ] Full event timeline, test output, screenshot/video capture and package hashes saved.

## Synthetic full lifecycle read model — 2026-11-14

The existing Portal now exposes **GET `/api/demo/acme-lifecycle`** as a no-store, read-only projection of the validated ACME impact fixture. It covers observability, incident correlation, business impact, Analyst/Critic, ITIL ticket, Policy/HITL, orchestration, independent verification, and ITIL Problem/PIR. Every phase is **UNKNOWN** until independently authenticated runtime evidence exists; no synthetic checkpoint can be promoted to PASS. The model rejects an asserted real GLPI ticket, runtime timestamp, runtime attestation, or LIVE qualification, and returns HTTP 503 for an invalid source. The source SHA-256 and SAN→Payments impact path are carried through.

This API is **not** a runtime incident lifecycle engine, Temporal workflow, GLPI writer, AI Analyst execution, or production verification. No LIVE capability is exposed. Offline tests and CI guard against laundering simulation into production evidence.

## ITIL transition readiness, no inferred remediation — 2026-11-14

Read-only **GET `/api/demo/acme-itil-readiness`** derives eight explicit ITIL transition gates from the nine-stage synthetic lifecycle: acknowledge P1, declare impact, propose remediation, request HITL, simulate, verify recovery, resolve, and close/open PIR. Each gate lists its required independent checkpoints and remains **UNKNOWN / unauthorized** because the local fixture provides no runtime evidence. Any forged stage PASS, LIVE Policy decision, effect receipt or runtime attestation causes rejection; invalid fixture yields HTTP 503. This is a diagnostic readiness view, **not** an authorization engine, GLPI write, Temporal execution or real incident resolution.

## Operator-facing ITIL evidence view — 2026-11-14

The existing Portal additionally serves **GET `/demo/acme-itil-readiness`**, a static French operator table showing each transition, its UNKNOWN readiness, missing independent checkpoints and explicit non-authorization. The page uses no scripts, forms, backend writes, or live service calls. It carries the fixture SHA-256 and an always-visible SIMULATION / NO-GO LIVE warning. API and page fail HTTP 503 on unqualified fixture data.

## Independent evidence collection contract — 2026-11-14

GET `/api/demo/acme-evidence-plan` provides a **non-executable** checklist for all nine lifecycle checkpoints, including expected source (Grafana, n8n, GLPI), evidence type, and minimum metadata (observation time, source ID, SHA-256). The plan records zero accepted/verified evidence, no outbound collection, no GLPI writes, no Temporal execution, and no LIVE authorization. This is a preparation contract only; independently authenticated evidence ingestion and attestation remain future work. A forged PASS in the synthetic lifecycle is rejected rather than silently accepted.

## Offline evidence manifest inspection — 2026-11-14

`portal.acme_evidence_manifest_validator.inspect_synthetic_evidence_manifest` accepts a strictly shaped **in-memory** DEMO metadata manifest for independent review. It checks scenario SHA-256/incident binding, unique checkpoints, expected source/evidence type, UTC observation timestamps, bounded source IDs and lowercase SHA-256 syntax. **A well-formed manifest is not an authenticated proof:** every item remains `UNVERIFIED`, zero evidence is independently verified, and no ITIL transition, GLPI write, Temporal action or LIVE remediation is authorized. There is deliberately no HTTP upload/acceptance route, no persistence and no remote evidence fetch. Future ingestion requires a separately reviewed tenant/actor trust boundary and source attestations.

## Operator-facing evidence checklist — 2026-11-14

GET `/demo/acme-evidence-plan` now renders the nine independent evidence requirements as a static French table in the canonical Portal: checkpoint, lifecycle phase, expected source, proof type, required metadata and MISSING status. The page visibly shows **0/9 verified**, the source fixture SHA-256, and the NO-GO LIVE warning. There are no scripts, forms, upload capabilities or backend calls. A broken or unqualified synthetic fixture fails HTTP 503.

## Analyst / Critic / Policy evidence review — 2026-11-14

GET `/api/demo/acme-analyst-critic-review` cross-checks the fixture's deterministic Analyst hypothesis, Critic HOLD and Policy DENY against the independent proof plan. The output explicitly lists missing `analyze`, `approve` and `verify` checkpoints, zero verified runtime citations and no verified HITL, simulation or postcheck. This is **not** an LLM call or independently sourced Critic decision; any forged LLM attestation, approval or LIVE authorization fails HTTP 503. No backend action is triggered.

## Unified synthetic incident cockpit — 2026-11-14

GET `/api/demo/acme-incident-cockpit` composes **one** validated ACME fixture snapshot into the nine-stage lifecycle, eight ITIL transition gates, nine evidence requirements and Analyst/Critic/Policy review. The composite checks cross-view incident IDs, fixture SHA-256, DEMO provenance and the absence of runtime evidence or execution authority before returning. If any projection is inconsistent or unqualified it fails HTTP 503. The result is a read-only **synthetic operator API**, not an incident engine connected to real monitoring, GLPI, Temporal, LLM or vault services.

## Unified operator cockpit page — 2026-11-14

GET `/demo/acme-incident-cockpit` renders the consolidated read-only synthetic incident view: SAN P1 → Payments P2 business impact path, nine lifecycle stages, eight ITIL transitions with missing evidence, Analyst/Critic/Policy HOLD/DENY, zero of nine independently verified checkpoints, and the fixture SHA-256. The page is script-free, form-free, no-store and always displays **DEMO SYNTHÉTIQUE — NO-GO LIVE**. It is backed by the same cross-checked snapshot as `/api/demo/acme-incident-cockpit`; invalid fixtures and forged success are rejected.

## ITIL incident handoff draft — 2026-11-14

GET `/api/demo/acme-itil-handoff-draft` generates a deterministic **non-executable** incident handoff draft from the consolidated ACME cockpit: SAN P1 source, Payments P2 impact path, proposed priority, hypothesis/Critic/Policy statuses, nine evidence requirements and operator next step. Its content has a stable SHA-256 for offline comparison. It is **not** a GLPI API payload: `glpi_ticket_id=null`, `glpi_payload=null`, `glpi_write_performed=false`; no approval, transition or LIVE authority. Any unqualified fixture fails HTTP 503. Authenticated GLPI ticket creation and HITL require separately qualified actor/tenant authorization and explicit operational approval.

## Independent read-only evidence digest comparison — 2026-11-14

`portal.acme_evidence_digest_readback.compare_synthetic_evidence_readbacks` adds a **callable-based readback boundary** to the offline DEMO evidence workflow. It validates the untrusted manifest **before** invoking a caller-supplied independent byte reader, compares SHA-256 against the actual returned bytes (bounded to 1 MiB), and records `DIGEST_MATCH_UNATTESTED`, `DIGEST_MISMATCH` or `READBACK_UNAVAILABLE` without exposing callback errors or bytes. A matching digest establishes only byte consistency: it **does not authenticate the source, tenant, freshness, HITL or runtime state**. Thus independently attested count remains zero and no evidence is accepted or ITIL/LIVE action authorized. This module deliberately has no HTTP route or default network adapter; a production source adapter requires separately qualified tenant/actor and source trust.

## Tenant/source-bound receipt integrity (offline) — 2026-11-14

`portal.acme_evidence_source_binding.inspect_source_bound_receipts` verifies an offline DEMO receipt MAC using a **caller-supplied trusted key resolver** keyed by tenant and source. The canonical signed body binds checkpoint, source, source ID, content digest, observation timestamp and fixture SHA-256. It rejects duplicate checkpoints and unrecognized claims; unavailable keys or MAC mismatches fail closed. A valid MAC is `MAC_VALID_SOURCE_KEY_UNATTESTED`: it does not authenticate a live monitoring session, establish tenant/actor ACL, independently verify observations or grant an ITIL/LIVE action. There is no endpoint, secret storage, default resolver or external call; source key provisioning and real attestation remain out of scope.

## Joint evidence integrity gate — 2026-11-14

`portal.acme_evidence_joint_qualification.qualify_synthetic_evidence_jointly` combines independent byte digest readback with the tenant/source-bound HMAC receipt check. A checkpoint is marked `integrity_consistent_unattested=true` only when **both** checks agree; a missing receipt, wrong MAC, changed bytes or unavailable callback fails that consistency check. Even a double match remains **UNKNOWN / unattested**: the module cannot prove source freshness, tenant/actor authorization, real runtime observation or operational effects. No HTTP upload, network adapter, GLPI write, Temporal execution or LIVE authorization is exposed.

## Cross-tenant receipt isolation hardening — 2026-11-14

The joint evidence qualification now **requires** a trusted, independently supplied `expected_tenant_id` keyword argument. All submitted receipt tenant IDs must match this scope before any key resolver or readback callback runs. A valid receipt from tenant B must not be processed in tenant A's context. This is a defensive tenant scope fence, **not** actor authentication or a production ACL grant; the trusted caller must establish the expected tenant independently. Tests cover foreign-tenant refusal without callbacks and missing/empty trusted tenant.

## Readback preflight hardening — 2026-11-14

Joint evidence qualification now blocks the independent byte reader **before** any external readback when a checkpoint has no source receipt, an invalid MAC, or a missing source key. The digest comparison then reports `READBACK_UNAVAILABLE`; it does not fetch untrusted or foreign-source content and only reports `DIGEST_MATCH_UNATTESTED` after the source MAC preflight succeeds. Tenant scope remains independently required. This is still offline DEMO-only, not source runtime attestation or an authorization to act.

## Cross-checkpoint source-address alias protection — 2026-11-14

The joint evidence reader addresses a source by `(source, source_id)`. It now refuses a manifest containing that same address under two distinct checkpoints, **before any resolver or readback callback**, because a valid receipt for one checkpoint could otherwise unlock the other's external readback. This is an integrity isolation guard for the offline DEMO adapter; it does not establish LIVE source identity or tenant/actor authorization.
