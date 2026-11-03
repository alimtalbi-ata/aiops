# AIOps2 — Architect integration cycle, 2026-11-01 12:34 Europe/Paris

**Decision: RELEASE_STABLE=NO_GO; sole candidate Draft #234, main unchanged.** This is a DEV-only source/CI cycle, not an on-host deployment, customer acceptance or LIVE qualification. Do not push `deploy/aiops2-stable` (its existing poller may deploy on a new SHA).

## Exact refs and source review

- Verified main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; candidate before selective port `6755405ffb8538470925163f1466b45686d9b4af`.
- Selective product commit `d3099158201e600d3e62ef7ea58a2366608a92c8` on sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), 14 exact source blobs, no historical branch merge, no schema/migration changes. Branch fast-forwarded with expected old SHA, not force-pushed.
- ACME [#284](https://github.com/alimtalbi-ata/aiops/pull/284), HEAD `75eb60d87c7c1e04b483f3448a510af6bf272e9a`: 3 paths (tools cross-domain projection, catalogue test, customer-story contract); [Quality #41300275138](https://github.com/alimtalbi-ata/aiops/actions/runs/41300275138) **3/3**, focused **181/181**. Seven full-event vs payload vs Core-wrapped hashes are NOT_EQUIVALENT / TEST_ONLY; runtime IDs and ITIL stages NOT_EXECUTED.
- Portal [#285](https://github.com/alimtalbi-ata/aiops/pull/285), HEAD `2523bad3985eaa85b0e5634b99e9a5550e9fe5c2`: 4 paths (Portal tests/fixtures, contract); [Quality #41300690573](https://github.com/alimtalbi-ata/aiops/actions/runs/41300690573) **3/3**, browser/API/consumer **48/48**. Synthetic IdP→GLPI and signer rotation never authorize; 503 UNKNOWN / revoked 401.
- Core [#287](https://github.com/alimtalbi-ata/aiops/pull/287), HEAD `20ecf05066e2d6090791fd8bd19384ce4de9e632`: 4 paths (negative-only HTTPS/TLS source preflight, PG16 test, dedicated workflow, ADR); [dedicated #41301484052](https://github.com/alimtalbi-ata/aiops/actions/runs/41301484052) **1/1**, **10/10 zero skips**, [Quality #41301484060](https://github.com/alimtalbi-ata/aiops/actions/runs/41301484060) **3/3**. Synthetic source read-only PG16 with 001/004/009→013, not GLPI human rights, not a positive Core ALLOW, not ACME hash equivalence.
- Policy/Worker [#288](https://github.com/alimtalbi-ata/aiops/pull/288), HEAD `33b4730d74232bb455b1dbc3dc19cee6bda0a0e6`: 3 paths (combined Worker test, workflow, qualification); [dedicated #41301975396](https://github.com/alimtalbi-ata/aiops/actions/runs/41301975396) **1/1**, **10/10 combined + 5/5 DR**, [Quality #41301975386](https://github.com/alimtalbi-ata/aiops/actions/runs/41301975386) **3/3**. Two disposable tenants, negative ACK/lease fencing, two Temporal restarts; exhausted leases remain LEASED attempts=8. Core-owned runtime DEAD transition absent. SQL-injected DEAD in prior case is not runtime.
- These are **source-head** checks only. As of product commit, **candidate exact-head CI = PENDING / NOT_VERIFIED**. Do not transfer source CI to combined head; check all required workflows and exact SHA after documentation commits before any further integration or merge. #234 remains Draft.

## Existing Debian host — read-only GitHub-reported evidence

Authoritative report path: [`ops/debian-reports/SRV-DEB-05/latest.json`](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) on `ops/debian-runtime-reports`. Observed report `collected_at=2026-11-01T11:29:01.709559+00:00` (**12:29:01 CET**), 61 containers: 53 running / 8 exited, 22 healthy / 38 no-healthcheck / 1 unhealthy. GitHub commits `013eb64855c351b61b32ee8b2cc3f45daeb89563` (11:29 UTC), `23c48c45edddc721f1ad2c1ee40829ce857e9fd9` (11:30 UTC), `bd0d2c78a86f60b3bc78c7e02becff8d24f898dc` (11:35 UTC) demonstrate repeated publication of the canonical path; cron firing origin and future cadence remain NOT_TESTED. Snapshot freshness at 12:34 CET ≈5 minutes; future cycles must check report `collected_at` and commit timestamps, not assume ongoing freshness.

| Component category | Reported state | Inference boundary |
|---|---|---|
| `aiops2-rebuild-portal` | running / healthy | Container health only; not verified operator login or service-level SLO |
| `aiops2-portal-candidate-web-20261029` | running / no-healthcheck | No health probe; do not label healthy |
| `aiops2-portal-rollback-v2-20261028` | exited / unhealthy | Historical rollback container; **not evidence of active Portal outage** |
| `aiops2-rebuild-core`, `-twin`, `-policy` | running / healthy | Container health only; no proof of current #234 deployment or full ITIL runtime |
| Remaining containers | mixed running/exited, many no-healthcheck | Do not equate no-healthcheck with unhealthy |

Legacy `COLLECTED_LOCAL_TOKEN_NOT_CONFIGURED` is a separate optional API publisher path, **not evidence of failure of the SSH Git report publisher**. No SSH/host command executed by this schedule. `deploy/aiops2-stable` untouched; existing Docker containers, volumes and networks untouched.

## Deduplication / security

[Draft #286](https://github.com/alimtalbi-ata/aiops/pull/286) adds a second systemd observer + token-based Issues publisher although existing read-only reporter and SSH publisher already produce canonical reports. **Do not integrate this duplicate observer, enable Docker socket access, or activate typed host tasks.** Review only narrowly reusable publisher runbook/guardrails, with no host deployment. Its local executor remains unconnected; no arbitrary command or LIVE executor.

No GLPI writes, real human IdP/GLPI attestation, host SSH, sudo, unrestricted Docker socket, LIVE, external data mutation or deployment has occurred. The 15 ITIL stages and six checkpoints remain NOT_EXECUTED as an integrated positive scenario.

## Gates and 8-hour bounded sprint

| Gate | State |
|---|---|
| SOURCE_REVIEWED | 14 exact source blobs and PR diffs, 4 focused sources; #286 duplicate identified |
| CI_PASS | Source exact-head 14/14 jobs; **combined candidate new head PENDING** |
| INTEGRATION_PASS | New combined-head qualification **NOT_VERIFIED** |
| RUNTIME_OBSERVED | GitHub-published host inventory only (report 12:29 CET); CI disposable PG16/Temporal/Chromium source runs |
| NOT_VERIFIED | Actual #234 host runtime, human GLPI rights, canonical ACME seven-event readback equivalence, Core DEAD, end-to-end ITIL, clean-host kit, client acceptance |

P0 owners (maximum three): Portal = native human IdP→GLPI authority, Core = canonical ACME seven-event source ownership, Policy = Core-owned DEAD interface contract negatives. ACME P1 = map seven event hash domains and prove explicit UNKNOWN until real Core source. Architect owns report freshness, duplicate #286 resolution, exact-head integration gates. No cross-team concurrent edits; each team owns its respective app/tests/docs, only architect updates candidate, board and #186.

**Next:** verify new #234 exact-head workflows; require all jobs SUCCESS with exact SHA and no skip before marking CI_PASS. Recheck Debian report every cycle; investigate if `collected_at` or publisher commit stalls beyond expected cadence, without touching host. Build disposable machine-readable end-to-end receipt for Event→Incident→Twin→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→VERIFY→resolution/reopen, with UNKNOWN for unproven GLPI authority. Target sprint closeout within 8 hours of directive; not a promise of client GO.

**Rollback:** close/revert unmerged Draft #234 or revert product commit `d3099158201e600d3e62ef7ea58a2366608a92c8` using a new revert commit on candidate, then revert subsequent documentation commits in reverse order, rerun exact-head CI. Preserve immutable 013 audit and never reset/force-push main. No rollback on host needed because no host deployment occurred.
