# AIOps V2.13.42 — n8n V1 02→03 canonical identity: HLD / LLD

Date: 2026-10-23. Scope: **offline, sanitized observations only**. This is not a production workflow change.

## HLD — security boundary and business objective

The legacy workflow must carry one unambiguous `run_id`, `incident_id` and `correlation_id` from ingress to Analyst. The offline verifier checks a four-stage handoff:

```text
02 Webhook → 02 RAG → 02 Canonical Identity → 03 Prepare Analyst Payload
       |          |             |                         |
       +----------+-------------+-------------------------+
             independently collected, sanitized identity tuples
                                  |
                     strict consistency gate
                          /             \
               CONSISTENT_UNAUTHENTICATED  BLOCKED
```

**Fail closed:** never create or recover a missing identifier downstream. A successful n8n execution is not a business outcome, and consistency of operator-supplied observations is not runtime authentication.

## LLD — exact schema and invariants

The input JSON has **exactly** the stage keys `webhook_02`, `rag_02`, `canonical_02`, `prepare_analyst_03`. Each stage is an object with **exactly** `run_id`, `incident_id`, `correlation_id`; all values must be nonempty strings matching the identifier allowlist. Unknown aliases, nested identity objects, shadow fields, absent fields, duplicate JSON keys and contradictory values are rejected.

The verifier produces `CONSISTENT_UNAUTHENTICATED` with a deterministic identity SHA-256 only if all stages match. Its explicit flags `runtime_execution_authenticated`, `analyst_completed`, `business_outcome_verified` and `live_remediation_authorized` remain `false`. Invalid CLI input returns exit 2 with `IDENTITY_UNVERIFIED` and no untrusted content.

Input collection must project only the three canonical fields from **independent**, redacted observations. Never use this verifier to patch production workflow 02/03, to import a workflow, or to create CMDB/ticket records.

## Threats, tests and release gate

- Shadow `runId`, `run_id_shadow` or nested `identity` containing another run: **BLOCK**.
- Missing or mismatched ID at any stage: **BLOCK**.
- Missing/extra stage, duplicate JSON key, symlink or oversized file: **BLOCK**.
- Four identical canonical tuples: **CONSISTENT_UNAUTHENTICATED**, not a runtime PASS.
- Temporal synthetic policy `OBSERVE/SIMULATE` remains separate from LIVE execution gates.

Local qualification command:

```sh
AIOPS_STAR_NO_RUNTIME=1 python -m unittest tests.test_star_n8n_identity_gate -v
```

For real runtime diagnosis of `RUN_ID_MISSING`, obtain authorized, redacted node execution outputs from workflow 02 (Webhook, RAG, Canonical Identity, Call Analyst) and workflow 03 (Prepare Analyst Payload). Verify the handoff at the precise failing execution. No production changes without explicit human approval.

## Operational restrictions

No Debian container restart; do not touch the V1 bridge with incomplete containerd image. No additional ports. Portal :17777, GLPI V1 :8080, n8n, Grafana and CMDB remain unchanged. Chromium evidence is separately collected, unreviewed by default and never equivalent to HITL authorization.
