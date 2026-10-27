# AIOps 2.0 — Architecture and Boundaries

**Author:** Abdelhalim Talbi  
**Status:** Working baseline; validate against current source and deployment before implementation.

## 1. Target architecture

```text
Sources / Simulators / Monitoring / ITSM / CMDB
                    |
              Ingestion adapters
                    |
        Normalize + identity/correlation
                    |
       Canonical Incident / Run context
                    |
        Durable workflow orchestration
                    |
   +----------------+-------------------+
   |                |                   |
 CMDB / RAG     Evidence service    Digital twin /
 enrichment     + provenance        simulation
   |                |                   |
   +---------- Analyst + Critic --------+
                    |
           Policy / Safety Gate
                    |
        +-----------+-----------+
        |                       |
    OBSERVE / ENRICH       HITL / APPROVAL
        |                       |
        +------------+----------+
                     |
       Remediation executor (guarded)
                     |
      Verify → reconcile → rollback if needed
                     |
       ITSM / notifications / audit / learning
                     |
            Portal / Command Center
```

This is a target responsibility map, not a claim that every edge is already implemented or qualified.

## 2. Existing architecture facts to preserve

The GitHub `README.md` describes the clean runtime as `Portal → Core → Temporal/Worker → Twin + Evidence + Policy`. It states that the simulator is isolated on `aiops2-execution`, n8n is an integration boundary and does not own Run state, the Portal does not write PostgreSQL directly, Run state uses optimistic versioning and idempotency receipts, Events and Evidence are append-only, each stage has durable state, and LIVE remediation is fail-closed. These are intended constraints and must be checked against code/tests whenever changed.

## 3. Service responsibilities

- **Portal / Command Center:** user experience, incident/run inspection, evidence and decision presentation, operator commands through APIs. Never access the database directly.
- **Core API:** canonical entry point for incident/run lifecycle, authorization, validation and persistence boundaries.
- **Temporal / Worker:** durable orchestration, retries/timeouts, stage progression and recovery. Workflow history must not be replaced by ad-hoc in-memory state.
- **Evidence:** evidence records, provenance, timestamps, source identity, freshness, integrity and links to decisions. Append-only by default.
- **Intelligence:** analyst and critic outputs, hypotheses, alternatives, confidence, supporting evidence and missing information. Model output is untrusted until schema-validated and policy-checked.
- **Policy / Safety Gate:** deterministic enforcement independent of the LLM. P1, invalid/unvalidated analysis, high-risk operations, stale ownership or missing preconditions must not silently reach autonomous remediation.
- **Digital Twin / Simulator:** scenario execution and impact prediction in a fenced execution domain. DEMO/REPLAY/SIMULATION must remain distinct from LIVE.
- **RAG:** retrieve historical incidents, known errors, runbooks and vendor documentation with citations/provenance; retrieval is advisory and cannot override policy.
- **CMDB / GLPI / ITSM:** authoritative CI/service and ticket relationships where configured. Do not assume data is current without freshness checks.
- **Integration adapters / n8n:** connect external systems; do not become the source of truth for workflow/run state.
- **Observability:** metrics, logs, traces, stage timings, error budgets and audit signals; redact secrets and identifiers where appropriate.

## 4. Canonical data and invariants

A canonical Run/Incident context should include stable identifiers, tenant/organization where applicable, source and source event ID, event/observed/ingested times, CI/service links, severity and classification, evidence references, decision and policy version, execution mode, workflow/stage state, idempotency key, optimistic version, actor/approval identity, action/preconditions, verification result, reconciliation status and audit references.

Required invariants:
- Idempotent ingestion and command handling.
- Optimistic concurrency or equivalent single-writer protection for state transitions.
- Append-only event/evidence audit trail; corrections are new records or explicit supersession.
- Explicit provenance and freshness on evidence.
- Versioned contracts and schema validation at boundaries.
- Separate proposed action, approved action, executed effect and verified outcome.
- No remediation without identity/ownership/fencing validation, current preconditions and policy authorization.
- Reconciliation after effects and recovery from partial failure.
- A rollback plan must be known before risky mutation; rollback itself must be verified.
- `UNKNOWN` is a valid state and must remain visible.

