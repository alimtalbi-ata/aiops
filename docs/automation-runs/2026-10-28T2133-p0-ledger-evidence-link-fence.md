# 2026-10-28 21:33 Europe/Paris — P0 NOC/Copilot — AI ledger citation link fence

## Baseline, scope and concurrent work
- Checked `main` HEAD `ec05c89e92a6611922dccbe3690ce1476e3aec92` (merged #151) and open PRs, including #36/#37/#39/#41/#43, #133/#139 (canonical synthetic ACME), #142/#148 (Twin), #143/#140/#145/#149 (Demo Studio/ledger), #147 (Policy), #150/#152 (UI) and #153 (deployment). Reviewed latest #145/#149 journals, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md`, reuse catalog and qualification protocol.
- **Stacked lineage:** #154 `fix/p0-ledger-evidence-links-20261028-2126` → #149 `test/p0-ledger-real-core-http-20261028-2106` → #145 `fix/demo-studio-ai-ledger-read-gate-20261028-1914` → separate Demo Studio V2 delivery branch. Base #149 HEAD checked immediately before branch creation: `fb640b17e2d7c2c0f7e7052f7ba7027048a6655c`. No bulk merge and no changes to another owner's branch.
- **Single vertical change:** reject fabricated evidence-to-claim links in the existing read-only viewer-authorized AI ledger projection. No new stack, fixture, service, route or workflow.

## Commits, files and contract
- `4d659abffadfd2652adb2bce09eff1c26d410ada` — `app/portal/demo_ledger_read.py`: preserve the `GET /api/demo-studio/runs/{rid}/ai-ledger` and `aiops.demo-ledger-read.v1` response shape; fail closed if duplicate Analysis/Critique IDs, dangling Critique→Analysis, supporting evidence not common to both the Analysis and Critique, or `supported=true` without at least one linked evidence ID. Existing viewer token and Core server-side token boundary unchanged.
- `79af0889bc6804c8dbf2ff08cf2b5cbe0c26c228` — `tests/test_demo_ledger_read.py`: positive supported citation and seven negative source-link cases; verify 503 UNKNOWN, no-store and non-disclosure.
- `223fa5f1bbdc02718dbf56e6957c8ee5a9e0a7fd` — `tests/test_demo_ledger_real_http.py`: seed separate DEMO Run with persisted synthetic Analysis/Critique and forged `supporting_evidence_ids`; assert real Core HTTP returns that row while real Portal refuses it with generic 503 UNKNOWN. Reuse #149's existing `quality.yml` database-migrations job, real ephemeral Core, two Portals and PostgreSQL 16.
- This dated journal commit: see PR #154 history. No changes to `.github/workflows/quality.yml`.
- Contract semantics tightened **without schema change**: `supported=true` now means a citation is internally linked to both the cited Analysis and Critique, **not** proof of external Evidence existence, tenant authorization, SAN metrics or runtime verification. Documented for consumers #145, #149, #139 and #133.

## Qualification and risk register
- **GitHub Actions `quality.yml`**: pending exact SHA/job verification at journal creation. The workflow is triggered by existing pull_request/push rules; no manual CI/deploy workflow.
- Tests added: one unit method with seven adversarial variants and one positive path, one actual HTTP/Core/PostgreSQL integration method. **NOT YET CLAIMED PASS** until CI step and log verified. No local Docker tests run.
- Pre-existing #145/#149 baseline has 11 Policy unit failures and runtime E2E failure on the V2 delivery lineage; these are unrelated but block overall green and merge. Do not weaken Policy to make CI green.
- **NOT_TESTED/BLOCKED:** tenant A/B actor-scoped ACL, actual Evidence existence and freshness (IDs are referential only), Grafana observed SAN CRC and Payments p95, Twin runtime impact, Checkmk/Thruk, Ollama 4B, GLPI/Temporal complete path, authenticated browser, Debian runtime, captures/video and LIVE.
- Core ledger response is not a cryptographic Evidence attestation; a fabricated ID copied into Analysis and Critique can still be internally consistent. Therefore `runtime_attested=false` and `tenant_acl_qualified=false` remain mandatory.
- No Debian access, SSH, secrets, NGX call, production migrations, deployment, merge or LIVE command.

## Next micro-lot
Implement an authorized Core-side evidence-reference resolution (source, hash, timestamp and tenant) for a read-only projection, with real Core/PostgreSQL A/B isolation before any claim of observed SAN→Payments causal diagnosis. Coordinate source and contract with owners #145/#139/#142; keep canonical ACME IDs from #133 distinct from CI-only ledger IDs.

## Verified CI on code/test SHA (2026-10-28 21:34 Europe/Paris)
- [Existing quality.yml PR run #40764417768](https://github.com/alimtalbi-ata/aiops/actions/runs/40764417768) on code/test SHA `223fa5f1bbdc02718dbf56e6957c8ee5a9e0a7fd`. Job `quality-build-package` completed/failure: compilation success, **ledger unit step completed/success, 11 tests / 11 OK** (job 123084602094, including new `test_sourced_claim_requires_linked_analysis_and_evidence`); then pre-existing Policy step **11 failures / 15 tests**, later steps skipped.
- Same run: `database-migrations` completed/success, including **real Core/Portal/PostgreSQL HTTP step, 5 tests / 5 OK** (job 123084602096, including `test_persisted_unsourced_claim_fails_closed`). `mariadb-dr-rehearsal` and `migration-runner-upgrade` completed/success. `runtime-e2e` was still in progress when checked; no success claim.
- **Overall CI NOT_PASS**, PR remains draft, no merge. A later journal-only SHA must be checked separately; no PASS inferred from the code SHA.
