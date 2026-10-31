# AIOps2 real runtime and customer-demo readiness — implementation priority

**Decision:** Runtime truth and a reproducible customer demonstration take priority over new feature breadth.  
**Reference PR:** #214 (Draft)  
**Reference branch:** `test/debian12-install-runtime-qualification-20261031`  
**Reviewed head at decision time:** `e5cda8549fad4965f0c3ff2a4335ec7076631170`  
**Lab host evidence:** SRV-DEB-05, Debian 13 Trixie, operator-confirmed Docker inventory.  
**Safety:** DEMO/REPLAY/STORY only; LIVE remains blocked. No production mutation or host system commands.

## 1. Executive decision

The platform has a healthy Docker runtime and a working deterministic Temporal workflow, but the current PR #214 source branch does not yet prove an end-to-end, real-model, GLPI-integrated customer journey.

Do not confuse:
- a healthy container with a qualified application integration;
- a Temporal stage event with an Analyst/Critic model invocation;
- a synthetic fixture/storyboard with a persisted runtime incident;
- a running GLPI container with an authenticated GLPI API/CMDB integration;
- a green deterministic CI gate with real-model accuracy or cost evidence.

The immediate target is one vertical slice that works reliably and can be demonstrated honestly:

**Synthetic enterprise event → canonical incident → source-backed Twin impact → Evidence ledger → actual Analyst model call → independent Critic model call → Policy decision → DEMO HITL simulation skip → Temporal no-effect simulation → independent verification → persisted run timeline and customer-facing Portal/GLPI reference.**

The first client story remains ACME SAN degradation affecting Payments. The scenario is explicitly synthetic; no actual SAN or payment environment is changed.

## 2. Verified gaps found by source inspection

### 2.1 Current PR #214 source branch

At head `e5cda8549fad4965f0c3ff2a4335ec7076631170`:

- The current source tree has no `app/intelligence/` service, no `app/intelligence/Dockerfile`, and no Intelligence service in its current `compose.yml`.
- `app/worker/main.py` advances `DGX_ANALYST` and `DGX_CRITIC` through the generic stage path: it writes a generic Evidence claim (for example, “DGX_ANALYST completed”) with hard-coded confidence values. It does not call an Analyst/Critic model endpoint.
- `app/copilot/main.py` is an evidence-first deterministic read model over Core/Twin/Evidence. It does not call an LLM provider.
- `app/portal/acme_explore_story.py` and `acme_impact_read_model.py` are a useful local fixture/storyboard, but their own contract correctly labels the content `SIMULATED_TARGET`, uses fixture-derived IDs and marks evidence/checkpoints `MISSING`. They do not create a canonical runtime Run or actual GLPI ticket.
- `app/portal/glpi_operator_view.py` deliberately performs no GLPI/Core request; it displays `NOT_INSTALLED` / `UNKNOWN` until a server-derived tenant ACL and authoritative ticket↔Run mapping are qualified.
- The active GLPI container on SRV-DEB-05 was observed running, but no authenticated API, tenant ACL, CMDB write/read reconciliation or ticket mapping has yet been demonstrated.
- The current `runtime-e2e.sh` is a deterministic synthetic integration check. It is not a real-model evaluation and must not be presented as one.

These are engineering gaps, not reasons to weaken the safety boundary. Until the missing adapters are integrated, the product must label those capabilities NOT_CONNECTED / NOT_QUALIFIED rather than manufacture success evidence.

### 2.2 Reusable implementation already exists in GitHub

Do not recreate these components. Integrate them selectively and reconcile their base/schema first:

- PR #194, head `40d38705cf2bde3be6052340442c117a81908f65`: Temporal HITL workflow, persisted Analyst/Critic proposal contracts, Critic-denial persistence, OIDC identity verification, outbox, fencing and LIVE fail-closed controls.
- PR #196, head `747f0df4b8bae0fa0265b6dc568558a6a9057ad1` (its latest reviewed PR metadata): existing Intelligence service, Analyst/Critic schemas and evidence-quality guards, provider-reported token/latency telemetry, evaluator, Ollama CPU experiment and benchmark aggregation.
- PR #196 explicitly records that earlier Ollama qwen3:4b/8b CPU attempts timed out and that no model benchmark PASS, provider token totals or cost were established. Preserve that honest status; do not inherit a green workflow as proof of model quality.
- Existing ACME fixture and customer story in this branch provide a useful deterministic scenario contract and narrative; reuse the data model but connect it to a canonical runtime Run and real stage receipts.

