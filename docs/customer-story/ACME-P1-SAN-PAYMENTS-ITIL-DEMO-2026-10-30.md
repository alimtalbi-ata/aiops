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
