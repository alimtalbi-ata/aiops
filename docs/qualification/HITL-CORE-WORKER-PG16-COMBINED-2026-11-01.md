# P0 Policy/HITL — Core ASGI / Worker / Temporal / PostgreSQL 16 combined preflight

**Date:** 2026-11-01. **Owner:** Worker/Policy HITL tests only. **Target:** sole Draft #234, `integration/enterprise-slice-main-20261031-2230`, initial base `98659d95c722c6eabcbf83815d5a16629a794877`. Source #251 already selectively integrated; no re-port. Source #254 Core populated PG16 tests remain independently owned, not imported.

## Scope and exact boundary

The dedicated test calls **actual Core REJECT-only FastAPI route handlers through ASGI HTTP TestClient**, backed by **actual PostgreSQL 16 transactions** on a newly created and dropped CI database. It uses installed migration chain 001/004/009 AI/010 Evidence/011 HITL/012 xref, pinned by Git blob SHA. A separate Temporal SDK development server runs an actual **test Worker**, which is stopped and restarted between two REJECT notifications. Core remains the sole authority for claim, lease token, proposal digest/revision and delivered ACK. The Worker only sends notification signals; no poller is wired.

The Core authorization token and tenant/run ownership HMAC are generated **inside disposable CI**, bound to a synthetic service principal and a synthetic Run, using a separate key and file. The signature tests the Core cryptographic integrity gate, **not independent GLPI source authority or a real OIDC subject**. A missing proof returns UNKNOWN before a lease. Real GLPI/IdP attestation remains NOT_ATTESTED and is a blocking dependency for any non-synthetic promotion.

Three test cases cover: (1) unsigned source denial without leasing; (2) Core HTTP claim → Temporal signal → committed Core ACK whose response is deliberately discarded → idempotent ACK replay → Temporal **test Worker** restart → second REJECT; (3) concurrent Core claims, lease expiry, stale token fencing, reclaim and exact delivered ACK. The response-drop injection occurs **after a real PostgreSQL commit**, but it is **not actual network packet loss**. Temporal server restart is **NOT_TESTED**. The full Core service process and production IncidentWorkflow are NOT_TESTED; HTTP uses in-process ASGI, not a TCP socket.

All fixtures are DEMO, REJECT, `SYNTHETIC_UNVERIFIED`. `execution_allowed=false` and `effect_allowed=false` are checked on Core HTTP replies and Temporal notifications. Zero APPROVE rows and zero effect receipts are asserted. The public Policy HTTP contract stays exactly `state/decision/reason` and is not edited. Temporal signals are never authorization.

## CI invocation

```bash
PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_pg16_temporal_combined.py' -v
/tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
pg_dump --version
pg_restore --version
sha256sum /tmp/hitl-combined-pg16-dr.dump
```

Only run in GitHub Actions with `AIOPS_CI_COMBINED_DISPOSABLE=YES`, `AIOPS_CI_OUTBOX_DISPOSABLE=YES`, an isolated PostgreSQL 16 service `postgres:5432/aiops`, and pinned `psycopg[binary]==3.2.13`, `fastapi==0.116.1`, `httpx==0.28.1`, `temporalio==1.16.0`. PostgreSQL client `pg_dump/pg_restore` must be version 16; **do not remove DR if installation fails**. Alternative on package failure: use a separately versioned `postgres:16-alpine` client service/container with explicit version check, then rerun both tests and DR. No shared Quality workflow changes.

Dedicated workflow: `.github/workflows/hitl-core-worker-pg16-combined-disposable.yml`. Evidence: combined test log, SQL-model/DR 5/5 log, synthetic classification JSON, dump and SHA256; GitHub artifact only if workflow executes successfully. Never claim N/N or runtime observed from source alone. The exact-head workflow status and artifact digest must be captured after CI.

## Dependencies, risks and rollback

Core owns source attestation and its independently authenticated tenant/Run mapping, exact hash/revision, lease ownership/expiry and ACK idempotence. The CI HMAC fixture **does not attest** human approval, GLPI actor rights, independent GLPI ownership or a durable nonce ledger. No real APPROVE, executor, LIVE, SSH, Ansible, GLPI write or deployment. A green test qualifies only this synthetic combined T1 preflight, not D1/D2/T4/T5.

Rollback: close the focused PR or revert its three new paths; no migration or Core code was copied. GitHub destroys the disposable PostgreSQL service; test teardown drops only its explicitly created database. Retain existing #234 PG16/DR and Worker tests. No merge by owner; architect alone integrates.