The source branches are stacked on different bases from PR #214. Do not merge wholesale or cherry-pick blindly. Port in bounded slices with schema, Compose, worker and exact-head CI compatibility checks.

## 3. Implementation order — strict priority

### P0.1 — Real Analyst/Critic runtime integration

- [ ] Bring the existing `app/intelligence` service and its Dockerfile into the current clean branch.
- [ ] Port required shared contracts: evidence identity, freshness and quality validation.
- [ ] Add the Intelligence service to Compose with internal-only network exposure, healthcheck, explicit provider/model configuration and bounded timeout/context/output limits.
- [ ] Wire Temporal Worker `DGX_ANALYST` to the real `/api/intelligence/analyze` endpoint using only Evidence IDs retrieved from the Evidence service.
- [ ] Wire `DGX_CRITIC` to `/api/intelligence/critic` with the exact persisted Analyst result and same evidence set; Critic must independently challenge it.
- [ ] Persist model output, invocation ID, provider/model, prompt version, latency, retries and provider-reported usage in the canonical run event / decision ledger. Missing token usage and cost remain null/UNKNOWN.
- [ ] Do not write a generic “stage completed” Evidence item for Analyst/Critic. Persist the actual output and its source references.
- [ ] If provider is not configured or invocation fails, record `AI_ADAPTER_UNAVAILABLE` / `UNKNOWN` and fail closed; do not fabricate confidence or mark model stages PASS.
- [ ] Add contract tests for evidence freshness, unsupported claims, Critic rejection, model timeout, schema repair, usage missing and idempotent retries.

Acceptance: one DEMO run visibly includes actual Analyst and Critic invocation records, persisted evidence references and truthful provider telemetry. A deterministic fake provider may be used in CI but must be labelled `TEST_PROVIDER`, never a real-model benchmark.

### P0.2 — Canonical end-to-end scenario

- [ ] Turn the ACME SAN→Payments fixture into a registered scenario with stable version/hash.
- [ ] Start a canonical incident and Run through Core APIs with idempotency keys.
- [ ] Drive scenario observations through Twin/Synthetic Simulator, with each observation labelled synthetic and linked to the Run.
- [ ] Verify the Twin impact path and redundancy assumptions from actual graph queries, not a static SVG alone.
- [ ] Persist each stage transition, evidence reference, model output, Critic disposition, Policy decision, HITL simulation-skip event, Temporal workflow ID and verification receipt.
- [ ] Confirm DEMO/REPLAY/STORY cannot create LIVE approval, outbox authority or real effect receipts.
- [ ] Add a single demo launcher and a read-only run verifier that emits a sanitized JSON evidence bundle and stable summary.
- [ ] Add Playwright browser E2E for the canonical runtime Run, not only the local fixture storyboard.

Acceptance: a customer can follow one incident ID and one Run ID across NOC, Twin, Analyst/Critic, Policy, Temporal, verification and Portal. Every displayed status is backed by a runtime API/ledger record or explicitly marked synthetic/unknown.

### P0.3 — GLPI as actual ITSM/CMDB system of record

- [ ] Inspect the installed GLPI version, plugins, entities, profiles, categories, ticket templates, CI types and API capabilities using a dedicated least-privilege integration identity.
- [ ] Establish tenant/entity-scoped authorization server-side. Portal viewer token alone is not a GLPI permission.
- [ ] Implement authenticated read-only discovery first: tickets, CI, relations, entities, groups, SLA/OLA and source freshness.
- [ ] Reconcile Docker/Twin observations to GLPI CI by stable external key; preserve curated business owner, criticality, SLA and support group.
- [ ] Produce dry-run diffs and duplicate/stale candidates before writes.
- [ ] Add controlled lab-only ticket create/update after approval, with idempotency and immutable correlation to Incident ID and Run ID.
- [ ] Enrich the Portal with real ticket/CI detail only after the API response and tenant ACL are attested. Otherwise retain UNKNOWN.
- [ ] Add integration tests for tenant isolation, expired tokens, missing CI, duplicate external IDs and GLPI API outages.

Acceptance: one lab-only synthetic ticket is created in GLPI and can be re-read from GLPI; its ID is linked to the canonical AIOps incident/Run and CI graph. No fixture-generated ticket number is presented as a GLPI ticket.

### P1 — Customer-ready Portal / NOC experience

