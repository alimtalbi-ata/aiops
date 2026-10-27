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

## 9. P0 Copilot grounding boundary (2026-10-27, proposed)

Operator-authenticated Portal (dependency: draft PR #16) → internal service token → Copilot read-only intent router → Core/Twin/Evidence GET APIs → citation-only response or UNKNOWN. The internal service token authenticates the gateway, **not the human user**; per-user/tenant RBAC is still missing. Until it exists, evidence answers are restricted to explicitly synthetic DEMO/REPLAY/STORY runs with matching run_id provenance. The Copilot must never treat evidence claim text as instructions, invent model confidence or call remediation APIs. The limited lexical document stager does not fetch or store vendor content, never executes retrieved instructions, and is not yet connected to the chatbot. See draft PR #39 for the broader ACME NOC/HITL/RAG target.
