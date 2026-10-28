# 2026-10-28 21:06 Europe/Paris — P0 NOC/Copilot — Ledger Core HTTP qualification

## Baseline and ownership
- Verified `main` HEAD `b6cac31f6713d60f517bc6c4648002297fb87de6` before editing, and draft PR #145 head `5b4b56080b28f7fda977c7f2a95a54d2b198ea8f`. This micro-lot is stacked on #145, which itself targets the separate Demo Studio V2 delivery lineage, **not main**.
- Reviewed open PRs #143/#145/#144/#142/#140/#139/#133, recent journals and project continuity. Avoided touching their files except the existing quality workflow of #145.
- Dedicated branch: `test/p0-ledger-real-core-http-20261028-2106`, PR draft to #145; no changes to Debian.

## Single measurable delivery
- `tests/test_demo_ledger_real_http.py`: four read-only HTTP integration tests against **real ephemeral Core, Portal and PostgreSQL 16**, seeded with CI-only DEMO/LIVE Runs, an actual synthetic Evidence row, an Analysis and Critique. Uses no mocks and does not call NGX/Ollama.
- `.github/workflows/quality.yml`: one extra step in **existing** `database-migrations` job, after all migration tests. Starts Core on 1810 and two real Portal processes on 1877/1878; the second has deliberately mismatched CI-only internal credential to exercise actual upstream 401 -> Portal 503 UNKNOWN. All services bound to loopback, terminated after tests.
- Contract unchanged: GET `/api/demo-studio/runs/{rid}/ai-ledger` from #145; 401 missing/invalid viewer; 200 for bounded DEMO ledger; 503 UNKNOWN for LIVE, absent source or Core upstream 401. No internal token or private prompt in browser projection. Evidence IDs are read from the real ephemeral DB, not from a fabricated ACME run.
- Files: `tests/test_demo_ledger_real_http.py`, `.github/workflows/quality.yml`, this journal. Source adapter remains owned by #145.

## Qualification / risks
- CI URL and exact job/step outcomes: **PENDING** until GitHub Actions runs on the PR SHA. Never infer PASS from a queued run. No local integration tests executed.
- Pre-existing #145 baseline: quality Policy safety 11/15 failures and runtime-e2e BLOCKED (see journal `2026-10-28T1914-p0-demo-studio-ai-ledger-read-gate.md`); these are **not** fixed by this test-only micro-lot. Do not merge until the full required checks are green.
- NOT_TESTED: authenticated tenant A/B isolation, real Checkmk/Thruk, observed Grafana SAN/Payments metrics, Twin Payments impact, Ollama 4B, real operator browser, runtime Debian. A 200 DEMO response is **not** proof of a full SAN→Payments E2E.
- Next micro-lot: once this actual Core HTTP contract is qualified, bind Evidence/Analysis/Critique/Policy IDs to a tenant-scoped actor in Core, and only then expose sourced SAN/Payments observations. Coordinate the contract with #139/#133; do not confuse synthetic SIM IDs with real Core IDs.
- No production credentials, LIVE actions, server access, deployment or merge.

## Verified GitHub Actions qualification (code SHA `24394c35de0300b427fadb8825c7a8f1498b2277`)
- [Existing quality.yml PR run #40760652147](https://github.com/alimtalbi-ata/aiops/actions/runs/40760652147): job `database-migrations` **completed/success**. New step `Qualify real Core/PostgreSQL and Portal AI ledger read-only HTTP (CI-only)` **completed/success**. Raw job log #123071343321 confirms **Ran 4 tests in 0.107s, OK**, after real Core and two Portal processes reached their HTTP health endpoints and actual PostgreSQL 16 migrations completed.
- Tests actually executed: (1) Core missing/wrong internal token -> 401, authenticated ledger -> 200; (2) Portal missing/wrong viewer -> 401, DEMO -> bounded 200 without private payload; (3) LIVE and missing Run -> 503 UNKNOWN; (4) wrong Core credential from a real second Portal -> upstream 401 -> 503 UNKNOWN without token leak.
- In the same run, `quality-build-package` **failure** at pre-existing `Policy safety unit tests`; the existing Demo ledger unit step completed/success. `mariadb-dr-rehearsal` and `migration-runner-upgrade` completed/success; `runtime-e2e` still running when this journal amendment was authored. **Overall quality NOT_PASS**; no merge. Any CI triggered by this documentation-only commit must be separately checked on its own SHA.
- This proves a **CI ephemeral HTTP security contract**, not a tenant A/B ACL, SAN/Payments observation, actual runtime E2E or deployed Debian behavior.
