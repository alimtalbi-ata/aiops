# ACME NOC + RAG — AIOps development schedule and delivery gates
Status: proposed backlog (relative weeks, not committed dates). Baseline 2026-10-28. **No runtime change**.

## Workstream schedule (12-week proposal)
| Weeks | Stream | Deliverable | Dependencies | Acceptance |
|---|---|---|---|---|
| W1–2 | WS0 Architecture/security | HLD, inventory, data authority, ACL model, RACI, risk register, baseline | NOC/SecOps/ITSM owners | approved contracts, security zones, no secrets |
| W1–3 | WS1 ACME NOC / Checkmk | authenticated read-only Checkmk provider, signed event ingest, idempotent normalization | WS0, test Checkmk | duplicate/stale/unauthenticated event tests |
| W2–4 | WS2 Core/GLPI/CMDB | canonical incident/Run ↔ GLPI ticket/CI mapping, reconciliation | WS0, WS1 | mismatches UNKNOWN, no synthetic IDs presented as real |
| W3–5 | WS3 NOC cockpit | Portal RBAC read models, Grafana dashboards, P1–P4 workflow and handover | WS1–2 | N1/N2/N3 role tests, stale-source indicators |
| W2–5 | WS4 RAG ingestion | ACL-scoped connectors, parsing, hash/version, vector/keyword index | WS0, source owner | revocation, redaction, source freshness tests |
| W4–7 | WS5 RAG inference | hybrid search, citations, local LLM, structured Analyst/Critic advisory | WS4, Evidence | groundedness, injection, tenant isolation, UNKNOWN fallback |
| W5–8 | WS6 AIOps intelligence | event correlation, SAN→Payments dependency/impact, Evidence/Twin linkage | WS1–5 | real vs synthetic separation, provenance and replay |
| W7–9 | WS7 Orchestration | Temporal/Worker integration, n8n notification, Ansible dry-run, HITL policy | WS2, WS6 | fencing, preconditions, P1 block, idempotency |
| W8–11 | WS8 24/7 resilience | HA/PRA, backup restore, runbooks, on-call, alert fatigue metrics | WS1–7 | fault injection, restore evidence, duty roster |
| W10–12 | WS9 Qualification | E2E, security review, staged pilot, go/no-go and rollback | all | recorded test evidence; LIVE only by separate approval |

## Weekly operating cadence
- Daily dev stand-up; NOC/ITSM integration review twice weekly.
- Weekly backlog triage, security threat review, RAG evaluation sample, and regression suite.
- Biweekly architecture decision review, capacity review and release candidate demo.
- Monthly restore/failover exercise after platform is available; weekly NOC quality metrics (noise reduction, ack time, MTTD/MTTR, ticket reconciliation, RAG citation validity).
- 24/7 NOC staffing and escalation rota must be approved separately; software availability does not imply staffed coverage.

## Priority backlog
**P0**: authoritative IDs; real Checkmk connector; event dedupe; GLPI reconciliation; NOC RBAC; P1 human escalation; signed source provenance; secrets and audit.
**P1**: RAG ACL and citations; NOC dashboards; CMDB service impact; Elastic log evidence; resilience; Temporal/HITL integration.
**P2**: advanced anomaly detection, supervised model feedback, low-risk approved Ansible automation, capacity forecasting, self-service.
**Explicit exclusions**: Thruk for greenfield target; autonomous P1 remediation; synthetic RAG as live evidence; n8n as Run owner.

## Definition of Done (each story)
Design and versioned schema, owner, security review, test fixture, unit/contract tests, isolated integration tests, negative cases, operator documentation, observability, migration/rollback, proof links. Label unexecuted checks NOT RUN. No production change through documentation PR.

## Suggested GitHub issue epics
1. NOC-CMK: Checkmk real provider and monitoring event contract.
2. NOC-GLPI: canonical Incident/Run ↔ GLPI/CMDB correlation.
3. NOC-UI: authenticated N1/N2/N3 cockpit, P1–P4 escalation and shift handover.
4. RAG-INGEST: governed document ingestion, ACL and redaction.
5. RAG-RETRIEVE: hybrid retrieval, citation validation and local inference.
6. AIOPS-CORR: SAN→Payments impact, Evidence and Twin enrichment.
7. SAFE-EXEC: Temporal, HITL, n8n integration, Ansible dry-run and fencing.
8. OPS-HA: monitoring of monitoring, HA/PRA, backup, runbooks and SLOs.
9. QA-E2E: fault injection, security, synthetic vs LIVE qualification.

## Key risks and owners to assign
NOC owner: monitoring coverage and shifts; ITSM owner: GLPI authority; Platform owner: Core/Temporal; AI owner: RAG quality and GPU; SecOps: ACL, secret management and approval; SRE: resilience and rollback. Track open risks: Checkmk edition, unverified live adapters, RAG ACL leakage, identity mismatch, log volume, 24/7 staffing, GPU capacity.

## Delivery sequence
Gate G0 architecture approved; G1 authenticated read-only NOC; G2 GLPI/CMDB reconciliation; G3 RAG evidence quality; G4 controlled dry-run; G5 staging resilience; G6 separate production go/no-go. Existing LIVE fail-closed rules remain until independently qualified.
