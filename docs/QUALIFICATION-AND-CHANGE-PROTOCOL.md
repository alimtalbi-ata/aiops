# AIOps 2.0 — Change and Qualification Protocol

**Author:** Abdelhalim Talbi

## Before a change

- Identify target runtime/version, source branch/commit and production impact.
- Inspect current service state, repository status, relevant contracts and active dependencies.
- Create a timestamped backup of files/configuration to be changed; do not bundle secrets into Git or chat.
- Define preconditions, expected result, stop conditions and rollback procedure.
- Confirm DEMO/REPLAY/LIVE mode and credentials scope.

## Test evidence labels

1. **Source inspection:** code read; no execution implied.
2. **Static:** lint, type checks, static audit or contract-shape checks.
3. **Unit/contract:** isolated deterministic tests.
4. **Integration:** cooperating services in an isolated environment.
5. **Synthetic E2E:** full flow using explicitly synthetic events and data.
6. **Live verification:** actual deployed service/API verified; report timestamp, endpoint, status and redacted result.
7. **Production qualification:** approved test window, safety checks, observed results, audit trail and rollback readiness.

Always list failed, skipped and not-run tests. Expected output is not evidence of actual execution.

## Change and promotion gates

- No direct main changes: branch → tests → commit → pull request.
- No automatic merge unless separately authorized.
- No production restart/cutover as a side effect of documentation or source changes.
- No live mutation from synthetic/demo flows.
- High-risk actions require policy authorization and human approval where policy requires it.
- Check fencing/ownership, current preconditions, idempotency, effect evidence, verification and reconciliation.
- Test partial failure after external effect, timeout, duplicate delivery, worker restart, stale evidence and rollback failure.
- Keep all logs and reports secret-safe.

## Release/handover checklist

- [ ] Component and API contracts updated.
- [ ] Architecture and decision log updated.
- [ ] Reuse matrix and catalog updated.
- [ ] Automated tests and exact outcomes recorded.
- [ ] Version, changelog, manifest and hashes updated where applicable.
- [ ] Install/upgrade/rollback steps tested or explicitly marked untested.
- [ ] Cumulative ZIP includes required source/scripts/docs/evidence, without secrets or runtime databases.
- [ ] Commit and PR verified on GitHub.
- [ ] Next steps, unresolved risks and current runtime snapshot recorded in `docs/PROJECT-CONTINUITY.md`.

## ACME-TEST V28 terminal promotion gates (ADR-0015)

- [ ] Verify exact #358 HEAD and all required CI, including PG16 001/004/009–019 and 19/19 named tests (including registered Temporal/PG16 same-Run; source CI only) with native backup/restore, zero SKIP.
- [ ] Verify Worker canonical `receipt_sha256` and ordered seven SOURCE IDs, Twin signed nonce/TTL, Policy SIMULATE, Core append-only terminal ticket receipt and 503 on missing proof.
- [ ] Verify #356 real Twin issuance includes the signed idempotency key and Simulator forwards internal bearer only to allowlisted service host:port; check integrated exact-head negative tests.
- [ ] Verify `test_17_registered_temporal_worker_same_pg16_run` on a single PG16 Incident/Run and registered Temporal activity, Worker canonical receipt, terminal SIM-GLPI digest and independent PG16 readback; explicitly mark Twin/Policy fixtures as CI-only. Do not promote on an incomplete/failed job.
- [ ] Review Compose five-service-only scope, host PG16 backup integrity, disk headroom, immutable source pin, image/port health and safe rollback before enabling release manifest.
- [ ] On Debian, require a fresh poller upgrade receipt with five changed image/container IDs and portal 7777 strict PASS; separately require correlated ACME incident/ticket/approval/Worker/Run terminal `RESOLVED` evidence and two independent read rounds.
- [ ] Do not treat 9/9 anonymous GET, isolated CI or a mock as host E2E; preserve NO_GO if reporter/poller timestamps are stale or missing.

- [ ] RG-ACME-22/23: real PG16 migration 019 seeds only nine ACME-TEST synthetic SAN nodes/eight edges; Twin GET rejects mixed provenance, does not fabricate payment impact. Host must attest sourced Twin capability and subsequent incident IDs; no claim of live Dell/Pure observations.
