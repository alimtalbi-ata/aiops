# Worker-only synthetic REJECT → VERIFY vertical qualification (2026-11-01)

**Owner:** Policy/HITL/Temporal Worker. **Scope:** disposable GitHub Actions PG16 + Core ASGI + Temporal SDK. **Target:** sole Draft #234 integration branch. **Release:** NO_GO. **No LIVE, GLPI write, executor, Portal change, Core API/schema change or Debian host operation.**

## Executable contract

`app/worker/hitl_reject_vertical_projection.py` is a pure read-only, fail-closed correlation function, **not** an additional ledger, runtime Worker poller, Core authority, Portal endpoint or execution permission. Its inputs are the existing Core Run/events/gates readback, a Core-owned PG16 fixture readback, and the existing deterministic Policy evaluator. It checks tenant/Incident/Run/evidence/Analysis/Critic/proposal/revision/approval/outbox/terminal-014 bindings and the exact stage sequence. It refuses missing/duplicate/foreign IDs, APPROVE/effect events, unsafe policy flags, LIVE mode, absent gate and a false verification claim.

The test uses the existing PG16 migration chain 001/004/009–014 and Core-owned `/dead` (eight REJECT claims, lease-clock acceleration only), validates one immutable 014 terminal receipt, then uses **Core's existing HTTP handlers** to append synthetic Analyst, Critic, Policy SIMULATE, HITL REJECT, REMEDIATE SUPPRESSED, VERIFY UNRESOLVED and BLOCK events. Core Run remains BLOCKED and Incident remains OPEN. Event-key replay is checked with the current Core version. The verification is **UNVERIFIED** and reopening is **RECOMMENDED_NOT_EXECUTED**; neither an independent live verifier nor an actual incident reopen has occurred. Policy SIMULATE is advisory and is vetoed by REJECT, so no simulator/effect is called.

The test starts a Temporal SDK server with persistent SQLite, restarts that server, and runs **two distinct disposable SDK Worker objects in one OS process** on the same task queue. Both produce the same read-only projection; Temporal signal count remains zero. This is not a two-OS-process test (that separate regression is covered by #316) or universal exactly-once proof. The Core Run API is exercised in-process via ASGI, **not** independent Core TCP; prior canonical /dead tests qualify TCP. The legacy Core `GET /api/runs/{id}` is not a tenant-authorized Portal API; the receipt is a correlated-ID contract for future Core/Portal ownership review, **not** a deployed Portal view.

## Qualification and evidence

Workflow: `.github/workflows/hitl-worker-vertical-reject-pg16.yml`. On exact source HEAD, run `PYTHONPATH=app:tests python -m unittest discover -s tests -p 'test_worker_hitl_vertical_reject_pg16.py' -v`, requiring 1/1 and zero SKIP; then existing `test_hitl_pg16_candidate_outbox.py` requiring DR 5/5 and zero SKIP, PG16 `pg_dump`/`pg_restore` 16.x. Check `AIOPS_EXPECTED_HEAD_SHA` against checkout and receipt. Upload **only** `worker-vertical-reject.json` plus SHA256 manifests, never raw dump, credentials, bearer or HMAC material. No SQL DEAD mutation, no SQL update to immutable 012/013/014. The synthetic fixture inserts provenance/analysis/critique/approval/outbox rows as test-only setup.

Evidence classification: `OBSERVED_CI_DISPOSABLE` only after exact-head green CI; otherwise `NOT_TESTED`. Actor is `SYNTHETIC_UNVERIFIED`, identity `NOT_ATTESTED`; CI signed manifest is not real OIDC/GLPI revocation. Host 7777 is `REPORTED_VERIFIED` **locally by operator**, not attested by this CI; external access, SSO/GLPI and portal uniqueness remain unverified. Gateway close in prior tests is injected after commit and is not physical packet loss.

## Handoff, dependencies and rollback

Core remains sole Incident/Run, audit 012/013/014 and HITL /dead owner. Portal owner must independently qualify any tenant-authorized UI/read model; no direct exposure of legacy Core `GET /api/runs/{id}` is approved. No native human GLPI approval/REJECT is asserted. This Worker module must not be attached to LIVE runtime.

Rollback: close focused Draft or revert only these four Worker-owned paths: `app/worker/hitl_reject_vertical_projection.py`, `tests/test_worker_hitl_vertical_reject_pg16.py`, `.github/workflows/hitl-worker-vertical-reject-pg16.yml`, and this qualification document. Do not revert or mutate Core 012/013/014 audit. No merge or main/stable push by Worker.
