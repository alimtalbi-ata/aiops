# Worker P0 — canonical Core /dead gateway replay (2026-11-01)

**Owner:** Policy/HITL/Temporal Worker tests only. **Target:** sole Draft #234, branch integration/enterprise-slice-main-20261031-2230. **Exact starting base:** 5045dfa0784c267ca839d16d5b32d9d1d8d09234. **main at branch creation:** ae7c3e5102b99a66bd7806d602146f1309a9749d. Source #299 positive test was already selectively integrated by the architect; do not re-port #299 or restore obsolete #296 404 assertion.

## Contract and delta

This focused test complements #299: its Core /dead endpoint is served by the **canonical core.main.app over independent loopback TCP**, not a test-only FastAPI router. The canonical Core route was mounted by the Core owner in the candidate; Worker neither implements nor changes that endpoint, migration 013/014, Core schema, or audit. The test creates two distinct synthetic REJECT outbox events and obtains eight real Core claims per event. It only accelerates the lease expiry timestamp in disposable PG16, **never writes status=DEAD in SQL**. Core /dead commits each transition and immutable 014 audit receipt using the exact eight-field ACK-shaped body: owner, run_id, proposal_id, proposal_hash, proposal_revision, lease_token, execution_allowed=false, effect_allowed=false.

The terminal call requires hitl:reject:terminal separately from hitl:reject:deliver. A delivery-only actor, foreign tenant and forged lease token are denied before transition. The gateway deliberately closes the downstream connection **after** the canonical Core HTTP response confirms a committed DEAD. The client then replays /dead after the disposable Temporal server has stopped and restarted from its persistent SQLite history; the replay must be idempotent and preserve the same Core 014 receipt digest. Both post-DEAD ACK attempts are denied. The Temporal sink is never signalled: 0 notifications, 0 APPROVE, 0 DELIVERED and 0 effect receipts. No Temporal signal is authorization.

**Evidence boundaries:** INJECTED_GATEWAY_CLOSE is not physical packet loss or partition (NOT_TESTED); synthetic ownership HMAC is not real OIDC/GLPI identity (NOT_ATTESTED); host_7777=NOT_VERIFIED; no universal exactly-once claim. This is isolated GitHub Actions CI only, never Debian/production, LIVE, executor, SSH, Docker socket or GLPI write. The CI runner's ephemeral PG16 service and Temporal process are not persistent host stacks. RELEASE_STABLE=NO_GO.

## Reproducibility and receipt

Three Worker-owned files:
- tests/test_worker_core_dead_canonical_gateway_pg16.py — one isolated canonical Core TCP /dead gateway-replay test; inherits only fixture/migration setup from the existing Worker test, masks inherited test cases.
- .github/workflows/hitl-worker-core-dead-canonical-gateway-pg16.yml — exact-head checkout, PostgreSQL client 16, pinned Python clients, disposable PG16 service, Temporal persisted restart and mandatory DR restore regression.
- This Worker qualification document.

Commands executed by dedicated CI (do not claim results before exact-head run):

    PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_dead_canonical_gateway_pg16.py' -v
    /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
    pg_dump --version; pg_restore --version
    sha256sum --check /tmp/hitl-core-dead-canonical.sha256
    sha256sum --check /tmp/hitl-core-dead-canonical-dr.sha256

Expected new test **1/1** and existing DR **5/5**, not yet observed at branch creation. If apt installation of postgresql-client-16 fails, propose a separately pinned major-16 client image in disposable CI, retaining the DR test.

Machine-readable receipt schema: aiops.worker-canonical-dead-gateway-replay.v1, path /tmp/hitl-core-dead-canonical-receipts/canonical-dead-gateway.json. Contains exact source HEAD, two synthetic event IDs and receipt SHA256s, immutable audit row counts, restart count, ACL and stale ACK checks, zero-signal/effect counters and explicit NOT_TESTED/NOT_ATTESTED classifications. Its canonical payload digest is verified in CI, and its file SHA256 manifest is uploaded. **Upload only the redacted JSON receipt and SHA256 manifests; NEVER upload raw PG16 dump, credentials, Bearers, lease tokens, HMAC secrets or raw 014 audit payload.** DR dump is ephemeral CI-only; only its checksum is retained. Workflow logs stay in GitHub Actions, not the artifact.

## Handoff, dependency and rollback

Dependency: Core-owned canonical core.main.app route, migrations 001/004/009–014 and immutable Core 014 terminal audit. Any Core API/schema defect belongs to Core; Worker must fail closed, not patch the Core route. CI exact-head run, N/N, artifact URL/checksum and final HEAD are reported separately after verification and posted to issue #186. A green source PR is not a host runtime attestation.

Rollback: close the focused Draft or revert its three Worker-owned files only. Never revert/drop Core 013/014, delete a PG16 volume, or alter the sole candidate directly. Architect alone decides selective port/merge. No shared Quality, architecture board, Portal, ACME, host 7777 or deploy/aiops2-stable edits.
