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


## Focused follow-up — concurrent retry after Core DEAD commit (2026-11-01 ~17:30 CET)

**Owner:** Worker tests/workflow/qualification only. **Source base:** sole Draft #234 at `e484f2e17bf4c72e4c5319e2e92f32430b4ec3b0`; **main reference:** `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Prior source #303 has already been selectively ported by the architect: do not re-port. No Core, Portal, ACME, shared Quality, architecture board, candidate or main edit.

A single additional adversarial test `test_13_concurrent_postdead_retry_fencing_after_temporal_restart` uses the **canonical Core main app on independent TCP**, disposable PG16 and migration 014. It acquires eight real Core REJECT claims for one synthetic event; SQL accelerates **lease expiry only**, never writes `DEAD`. Core alone atomically transitions to DEAD and writes one immutable 014 audit receipt. The gateway closes the downstream connection **after Core commits**. This is `INJECTED_GATEWAY_CLOSE`, not a physical packet loss or partition test.

After stopping Temporal and restarting its server with the same persisted SQLite history, the test issues **18 concurrent Core HTTP calls** against that event: six `/dead` replays (all 200 DEAD, idempotent and same 014 SHA256), six late `/ack` calls (all UNKNOWN), and six `/claim` attempts (all empty). Delivery-only service identity cannot use the distinct terminal permission; forged lease token is rejected. The test reads the immutable audit before and after the race, validates canonical SHA256, one receipt row, status DEAD/attempts=8/REJECT, zero DELIVERED, zero Temporal signals and zero effects. `execution_allowed=false` and `effect_allowed=false` on all tested paths; no APPROVE or LIVE.

The dedicated workflow now expects **2/2 combined Worker tests** (historical gateway replay plus new concurrent post-commit race) and **5/5 PG16 DR**. Both JSON receipts are checked against exact `AIOPS_EXPECTED_HEAD_SHA`, canonical payload digests and explicit safety counters. Only **redacted JSON and SHA256 manifests** are uploaded. The raw PG16 dump remains ephemeral on the runner for mandatory `pg_restore 16.15` regression and is NEVER uploaded. No Bearer, lease token, HMAC secret, or raw 014 receipt payload in the uploaded artifacts. Receipt schema `aiops.worker-canonical-dead-concurrent-retry.v1`, file `/tmp/hitl-core-dead-canonical-receipts/canonical-dead-concurrent-retry.json`.

**Proof boundaries:** a deterministic race over one synthetic exhausted event is not universal exactly-once; `physical_packet_loss=NOT_TESTED`, `oidc_glpi_identity=NOT_ATTESTED`, `host_7777=NOT_VERIFIED`, `sql_dead_injection=false`. CI is disposable, not Debian. `RELEASE_STABLE=NO_GO`.

**Commands** (CI, exact-head only after run):
```bash
PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_dead_canonical_gateway_pg16.py' -v
/tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
sha256sum --check /tmp/hitl-core-dead-canonical.sha256
sha256sum --check /tmp/hitl-core-dead-canonical-dr.sha256
```

**Rollback:** close the focused Draft or revert only this cycle's three Worker-owned file edits. Preserve Core 013/014 immutable audit, migrations and sole candidate. CI URL, exact HEAD, N/N and checksum are reported only after verification and handed to issue #186. No persistent Debian stack, host access, GLPI write, executor or deploy.


## Focused follow-up — post-DEAD tenant provenance and actor ACL revocation (2026-11-01 ~18:29 CET)

**Owner:** Worker tests, dedicated disposable workflow and this qualification only. **Base:** sole Draft #234 exact `e6381a6d7e8e088add37e6e28e9fde9ef543a9ff`; **main reference:** `ae7c3e5102b99a66bd7806d602146f1309a9749d`. The architect has already selectively ported #303/#307; do not re-port. New source Draft is independent of candidate integration. Only three Worker-owned paths: new `tests/test_worker_core_dead_revocation_pg16.py`, existing dedicated workflow and this document.

