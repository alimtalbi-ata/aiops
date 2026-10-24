# AIOps STAR V2.13.40 — V1 02/03 run_id handoff (HLD / LLD)

**Status:** offline candidate, synthetic qualification only. No Debian, n8n, CMDB, GLPI or ticket mutation. No production execution evidence was collected.

## HLD — immutable identity across workflows

The single user portal remains on **17777**. The historical V1 flows remain untouched. For the ACME STAR Brocade SAN P1 / Payments P2 scenarios, the canonical upstream `run_id`, `incident_id` and `correlation_id` must be present and equal at **02 Webhook → RAG → Canonical Identity → 03 Prepare Analyst Payload**. The 02 Call Analyst boundary must not fabricate missing identity. `RUN_ID_MISSING` is a *blocking* diagnostic, never an invitation to generate an identifier downstream.

An n8n execution marked successful is not proof of Analyst/Critic validity, Policy approval, HITL authorization, simulated remediation verification, closure, or replay determinism. Live remediation is prohibited by this demo contract.

## LLD — offline verification

`demo/star_n8n_identity_gate.py` consumes a **sanitized, operator-supplied four-stage JSON** with keys `webhook_02`, `rag_02`, `canonical_02`, `prepare_analyst_03`. Each stage must contain three identical, nonempty canonical IDs. Unknown/missing stages, contradictory or malformed IDs, duplicate JSON keys, symlinks and oversized files are rejected. No default identity or recovery path exists. The success report contains an identity SHA-256 fingerprint but expressly marks runtime, Analyst, business and LIVE assertions **false**.

Use `python -m demo.star_n8n_identity_gate sanitized-stages.json` on an offline machine. Do **not** pass raw n8n exports, credentials, bearer tokens, webhook URLs or production traces. Exit code 0 means **consistency of supplied data only**; 2 means blocked. The module never contacts services or imports workflows.

## Qualification and next steps

The isolated CI runs `python -m unittest tests.test_star_n8n_identity_gate -v` with `AIOPS_STAR_NO_RUNTIME=1`. Before any real V1 diagnosis, obtain separately approved and redacted per-stage outputs, verify that the n8n 02 Call Analyst payload preserves the upstream identity, and correlate 03's `RUN_ID_MISSING` with its exact execution ID. Do not infer propagation from a workflow graph alone. Maintain strict cross-run isolation and fail-closed behavior.

**Rollback:** remove these branch-only files; no runtime rollback is necessary. The Chromium read-only adapter, runtime screenshots (n8n, Grafana, GLPI V1 :8080) and Temporal E2E failure remain separate open qualifications. Synthetic fixtures are never runtime proof.
