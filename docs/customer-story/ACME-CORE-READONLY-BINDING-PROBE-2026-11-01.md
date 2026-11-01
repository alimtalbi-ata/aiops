# ACME — Core read-only binding discovery, fail-closed (2026-11-01)

**Scope:** ACME-owned source-only contract, not an authenticated customer run. This document does not qualify production, tenant identity, GLPI tickets, Evidence, AI model output, Policy, HITL or effects.

## Pinned inputs and what can be checked

- Canonical seven-event `SCN-GOLDEN-PAYMENT-P1` replay, seed `20261018`, SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`.
- Pinned 005 graph: 18 CI / 17 edges; SAN-A → Pure01 → PAY01 → OraclePay → Payments, edge IDs `ACME-E08,E06,E04,E02`. ERP/Payments are reverse-reachable **candidates**, not observed outages.
- `tools/acme_synthetic_core_binding_probe.py` first validates the offline 15-stage receipt contract, then, **only with an operator-supplied expected pair**, an explicit trusted Core origin pin and a configured internal Bearer, makes at most three GET requests: `/api/runs`, `/api/runs/{run_id}`, `/api/noc/runs/{run_id}`. Only the last receives the Bearer. It reuses the hardened `find_acme_demo_run.fetch_json`: exact origin allowlist, no proxy inheritance, no redirects, no cross-origin forwarding.
- The probe compares registry/detail/internal pair, scenario/mode, creation anchor and bounded Core creation timestamp. Matching IDs are *not* returned as attested runtime IDs. The seven fixture events are not claimed to have been ingested merely because a Run has the same scenario name.
- The internal NOC projection deliberately reports `runtime_authenticated=false` and `tenant_acl_qualified=false`. Current Core `/api/runs` and `/api/runs/{rid}` are public read models. **No current read-only Core endpoint independently binds actor + tenant + Incident + Run to these seven source events.** An internal service token is not tenant authentication. Even a matching response is `result=UNKNOWN`, `reason=TENANT_ACTOR_AND_CANONICAL_EVENT_BINDING_UNAVAILABLE`, `core_internal_pair_match=true`; not `VERIFIED`.

## Reproducible safe invocation

```bash
# Only on an explicitly disposable Core instance, with operator-sourced IDs.
export AIOPS_ACME_TRUSTED_CORE_ORIGINS='https://approved-disposable-core.example'
export AIOPS_INTERNAL_TOKEN='<operator-supplied-secret-not-logged>'
python -m tools.acme_synthetic_core_binding_probe \
  --core-url 'https://approved-disposable-core.example' \
  --expect-run-id '<read-from-Core-API>' \
  --expect-incident-id '<read-from-Core-API>'
# Exit 2 by design: no current tenant/actor authority. Do not treat as a green runtime gate.
```

No Core instance, token or expected API IDs are provided by the pinned fixture. Do not run the command against production or invent IDs. Unit tests use `TEST_ONLY` placeholders, not customer receipts.

## Negative provenance and runtime boundary

The existing Quality catalogue discovery executes the new adversarial cases covering: missing IDs/token, untrusted origins, foreign/duplicate registry records, mismatched Run/Incident, stale/future/missing timestamps, forged tenant/actor claims, foreign partition, altered seed, malformed creation event and missing internal response. The test transport is a pure in-memory function; no network request is made.

Every output preserves **15/15 ITIL stages `NOT_EXECUTED`** and **6/6 checkpoints `NOT_EXECUTED`**, with `tenant_id`, `actor_subject`, `incident_id`, `run_id`, `glpi_ticket_id` null and `evidence_ids=[]`. P1 is a candidate, HIGH an estimate, and observed impact `UNKNOWN`. No GLPI write, Core write, simulated effect, AI receipt, verified SLA/OLA or HITL decision.

## Actionable dependency for Core/identity owners

Provide a *separately reviewed, actor- and tenant-authorized read-only* Core endpoint/response that binds `tenant_id`, authenticated `actor_subject`, `incident_id`, `run_id`, `scenario_id`, `source_event_ids` and immutable source hashes, with server-side ACL, freshness and provenance. The ACME owner must validate this exact response before promoting any stage; a client-supplied tenant, internal Bearer or matching scenario string is insufficient. GLPI/Evidence need their own independent readback authorities.

**Rollback:** revert only the focused ACME tool, tests and this document. Do not touch the integration candidate or shared workflow. `RELEASE_STABLE=NO_GO`.
