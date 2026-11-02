# Policy/HITL P0 — Core REJECT wire preflight (2026-11-01)

**Status:** focused Worker-owned Draft, synthetic-only. **RELEASE_STABLE=NO_GO.**
Architect's sole integration candidate: Draft #234, `integration/enterprise-slice-main-20261031-2230`. The branch is based on the candidate exact SHA `a794b725c2059006380deb7d49afceb3b510ba8e`; source Core Draft #250 `ae9d17fc0a28d3d2734f4aa6365434b3af6f4653` is **NOT integrated**. No #247/#243/#239/#204 re-port. Main reference at start: `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Refresh refs before integrating.

## Delta / authority

- `app/worker/hitl_reject_core_wire.py`: opt-in, injected `post(path, json_body)` callback; no HTTP client, credentials, network origin, runtime poller, Temporal client or Core state writer. Validates Core v1 `schema`, HTTP 200, no-effect flags, exact tenant and lease owner, SHA256 proposal hash/revision via existing `prepare_reject`, timezone-aware future `lease_until`, one-item REJECT-only batch. Refuses stale/foreign/malformed claims before any signal. Calls existing `notify_reject_batch`; Core remains the only lease and ACK authority. A Temporal signal is never an approval.
- **Exact Core #250 ACK contract:** Worker internal ACK includes tenant binding; Core's strict 8-field HTTP body does not. Adapter checks tenant against path/claim and drops only `tenant_id` from JSON body. Never drops tenant from route or claimed proof. Core must confirm this contract before activation. Strict `DELIVERED` + idempotent boolean + immutable receipt bindings are required; HTTP 200 alone is insufficient.
- `tests/test_worker_core_reject_wire.py`: adversarial **synthetic Core wire fixture**, not a Core HTTP server. Includes explicit ACK response loss **after fake commit**, with explicit identical ACK replay; **not** real network loss or automatic recovery. Uses disposable Temporal SDK dev server and real **test Worker** restart for two REJECT notifications, never Temporal server restart.
- Existing dedicated Worker workflow additionally runs this test on candidate PRs, pins `temporalio==1.16.0`, retains the separate existing PostgreSQL 16/DR job with `postgres:16-alpine`, `psycopg[binary]==3.2.13`, version-16 `pg_dump`/`pg_restore`, pinned installed 001/004/009/010/011/012 migrations. Does not edit shared Quality. The SQL-model lost ACK remains a model, not Core claim/ACK.
- No Policy HTTP changes: exactly `state`, `decision`, `reason`. No synthetic APPROVE, verified human identity, GLPI write, executor, LIVE, effect receipt, SSH, host, deploy or main push. All paths: `execution_allowed=false`, `effect_allowed=false`.

## Qualification commands and evidence

Dedicated disposable CI (requires GitHub Actions and ephemeral services):

```bash
PYTHONPATH=app python -m unittest discover -s tests -p 'test_worker_hitl_reject_notification.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_worker_core_reject_wire.py' -v
/tmp/hitl-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
pg_dump --version
pg_restore --version
sha256sum /tmp/hitl-worker-pg16-dr.dump
```

Use **only** actual exact-HEAD workflow logs for N/N, artifacts and hashes. No local tests or combined Core HTTP may be claimed from source inspection. Real disposable Temporal **Worker restart** may be marked OBSERVED only when the CI-gated test executes without skip. PG16 SQL-model and DR are separate proofs.

## Core/architect dependency and next combined test

Core Draft #250 owns `app/core/hitl_reject_delivery.py`, `app/core/itsm_xref.py`, service Bearer permission `hitl:reject:deliver`, signed tenant/Run→Incident ownership, immutable proposal hash/revision, random 30s lease token/owner/expiry, and delivered ACK idempotence. Core #250 exact-head Quality 3/3 and 009–012 SQL EXPLAIN do **not** establish real PostgreSQL claim/ACK concurrency, HTTP network loss or Core+Worker integration. Until architect selectively integrates Core after review, `CORE_CLAIM_ACK_HTTP=NOT_TESTED`, `REAL_NETWORK_ACK_LOSS=NOT_TESTED`, `TEMPORAL_SERVER_RESTART=NOT_TESTED`, `OIDC_HUMAN=NOT_ATTESTED`.

Next, **only after Core owner agreement and candidate exact SHA refresh**, run an additional same-SHA disposable integration: create REJECT-only synthetic outbox row under signed tenant/run ownership, use actual Core HTTP claim with a service identity, run the existing Worker notification against Temporal, restart the test Worker, send ACK, assert delivered and idempotent retry after injected ACK response failure, concurrent claim fencing and lease expiry on real PG16; retain pg_dump/pg_restore 16. Do not fake human approval or bypass ownership attestation to make it pass. Never enable the runtime poller on this preflight alone.

## Rollback

Close this Draft or revert the focused Worker wire module, test, qualification document and dedicated Worker workflow change. No migrations, Core/Portal/shared Quality changes, persistent data, real network connections or deployed services are introduced. Dispose of ephemeral Temporal/PG16 resources; preserve existing DR gate.
