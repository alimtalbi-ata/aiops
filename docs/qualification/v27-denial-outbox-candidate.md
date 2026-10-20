# Worker V2.7 — Denial outbox candidate, deployment & qualification

**Branch:** `feat/worker-v27-denial-reconciliation-20261020`  
**Status:** code pushed for review, **not built or run on the Debian server**. DEMO-only qualification outstanding. Production **NO-GO**.  
**Baseline evidence:** `docs/qualification/2026-10-20-temporal-policy-outage-e2e.md`; P0 tracking issue #33.

## Implemented in this candidate

1. Explicit migration `db/migrations/090_critic_denial_outbox.sql`: one durable denial intent per `(run_id, critique_id)`; PostgreSQL foreign keys back to Core ledger; status `PENDING` or `RECONCILED`; references and payload retained.
2. New Core authenticated routes: `POST /api/runs/{rid}/denial-intent`, `GET /api/denial-intents/pending?limit=20`, `POST /api/runs/{rid}/denial-intent/{cid}/reconciled`. Intents require a persisted rejected Critic. Reconciliation only acknowledges a persisted `BLOCKED` Policy record matching analysis, critique and run.
3. Worker writes denial intent after the Critic record and before contacting Policy, still issues `BLOCK` regardless of Policy availability.
4. Worker periodically scans pending intents and idempotently calls Policy, persists the Policy denial in Core and acknowledges the outbox item. The loop restarts when Worker restarts; no effect stage is triggered by reconciliation.
5. Deterministic test provider source copied with explicit `0644` permissions; added permission regression script.

## Deployment precautions

**Do not point this candidate at the operational `aiops2-rebuild` databases or volumes.**

The SQL file must be **applied separately to the isolated existing laboratory database before starting the new Core/Worker**. Docker's PostgreSQL `/docker-entrypoint-initdb.d` migrations only run on first initialization. Apply the migration with `psql -v ON_ERROR_STOP=1`, inspect schema and verify constraints. Backup the lab database first. Rebuild and pin the Core image from the exact branch revision, then rebuild/pin Worker. The existing Worker image `b870f48` does **not** contain this code.

Do not deploy Core V2.7 and Worker V2.7 without the migration: the Core API would fail when accessing the new table. Do not auto-promote main.

## Qualification needed (not yet run)

- Initial-state integration test: rejected Critic yields exactly one `PENDING` row and Core run `BLOCKED`.
- Stop **only lab Policy**, create synthetic DEMO run and confirm denied run with pending outbox, no HITL/REMEDIATE.
- Restart lab Policy: wait for reconciler to create exactly one `BLOCKED` Policy decision linked to correct analysis/critique and acknowledge the outbox. Verify across Worker restart.
- Replay same requests with equal and conflicting payload: ensure idempotent response or HTTP409; no duplicate.
- Concurrent Workers, crash between Policy write and ACK, loss of Core/Postgres, high retry frequency. Examine transaction and ordering invariants.
- Confirm that lab services remain in internal networks with no host ports. Audit no LIVE effects and no production connections.
- Run `scripts/qualification/test-provider-permissions.sh` against the reviewed source under a disposable Docker environment (script uses no network).
- Run syntax tests, Core route tests, candidate image builds, Temporal complete E2E, database migration test and GitHub CI before marking PASS.

## Remaining P0 gaps

This is an **initial implementation**, not an accepted fix for #33. It deliberately does not claim transactional coupling between the outbox record and Core's terminal BLOCK command. If Core fails after Critic persist but before an intent is recorded, the run is still denied via existing best-effort safety path, but a durable outbox gap may remain. Similarly, the simple scanning reconciler lacks leases/fencing for strong multi-worker concurrency. It has no dead-letter/status metrics or bounded retry policy. These must be resolved and tested before production.

The old direct Policy persistence path remains to maintain compatibility. It and the asynchronous reconciler could race to insert the same Policy decision; the existing `input_hash` deduplication must be load-tested for concurrent writes and protected by a database unique constraint. The candidate must **not** be promoted based solely on code review.
