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

## Pure DEMO remediation simulator — 2026-11-14

`portal.acme_isolated_remediation_simulator.simulate_remediation_dry_run` provides a deterministic **in-memory hypothetical** state transition for `SERVICE_RESTART_SIMULATION` or `NOOP_OBSERVATION` under explicit `DEMO` / `SIMULATE_ONLY` inputs. The result includes request, before/after and receipt SHA-256 digests; `verify_simulation_receipt` independently recomputes the expected output to detect tampering. A hypothetical HEALTHY state is **not actual recovery**: no worker, Temporal execution, command, network call, post-check, GLPI write or LIVE authorization is performed. The module is not exposed as a production endpoint.

## Simulation receipt × evidence integrity gate — 2026-11-14

`portal.acme_simulation_evidence_gate.assess_simulation_evidence_gate` checks the deterministic simulator receipt by recomputation, enforces the same expected tenant and validates the joint evidence integrity summary, rejecting forged authorization, recovery and attestation flags. It outputs a linked simulation receipt hash and hypothetical after-state hash, but keeps `actual_recovery_state=UNKNOWN`, `independent_runtime_postcheck_verified=false` and ITIL/LIVE authorization false. It is an offline DEMO assessment only, not an operational post-check or a Temporal/Worker execution.

## Incident digest binding for simulation/evidence join — 2026-11-14

The simulation/evidence gate now requires a **trusted independently supplied** `expected_source_sha256` (exact lowercase 64-character SHA-256). The joint evidence report must match it, as well as the expected tenant from the simulation request. This prevents an internally consistent evidence summary for a different incident fixture being attached to the simulation. The caller must obtain the digest from a trusted validated incident context, not from the submitted evidence report itself. This remains DEMO-only and never proves live incident identity or authorizes remediation.

## Independent incident identity fence — 2026-11-14

The simulation/evidence gate additionally requires `expected_incident_id` from a trusted incident context, independent of the submitted simulation request. It rejects a valid simulation receipt bound to a different incident **even within the same tenant**. Both the incident ID and source fixture digest must come from the trusted context; copying either from untrusted input defeats the intended boundary. No production authorization is inferred.

## Callable incident → simulation → evidence gate DEMO — 2026-11-14

`portal.acme_demo_simulation_pipeline.run_acme_demo_simulation()` now composes the validated ACME incident cockpit snapshot, a deterministic hypothetical Payments restart, and the simulation/evidence safety gate **in one callable path**. The trusted incident ID and fixture digest come from the cockpit; the DEMO has no collected runtime evidence and therefore produces an empty evidence summary, no accepted proof and actual recovery `UNKNOWN`. The result contains the simulation receipt and the gate result, with explicit false runtime/Temporal/GLPI-write flags. This is a real executable *in-memory* DEMO flow, **not** a production worker or operational integration.

## Operator CLI for the offline simulation — 2026-11-14

From the repository root, run `python scripts/run_acme_demo_simulation.py --verify`. The command composes the local synthetic ACME cockpit, simulates the hypothetical Payments restart, independently recomputes the receipt, checks the safety gate and prints deterministic JSON to stdout. It exits with status 2 and emits no JSON on invalid tenant or failed verification. It does **not** connect to GLPI, n8n, Grafana, Temporal, Core or production; `--tenant` is a DEMO label, not authenticated tenant authorization. No real recovery or ITIL transition is asserted.

## Independent saved DEMO artifact verification — 2026-11-14

To save and verify a run locally:

```sh
python scripts/run_acme_demo_simulation.py --verify > acme-demo.json
python scripts/verify_acme_demo_simulation.py acme-demo.json --expected-tenant acme-demo
```

The second command recomputes the **entire** expected artifact from the trusted local ACME fixture, instead of accepting the incident ID, tenant or hashes claimed by the saved JSON. It refuses modified results, duplicate JSON keys, nonfinite values, symlinks and files over 128 KiB; exit 0 means only `DEMO_ARTIFACT_MATCHES_LOCAL_FIXTURE`, **not** independent runtime evidence. Exit 2 means rejected. This is a local deterministic comparison, not a digital signature, anti-replay system or production authorization.

## DEMO simulator input hardening — 2026-11-14

The deterministic simulator now constrains tenant, incident, action and service identifiers to explicit ASCII `[A-Za-z0-9_.:-]` (1–128 characters). This avoids accepting visually confusable Unicode identifiers or control characters. The `before.health` field is type-checked before set membership, so malformed lists/dictionaries fail closed with `ValueError` rather than an unhandled `TypeError`. No LIVE authorization or external action is introduced.

## Supplied evidence → source MAC → byte readback → simulation gate — 2026-11-14

`portal.acme_demo_evidence_pipeline.inspect_acme_demo_evidence(manifest, receipts, readback, resolve_key, expected_tenant_id=...)` now executes the full **offline** DEMO integrity path with caller-supplied callbacks: validates the manifest against the trusted ACME cockpit, checks tenant/source-bound HMAC receipts, permits readback only after valid MAC, compares bytes to manifest SHA-256, and joins the resulting qualification to the deterministic Payments simulation. Wrong tenant/incident is refused before callbacks; bad MAC never triggers readback. A matching MAC and digest still yield **runtime recovery UNKNOWN, no ITIL/LIVE authorization**. This is not a network adapter, credential vault, independent source attestation, durable anti-replay barrier, production actor ACL or Temporal execution.

## Temporal Worker DEMO VERIFY safety boundary — 2026-11-14

