# Twin #460 — URI regression, BLOCKED

UTC: 2026-11-08T16:59:52.066372+00:00
Role: Twin; issue: https://github.com/alimtalbi-ata/aiops/issues/460
Branch: agent/twin/460-uri-regression
Tested code SHA: a1261153d5403f72d6c59ddeb4e55a25df50b7a9 (this handoff follows in a documentation commit).
Development parent: 0e232c9fdf4a519de36ba8035b506621854e0277; not an approved PR target.

## Scope and ownership
New paths: tests/test_fs147_twin_460_replay_isolation.py and this role-specific handoff.
Read-only reuse: #453 @ d99f552a2e48b9dcdd0bbda585e1d1339c670576. No files from #453 changed. Tests execute its exact Git blobs; the Git object must be present, otherwise setup fails explicitly. No network or service startup during tests.
All fetched origin branch trees checked for the test path: no match. Existing origin/agent/twin/460-scenarios @ 637b9bf47c25aaf20f702b5d6f36de3f5409bfc6 was compared; its five replay tests remain unchanged. Overlapping cases removed from this increment. New branch chosen explicitly after original push was rejected non-fast-forward; no overwrite/merge/force push.
Read #460/#462 public comments again: reuse/new file authorized; PR base still explicitly NOT APPROVED. No PR opened.

## Actual validation
Command: python3 -m unittest discover -s tests -p 'test_fs147_twin_460_*.py' -v
At tested code SHA: 2 methods executed, 1 PASS, 1 FAIL with 2 failed subtests; exit 1, 0.010 seconds. No skips or expected failures.
PASS: mutation of a returned qualification result does not poison a subsequent result.
FAIL: reject_foreign_provenance accepts metadata.uri = fixture://foreign/<foreign run_id> in both FS→SAN and SAN→FS directions. HTTP/HTTPS/URN are inspected by #453, fixture scheme is not. This is a synthetic contract coverage gap, not established production ingress behavior.
Original #453 suite previously executed: 25 PASS. Existing remote #460 replay coverage inspected; not represented as a new execution here.
Persistent duplicate suppression/concurrent event processing NOT_VERIFIED; no event store or consumer exercised.

## Gates, dependencies, next action
CODE: regression committed; suite FAIL intentionally exposes unmet isolation assertion. CI: UNKNOWN at exact SHA; no run URL claimed. DEBIAN: UNKNOWN, receipt timestamp/freshness UNKNOWN. E2E: NOT_VERIFIED; FS1250 HOLD.
Integration #462: approve target base and sequence, arbitrate this separate branch against existing #460; no inferred Portal or #453 target.
Owner #453: decide supported fixture URI contract and implement rejection in owned validator if required; this regression stays pinned to original SHA until a reviewed replacement is authorized. No production fix claimed.
Core #458 / Worker #459: supply real read-only incident→RUN→Evidence and idempotency/delivery contracts for independent integration qualification.
Runtime GitHub API read via gh returned Forbidden; public HTML and Git read work. Issue comment publication remains blocked until API access/authentication is verified in this runtime. No secret values requested or extracted.
Risks: pinned unmerged synthetic test prerequisite; red regression must be resolved before qualification. Rollback: revert isolated test and handoff commits. No runtime impact.
No Core/Worker/Portal/Integration source, cron/Compose, production, GLPI/PG, Debian, deployment, merge, Policy/Critic/HITL changes.
