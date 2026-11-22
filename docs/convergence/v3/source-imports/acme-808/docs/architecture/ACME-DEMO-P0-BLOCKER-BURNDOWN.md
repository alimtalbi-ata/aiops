# ACME Demo — blocker burn-down and acceptance order

**Goal:** a convincing, repeatable, source-backed SAN P1 → Payments P2 demonstration of **the existing AIOPS2 platform**, not a parallel product. **State: OFFLINE_PASS, BROWSER_NOT_TESTED, E2E_NOT_VERIFIED, LIVE_NO_GO.**

## P0 — fix these before calling the demo qualified

| Priority | Blocking issue | Evidence currently available | Required acceptance test / stop condition |
|---|---|---|---|
| P0-1 | ITSM / worker receipt scene absent | No verified read-only Portal route for a synthetic SIM-GLPI worker receipt in `app/portal/main.py` | Trace a **real sandbox Core evidence record** to a tenant-scoped read-only route and render source, status, ID, timestamps; reject missing evidence as UNKNOWN. No POST, no actual GLPI call, no fabricated ticket |
| P0-2 | Core→Twin SAN→Payments join unproven | ACME Pydantic 17-stage fixture passes offline only | In isolated sandbox, capture the same incident/run/tenant identifiers at source and destination; require P1 SAN and P2 Payments relationship, explicit negative cases for missing or cross-tenant joins |
| P0-3 | Tenant ACL not qualified | Convergence `acme_run_detail.py` intentionally fails closed `TENANT_ACL_NOT_QUALIFIED` | Positive authorized ACME-TEST sandbox test and negative cross-tenant/anonymous test; **never bypass fail-closed 503** |
| P0-4 | Seven browser scenes not demonstrated | Existing Playwright host runner #404/#407; source-only route candidates #808 | Seven distinct screenshots on disposable sandbox, verified routes/selectors, visible SIMULATION, zero external requests, private atomic PNGs, SHA-bound manifest; missing scene = NO_GO |
| P0-5 | Deployed provenance not attested | Host runner can report checkout SHA + Docker image ID | Compare actual deployed checkout and container image to expected source, capture timestamp and host receipts; a supplied SHA alone is not attestation |

## P1 — improve demo credibility after P0

| Priority | Deliverable | Acceptance |
|---|---|---|
| P1-1 | Guided showrun | 10-minute SAN→Payments narrative with clear links from NOC, Twin, Analyst/Critic, Policy/HITL, ITSM, Timeline |
| P1-2 | Honest verdict | Offline gate, PNG byte integrity, browser run, runtime E2E and ACL displayed **separately**; no synthetic fixtures passed off as production events |
| P1-3 | Robust negative paths | Missing Core, missing Twin, 404 run, denied tenant, failed worker, stale receipt, missing PNG, corrupt PNG CRC, external request, disabled launch |
| P1-4 | Evidence export | Redacted metadata and SHA256 references; no secrets, real GLPI tickets or private screenshots in Git history |

## Execution sequence

1. **Now, no environment access:** harden evidence PNG validation, run CI at exact PR #808 SHA, audit existing Portal GET and evidence models, document source route gap.
2. **Next, source-only PR:** implement only a read-only ITSM receipt view **after locating its canonical Core evidence shape**. Keep missing fields UNKNOWN, tenant ACL fail-closed, add negative tests. Do not create a fake SIM-GLPI record to fill the screen.
3. **Then, authorized isolated sandbox:** qualify ACL and Core→Twin correlation first, followed by seven Playwright captures using the existing runner. No LIVE Debian mutation, no real GLPI, no Temporal side effects without explicit approval.
4. **Finally:** publish a redacted evidence pack and verdict tied to the exact SHA and image ID; do not promote if any P0 remains.

## Quality note: PNG bytes are not browser proof

The addon previously accepted a PNG signature plus IHDR header as `BYTES_CONSISTENT`. The current hardening checks **complete chunk framing, CRCs, IDAT and terminal IEND** and tests corruption/truncation. It still does not decode pixels or authenticate Chromium. A valid synthetic PNG remains insufficient for `runtime_e2e` or `browser_execution`.

## References

