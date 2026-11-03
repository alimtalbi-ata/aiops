# Worker-only synthetic REJECT → VERIFY vertical qualification (2026-11-01)

**Owner:** Policy/HITL/Temporal Worker. **Scope:** disposable GitHub Actions PG16 + Core ASGI + Temporal SDK. **Target:** sole Draft #234 integration branch. **Release:** NO_GO. **No LIVE, GLPI write, executor, Portal change, Core API/schema change or Debian host operation.**

## Executable contract

`app/worker/hitl_reject_vertical_projection.py` is a pure read-only, fail-closed correlation function, **not** an additional ledger, runtime Worker poller, Core authority, Portal endpoint or execution permission. Its inputs are the existing Core Run/events/gates readback, a Core-owned PG16 fixture readback, and the existing deterministic Policy evaluator. It checks tenant/Incident/Run/evidence/Analysis/Critic/proposal/revision/approval/outbox/terminal-014 bindings and the exact stage sequence. It refuses missing/duplicate/foreign IDs, APPROVE/effect events, unsafe policy flags, LIVE mode, absent gate and a false verification claim.

The test uses the existing PG16 migration chain 001/004/009–014 and Core-owned `/dead` (eight REJECT claims, lease-clock acceleration only), validates one immutable 014 terminal receipt, then seeds **test-only mutable PG16** Run/event rows for synthetic Analyst, Critic, Policy SIMULATE, HITL REJECT, REMEDIATE SUPPRESSED and VERIFY UNRESOLVED; Core's existing HTTP **gate** and **GET Run** handlers are exercised, including a repeated gate upsert. Core Run remains BLOCKED and Incident remains OPEN. **Actionable Core gap:** the existing Core `/events` and `/command` writer references `aiops.run_events.event_key`, which is absent from the installed 001/004/009–014 migration chain. Core event/command writes are therefore **NOT_TESTED**, not silently repaired by Worker. Core owner must supply the full migration contract and qualify this writer before a real vertical Run transition is claimed. The verification is **UNVERIFIED** and reopening is **RECOMMENDED_NOT_EXECUTED**; neither an independent live verifier nor an actual incident reopen has occurred. Policy SIMULATE is advisory and is vetoed by REJECT, so no simulator/effect is called.

