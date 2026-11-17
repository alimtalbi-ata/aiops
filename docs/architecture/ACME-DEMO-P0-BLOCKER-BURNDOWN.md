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
