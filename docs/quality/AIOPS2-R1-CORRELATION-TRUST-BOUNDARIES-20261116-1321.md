# R1/5 — Correlation trust-boundary gap assessment (2026-11-16, Europe/Paris)

Base: PR #713 HEAD `91551be28bc1383062669ef48d9c29aff6a83718`. Scope: source inspection only, **not** runtime or CI qualification.

## Verified source contract

Inspected `scripts/aiops2_event_correlation.py` and `tests/test_aiops2_event_correlation.py` on the exact base SHA. The function `normalize_event` validates tenant/source/event/CI/service identifiers, severity, a lowercase 64-hex digest **shape**, and timezone-aware timestamps. `correlate_events` rejects observations outside the age window or known after `as_of`; identity is `(tenant_id, source, source_event_id)`; contradictory duplicate identities reject both receipts; incidents group by `(tenant_id, service_id)`. The returned impact is `UNKNOWN`, with runtime attestation and LIVE remediation authorization both `False`.

## Material unqualified boundaries

1. **Digest provenance:** a regex match does not establish that a SHA-256 digest was computed over the event/evidence bytes, signed, or linked to an immutable evidence receipt. An arbitrary 64-hex string passes shape validation. Required next contract: authenticated source receipt and digest recomputation using fixture bytes, with missing/mismatch -> UNKNOWN/BLOCKED. Owner: Evidence/Core; do not modify their code concurrently.
2. **Source identity:** `source` is one of checkmk/prometheus/grafana but is supplied by the event. The corrrelator does not attest source transport identity or a tenant-scoped source registration. Required next contract: forged `source` and tenant assertions must be rejected at the trusted ingestion boundary; do not treat offline normalization as authentication. Owner: Core.
3. **Causal graph:** grouping two events by tenant and service is *not* proof that SAN degradation caused Payments impact. Required next contract: graph edge IDs, graph version, CI/service mapping provenance and freshness; absent/contradictory edge -> UNKNOWN. Owner: Twin/CMDB.
4. **Policy/HITL:** hardcoded `live_remediation_authorized=False` is a safe synthetic boundary, not an execution-time authorization check. Required next contract: independent Policy refusal and absent/expired approval -> BLOCKED, with zero side effects and no fabricated receipt. Owner: Policy/HITL.
5. **Input identity canonicalization:** required string fields are checked using `strip()` but retained untrimmed. Thus `tenant_id='acme'` and `tenant_id=' acme '` remain distinct tenant keys, while both pass validation. Whether whitespace is valid must be defined at the authenticated boundary; until then do not claim canonical tenant identity. Suggested contract: reject noncanonical identifiers or use a separately verified canonical tenant principal. Owner: Core/identity.

## Non-overlap and acceptance

Reuse #718, #751, #756, #765, #770, #775 and #784 for existing duplicate/freshness/namespace cases. Do not add competing edits to their files. For the next targeted test PR, add a new offline test file for the *uncovered* identity-canonicalization ambiguity, first agreeing the canonicalization rule with the Core owner. Keep this document as a review handoff, not a new runtime authority.

## Qualification ledger

- Source inspection on base SHA: PASS (manual code review; two files).
- New automated tests executed: NOT_TESTED.
- CI on base SHA: NOT_TESTED (PR-triggered workflow lookup returned zero runs; combined commit statuses empty; this is not proof that no other workflow ran).
- Digest authenticity, tenant authentication, causal SAN→Payments and Policy/HITL execution: NOT_TESTED / UNKNOWN.
- LIVE: NO-GO; DEMO/SIMULATION only.

Rollback: close the documentation PR or revert only this file after review. No merge, rebase, cherry-pick, deployment, host access, new scheduler, or V1/V30 changes.