The test starts a Temporal SDK server with persistent SQLite, restarts that server, and runs **two distinct disposable SDK Worker objects in one OS process** on the same task queue. Both produce the same read-only projection; Temporal signal count remains zero. This is not a two-OS-process test (that separate regression is covered by #316) or universal exactly-once proof. The Core Run API is exercised in-process via ASGI, **not** independent Core TCP; prior canonical /dead tests qualify TCP. The legacy Core `GET /api/runs/{id}` is not a tenant-authorized Portal API; the receipt is a correlated-ID contract for future Core/Portal ownership review, **not** a deployed Portal view.

## New bounded Core writer rollback gate (Worker-owned test only)

The second disposable PG16 test, \`test_16_core_event_command_writer_rollback_gate\`,
probes the actual Core ASGI \`/api/runs/{id}/events\` and \`/command\`
writers against the installed migration chain. It is a **negative contract**
when \`aiops.run_events.event_key\` is missing: both requests currently return
HTTP 500, and the test asserts the Run remains CREATED at its original
version, zero events, zero command receipts, zero effect receipts and zero
APPROVE. The 500 is a **Core-owned release blocker**, not an acceptable
production API response. An invalid internal bearer is separately rejected
with HTTP 401. The test never writes SQL DEAD or modifies immutable
012/013/014. The existing first test still covers Core-owned /dead, one
immutable 014 receipt, synthetic REJECT veto, and Temporal persisted restart.

The test detects the column in PostgreSQL rather than hard-coding a
perpetual 500 expectation. **When Core installs event_key**, it requires
successful event and command writes with idempotent replay, two persisted
events, one command receipt and no effects; a partial Core migration or
writer defect must fail the workflow. The Core owner must supply and qualify
the complete migration/API chain; Worker does not add a schema, fix Core
handlers or represent test-fixture SQL as Core-written events. The conditional
receipt records which branch actually ran, so a green negative case is never
reported as a positive vertical.

The second redacted machine receipt is
\`worker-core-writer-rollback-gate.json\` with schema
\`aiops.worker-core-writer-rollback-gate.v1\`, source HEAD, actual HTTP
status codes, PostgreSQL column presence, Run version delta, persisted
row counts, no-effect assertions and canonical SHA256. The CI artifact
contains **two JSON receipts and SHA manifests only**; no PG16 dump or
credential. Exact-head workflow requires **2/2 tests, zero SKIP**, plus the
existing **DR 5/5**. These are disposable CI observations, not Debian
runtime, native GLPI/OIDC human authority or Portal tenant authorization.

## P1 conditional Core-written vertical path (2026-11-01)

The first PG16/Temporal regression now probes the installed schema for
`aiops.run_events.event_key` before choosing the source of six synthetic
Analyst/Critic/Policy/HITL/REMEDIATE/VERIFY Run events. **If Core installs
the full migration**, the test requires Core HTTP `START`, six distinct
`/events` writes with exact event keys and idempotent replays, then Core
HTTP `BLOCK` with idempotent replay. The Core GET readback must contain
eight events (two state transitions plus six stage events), and the existing
REJECT veto, independent UNVERIFIED verification, recommended-not-executed
reopen, one immutable 014 terminal receipt, two SDK Worker instances,
persisted Temporal restart and zero-effect assertions remain mandatory.
This is a test contract, **not a claim that the positive branch ran**.

**If the column is missing**, the original six mutable fixture rows remain
explicitly `CI_PG16_FIXTURE_ONLY`, while the separate test_16 probes the
real writers and requires HTTP 500 with transactional rollback. This is a
Core-owned P0 defect, not an acceptable writer success. The exact-head
receipt distinguishes `CORE_WRITTEN_PG16_OBSERVED` from
`NOT_TESTED_MISSING_EVENT_KEY_MIGRATION`; the CI validator cross-checks
the first receipt against test_16's independently recorded column presence.
Any partial Core migration or broken HTTP idempotence fails rather than
silently falling back to fixture SQL.

No Worker schema, Core handler, Portal or Quality edit; no SQL DEAD or
immutable 012/013/014 mutation. No real OIDC/GLPI human identity, no
LIVE executor, no GLPI write, no Debian runtime attestation, and no
universal exactly-once claim. PG16 DR 5/5 and zero SKIP are mandatory.
Rollback is a code-only revert of the focused Worker test/workflow/docs
delta, preserving all existing Core audits and host data.

## Qualification and evidence

Workflow: `.github/workflows/hitl-worker-vertical-reject-pg16.yml`. On exact source HEAD, run `PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_worker_hitl_vertical_reject_pg16.py' -v`, requiring 2/2 and zero SKIP; then existing `test_hitl_pg16_candidate_outbox.py` requiring DR 5/5 and zero SKIP, PG16 `pg_dump`/`pg_restore` 16.x. Check `AIOPS_EXPECTED_HEAD_SHA` against checkout and receipt. Upload **only** `worker-vertical-reject.json`, `worker-core-writer-rollback-gate.json` plus SHA256 manifests, never raw dump, credentials, bearer or HMAC material. No SQL DEAD mutation, no SQL update to immutable 012/013/014. The synthetic fixture inserts provenance/analysis/critique/approval/outbox rows as test-only setup.

Evidence classification: `OBSERVED_CI_DISPOSABLE` only after exact-head green CI; otherwise `NOT_TESTED`. Actor is `SYNTHETIC_UNVERIFIED`, identity `NOT_ATTESTED`; CI signed manifest is not real OIDC/GLPI revocation. Host 7777 is `REPORTED_VERIFIED` **locally by operator**, not attested by this CI; external access, SSO/GLPI and portal uniqueness remain unverified. Gateway close in prior tests is injected after commit and is not physical packet loss.

## Handoff, dependencies and rollback

Core remains sole Incident/Run, audit 012/013/014 and HITL /dead owner. Portal owner must independently qualify any tenant-authorized UI/read model; no direct exposure of legacy Core `GET /api/runs/{id}` is approved. No native human GLPI approval/REJECT is asserted. This Worker module must not be attached to LIVE runtime.

Rollback: close focused Draft or revert the three modified Worker-owned paths (test, dedicated workflow and this document); the existing projection module remains on the architect candidate. Original source-only #321 rollback, if independently required, concerns its four paths: `app/worker/hitl_reject_vertical_projection.py`, `tests/test_worker_hitl_vertical_reject_pg16.py`, `.github/workflows/hitl-worker-vertical-reject-pg16.yml`, and this qualification document. Do not revert or mutate Core 012/013/014 audit. No merge or main/stable push by Worker.
