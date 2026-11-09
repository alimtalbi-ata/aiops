# Night cycle #462 — fence foreign receipts on retry

UTC: 2026-11-09T22:27:40.046238+00:00. Dedicated branch `agent/integration/462-night-20261109`. Reviewed remote parent `b9df47526bc4d63882bc18dfdc24fe532c0cd2b3`. DRAFT PR #478 retained against `agent/integration/462-isolated-candidate`. Delivery SHA is recorded in the GitHub publication comment and runtime/retry-cycle-published.json. Deadline 2026-11-10 11:00 Europe/Paris (10:00 UTC), 540-second cycle.

Read AGENTS.md on PR #456 branch and its orchestration/reuse inventory; local continuity, architecture/boundaries, catalogue, stack inventory and change protocol before code. Reviewed issues Core #458, Worker #459, QA #68 (no comments), open PR DAG, recent #477/#479 comments, and diffs #475/#477/#479. Core #475 0777c0805f332581141c62938e0241eab8729ac2; #476 a3a4a210d54594c347ee9c7c6a3f5fe22b0febd8; #479 8fc931e2426f8d098333883f4d879fcce0b2cde4; Worker #477 d9666f7b62c1560569d8c860747b339126141ce2. No owner branch changed. User authorization permits reproduced corrections on the integration candidate without waiting for inactive owners.

Initial dirty app/core/main.py, quality.yml, latest-cycle.md, untracked cycle-2218.md and winner test examined: retained prior published b9df475 work, not reset. Local HEAD is 9dfe31888ca0210ea922ea81d24645e783671823, not remote delivery HEAD. `git fetch origin` failed once because .git/FETCH_HEAD is read-only. Used existing normal GitHub Git API publication without force; explicitly checked parent and original remote bytes before adapting Core; checked test base against HEAD. No metadata permission workaround, other checkout, merge/rebase/cherry-pick, supervisor or mission change. API verifies all delivery bytes after commit.

## Reproduction and correction

The candidate's retry path accepted a nonempty durable workflow ID without matching the canonical Run ID, although its post-dispatch guard already required this match. Added regression adapted from #475: 3 synthetic modes x 5 states x 3 foreign/invalid receipts. Before source correction: 8 tests run, 45 failing subtests (HTTPException not raised). One relevant reproduction followed by one corrected run; no repeated blocked attempt.

Selectively reused #475 guard: durable workflow ID must be a string equal to rid; otherwise HTTP 409 before Worker dispatch. Tests additionally assert only SELECTs occur and Worker is never called. Positive retry fixture changed from wf-existing to canonical RUN-1, matching the actual Worker contract (app/worker/main.py uses args['run_id'] as Temporal workflow ID). Positive assertions and LIVE/mode/identity/winner checks preserved. No whole-branch import. No #479 HTTP lock-scope change: real two-client PG/Temporal concurrency and timeout reconciliation remain unqualified. Existing workflow already selects test_candidate_core*.py; workflow not modified this cycle.

Actually executed: `python3 -m unittest discover -s tests -p 'test_candidate_core*.py' -v` 10/10 PASS; `python3 -m unittest discover -s tests -p 'test_fs147_*.py' -v` 9/9 PASS; `bash -n tests/postgres-dr-rehearsal.sh` PASS; `git diff --check` PASS. No heavy local/container/database/remote tests. Source extraction/mock DB tests do not establish real PG transaction or Temporal behavior.

## Qualification

Parent b9df475 exact-SHA Actions all SUCCESS:
- https://github.com/alimtalbi-ata/aiops/actions/runs/42710576843
- https://github.com/alimtalbi-ata/aiops/actions/runs/42710576839
- https://github.com/alimtalbi-ata/aiops/actions/runs/42710576840
- https://github.com/alimtalbi-ata/aiops/actions/runs/42710576842 (quality, MariaDB DR, runtime-e2e, migrations, upgrade and release-kit all success).
These are parent evidence only. New delivery CI UNKNOWN until exact-SHA runs observed. CI runtime-e2e is synthetic, not Debian real FS147/FS1250 E2E.

Existing run 42703074786 evidence retained; read stored complete log client paths /usr/lib/postgresql/16/bin and pg_dump/pg_restore/psql 16.15, server 16.15/160015. PG fixes 8011ddd6ff0130e52500a0832db187759a0e1025 + e7c76514b8e98cb35a9594226e7106fde98a42aa not redone. Restoration script unchanged: identity/loopback/version guards, target refusal, corruption negative control, transaction/exit-on-error, checksums and scoped cleanup preserved.

Reporter read this cycle: collected 2026-11-09T22:25:01.264252+00:00, expires 22:28:01.264252Z at 180-second threshold; freshness must be recalculated when consumed. Core running healthy sha256:87427734395dd212f550f03498fb77954c572675b41d8e5ba5dd4f295ecbef4d; Portal running no-healthcheck sha256:e0559a90b34adcfe59ad3545e44195a10274398c17a308b6d8df316d4552eed1; Worker healthy aiops2-worker:fs-demo-candidate-20261105. Not a verified mapping to candidate source. latest-usecase.json again HTTP 404: absent / NOT_VERIFIED. Existing source qualifier and read-only release audit examined: neither establishes source/image provenance from this limited reporter receipt, verified clean deployment checkout, unique deployment lock, backup or rollback receipts. Authorization is valid; operational prerequisites remain missing. No remote command or deployment attempted.

CODE: scoped retry fix PASS in 19 focused tests. CI: delivery UNKNOWN pending exact SHA. DEBIAN: candidate NOT_VERIFIED, source/image provenance UNKNOWN. E2E: NOT_VERIFIED; FS1250 HOLD. Merges=0; deployments=0; rollback executed=none; observed active image as above, not this delivery. Risk: historical foreign receipts now return 409 and require investigation; no data rewritten. Concurrent first dispatch and timeout-after-start remain unresolved. Rollback: abandon dedicated branch/PR or revert this limited guard, no production rollback required.

Next action: inspect exact delivery CI, then qualify isolated two-client PG/Temporal and timeout reconciliation using existing GitHub Actions; obtain verified image/source, clean checkout, unique delivery lock, backup and rollback receipts before any merge/deploy. No ready promotion.