- [ ] Keep one coherent cockpit and role-based views for Service Desk N1, NOC N2, SRE/N3, Incident Commander and Change Manager.
- [ ] Show current source freshness, incident priority rationale, impacted business service and CI dependency path.
- [ ] Show Analyst hypotheses, supporting/contradicting evidence, Critic objections and Policy reason codes.
- [ ] Show DEMO HITL as “simulation skipped — no human approval required”; LIVE approval UI must be distinct and unavailable until IdP/outbox/fencing/executor gates pass.
- [ ] Show simulation receipt, no-effect guarantee, independent verification and closure conditions.
- [ ] Include a guided customer narrative with a clear beginning, operational decisions, service impact, recovery and post-incident learning.

### P1 — Real AI quality and cost benchmark

- [ ] Reuse PR #196 evaluator, dataset, telemetry and summarizer after base reconciliation.
- [ ] Run against an isolated configured model endpoint; keep provider/model/prompt/dataset/policy/retrieval versions fixed.
- [ ] Capture provider-reported input/output/cached/reasoning tokens, latency, retries and HTTP status per invocation.
- [ ] Calculate cost only from a pinned provider price schedule or invoice source; otherwise UNKNOWN.
- [ ] Add per-run/per-tenant budget enforcement and a spend circuit breaker before customer exposure.
- [ ] Score RCA accuracy, evidence grounding, stale/contradictory evidence detection, Critic false accept/reject, proposal actionability, safety, human acceptance and verified resolution.
- [ ] Run at least three repeats for nondeterministic models and publish p50/p95 only from actual measured invocations.
- [ ] Compare quality-adjusted cost per successfully resolved incident, not token count alone.

### P2 — Second-server reproducibility

- [ ] Use the separate reproducibility guide and build a clean-server qualification lane.
- [ ] Include Intelligence/model endpoint and GLPI configuration in the install manifest.
- [ ] Demonstrate database migration and complete state restore on a second clean host.
- [ ] Publish a release tag only after all P0 acceptance criteria pass.

## 4. Customer demonstration script (target)

1. **Business context:** ACME Payments, service owner, criticality, SLA and dependency graph.
2. **Detection:** a synthetic SAN fabric event with source ID, timestamp and measured metric.
3. **Impact:** Twin resolves SAN → storage → VM → Payments; show redundancy and uncertainty.
4. **Incident:** one canonical P1 incident with priority rationale and linked GLPI ticket (if actual API integration is qualified).
5. **Investigation:** Analyst provides ranked hypotheses and citations; Critic challenges them independently.
6. **Decision:** Policy shows reason codes and missing prerequisites; no unsupported auto-remediation.
7. **HITL:** DEMO records a simulation-only skipped approval; explain that LIVE requires real IdP identity, approval outbox and fencing.
8. **Simulation:** Temporal executes a synthetic no-effect workflow; effect receipt count remains zero.
9. **Verification:** independent postconditions confirm simulated recovery; the incident is resolved only when verification passes.
10. **Learning:** Problem candidate, known error, runbook improvement, metrics and benchmark report.

A demo is accepted only if the operator can open the same incident/Run from the Portal and inspect all corresponding backend records.

## 5. Required evidence bundle per demo

- scenario ID, version, fixture SHA-256 and provenance;
- host/runtime manifest and image digests;
- incident ID, canonical Run ID and Temporal workflow ID;
- ordered event timeline and stage-state records;
- Evidence IDs, payload hashes, observed_at and known_at;
- Analyst and Critic outputs plus model invocation telemetry;
- Policy decision and HITL mode-specific event;
- simulation/no-effect receipt and independent verification evidence;
- GLPI ticket and CI IDs only if read back from the real GLPI API;
- browser E2E artifact and test run links;
- benchmark report with unknown metrics retained as null;
- sanitized release/config/migration manifest.

## 6. Release gates

| Gate | Required proof | Status at decision time |
|---|---|---|
| Docker/runtime baseline | Operator-confirmed inventory; main stack healthy | OBSERVED |
| Deterministic Temporal E2E | CI runtime E2E | CI PASS |
| Real Analyst/Critic calls in current #214 source | Service + worker wiring + provider telemetry | NOT INTEGRATED |
| Real model quality/cost | Actual provider runs with usage and ground truth | NOT QUALIFIED |
| GLPI API + tenant ACL + CMDB | Authenticated read/write and read-back tests | NOT QUALIFIED |
| Canonical incident/Run cross-link | Same IDs across Core, Portal, GLPI and evidence | NOT QUALIFIED |
| Customer-ready guided demo | Playwright and backend evidence bundle | PARTIAL / FIXTURE ONLY |
| LIVE remediation | OIDC, HITL outbox, policy fencing and executor acceptance | DISABLED |

