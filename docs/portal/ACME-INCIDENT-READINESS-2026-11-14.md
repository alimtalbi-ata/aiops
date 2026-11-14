# ACME SAN → Payments — incident readiness (DEV only)

Date: 2026-11-14. Branch: `work/acme-incident-readiness-20261114`.

## Purpose
Expose an operator-readable, deterministic qualification state for the existing SAN P1 → Payments P2 synthetic incident. The Portal API adds `incident_readiness` and the local scenario page displays its blocked state. This does not add an incident engine, a GLPI ticket, a model inference, or an authenticated runtime observation.

## Contract
- `state=BLOCKED_UNATTESTED`, `mode=SYNTHETIC_ONLY`
- `required_checkpoints=9`, `verified_checkpoints=0`, `missing_checkpoints=9`
- `next_operator_action=COLLECT_AUTHENTICATED_RUNTIME_EVIDENCE`
- `live_action_allowed=false`

The checkpoint counts are derived from the synthetic checkpoint projection (currently nine MISSING), not from runtime health. The builder rejects any unexpectedly attested checkpoint in this synthetic-only view. The scenario's Analyst/Critic/Policy decision still denies LIVE actions. Missing proof is never upgraded to success.

## Validation and limitations
Added offline contract assertions in `tests/test_acme_impact_read_model.py`. Tests **not executed in this session**; no PASS claimed. No container, API, GLPI, Checkmk, Grafana, Temporal, Debian or production qualification. Existing API fields preserved; this is an additive DEV contract requiring consumer review.

## Rollback
Revert the feature and test commits on this branch, or discard the branch. No deployment or data migration occurred.

## Next
Run exact-head Python unit tests and quality workflow; review additive API compatibility and operator display; obtain independently authenticated runtime checkpoints before designing any LIVE readiness transition. Preserve G0/G1 and human authorization gates.

## Follow-up: offline Incident → Run → Ticket correlation

`app/portal/incident_ticket_correlation.py` adds an isolated, deterministic identity-join contract. It does **not** mount a route, call GLPI/Core, inspect real tickets or grant tenant ACL. Default without the explicit caller prerequisite is `UNKNOWN / ACTOR_TENANT_ACL_REQUIRED`. A synthetic exact-match case returns `MATCHED_UNATTESTED`, never `CONNECTED`, `runtime_attested=true` or LIVE authorization. Cross-tenant identities, malformed IDs, unknown/LIVE modes and mismatched Run/Ticket IDs are refused. The boolean caller prerequisite does **not** establish authorization; the returned `tenant_acl_qualified` is always false. A future integration must supply independently authenticated actor/tenant/entity authorization and authoritative service records before any browser exposure.

`tests/test_incident_ticket_correlation.py` covers refusal and matching; `.github/workflows/quality.yml` now runs it. No host action, deployment or runtime proof. Check the exact latest CI SHA before qualification.
