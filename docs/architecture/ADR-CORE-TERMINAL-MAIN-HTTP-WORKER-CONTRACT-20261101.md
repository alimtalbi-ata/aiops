# ADR — Canonical Core HTTP mount for audited terminal REJECT (2026-11-01)

**Status:** Draft Core-only source; architect integrates selectively. **Decision:** mount the existing `core.hitl_reject_delivery.router` in the canonical `core.main.app` and prove the real ASGI route, not a stand-alone test FastAPI application.

## Reproduced gap

At sole Draft #234 base `0a9bde5b183ae15b511f45c82f913c9785fbc116`, `app/core/main.py` mounted only the xref router. The Core-owned `POST /api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead` handler and immutable migration 014 existed, and the Worker source #299 tested a **separate** `FastAPI(); app.include_router(router)` test server. Thus successful handler/Worker tests did **not** prove that the deployed canonical Core application exposed the endpoint. No Debian runtime assertion follows from this fix.

## Contract (no schema change)

The canonical Core app now mounts the existing REJECT-only router (claim, ACK, terminal DEAD). The terminal endpoint accepts the **same exact eight-field ACK JSON** (`owner`, `run_id`, `proposal_id`, `proposal_hash`, `proposal_revision`, `lease_token`, `execution_allowed=false`, `effect_allowed=false`) and requires service permissions `hitl:reject:deliver` **and** `hitl:reject:terminal`. It checks actor/tenant, exact Run/proposal/hash/revision, lease owner/token, exhausted attempts (at least eight), expiry, REJECT state and independent Core source ownership proof. It never authorizes remediation or human GLPI rights.

The canonical FastAPI `TestClient(core.main.app)` contract on disposable PostgreSQL 16 asserts 401 unauthenticated, 403 wrong-tenant service, non-enumerating 200 UNKNOWN for foreign tenant and mismatched Run/proposal/hash/revision/token/effect, one atomic 200 DEAD and immutable 014 receipt, idempotent replay of the same receipt, and late ACK 200 UNKNOWN. A simulated SQL INSERT failure **after** the DEAD UPDATE must return 503 UNKNOWN and roll the UPDATE back to LEASED attempts=8 with zero 014 rows; a subsequent valid call succeeds. This test injects SQL failure in Python only; it does not change or drop schema.

## Exact-head evidence and machine-readable receipt

Dedicated `.github/workflows/core-reject-terminal-pg16.yml` runs the existing installed 001/004/009–014 suite with two additional canonical HTTP tests (expected **14/14**, zero SKIP), verifies native PG16 `pg_dump/pg_restore` of populated 013/014 audit into a separate disposable database, and uploads only redacted receipts. New `aiops.core-terminal-main-http-contract.v1` JSON contains checked-out `source_head`, HTTP outcome matrix, attempts, count of 014 audit rows, canonical receipt SHA256, negative human authorization and zero effects, plus a self-check SHA256. It contains no bearer, lease token or database URL. Workflow results, exact-head N/N and artifact SHA256 must be filled from observed CI; a green prior source run is not qualification of this PR.

Command: `AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true PYTHONPATH=app:tests python -m unittest discover -s tests -p test_core_hitl_reject_terminal_pg16.py -v`. It is allowed **only** against a disposable CI PG16 service, not host or production.

## Ownership, dependencies, limitations, revert

Core owns the route, 013/014 ledgers and receipts. Worker owns delivery orchestration and must never inject DEAD SQL; coordinate the eight-field body with Worker #299 without editing Worker files. No shared Quality/board/Portal/ACME/packaging or candidate branch changes. This does **not** attest real IdP/GLPI human User/Profile/Entity/Ticket rights, ACME full-event hash equivalence, host port 7777, a Debian cutover, LIVE or an exactly-once external delivery. `actor_authorization=UNKNOWN`, `link_status=UNKNOWN`, `RELEASE_STABLE=NO_GO`.

Rollback is **CODE_ONLY_KEEP_013_014_AUDIT**: revert the router mount, tests, workflow and ADR if required; retain installed 001/004/009–014 and all 013 nonce/JTI/revocation and 014 terminal audit rows. Never issue schema DOWN/DROP, truncate, mutate audit, or deploy a second stack. Host consolidation and canonical portal TCP 7777 remain architect-owned and unverified.