The existing Temporal Worker now **blocks DEMO at VERIFY** after a stage-start event when no independent runtime postcheck exists. It emits `INDEPENDENT_POSTCHECK_MISSING` with `actual_recovery_state=UNKNOWN`, issues an idempotent Core `BLOCK` command, and stops the workflow before `STAGE_COMPLETED/PASS`, `RECONCILE`, `LEARN` or `RESOLVE`. This deliberately changes the previously optimistic synthetic DEMO workflow: a simulated observation is not a verified recovery. This is a fail-closed stop, **not yet** a production-attested postcheck or a resume mechanism. No LIVE remediation is enabled. A static AST contract test in CI guards the stop ordering; real Core/Temporal runtime E2E of this specific branch remains to be qualified.

## Executed Worker VERIFY safety regression — 2026-11-14

`tests/test_worker_demo_verify_execution.py` executes the **actual async `execute_stage` body** from `app/worker/main.py` with inert Core/Evidence/Policy/Twin stubs (no Temporal service). It asserts DEMO VERIFY emits `STAGE_STARTED` → `INDEPENDENT_POSTCHECK_MISSING` → idempotent `BLOCK`, with no Evidence/Twin/Policy calls or `STAGE_COMPLETED`. The LIVE VERIFY branch must likewise block with `LIVE_ADAPTER_UNAVAILABLE`. This supplements the static ordering test; it is not a full Temporal/Core integration test.

## Executed Temporal workflow stop-order regression — 2026-11-14

`tests/test_worker_temporal_workflow_stop.py` executes the actual `IncidentWorkflow.run` coroutine with a deterministic `workflow.execute_activity` stub. It asserts that a `VERIFY` block stops the stage sequence before `RECONCILE` and `LEARN`, and never invokes `finish_run` / `RESOLVE`; earlier `POLICY`, `HITL` and `REMEDIATE` blocks also stop immediately. This is a unit-level orchestration test, not a Temporal server E2E.

## In-process Worker orchestration with actual activity bodies — 2026-11-14

`tests/test_worker_orchestration_integrated_demo.py` composes the real async `IncidentWorkflow.run`, `start_run` and `execute_stage` bodies with deterministic fake Core, Policy, Evidence and Twin services. It runs all DEMO stages through VERIFY, confirms 10 earlier synthetic stage evidence writes, then `INDEPENDENT_POSTCHECK_MISSING` and Core `BLOCK` without VERIFY completion, RECONCILE, LEARN or RESOLVE. This is a higher-level in-process integration regression, **not** a Temporal server or real Core/Postgres E2E.

## Policy gate refusal persists Core run BLOCK — 2026-11-14

The Temporal Worker previously returned a blocked Policy stage event without necessarily transitioning the canonical Core run to BLOCKED. A non-PASS Policy decision now writes `GATE_BLOCKED` at confidence zero, then issues an idempotent `BLOCK` Core command with the returned version before ending the workflow. Actual async activity tests cover both `BLOCKED` and `UNKNOWN` Policy decisions and assert no checkpoint or DEMO PASS artifact after refusal. This is an in-process regression, not a live Policy/Core E2E.

## Worker Temporal start request validation — 2026-11-14

`POST /api/execution/start` now rejects malformed envelopes **before connecting to Temporal**: exact Core fields `run_id,mode,scenario_id,version`, bounded ASCII identifiers, non-negative integer version (not bool), and an allowed mode under the existing simulation policy contract. Internal bearer authentication remains required before validation. Inert-client async endpoint tests cover missing/extra fields, Unicode/control/path-like IDs, invalid versions/modes, unauthorized calls and a valid canonical Core envelope. This does not introduce tenant/actor-facing authorization or enable LIVE remediation.

## Temporal workflow-ID replay requires reconciliation — 2026-11-14

A `WorkflowAlreadyStartedError` previously returned `idempotent=true` solely because the workflow ID matched, without verifying the existing workflow's original mode, scenario, version or Core receipt. The Worker now returns HTTP 409 and asks the caller to reconcile against the canonical Core execution receipt; it does **not** assert that a new request is identical to the existing workflow. Core currently maps Worker HTTP failures to 503 when it lacks a persisted receipt, so automatic recovery from an ambiguous lost start response is **not yet implemented**. This is fail-closed and may require operator reconciliation; no duplicate execution is authorized.

## All synthetic execution modes stop before unverified recovery — 2026-11-14

The Temporal Worker accepts `DEMO`, `REPLAY`, `STORY` and `LIVE`. The independent-postcheck safety stop at `VERIFY` now covers **all three synthetic modes** (`DEMO/REPLAY/STORY`), not just DEMO. Executed stage-body tests and in-process full-workflow tests exercise each mode and require `INDEPENDENT_POSTCHECK_MISSING`, Core `BLOCK`, no synthetic VERIFY PASS, and no `RECONCILE/LEARN/RESOLVE`. LIVE remains separately blocked by `LIVE_ADAPTER_UNAVAILABLE`. These are CI-inert tests, not production attestation.

## Core ↔ Temporal ambiguous start response — 2026-11-14

Core now preserves the Worker's HTTP 409 workflow-ID conflict as a **409 operator-reconciliation-required** response instead of disguising it as a generic 503. A timeout or transport failure is reported as `execution start outcome unknown; reconcile before retry` (503), without inserting a false execution receipt or claiming idempotency. An upstream non-409 HTTP failure remains a generic 503 without leaking response internals. Inert DB/HTTP tests execute the actual Core handler for conflict, timeout and other HTTP failure. **Automatic reconciliation and crash-safe start deduplication are still not implemented**; do not blindly retry ambiguous starts.