## 7. Change governance

Each implementation PR updates this document with:
- code paths and schema/config changes;
- test commands and exact CI run URLs;
- whether a test used TEST_PROVIDER, local model, external model or deterministic fixture;
- whether it was CI-only, installed on SRV-DEB-05 or verified on a second host;
- measured metrics and explicit UNKNOWN values;
- rollback, security implications and remaining blockers.

Never label a container stage as Analyst/Critic PASS unless a real endpoint invocation succeeded and the persisted output passes deterministic evidence-quality checks. Never label a GLPI ticket connected unless the actual ticket has been read back from GLPI. Never label a demo simulation as a real customer remediation.


## 8. Implementation progress — integration PR #215 (2026-10-31)

A separate draft integration branch `integration/real-ai-runtime-demo-20261031` was created from the PR #214 head. This avoids rewriting the PR #214 operations/reproducibility baseline and isolates the AI/HITL runtime port.

### Ported source assets

- Existing Intelligence service and Dockerfile from PR #196, including strict Analyst/Critic contracts, evidence freshness/integrity guards, provider-reported usage/latency/retry telemetry and bounded model requests.
- Existing Temporal Worker and deterministic workflow from PR #194/#196, including real calls to `/api/intelligence/analyze` and `/api/intelligence/critic`, analysis/critique ledger persistence, fail-closed model-unavailable handling and explicit DEMO HITL simulation skip.
- Core decision ledger and denial/HITL modules plus migrations 009, 010, 011 and 090–092.
- Compose service wiring for Intelligence, model evaluator, test provider, GLPI API configuration and Temporal schema/namespace initialization.
- Portal authenticated GLPI read client and ticket↔Run context routes, while preserving the current ACME Explore/Impact and GLPI operator handoff routers.
- Fixed synthetic AI evaluation dataset, evaluator, benchmark summarizer and opt-in Ollama CPU benchmark workflow.
- CI tests for Intelligence contract, AI evaluation/summary, OIDC identity and HITL workflow contract.

### Important qualification distinction

This is a **source integration in a Draft PR**, not a host deployment. The PR has 58 changed files and approximately 8.5k additions. It is a selective file-level port from divergent PR #194/#196 histories, not a wholesale merge. CI has been triggered; no exact-head PASS is claimed yet.

### Remaining work before a real customer demonstration

1. Resolve all CI failures and migration ordering/upgrade compatibility.
2. Run a full synthetic Temporal scenario with a configured isolated model endpoint; verify persisted Analyst/Critic outputs and provider telemetry.
3. Configure a dedicated least-privilege GLPI API identity and verify read-only ticket/CI access with entity/tenant scope.
4. Prove one canonical Incident ID and Run ID are linked to a real lab GLPI ticket read back from GLPI.
5. Execute Playwright against the runtime-backed Portal journey and capture a sanitized evidence bundle.
6. Run at least three model repeats where feasible; keep actual quality, tokens and cost UNKNOWN when no provider evidence exists.
7. Only after exact-head CI and isolated lab qualification, plan a controlled SRV-DEB-05 deployment. No application changes have been made on that host by this integration.

### CI reference

- Integration PR: https://github.com/alimtalbi-ata/aiops/pull/215
- First exact-head quality workflow: https://github.com/alimtalbi-ata/aiops/actions/runs/41221642043


### CI integration findings and corrections

The first exact-head runs exposed genuine integration conflicts; they were not suppressed:

- Porting the newer Policy module changed the already-qualified synthetic decision contract (P1 DEMO/REPLAY/STORY behavior). Restored the PR #214 Policy implementation, preserving the existing synthetic simulation contract and LIVE fail-closed posture. The newer autonomy/fencing modules remain unused until separately reconciled with the existing policy tests.
- The Core integration test exposed a missing regex import in the preserved signed NOC projection; added the import.
- The AST-isolated Core INGEST test executes only the `create()` function body and therefore needs its shared `initial_stage_state` collaborator injected explicitly. Updated the test harness rather than changing runtime behavior.
- The signed NOC read projection from PR #214 was appended to the newer Core main so the existing NOC read security contract remains intact.
- The first failures from missing policy modules were fixed by porting their source files and making the execution-fence import work both as a service package and under the `app.policy` test import path.

Exact-head requalification is running again after these corrections. Prior failed runs remain visible in GitHub history; they are not being relabelled as PASS.