**Bounded adversarial contract:** canonical `core.main.app` over independent loopback TCP and disposable PG16 migrations through Core-owned 014. One synthetic REJECT reaches eight genuine Core claims; SQL accelerates *only lease_until*, never writes DEAD. Core `/dead` commits the terminal state and one immutable 014 receipt. A deterministic gateway drops the downstream HTTP response after Core commit; this is **INJECTED_GATEWAY_CLOSE, not physical packet loss**. An additional synthetic REJECT is left PENDING/attempts=0 to make a later claim check meaningful.

The test explicitly revokes the two **CI-synthetic tenant/Run ownership attestations** by withdrawing the CI-only signed ownership proof manifest **without changing immutable Core ownership rows** (Core 012 rejects UPDATE). While the original actor remains ACL-authorized, four concurrent `/dead` replays, four late `/ack` calls and four `/claim` calls must all fail closed with UNKNOWN. Then the canonical Core TCP process restarts with that actor token removed from its server-held digest ACL; a restarted Temporal dev server reads the same persisted SQLite workflow history. Another 4+4+4 concurrent requests must all fail with 401 UNKNOWN. A delivery-only principal and a foreign-tenant principal cannot use the terminal permission (403 UNKNOWN). No Worker/Core schema or endpoint is introduced.

Post-revocation DB readback must show **DEAD/attempts=8 and exactly one 014 receipt with identical canonical SHA256**, plus **PENDING/attempts=0 and zero 014 receipts** for the second event. Temporal query stays at zero signals across stop/start; zero APPROVE, DELIVERED and effect receipts, `execution_allowed=false`, `effect_allowed=false`. The receipt `aiops.worker-postdead-revocation-fencing.v1` records event ID *hashes only*, immutable audit SHA256 before/after, denial counts, exact source HEAD and explicit negative qualification boundaries. It must not contain Bearers, raw lease tokens, owner HMAC secrets or raw PostgreSQL dumps.

**Evidence classification:** synthetic signed-proof manifest withdrawal is **CI_INJECTED_PROVENANCE_REVOCATION**, not authenticated GLPI/OIDC revocation (`NOT_ATTESTED`). ACL revocation is a controlled Core process restart with a new server-only ACL snapshot, **not** live identity-provider propagation. Physical packet loss/partition `NOT_TESTED`; host port 7777 `NOT_VERIFIED` (17777 is different). This is one bounded race, **no universal exactly-once claim**. `RELEASE_STABLE=NO_GO`.

**Exact-head reproducibility:**

```bash
PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_dead_canonical_gateway_pg16.py' -v
PYTHONPATH=app:tests /tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_worker_core_dead_revocation_pg16.py' -v
/tmp/hitl-combined-venv/bin/python -m unittest discover -s tests -p 'test_hitl_pg16_candidate_outbox.py' -v
sha256sum --check /tmp/hitl-core-dead-canonical.sha256
sha256sum --check /tmp/hitl-core-dead-canonical-dr.sha256
```

The workflow verifies the new JSON canonical payload SHA256 and redaction, uploads only redacted `canonical-dead-*.json` and SHA256 manifests, **never raw PG16 DR dump**. Existing PG16 client major 16 and mandatory `pg_dump/pg_restore` DR are preserved. Expected 2/2 existing canonical, 1/1 new revocation and 5/5 DR; actual exact-head counts, run URL, artifact/checksum and rollback are reported only after CI. On PostgreSQL 16 package install failure, propose a separately version-pinned disposable major-16 client without removing DR.

**Rollback:** close focused Draft or revert only these three Worker-owned file changes; do not revert Core 013/014, edit shared Quality, main, candidate, architecture board, Portal/ACME or any host stack. No real GLPI write, LIVE, executor, SSH, Docker socket, persistent stack or deploy.

