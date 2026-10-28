# 2026-10-28 22:11 Europe/Paris — P0 NOC/Copilot — synthetic Evidence refs

## Source review / concurrency
- Verified `main` HEAD `ec05c89e92a6611922dccbe3690ce1476e3aec92` immediately before work; reviewed open PRs #140–#146, #149, #154, plus #133/#139 (canonical ACME), #142/#148/#157 (Twin), #144/#155 (Core/Policy), #153/#156 (stable deployment). Consulted `docs/PROJECT-CONTINUITY.md`, the latest #149/#154 journals and existing `quality.yml`.
- Stack dependency **#145 → #149 → #154 → this candidate**. Verified #154 HEAD `1b18e7d7a6d056b9abf484d1cc079a5f97cebdcb` before creating dedicated branch `test/p0-ledger-evidence-attestation-20261028-2211`. No merges, no overwriting another slot, no direct push to stable.
- Single measurable vertical: authenticated Core evidence-reference read model backed by real PostgreSQL event/ledger links, with negative HTTP tests.

## Changes and commits
- `55757e2a5abb5e714a0d4b043608757706814524`: add `app/core/demo_evidence_read.py`, fail-closed internal GET `/api/noc/runs/{rid}/evidence-refs`.
- `98ecb89b4bd0bde0ca6287d3271adca0d77f8c0e`: register route in `app/core/main.py`.
- `3396d1be8e73c6198792192cd1af64650336817d`: extend `tests/test_demo_ledger_real_http.py` with real HTTP/PostgreSQL 401, event-link success, LIVE/cross-Run/missing and tenant-metadata denial.
- `df6e2ac40cb68abb2a06d53da72f4327b4373589`: `docs/demo/ACME-CORE-LEDGER-EVIDENCE-REFS-V1.md`, contract and deployment coverage.
- This journal commit/PR SHA: see GitHub PR history. No workflow duplication.

## Security and contract
- Internal token required before DB I/O. DEMO/REPLAY/STORY only; synthetic evidence requires Run event, Analysis+Critique references, matching `provenance.run_id`, known timestamp and 64-hex digest. Raw payloads and tokens never returned. Generic 503 on missing/unqualified evidence; 401 on missing/invalid token.
- Additive contract `aiops.core-demo-evidence-refs.v1`; existing `aiops.demo-ledger-read.v1` Portal route unchanged and **not yet connected**. The result is **synthetic referential provenance**, not hash-of-original-bytes verification, external observation, tenant ACL or runtime attestation.
- CI existing `quality.yml` will execute HTTP tests on real ephemeral Core/PostgreSQL 16. **CI pending at journal creation**; no PASS claimed. Prior #154 `quality.yml` run #40764588592: ledger unit 11/11 and Core/Portal/Postgres 5/5 passed, but Policy 11/15 failed and runtime-e2e failed; global **NO-GO**. Do not merge while inherited failures persist.

## Deployment and release decision
- **BLOCKED / NOT_READY_FOR_STABLE**. The current Debian cron deployer only copies `demo_v2.py`, `test_demo_v2.py` and injects Portal `main.py`, so it cannot deploy new Core modules. Schedule 5/5 must review Core deployment coverage, rollback and read-only post-deployment smoke before any stable promotion. No `applied.sha` or Debian E2E evidence.
- **NOT_TESTED**: actual Debian, Core tenant A/B actor authorization, browser Portal consuming new endpoint, Grafana SAN CRC / Payments p95 observations, Twin Payments impact, Ollama 4B, Temporal/Policy full E2E, screenshots/video, rollback. No SSH, deploy, LIVE command or production secrets.
- Next micro-lot: integrate this resolver into the viewer-authorized Portal adapter (server-side only), reconcile supported citations with verified Core IDs, and test absence/401 with Core+Portal+PostgreSQL. Coordinate with #145/#149/#154 and schedule 5/5; no new ACME fixture IDs.