## 5. Historical AIOps v1 / V145 integration strategy

Treat v1 as a capability library and evidence source, not as a second production control plane. Inspect the exact source and contracts of each candidate. Preferred pattern:

1. inventory code, API routes, schema/contract, config, dependencies, tests, runtime ownership and data stores;
2. identify duplication against current AIOps 2.0;
3. wrap a reusable function behind a versioned adapter;
4. map its data to canonical schemas without changing safety semantics;
5. add contract and failure tests;
6. run offline, then isolated integration tests;
7. promote only after evidence-backed qualification.

Never connect two writers to the same state without an explicit ownership and consistency model. Do not import historical secrets, production data, opaque binaries or old runtime state into source control.

## 6. Candidate V145 modules from the 2026-10-19 host inventory

Candidate names found: `v145-d4.54-decision-intelligence`, `v145-d4.55-evidence-fusion`, `v145-d4.56-evidence-matrix`, `v145-d4.57-evidence-acquisition`, `v145-d4.58-evidence-decision-adapter`, `v145-d4.59-evidence-enrichment`, `v145-d4.60-semantic-evidence-engine`, `v145-d4.61-decision-intelligence`, `v145-functional-bridge`, `v145-functional-orchestrator`, `v145-functional-read-model`, `v145-decision-cockpit`.

Presence is not proof of readiness. The reported orchestrator directory had no files in the shallow inventory; this must be rechecked before planning integration. The cockpit directory contained architecture/contract/demo/integration-plan documentation, which should be read before altering UI or integration.

## 7. Network and deployment safety

- Keep the simulator/execution network isolated from data/control networks.
- Declare allowed service-to-service paths explicitly; avoid broad host networking.
- Preserve health/readiness checks and bounded startup dependencies.
- Never retire legacy services just because a new stack starts; prove ownership, dependencies, backup and rollback first.
- Do not publish internal ports by default.
- Validate bind addresses, authentication, authorization, CORS and secrets handling before exposing an API.
- Use separate demo credentials/data and guard synthetic mutations by explicit mode and token.

## 8. ACME 2.0 selected target architecture (2026-10-27)

This is a **logical target**, not a deployment inventory or proof of integration.

```text
ACME ENTERPRISE TWIN (sites, users, ERP/CRM/e-commerce, DB, network, CMDB graph)
  | synthetic business traffic + seeded fault injection + ground-truth oracle
  +--> Checkmk [infrastructure checks] --> compatible Livestatus backend? --> Thruk [NOC UI]
  +--> OpenTelemetry Collector [candidate] --> Prometheus / Alertmanager --> Grafana
  +--> GLPI [ITSM tickets / CI references]
             \                 |                    /
              \--- read-only versioned adapters ----/
                                |
                      CORE canonical Incident/Run
                                |
             Evidence + provenance + CMDB impact graph
                                |
          +---------------------+--------------------+
          |                                          |
  ACME Knowledge Hub / RAG                   AI Investigator / Critic
  vendor + internal docs, ACLs                hypotheses, alternatives,
  versions, citations                        uncertainty and cited evidence
          |                                          |
          +--------------- scoped NOC Copilot -------+
                      (read-only; no actions)
                                |
                   POLICY deterministic safety gate
                                |
             HITL approval service (authenticated actor)
       approve / reject / request changes / expiry / audit
                                |
               Temporal workflows + guarded Workers
                                |
           versioned Remediation Lab recipe allowlist
         sandbox SIMULATION/REPLAY first; LIVE blocked
         until independently authorized and qualified
                                |
          technical postchecks + business SLO verification
                                |
            GLPI reconciliation + append-only Evidence
                                |
               Portal / NOC / Evidence Studio
```