**CI red-cycle correction:** initial exact-head run [#41331929270](https://github.com/alimtalbi-ata/aiops/actions/runs/41331929270) failed at attempted UPDATE of immutable Core ownership provenance (Core 012 trigger). This is an expected safety barrier, not a Core defect. Follow-up removes that SQL mutation entirely and withdraws only the CI-signed proof manifest; final N/N must be requalified at the new exact HEAD. No Core changes.


## P0 follow-up — two independent OS Workers after Core actor revocation (2026-11-01 20:31 CET)

**Ownership:** exactly three Worker-only paths (revocation test, dedicated disposable workflow, this qualification). **Source base:** sole Draft #234 at `b31cdbae926f8feb80af2fb42e05900286c28457`, main reference `ae7c3e5102b99a66bd7806d602146f1309a9749d`. No re-port of #303/#307/#311 and no Core, Portal, ACME, shared Quality or candidate edits. The architect is sole integrator.

**Added adversarial boundary:** the existing canonical Core TCP /dead test obtains the eighth REJECT lease using real Core claim handlers on disposable PG16, accelerates only lease expiration, then commits Core-owned DEAD with exactly one immutable migration 014 receipt. Gateway response close is injected **after commit**, not a packet loss claim. The CI-signed tenant/Run proof manifest is withdrawn without SQL UPDATE to immutable ownership 012. Core restarts with the original actor absent from its server-held ACL; the Temporal development server restarts from the same SQLite file. **Two separate disposable Python OS processes** now each instantiate a real Temporal Worker on the persisted queue, synchronize at a local barrier and each concurrently retry four /dead, four late /ack and four /claim requests against canonical Core TCP using the revoked bearer. All 24 calls must return 401 UNKNOWN with both effect flags false, no receipt or claim items. Existing parent-runner calls independently check another 12 revoked-actor attempts; delivery-only and foreign-tenant principals remain 403 UNKNOWN. The test requires two distinct process IDs and verifies zero Temporal signals before/after. All processes are terminated before disposable CI ends.

**Immutable DB readback:** terminal event remains DEAD/attempts=8 with exactly one migration 014 audit row and identical canonical receipt SHA256 before/after the concurrent Worker processes; a second event remains PENDING/attempts=0 with no terminal receipt. No SQL DEAD, no 012/013/014 ownership UPDATE, no APPROVE, DELIVERED, LIVE or effect receipts. `execution_allowed=false`, `effect_allowed=false`.

**Machine receipt:** `canonical-dead-revocation.json`, schema `aiops.worker-postdead-revocation-fencing.v1`, now includes `disposable_worker_processes=2`, `distinct_worker_processes=true`, `revoked_worker_retry_requests=24` and exact source SHA; payload SHA256 is verified canonically in CI. The workflow requires one revocation test, five PG16 DR tests, zero SKIP and `sha256sum --check`, uploading only redacted JSON and SHA256 manifests. **Never upload the raw PG16 dump or any bearer, lease token or HMAC secret.** PG16 client 16 and pg_dump/pg_restore remain mandatory.

**Limits:** `CI_SIGNED_PROOF_MANIFEST_WITHDRAWAL` and server-held digest ACL restart are synthetic, **not** real GLPI/OIDC identity revocation; external SSO/GLPI remains NOT_ATTESTED. Local host 7777 has an operator-reported successful health/binding check, but is **not verified by this CI**; external access and uniqueness remain NOT_ATTESTED. 17777 is a distinct port. Gateway-close is not physical packet loss or partition; no universal exactly-once guarantee. `RELEASE_STABLE=NO_GO`. CI tests do not attest Debian runtime.

**Rollback:** close this focused Draft or revert its three Worker-owned file deltas; retain all Core 012/013/014 audit rows, migrations and the sole candidate. No persistent stack, host Docker/SSH, GLPI writes, LIVE, deploy or main push. Exact-head run URL, N/N, artifact digest and #186 handoff must be added only after the CI actually finishes.
