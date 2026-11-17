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
