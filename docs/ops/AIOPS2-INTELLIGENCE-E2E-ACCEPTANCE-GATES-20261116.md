# AIOps2 4/5 — Analyst/Critic evidence-closure acceptance gate (2026-11-16)

Status: **CONTRACT ONLY / NOT_EXECUTED / LIVE NO-GO**. Scope: isolated deterministic SAN→Payments simulation, never a claim of a qualified LLM, GLPI, Temporal, ACL provider, or CMDB. Priority integration reference: PR #713, branch `integration/aiops2-convergence-20261114`. This new document deliberately avoids modifying existing scripts, tests, or shared continuity files while overlapping PRs are under review.

## Required read-only chain and trust boundaries

`correlated_event → incident(SAN) → versioned dependency(SAN→Payments) → tenant-scoped Evidence → source-backed runbook → Analyst hypotheses → independently executed Critic → Policy DENY → HITL DENY → ITIL READ_ONLY`.

An Analyst response MUST include: correlation/incident/run IDs; tenant and mode; graph version and directed SAN→Payments path; impact classified *estimated* unless externally confirmed; ranked hypotheses with explicit supporting citation IDs; contradictions and missing evidence; runbook ID/version/source with applicability constraints; timestamps, freshness decision, and provenance; proposed next read-only verification. The Critic MUST separately assess each hypothesis/citation, challenge contradictions and missing evidence, and return a distinct execution provenance (not merely a different string ID). Never interpret an Analyst recommendation as authorization.

## Acceptance gates (all mandatory; UNKNOWN fails closed)

| Gate | Negative mutation | Expected deterministic outcome |
|---|---|---|
| Identity | missing or mismatched tenant/incident/run/correlation key | BLOCKED, UNKNOWN, no cross-tenant text |
| Dependency | missing edge, reversed edge, graph-version mismatch, fabricated Payments blast radius | BLOCKED; impact UNKNOWN |
| Evidence provenance | nonexistent citation, mismatched content digest, forged source, missing source timestamp | BLOCKED; citation not used |
| Freshness | stale/future evidence, missing clock basis, inconsistent observed/ingested times | BLOCKED; freshness UNKNOWN |
| ACL | unauthorized tenant/actor, unverified entitlement, cross-tenant runbook or evidence | BLOCKED; no leaked snippets |
| Prompt injection | evidence/runbook text requests instruction override, tool call, exfiltration, or approval | treat as untrusted data; BLOCKED if followed |
| Analyst | unsupported certainty, omitted contradiction or missing evidence, uncited hypothesis | BLOCKED |
| Critic | absent review, shared execution provenance, self-approval, ignored unsupported claim | BLOCKED; independence UNKNOWN |
| Runbook | missing source/version, unapproved or wrong-service runbook | BLOCKED; no recommendation to execute |
| Policy/HITL | Policy ALLOW, HITL APPROVE, effects_allowed=true, LIVE mode | BLOCKED, DENY, DENY, false, LIVE NO-GO |
| ITIL | create/update ticket, status mutation, remediation command or external call | BLOCKED; READ_ONLY only |

For each negative fixture, acceptance requires both a machine-checkable blocked result and an auditable reason code. A valid fixture may pass *syntactic consistency* only; it must not yield LIVE authorization. Use fixed fixture time and seed, do not call services, and keep tenant isolation before retrieval or rendering.

## Minimal synthetic receipt contract

```json
{
  "schema": "aiops.intelligence.acceptance.v1",
  "mode": "SIMULATION_ONLY",
  "scenario": "SAN_TO_PAYMENTS",
  "source_sha": "UNKNOWN",
  "fixture_seed": "UNKNOWN",
  "incident_id": "SYNTHETIC-SAN",
  "dependency_graph_version": "UNKNOWN",
  "analyst": {"hypotheses": [], "citations": [], "contradictions": [], "missing_evidence": []},
  "critic": {"execution_provenance": "UNKNOWN", "independence": "UNKNOWN", "findings": []},
  "acl_authority": "UNKNOWN",
  "evidence_authority": "UNKNOWN",
  "runbook_authority": "UNKNOWN",
  "policy": "DENY",
  "hitl": "DENY",
  "itil": "READ_ONLY",
  "effects_allowed": false,
  "live_gate": "NO_GO",
  "tests_executed": [],
  "ci": "UNKNOWN",
  "integrated_e2e": "NOT_EXECUTED"
}
```

Do not substitute fixture-provided ACL/provenance assertions for an authoritative read. A distinct Critic ID is insufficient proof of independence; require separately captured invocation trace and model/tool context, or report UNKNOWN. Hash-shaped strings are not integrity verification. Never claim ITIL/GLPI read-only execution without a recorded connector response; a synthetic projection is not a connector test.

## Qualification plan and ownership

1. **G0 (source)**: architect verifies #713 interface contracts, current exact base/head SHA and file ownership; run committed tests at the exact head; attach command, exit code, case counts and fixture hash.
2. **G1 (isolated integration)**: attach trusted tenant/actor ACL and versioned graph/Evidence/runbook authorities with disposable adapters; prove deny-on-unavailable and no side effects.
3. **G2 (vertical E2E)**: capture SAN event → Payments impact → Analyst → independently invoked Critic → Policy/HITL DENY → ITIL read-only receipt under one trace; demonstrate no mutation and retain redacted evidence.
4. **G3 (security)**: replay every negative mutation, including injected evidence and inter-tenant retrieval; require zero unauthorized disclosures and zero effects.
5. **G4 (release)**: exact-head CI and architecture review; LIVE remains NO-GO absent separately approved production controls.

**This document is not a test execution receipt.** Tests actually run for this document: NONE. CI status: UNKNOWN. Real LLM/GLPI/Temporal: NOT_EXECUTED. Source SHA must be filled from GitHub after commit. Dependencies: #713 canonical IDs and graph contract; Core/Evidence/ACL authoritative APIs; independently observable Critic execution; ITIL read-only adapter. Revert: delete this new document on the dedicated branch. No merge/rebase/cherry-pick/deployment/SSH/Debian/V1/V30/LIVE changes, secrets, new stack, cron, or external effects.
