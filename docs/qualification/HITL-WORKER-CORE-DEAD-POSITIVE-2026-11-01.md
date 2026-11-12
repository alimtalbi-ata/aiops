# Worker P0 — Core-owned terminal DEAD positive integration (2026-11-01)

**Owner:** Policy/HITL Worker tests, dedicated disposable CI only. **Base:** sole integration Draft #234 branch `integration/enterprise-slice-main-20261031-2230`, exact starting SHA `8b1e121cbd7123d95786133c4cf579030d1bf052`. Main reference `ae7c3e5102b99a66bd7806d602146f1309a9749d`. No changes to candidate/Core/Portal/ACME/shared Quality/board; no re-port of #296. The earlier #296 404 negative route-absent contract is **obsolete on this candidate**, because Core-owned 014 and `/dead` are now selectively integrated.

## Interface and ownership

Core alone implements `POST /api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead` and owns migration `014_hitl_reject_terminal_receipts.sql`. Worker **does not call this endpoint in production**, implement terminal transitions, mutate Core schema or infer DEAD from retry exhaustion. Test harness calls the real Core route with the exact eight-field ACK body: `owner`, `run_id`, `proposal_id`, `proposal_hash`, `proposal_revision`, `lease_token`, `execution_allowed=false`, `effect_allowed=false`. Separate permission `hitl:reject:terminal` is required in addition to `hitl:reject:deliver`. Synthetic actor/ownership HMAC are fixture integrity controls, not GLPI/OIDC attestation.

## Positive and negative assertions

The test reuses the existing disposable PostgreSQL 16 fixture and installed 001/004/009–012 chain, then applies **Core-owned** 013 and 014 in the new CI database, without copying/mutating any migration. Two distinct REJECT events reach eight Core-issued claims; the harness accelerates expiry by SQL `lease_until` update, **never SQL-injects DEAD**. Core /dead performs the actual terminal transition and writes one immutable 014 audit row per event. Replays with the same eight-field body are idempotent. Deliver-only identity receives 403; wrong tenant, owner, Run, proposal hash/revision, token and effect flag cannot produce DEAD. ACK after terminal is refused.

Independent Uvicorn Core HTTP runs on ephemeral loopback TCP; a deterministic gateway closes the downstream response **after Core /dead committed**, and replay reads the durable receipt. This is `INJECTED_GATEWAY_CLOSE`, **not** physical packet loss, network partition or host deployment. A disposable Temporal dev server is stopped and restarted with its SQLite history; the test Worker resumes the synthetic notification sink, which remains at zero signals across generations. Zero DELIVERED, APPROVE, execution or effect receipts for these exhausted events; no Temporal signal grants authority. No universal exactly-once claim.

## Machine-readable evidence

`tests/test_worker_core_dead_positive_pg16.py` writes `/tmp/hitl-core-dead-positive-receipts/core-dead-positive.json` with schema `aiops.worker-core-dead-positive.v1`, exact source HEAD, event IDs, two audit digests, Core status/attempts, restart count, zero-signal/effect counters and explicit `NOT_TESTED` / `NOT_ATTESTED` classifications. Raw Bearers, lease tokens, HMAC and raw audit payloads are not exported. The dedicated workflow recomputes canonical SHA256, checks exact HEAD, validates counters, and emits a `sha256sum` manifest. PostgreSQL 16 `pg_dump/pg_restore` regression stays mandatory and produces a separate checksum. CI runner service is ephemeral; it is **not** a new persistent Debian stack.

## Exact-head qualification

```bash
PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_dead_positive_pg16.py' -v
/tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
pg_dump --version
pg_restore --version
sha256sum --check /tmp/hitl-core-dead-positive.sha256
sha256sum --check /tmp/hitl-core-dead-positive-dr.sha256
```

**Expected** new positive 1/1 and existing DR 5/5; **NOT OBSERVED** until exact-head CI completes. Workflow: `.github/workflows/hitl-worker-core-dead-positive-pg16.yml`, pinned `psycopg[binary]==3.2.13`, `temporalio==1.16.0`, `uvicorn==0.35.0`, `httpx==0.28.1`, PostgreSQL 16 client and service. If `postgresql-client-16` installation fails, use a separately versioned major-16 client image in disposable CI, **without removing DR**. Artifacts/checksums and N/N are to be filled from actual workflow run, never inferred.

**Dependencies:** Core 013/014 and Core `/dead` implementation already present in candidate HEAD cited above; Core owns all future schema/API fixes. Independent real GLPI/OIDC authority remains `NOT_ATTESTED`. Host 7777 `NOT_VERIFIED`; no host SSH/Docker/volumes, persistent stack, GLPI write, LIVE, executor or deployment. `execution_allowed=false`, `effect_allowed=false`. `RELEASE_STABLE=NO_GO`.

**Rollback:** close focused Draft or revert only its three new Worker test/workflow/doc files; **retain** Core 013/014 immutable audit and existing DR, never DROP or delete rows. Architect alone decides selective integration. Publish exact-head PR SHA, CI URL, N/N, artifact SHA256 and limitations to #186.