- [#808](https://github.com/alimtalbi-ata/aiops/pull/808): additive Workbench / Demo qualification addon
- [#807](https://github.com/alimtalbi-ata/aiops/pull/807): existing capture engine and incompatible manifest inventory
- [#805](https://github.com/alimtalbi-ata/aiops/pull/805): Pydantic readiness gate
- [#804](https://github.com/alimtalbi-ata/aiops/issues/804): central status and evidence tracker

## Source-backed Portal investigation — 2026-11-17

Inspected the actual `app/portal/main.py` on this branch:

- `GET /demo-studio` reads Core `/api/dashboard`, Twin `/api/twin/graph` and `/api/twin/impact/ACME-SAN-FABRIC-A`, and lists DEMO/REPLAY/STORY runs. It does **not** establish a verified SAN→Payments join or worker receipt.
- `GET /demo-studio/run/{rid}` validates run ID, restricts the selected run to a pre-existing DEMO/REPLAY/STORY record, and reads Core `/api/runs/{rid}`, `/ai-ledger`, `/gates`. It renders the canonical events and policy decisions. **A valid pre-existing run ID is required**; do not invent one.
- `GET /evidence` explicitly says that a cross-cutting Evidence ledger still requires an adapter and rights controls; it does not display worker receipts.
- `GET /policy` shows blocked/waiting runs and safety messaging; it does not constitute an approved HITL action.
- The `POST /api/demo` endpoint triggers incident/run execution when enabled and authorized. **Never invoke it from capture or preflight.**

**Implementation decision:** do not add a generic ITSM route that guesses worker evidence or bypasses tenant ACL. First establish the canonical worker receipt shape and authorized read-only source; then add a tenant-scoped presentation with explicit `UNKNOWN` for missing fields and negative ACL tests. Until then, `itsm_worker` remains `NOT_IMPLEMENTED` in the static inventory and the seven-scene gate remains NO_GO.

## P0-1 discovery: canonical Worker sandbox receipt found

**Source-backed finding:** `app/worker/main.py` lines 406–527 implements a canonical **read-only, authenticated** endpoint `GET /api/sandbox/acme/e2e/{attempt_id}` on the **Worker service**, not on Portal. This supersedes the earlier wording "canonical worker receipt shape unknown" but **does not** qualify the missing Portal scene.

- Requires `AIOPS_ACME_SANDBOX_ENABLED=true` and a configured internal token of at least 32 characters; otherwise 503.
- Requires service bearer authentication; otherwise 401. **Never forward or expose this token in browser JavaScript.**
- Restricts the attempt ID to `ACME-SIM-...` and the workflow lookup to `acme-simulated-ACME-TEST-{attempt_id}`; invalid attempt is 404.
- Requires completed Temporal workflow and validates the returned `aiops.worker-acme-simulated-no-effect.v1` receipt, `tenant_id=ACME-TEST`, `approval_kind=SIMULATED`, `receipt_status=SIMULATED_NO_EFFECT`, `receipt_phase=PRE_RESOLUTION`, `execution_allowed=false`, `effect_allowed=false`, `effect_receipts=0`, `real_glpi_writes_allowed=false`, `live_effects_allowed=false`, `audit_authority=TEMPORAL_WORKFLOW_HISTORY_ONLY`, and `receipt_digest_valid(result)`. Incomplete or inconsistent evidence is 503.
- `POST /api/sandbox/acme/e2e` is a **mutative workflow start** and is explicitly out of scope for Playwright read-only capture.
- **Important:** this is a no-effect sandbox **pre-resolution** receipt, **not** a GLPI ticket, a real human approval, a completed production remediation, or a Core run join.

**Remaining P0-1 gap:** provide a secure, server-side, tenant-authorized read-only adapter from this Worker receipt to the Portal scene, with independent negative tests for 401/404/503 and disabled capability. The existing `/demo-studio/run/{rid}` uses a Core run ID, whereas the Worker readback uses a separate `attempt_id`. **Do not join these IDs by string guesswork.** Establish a source-backed mapping or show the Worker receipt as a separately scoped artifact; never claim a Core→Worker join without evidence.

## P0-2 identity discovery: Core already owns canonical binding

Source inspection of `app/core/acme_sandbox.py` establishes an **existing canonical mapping**, rather than a missing string-derived join:

- `aiops.acme_sandbox_attempts` persists `tenant_id, attempt_id, incident_id, run_id, ticket_id, proposal_id` together; `read(c, attempt)` re-queries the canonical Incident/Run and source/evidence records and refuses inconsistent state.
- `GET /api/sandbox/acme/e2e/{attempt_id}` (Core, lines 416–428) is a **service-bearer-protected** readback, disabled unless the sandbox capability is enabled. It exposes `aiops.core-acme-sandbox-readback.v1` with the canonical IDs. This is the proper mapping authority, not a string convention.
- In the **RESOLVED** state, Core verifies an append-only terminal ticket ledger, the persisted Worker receipt digest, matching canonical ticket/run/incident/proposal/approval, seven SOURCE event IDs, and a resolution event. In **PREPARED** state the Worker receipt is not yet verified. These states must not be conflated.
- `app/core/acme_sandbox.py` also exposes `POST /api/sandbox/acme/e2e` and `POST /api/sandbox/acme/resolve`; **do not call** either during read-only qualification.
- Added `scripts/acme_core_worker_binding.py` and five offline negative tests to compare **Core and Worker readback declarations** (IDs, tenant, source events, request digest, receipt digest, resolved flags, no live effects). This is **not** a cryptographic verification of the Worker receipt and not proof of authenticated runtime calls. The existing Core and Worker authorities must independently validate their own data.

**Remaining implementation gap:** an ACL-qualified, server-side Portal adapter must read the canonical Core and Worker endpoints using a fixed service allowlist and a secret that never reaches the browser. Before implementing, prove a user-facing tenant authorization mechanism exists; if absent, retain 503/NO_GO rather than expose the internal readbacks.

## P0-3 viewer ACL inspection — hard stop

Inspected actual `app/portal/main.py` on PR #808 and `app/portal/acme_run_detail.py` on `main`:

- `main.py` has public-looking GET pages and an **internal shared bearer** for POST demo launch, but no source-backed authenticated **viewer actor → tenant → exact Core run/attempt** authorization boundary for the proposed ACME Worker evidence view. The presence of GET pages is not ACL evidence.
- The existing `main` branch `acme_run_detail.py` explicitly refuses to reveal even Run IDs/status until an independent server-side exact-run tenant ACL is available. Its shared read bearer and short-lived session mechanics do **not** confer viewer tenant authorization; it returns `TENANT_ACL_NOT_QUALIFIED` and HTTP 503.
- Added `scripts/acme_portal_acl_preflight.py` with four offline tests. This is a **source-only readiness report**, deliberately returns `NO_GO` even when a caller asserts `tenant_authority_attested=True`. It must not be used as a security enforcement component.
- **Acceptance required before implementation:** an independently authenticated viewer identity, server-derived tenant membership, explicit per-run/attempt authorization decision, 401 anonymous, 403 cross-tenant, 404/constant-denial unknown run, no internal bearer in HTML/JS, no Core/Worker fetch before authorization, and negative tests. An operator's shared internal token is never a viewer ACL.

**Decision:** no new public Portal Worker evidence route until the above authorization contract is implemented and tested. The offline addon can show `NOT_QUALIFIED` safely, but it cannot declare a seven-scene browser demo PASS.

## P0 identity anti-forgery hardening

The offline Core↔Worker binding check now recomputes Core's actual deterministic `ident(prefix, attempt)` formula (`SHA256("ACME-TEST:" + attempt)`, uppercase truncated digest) for `incident_id`, `run_id`, `ticket_id`, `proposal_id` and all seven `SYN-EVT-` SOURCE IDs (suffix `":" + sequence`, length 20). It rejects even **coordinated forgery** where Core and Worker declarations agree on the same incorrect identifiers. Added two negative tests. This remains an offline consistency check: authenticated Core PG16 readback, Worker receipt digest and viewer ACL must still be qualified independently.

## P0-3 viewer policy contract (offline, not integrated)

Added `scripts/acme_viewer_access_policy.py` and seven tests. The pure function models the intended authorization decision over **server-derived** actor identity, tenant membership, exact run allowlist, requested tenant, attempt and run. It defaults to 503 `TENANT_ACL_NOT_QUALIFIED` unless both authority qualifications are explicitly supplied; rejects anonymous 401, cross-tenant 403, foreign run 404, and malformed claim containers 503.

**Crucial limitation:** the function's two `*_authority_qualified` booleans and membership sets are ordinary caller arguments, not cryptographic proof. The 200 `POLICY_CONDITIONS_SATISFIED_ONLY` test is a **hypothetical pure-policy case**, not a runtime authorization success. This module is not imported by Portal and must **never** be wired to an HTTP route using browser-provided claims or arbitrary caller-supplied booleans.

To qualify the actual Portal adapter: introduce a trusted server-side identity/session verifier, tenant membership and exact-run permission provider, check the canonical Core attempt→run binding, reject before any upstream Core/Worker fetch, and integration-test 401/403/404/503 with the real provider boundary. Until then the Portal scene stays unavailable and runtime ACL remains NO_GO.

## P0 viewer ACL + read ordering hardening

- The pure viewer policy now verifies the exact deterministic `ACME-TEST:attempt_id` → `RUN-SIM-` binding, and requires `is True` (not truthy integers/strings) for both hypothetical authority flags. Two extra negative tests cover mismatched attempts and truthy fake flags.
- New `scripts/acme_evidence_read_seam.py` is a **non-HTTP, non-integrated orchestration seam**: rejected decisions perform **zero** Core/Worker reads; mismatched Core attempt prevents Worker reads; source exceptions are redacted; even successful injected offline documents yield `OFFLINE_CONSISTENT_ONLY` rather than runtime PASS. Four tests cover deny-before-I/O and no leakage.
- **Not an ACL implementation:** an untrusted caller could fabricate a positive `ViewerDecision`. Never expose this seam as a route or treat its positive decision as identity proof. Only a future trusted server-side verifier may create and enforce authenticated viewer decisions. No browser credentials or tenant data are exposed by this module.

## P0 Worker receipt integrity gap closed in offline validator

The original `scripts/acme_worker_receipt_contract.py` only checked selected structural fields, so a receipt with altered fields and stale `receipt_sha256` could pass that offline structural gate. The validator now independently recomputes the **existing Worker** canonical JSON SHA256 over all fields excluding `receipt_sha256`, validates both 64-hex source digests, recomputes all seven canonical SOURCE IDs, and requires `core_014_015_written=False` and `glpi_write=False`. Tests include tampered receipt and forged SOURCE IDs, and the cross-module fixtures now generate coherent canonical digests. This is an **integrity check**, not a signature, Temporal history attestation, Core authority, or viewer ACL.

Additional Worker receipt hardening: independently derive canonical incident/run/ticket/proposal IDs from the attempt and validate the simulated approval ID. A maliciously altered receipt with a **recomputed valid SHA256** must still fail the canonical identity check. Two regression tests added. This is not authentication or signature verification.

The offline Core↔Worker binding now additionally requires resolved Core evidence and nonce invariants: nonce consumed/not revoked, analyst+critic+source hash qualified, exactly 7 source events and 2 evidence records (strict integer checks), synthetic analysis/issuer, and valid terminal-ticket/request digests. Two negative tests cover nonce consumption and malformed counts/digests. This checks declared Core fields; PG16 readback and runtime authority are still independently required.

The non-HTTP evidence seam now validates the attempt ID before **any** Core read and the canonical Core tenant/run mapping before **any** Worker read. Two negative tests assert zero upstream I/O for malformed attempt and zero Worker I/O for a forged Core run. This reduces exposure if a positive pure-policy decision is supplied incorrectly, but does not establish a trustworthy ACL provider.

Portal ACL preflight additionally inventories direct imports of the offline-only `scripts.acme_evidence_read_seam` and `scripts.acme_viewer_access_policy` modules into `app/portal/main.py` as unsafe integration signals. This is a source-only guard, not an exhaustive transitive import analysis or a runtime ACL. Never expose these modules via a browser endpoint until a trusted server-side viewer identity and exact-run ACL adapter is implemented.

## Provider-neutral OIDC integration preparation (offline only)

`scripts/acme_oidc_integration_preflight.py` checks the **shape** of a proposed OIDC issuer/client/audience and server-side tenant/run ACL source identifiers. It does **not** perform OIDC discovery, verify JWKS/signatures, exchange credentials, authenticate a user, read Core, or grant access. Every output remains `NO_GO` and `browser_evidence_enabled=false`, even with a plausible HTTPS issuer. No secrets or actual identity provider are embedded. Negative tests are in `tests/test_acme_oidc_integration_preflight.py` and the ACME offline CI.

**Before any Portal integration:** choose and approve a real OIDC provider and server-side identity session verification (issuer, audience, signature, expiry, nonce/state, key rotation), independently authoritative actor→tenant membership and exact tenant+attempt+run ACL, then verify against Core canonical readback **after authorization**. Test anonymous 401, cross-tenant 403, missing/unpermitted run 404, no Core/Worker read before denial, and no browser service tokens. Only a separately approved isolated sandbox runtime test may qualify this boundary. Configuration strings and policy booleans are never proof.

## Architecture decision — identity and authorization

[ADR: Keycloak sandbox OIDC + Portal BFF + server-owned tenant/exact-run ACL](ADR-ACME-SANDBOX-IDENTITY-KEYCLOAK-BFF.md) is the selected **target**. It does not imply that an IdP or grant store is deployed. Keep P0-3 **NO_GO** until actual runtime negative tests prove deny-before-read; the offline policy and evidence seam must not be exposed as HTTP authority.

## Opt-in read-only runtime recipe (source-only)

`scripts/acme_readonly_runtime_recipe.py` is a **manual** GET-only check of the existing sandbox Core and Worker readbacks on two distinct loopback endpoints. Its CLI requires **both** `ACME_READONLY_SANDBOX_APPROVED=YES` and `ACME_SANDBOX_ISOLATED=YES`; missing either returns `SANDBOX_EXECUTION_NOT_APPROVED` before network access. These flags are operator acknowledgements, **not** technical proof of isolation, authentication or authorization. Execution still requires separately approved isolated infrastructure and server-held service credentials supplied via environment (never commit or print them). The offline CI tests use injected fake responses and do **not** make HTTP requests. A successful runtime readback only establishes `RUNTIME_READBACK_CONSISTENT_ONLY`; browser, viewer ACL, Core→Twin join, deployed provenance, and real autonomy remain unverified. Never run this recipe on LIVE Debian.

## Ephemeral HTTP integration test lane (CI, not AIOPS2 runtime)

`tests/test_acme_readonly_http_integration.py` starts two **in-process Python HTTP servers**, each bound to `127.0.0.1` on an ephemeral port and stopped after each test. Unlike callback-mocked tests, it exercises the actual `urllib` GET transport of the read-only recipe, including environment proxy bypass, redirect rejection, JSON content type, 256 KiB response limit, HTTP error rejection, strict Core-before-Worker ordering, tenant isolation, and Worker no-effect receipt rejection. The test data are synthetic and service tokens are test-only literals. **No deployed Core/Worker, Temporal, GLPI, database, Docker, SSH or browser is contacted.** CI PASS here establishes transport behavior against fake local endpoints, **not** sandbox runtime provenance, identity/ACL or autonomous remediation. Manual runtime recipe remains separately opt-in and blocked without an approved isolated sandbox.

## Autonomous loop stage-level qualification

`assess_autonomous_loop` now separates **seven structurally declared synthetic stages** (observe, correlate, diagnose, policy, simulated no-effect Worker action, synthetic Core verification, declared Worker audit) from two **NOT_VERIFIED** capabilities: remediation effect and learning. A consistent Core/Worker pair is still `OFFLINE_CONSISTENT_ONLY`; the Worker receipt is explicitly `SIMULATED_NO_EFFECT` and `PRE_RESOLUTION`, while Core's later synthetic resolution does not prove external service recovery. Temporal history is declared in supplied bytes, not independently attested. No stage is runtime-attested by this assessment. The distinction is intended for the Workbench status model, not an authorization to display runtime GO.
