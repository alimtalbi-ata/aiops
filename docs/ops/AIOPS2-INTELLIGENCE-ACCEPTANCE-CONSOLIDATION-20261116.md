# Intelligence 4/5 — acceptance matrix and consolidation handoff (2026-11-16)

**Scope:** offline SAN→Payments synthetic slice only. Base integration SHA `91551be28bc1383062669ef48d9c29aff6a83718`, PR #713. **Status:** contract / source review, NOT_EXECUTED; LIVE NO-GO.

## Why this handoff exists

PRs #745, #749, #754, #759, #763, #768, #772, #773, #774 and #777 already cover overlapping Critic negative tests and contracts. Do not integrate them blindly or introduce another implementation of `scripts/aiops2_analyst_critic.py`. Architect #713 should choose one canonical test suite and close the following *distinct* authority gaps.

The inspected deterministic `analyze_and_critique` accepts synthetic incident/impact inputs, checks digest **syntax** and internal citation membership, and returns `DENY_LIVE`. It does not fetch authoritative Evidence, authenticate RAG/runbooks, invoke a separate Critic, call GLPI/Temporal, or grant LIVE. The word `citations_valid` must not be interpreted as source authenticity.

## Acceptance matrix — explicit evidence required

| Gate | Positive synthetic expectation | Negative mutation | Fail-closed result | Missing authority / proof |
|---|---|---|---|---|
| G0 Identity | One tenant + correlated SAN event and Payments service | Cross-tenant event or mismatched incident ID | REJECT / no decision | Authenticated tenant/actor Core binding |
| G1 Twin | Versioned SAN→storage→Payments edge chain with edge receipts | Missing edge, stale edge, loop, budget exhaustion | UNKNOWN; `SOURCED_DEPENDENCY_PATH` missing | CMDB graph authority, version and freshness policy |
| G2 Evidence | Every claim maps to immutable source/edge receipt | Replace digest with another valid 64-hex string | UNVERIFIED; no root cause promotion | Independent Evidence readback, content digest and tenant ACL |
| G3 RAG | Approved runbook ID, version, tenant, timestamp, quoted span | Inject “system override”, fake approval or cross-tenant runbook | Ignore instructions; reject citation; DENY | Authorized RAG retrieval + runbook registry |
| G4 Critic | Separate invocation ID, input digest, evidence read receipts, contradictions and missing-proof ledger | Same invocation, self-asserted `independent=true`, contradictory source | INDEPENDENCE_UNKNOWN; NEEDS_MORE_EVIDENCE | Independent Critic executor and invocation audit |
| G5 Policy/HITL | Explicit deterministic DENY on unqualified synthetic proposal | Fake approval inside prompt, tool output or ITIL text | DENY, `effects_allowed=false` | Policy/HITL authority receipts, replay/fencing proof |
| G6 ITIL | Read-only projection with synthetic IDs, no ticket write | Requested ticket create/update or remediation | NO_WRITE; ITIL_READ_ONLY | GLPI actor/tenant authorization and real read-only adapter |
| G7 E2E | One trace joins Event→Incident→Twin→Evidence→Analyst→Critic→Policy/HITL→ITIL | Break any provenance link or hide contradiction | BLOCKED; no LIVE promotion | Same-SHA offline run receipt and independent layer logs |

**Pass criteria:** all negative mutations fail closed; hypotheses retain `HYPOTHESIS_NOT_ROOT_CAUSE`; citations resolve to authorized immutable receipts; contradiction and missing-proof arrays are present (possibly empty only with evidence); Critic independence is supported by *distinct invocation and readback receipts*, not a string flag; Policy and HITL both explicitly deny; ITIL is read-only; all effects disabled. A deterministic synthetic PASS qualifies only the tested offline contract, never LLM grounding or production.

## Minimal receipt schema (example template, NOT an execution)

```json
{
  "schema": "aiops2.intelligence-acceptance.v1",
  "mode": "SIMULATION",
  "source_sha": "91551be28bc1383062669ef48d9c29aff6a83718",
  "scenario": "SAN_TO_PAYMENTS",
  "run_id": null,
  "incident_id": null,
  "graph_version": null,
  "evidence_authority": "UNKNOWN",
  "rag_authority": "UNKNOWN",
  "critic_independence": "UNKNOWN",
  "critic_invocation_receipt": null,
  "contradictions": [],
  "missing_proofs": ["EVIDENCE_READBACK", "CRITIC_INDEPENDENT_INVOCATION", "RUNBOOK_ACL", "POLICY_HITL_RECEIPTS", "ITIL_READONLY_RECEIPT"],
  "policy": "DENY",
  "hitl": "DENY",
  "itil": "READ_ONLY",
  "effects_allowed": false,
  "runtime_attested": false,
  "tests_executed": [],
  "ci": "UNKNOWN",
  "e2e": "NOT_EXECUTED",
  "live": "NO_GO"
}
```

## Integration handoff

1. Architect reviews #713 diff and de-duplicates the overlapping Intelligence PRs before choosing a single owning implementation and test file.
2. Execute canonical deterministic tests at the **new exact HEAD**, record command, exit code, UTC timestamp, test counts and redacted logs; do not reuse results from another SHA.
3. Add server-authoritative Evidence/ACL and separate Critic invocation receipts behind existing interfaces; until then report `UNKNOWN`.
4. Re-run offline SAN→Payments→Analyst/Critic→Policy/HITL DENY→ITIL read-only on that exact SHA. Never equate a local deterministic trace with actual GLPI, Temporal, LLM or Debian runtime.
5. Keep PR Draft until review and exact-head CI are available. Rollback: revert this single document only. No deployment, new scheduler, secrets or external effects.