### Authority and boundaries
- **Core** is authoritative for canonical incident/run state and lifecycle. Checkmk, Thruk, Alertmanager and GLPI supply external facts/views; none can silently become a second Run writer.
- **Checkmk** is the candidate infrastructure monitoring engine; **Thruk** is a NOC UI requiring a compatible Nagios/Icinga/Livestatus backend. Direct Checkmk↔Thruk interoperability, editions, versions, permissions and API semantics **must be proven in a compatibility spike**, not assumed.
- **OpenTelemetry/Prometheus/Grafana** collect and visualize telemetry, not incident truth or remediation authority. The Collector is a candidate, not asserted installed.
- **CMDB/GLPI** links must carry CI ID, source, sync time and freshness. Twin dependencies and impact propagation are hypotheses until validated against CMDB/business evidence.
- **Copilot** may retrieve only enterprise-authorized incident, CMDB, telemetry, runbook and evidence data; external documentation is general product guidance, **never proof of ACME's current state**. Every factual claim needs a traceable, permission-checked citation; otherwise abstain. Retrieved text is untrusted and cannot issue commands or override policy.
- **Knowledge Hub** ingestion separates vendor/official reference docs, internal architecture and deployment docs, operating procedures, approved remediation recipes, incidents and postmortems. Store URI, owner, license/permission, product/version, effective/review dates, ACL, content hash, chunk location, index version, retention and deletion/tombstone state. Search combines metadata filters, keyword/full-text and optionally embeddings. Filter ACLs before retrieval and again before rendering/citing; test stale, contradictory, poisoned and inaccessible documents.
- **HITL** records authenticated actor, role, separation of duties, target CI, action catalog ID and immutable version/hash, parameters, risk, evidence snapshot, policy version, decision, rationale, timestamps, expiry and single-use/idempotency receipt. Reject, clarification and amended plans return to analysis; a changed plan invalidates prior approval. No LLM self-approval.
- **Remediation Lab** is a typed, signed/versioned catalog of allowlisted Ansible playbooks, scripts, CLI and API calls, with target scopes, preconditions, secret references (never values), dry-run/sandbox contract, timeouts, compensating action, postchecks and expected effects. Execution is only through Policy + Temporal/Worker. No free-form command execution from chatbot/LLM. Keep demo outputs explicitly synthetic; a postcheck failure leaves the Run unresolved or escalated.
- **Execution modes:** DEMO/REPLAY/SIMULATION fenced from LIVE; no shared writable production credentials or networks. LIVE remains blocked until adapter, identity, fencing, approval, effects, reconciliation and rollback paths pass independent qualification.
- **Evidence:** preserve source IDs, timestamps, raw/reference hashes, actor decisions, workflow history, effect receipts, technical and business verification, redaction and retention. Display UNKNOWN where evidence is absent.

### Illustrative bounded vertical slice
Seeded ERP service outage → Checkmk service CRIT and OTel error-rate increase → Core correlation to GLPI CI → RAG cites internal ERP runbook and matching vendor procedure → AI proposes a cataloged Ansible `systemd_service: state=started` action targeting a synthetic ERP host → NOC operator may reject, ask for clarification or approve → Policy validates immutable recipe/CI/version → Temporal runs a sandbox executor → postchecks verify service health *and* order flow → Evidence Studio renders an auditable replay. Example is a design/test fixture, not a deployed or successfully executed incident.

### Proposed interfaces (version before implementation)
`MonitoringEvent`, `CMDBSnapshot`, `KnowledgeCitation`, `InvestigationHypothesis`, `RemediationProposal`, `HumanDecision`, `ExecutionReceipt`, `VerificationResult`, `EvidenceManifest`. Include correlation/run IDs, actor/tenant ACL, schema version, source/provenance, timestamps and explicit simulation flag. Enforce ownership, fencing and optimistic concurrency at write boundaries.
