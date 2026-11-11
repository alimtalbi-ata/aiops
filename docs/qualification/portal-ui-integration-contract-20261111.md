# Portal UI consolidation — integration boundary (2026-11-11)

Candidate: PR #651; base `deploy/aiops2-stable` at `a0d2a751de57001b9a1bd6beb6ecceaf4afdb222`.

## Verified source-level gap

The stable `app/portal/main.py` defines `GET /api/portal/bootstrap` as an unauthenticated aggregation of `get_json(CORE, '/api/dashboard')`, `get_json(CORE, '/api/runs')`, and `get_json(TWIN, '/api/twin/summary')`. It does **not** return the `aiops.portal.readmodels.v1` envelope or assert a tenant-qualified actor identity.

The extracted `app/portal/portal_bootstrap_client.js` accepts only an envelope with `tenant_acl_qualified === true`, `actor_identity_server_derived === true`, `runtime_authenticated === false`, `live_remediation_authorized === false`, and `provenance === 'UNATTESTED_UPSTREAM_API_READ'`. It fails closed on missing/contradictory fields. **Do not forge these fields, add a client-side bypass, or wire this script to the legacy bootstrap endpoint.**

## Qualified reusable pieces

- #644 `read_settlement_guard.mjs`: pure server-side transport diagnostic; never promotes READY.
- #643 `evidence_request_gate.mjs` + `evidence_request_settlement.mjs`: UI-only latest-request-wins, no authorization.
- #629 `portal_bootstrap_client.js`: bounded Runs read projection (up to 100) with no HTML interpolation, but **requires a separately qualified backend read-model**.

## Exact-SHA CI

`Portal UI consolidation contracts` workflow run [43086549268](https://github.com/alimtalbi-ata/aiops/actions/runs/43086549268) completed SUCCESS at commit `6f7765428237e7c25563381279b65ad4bee9987d`. This is **isolated synthetic UI contract testing**, not Debian, authenticated Chromium, or SAN→Payments E2E evidence.

## Promotion gates

1. Server-side actor identity and tenant ACL must be established by trusted middleware; bearer possession alone is insufficient. Preserve 401/403/503 distinctions, no token persistence, and no runtime/LIVE attestation from upstream read success.
2. Connect read models and Evidence/Runs generation guards only after inspecting the actual Portal controller; test stale, navigation, unmount, 17/100/101 Runs, and cross-tenant rejection.
3. Select an existing synthetic ACME scenario and prove start/replay → timeline → SAN→Payments impact → Evidence, correlated by one `run_id` and `incident_id`; never bypass Policy/Critic/GLPI HITL.
4. Run authenticated Chromium on isolated candidate, verify no regressions, qualify rollback and Portal's two persistent mounts and absent Docker healthcheck.
5. Fix the active Debian poller's dirty checkout with a separate Git worktree, preserving six local edits. Do not push stable until exact-SHA gates and host receipts pass.

Status: **DRAFT / NO-GO / NOT DEPLOYED**.
