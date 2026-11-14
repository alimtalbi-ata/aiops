# ACME SAN → Payments — incident readiness (DEV only)

Date: 2026-11-14. Branch: `work/acme-incident-readiness-20261114`.

## Purpose
Expose an operator-readable, deterministic qualification state for the existing SAN P1 → Payments P2 synthetic incident. The Portal API adds `incident_readiness` and the local scenario page displays its blocked state. This does not add an incident engine, a GLPI ticket, a model inference, or an authenticated runtime observation.

## Contract
- `state=BLOCKED_UNATTESTED`, `mode=SYNTHETIC_ONLY`
- `required_checkpoints=9`, `verified_checkpoints=0`, `missing_checkpoints=9`
- `next_operator_action=COLLECT_AUTHENTICATED_RUNTIME_EVIDENCE`
- `live_action_allowed=false`

These are fixture-specific constants, not computed runtime health. The nine checkpoints remain MISSING. The scenario's Analyst/Critic/Policy decision still denies LIVE actions. Missing proof is never upgraded to success.

## Validation and limitations
Added offline contract assertions in `tests/test_acme_impact_read_model.py`. Tests **not executed in this session**; no PASS claimed. No container, API, GLPI, Checkmk, Grafana, Temporal, Debian or production qualification. Existing API fields preserved; this is an additive DEV contract requiring consumer review.

## Rollback
Revert the feature and test commits on this branch, or discard the branch. No deployment or data migration occurred.

## Next
Run exact-head Python unit tests and quality workflow; review additive API compatibility and operator display; obtain independently authenticated runtime checkpoints before designing any LIVE readiness transition. Preserve G0/G1 and human authorization gates.
