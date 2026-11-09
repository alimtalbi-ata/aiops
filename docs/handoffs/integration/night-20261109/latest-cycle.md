# Night coordination #462 — initial review / launch attempt

UTC: 2026-11-09T21:53Z. Role: Integration. Branch: agent/integration/462-night-20261109.
Base SHA: 3218228ab4b0d24faa117b49d08272c8e025750a (remote checked before work); original requested reference e0fc66c3bc8f56cace0074de2f0a07d5bb551303. Delivery SHA is the commit containing this handoff, resolved by `git rev-parse HEAD`; exact published SHA is recorded in PR / issue comment to avoid a self-referential hash.

## Actually verified

- Fresh independent clone `/tmp/aiops-night-20261109/checkout`, no edits to existing checkouts. Original checkout Git metadata read-only; fetch there failed once, then independent clone succeeded. All remote heads fetched at clone time; historical branch/commit search found existing PostgreSQL fixes and no reusable nightly supervisor at the searched paths.
- Existing fixes 8011ddd6ff0130e52500a0832db187759a0e1025 and e7c76514b8e98cb35a9594226e7106fde98a42aa solve the known PG failure. Inspected diff and full DR shell script: loopback and DB identity fences, existing-target rejection, corrupted-archive negative control, single-transaction restore with exit-on-error, table counts/row hashes and scoped cleanup retained. No SQL filtering.
- [CI 42703074786](https://github.com/alimtalbi-ata/aiops/actions/runs/42703074786) success at exact base SHA 3218228ab4b0d24faa117b49d08272c8e025750a. Downloaded logs independently show pg_dump/pg_restore/psql 16.15 from `/usr/lib/postgresql/16/bin`, server 16.15 / 160015. No PostgreSQL client installed or live DB contacted locally.
- Core [PR #476](https://github.com/alimtalbi-ata/aiops/pull/476) head a3a4a210d54594c347ee9c7c6a3f5fe22b0febd8: inspected conflict-winner fence and tests, stacked on #475. Three GitHub check-runs success: [42700054700](https://github.com/alimtalbi-ata/aiops/actions/runs/42700054700). This is not proof the newly added tests are selected by those jobs. Requires candidate-specific integration review; no blind import.
- Worker [PR #477](https://github.com/alimtalbi-ata/aiops/pull/477) head d9666f7b62c1560569d8c860747b339126141ce2: inspected explicit contradictory Critic metadata denial and tests, stacked on #473. Three check-runs success: [42701600099](https://github.com/alimtalbi-ata/aiops/actions/runs/42701600099). Generic check success does not independently establish feature-test coverage. No overwrite of Worker ownership.
- QA #68 comments API returned no comments. No new QA qualification inferred. Agent 7 published handoff read from qualification-462/isolated-agent7-final-handoff.md; its reported bench results were not rerun here.
- Tools in this execution context: codex-cli 0.167.0, gh 2.46.0, Git 2.47.3, Python 3.13.5, GNU timeout 9.7. `codex exec --help` confirms workspace-write and configuration override syntax. This environment lacks rg in the independent checkout's shell PATH; grep/find used after that observation.

## Launch / local validation

Supervisor launch attempted once using `python3 docs/handoffs/integration/night-20261109/supervisor.py start`.
Result: exit 78, blocked_host_context, NoNewPrivs=1. PID 1 observed as codex. No nested Codex was launched; first automatic cycle NOT_STARTED. This initial review was performed by the current authorized session, not by an independent child. No active supervisor PID or unit.

Six offline supervisor tests PASS using unittest discovery: expired deadline denies launch; nested sandbox denies launch; unique flock denies second instance; STOP denies launch; group kill/reap; real /bin/sleep children used to verify timeout, spacing and deadline cleanup. Tests use shortened timings, never Codex children or production services. `python3 -m py_compile .../supervisor.py` PASS; `bash -n tests/postgres-dr-rehearsal.sh` PASS. Host Codex execution, authentication, sustained ten-minute cadence and actual overnight survival remain NOT_VERIFIED.

## State and boundaries

CODE: local supervisor safety tests PASS; no application code changed. CI: base exact SHA success; nightly delivery CI must be checked separately after publication. DEBIAN: UNKNOWN, no fresh runtime receipt collected. E2E: NOT_VERIFIED; FS1250 HOLD. No deployment, host commands, production write, merge, Docker, cron or Compose action.

Runtime: `/tmp/aiops-night-20261109/runtime/{state.json,supervisor.log}`. Fixed unique lock `/tmp/aiops2-night-20261109.lock`. Deadline 2026-11-10 07:00 Europe/Paris = 06:00 UTC. Cadence start-to-start 600 seconds; cycle budget 540 seconds; GNU timeout independently kills the child group even if supervisor dies, and is capped before the absolute deadline. SIGTERM/SIGINT/STOP cause group kill and reap. This is a local process supervisor, not a durable system service. OS suspension or forced host shutdown cannot be covered by a userspace deadline guarantee. `/tmp` storage may be purged by host policy.

Risks / rollback: don't change candidate source based on generic checks; active ownership and cross-service evidence still require review. Stop via the prepared `stop` command, retain runtime evidence, close draft PR/abandon branch. No runtime deployment rollback required. Never remove the lock file while processes may hold it. STOP intentionally persists across restarts; operator must explicitly remove it to restart before the deadline.
Next owner/action: host operator runs the single prepared start command; cycles then consume GitHub deliveries and maintain this handoff and the one DRAFT PR. No conversation control claimed.
