# AIOps2 — Automation Control Plane (A/B/C/D)

**Observed 2026-10-31 20:11 UTC (21:11 Europe/Paris).** Architecture owner: 5/5, tracking PR #195 and issue #186. This is a point-in-time **evidence inventory**, not a deployed scheduler or live heartbeat. `main` DEV baseline; GitHub API reports `protected=false` (not protected); only main-based integration candidate [#201](https://github.com/alimtalbi-ata/aiops/pull/201) `add733c233483e55e23c8a8a2deb0ba0d5fe2aa6`. `RELEASE_STABLE=NO_GO`.

## One control matrix — scheduler → owner → cadence → action → environment → last success → next → evidence → alert → recovery

| Scheduler / owner | Cadence and command/workflow | Environment | Last independently observed success | Next run | Logs / artifact | Alert and recovery |
|---|---|---|---|---|---|---|
| A Debian cron/systemd / host operator | **Requested** `*/1`; actual crontab, user, command, cwd, PATH, lock, retries and timeout **UNATTESTED** | SRV-DEB-05, **NO ACCESS** | UNKNOWN | UNKNOWN | Local journal/syslog/receipt **NOT_OBSERVED** | Host heartbeat absent; inventory first, no second cron, no auto-deploy |
| B GitHub default-branch quality / CI owner | `pull_request` + `push(main,fix/**)`; `.github/workflows/quality.yml`, **no schedule or workflow_dispatch** | GitHub-hosted ephemeral CI | [#201 Quality 41237316197](https://github.com/alimtalbi-ata/aiops/actions/runs/41237316197) 3/3 SUCCESS at 20:07 UTC, **PR SHA only** | Event-driven, not periodic | [synthetic artifact 13055907092](https://github.com/alimtalbi-ata/aiops/actions/runs/41237316197/artifacts/13055907092), retention 7d | Failure via Actions checks; re-run only exact HEAD, no green-by-proxy |
| B #188 full-quality proposal / CI owner | `23 2 * * *` UTC + PR/push + dispatch; **UNMERGED** | Hosted CI | NOT_ACTIVE | NOT_SCHEDULED | Candidate workflow source [#188](https://github.com/alimtalbi-ata/aiops/pull/188) | Review one consolidated schedule; do not activate duplicate #189 |
| B #188 runtime-smoke proposal / host+CI | `*/15 * * * *` UTC + dispatch; `bash scripts/runtime-smoke.sh`; **UNMERGED** | Self-hosted `aiops2-runtime` runner **NOT_ATTESTED** | NOT_ACTIVE | NOT_SCHEDULED | No host runner receipt | No activation on Debian without explicit change approval; never untrusted PR code |
| B #189 quality duplicate / CI owner | `23 */2 * * *` UTC + dispatch + PR/push; **UNMERGED** | Hosted CI | NOT_ACTIVE | NOT_SCHEDULED | [#189](https://github.com/alimtalbi-ata/aiops/pull/189) | Supersede after #188 contract reconciliation, never run both |
| C ChatGPT 1/5 / ACME | HOURLY; fixture/storyboard only | ChatGPT + synthetic local/CI | 20:03 UTC completed result, #198 `685effe1…` | **NULL**; current run in progress | [Quality 41236898943](https://github.com/alimtalbi-ata/aiops/actions/runs/41236898943), replay 13055468181 | Check missed result after 1h+grace; no guaranteed minute cadence |
| C ChatGPT 2/5 / Portal | HOURLY; actor+tenant fail-closed | ChatGPT + ephemeral CI | 20:07 UTC completed result, #201 `add733c2…` | **NULL**; current run in progress | [Quality 41237316197](https://github.com/alimtalbi-ata/aiops/actions/runs/41237316197) | Alert on missing completed handoff; no assumed positive ACL |
| C ChatGPT 3/5 / Core | HOURLY; xref/Evidence read-only | ChatGPT + PG16 disposable | 20:07 UTC completed result, #205 `4909f4bb…` | **NULL**; current run in progress | [Quality 41237287968](https://github.com/alimtalbi-ata/aiops/actions/runs/41237287968) | Block same-SHA integration until migrations reconciled |
| C ChatGPT 4/5 / Policy/HITL | HOURLY; offline HITL | ChatGPT + PG16/Temporal CI disposable | 20:01 UTC completed result, #204 `1e79aa22…` | **NULL**; current run in progress | [Quality 41236643024](https://github.com/alimtalbi-ata/aiops/actions/runs/41236643024), PG16 artifact 13056251372 | Never equate CI worker restart with production approval |
| C ChatGPT 5/5 / architect | HOURLY; board, release, control plane | ChatGPT + GitHub docs | 19:29 UTC completed result, #195 `78e538e4…` | **NULL**; current run in progress | [Quality 41234354180](https://github.com/alimtalbi-ata/aiops/actions/runs/41234354180) | Record exact base/head/CI, no merged promotion |
| D Lab / ACME | On-demand, seed `20261018`, seven synthetic events | Offline/CI synthetic | #198 63/63 owner tests reported; CI 3/3 | N/A | Replay artifact 13055468181 | Label SYNTHETIC, not Debian/GLPI runtime |
| D Lab / Core + HITL | On-demand PG16/Temporal fixtures | CI disposable | #205 PG16 9/9; #204 PG16 13/13, DR 32 tables | N/A | #204 DR 13055437863, Temporal 13055676514 | Not OIDC, real network ACK, or LIVE |
| D Lab / Portal + benchmark | On-demand Chromium / Ollama | Synthetic browser + CPU model eval | Portal Chromium 7/7; #196 evaluator **FAIL** | N/A | #201 synthetic 13055907092; #196 [Quality failure](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) | No real model quality PASS, provider tokens only, cost UNKNOWN |

**GitHub event audit:** main contains **one** workflow file (`quality.yml`) with `pull_request` and `push`, `permissions: contents: read`, three disposable jobs and a seven-day synthetic screenshot artifact. GitHub API `actions/runs?event=schedule` returned **0** scheduled runs. #204 branch contains five workflows (quality, V2.8, V2.12.8, V2.12.9, promote-stable); its `promote-stable` uses `workflow_run` and write permissions, but is **not on main**. No main schedule/dispatch, runner registration, cron job or alert channel is attested. `workflow_dispatch` is not a cron. #146/#153 Debian auto-deploy proposals remain unmerged and unauthorized.

## Read-only Debian inventory handoff (operator only; NOT EXECUTED)

Before installing anything, record `date -Is`, `id`, effective `PATH`, `pwd`, `crontab -l` for the actual service account, `/etc/crontab`, `/etc/cron.d` and systemd user/system timers. Run `systemctl list-timers --all --no-pager`, `systemctl list-units --type=service --all --no-pager`, `systemctl show <unit> -p User -p WorkingDirectory -p Environment -p ExecStart -p TimeoutStartUSec -p Restart`, and read relevant `journalctl -u <unit> --since ... --no-pager` / cron syslog. **Redact credentials and internal addresses before sharing.** Inspect actual command, shell, cwd, PATH, `flock` lock, overlap, wall duration, exit codes, timeout, retries, idempotency, secret source, log retention, last successful receipt, and missed-run alarms. No `sudo`, SSH, crontab install or systemctl mutation was performed by this work.

**Minute cadence is a requirement, not an observation.** Do not replace or add a Debian scheduler before this inventory. Keep Debian host telemetry separate from GitHub Actions and ChatGPT schedules.

## Verifiable heartbeat protocol and missed-run gate

Versioned **offline** checker: `scripts/automation_heartbeat_gate.py`; tests `tests/test_automation_heartbeat_gate.py`. It reads an evidence JSON snapshot and never calls an external system. Each entry carries `plane` (`debian|github|chatgpt|lab`), unique `id`, `enabled` (`true|false|null`), `state`, `cadence_seconds` or null, UTC `last_success_at`, UTC `next_run_at` or null, `evidence_ref` and optionally local `receipt_path` + `receipt_sha256`. The schema is `aiops.automation-heartbeat.v1`. A host receipt, when eventually installed by an operator, should include run UUID, scheduled/start/finish UTC, command digest, source SHA, user, working directory, exit code, duration, lock status, log path, mode, effect fence and local hash; never embed secrets.

Checker: `python scripts/automation_heartbeat_gate.py --input control-plane-snapshot.json --now 2026-10-31T20:11:00Z`. Exit `0=PASS`, `1=WARN`, `2=FAIL`; default grace 300 seconds. Flags `MISSED_RUN`, `NEXT_OVERDUE`, `NEXT_UNKNOWN`, `NO_SUCCESS_EVIDENCE`, `UNATTESTED`, `INACTIVE`, `CLOCK_SKEW`, `EVIDENCE_MISSING`, `RECEIPT_HASH_MISMATCH`, `LAB_PROVENANCE_UNKNOWN`. If an evidence path+SHA is provided, the file hash is verified. An URL-only reference is **not** independently cryptographically verified. Null `next_run_at` remains **UNKNOWN** even when an hourly task is enabled. The checker does not prove the scheduler will execute, nor that a CI/lab result ran on Debian.

**Alerting design, not activated:** a separate approved observer should collect host receipts and GitHub/ChatGPT completed-run timestamps, evaluate each cadence+grace, notify the owner for `FAIL` or repeated `WARN`, and store immutable redacted receipts with retention and acknowledgements. Recovery: inspect missed/overlapping runs, locks, exit codes and source SHA; replay only idempotent read-only work after owner approval. Never auto-retry deploy/LIVE or install a duplicate cron. The current five ChatGPT tasks all report `next_run_time=null` and a new run `in_progress` at 20:11 UTC: cadence is **configured hourly, not guaranteed**.

## Release gates and handoff

Owners: 1/5 ACME fixture, 2/5 Portal actor+tenant ACL, 3/5 Core xref/Evidence, 4/5 Policy/HITL; 5/5 integration/board. P0 WIP <=3: positive Portal/Core ACL; ordered PG16 `009/010/011/012` and D1/D2 on #201; semantic kit + D3. No green-by-proxy. #204 [artifact 13055293798](https://github.com/alimtalbi-ata/aiops/actions/runs/41236643024/artifacts/13055293798) independently audited: sidecar 412/412 PASS, JSON 38/68 PASS, 30 mismatch, VERSION 2.1.0-core-rc1.4 vs JSON 8.0.0, packaged git_commit differs from #204 HEAD, repack 413/413, install/upgrade/rollback 0/0/0. **D0 isolated only; D1/D2 NOT_QUALIFIED; D3 NO_GO; D4 NOT_ATTESTED.** No merge/main push, Debian/cron/runner, SSH/sudo, GLPI write, executor activation, production or LIVE.

## 2026-10-31 20:38 UTC — incremental A/B/C/D control-plane observation

| Plane / owner | Cadence / command or workflow / environment | Last verified success | Next execution | Evidence / alerting / recovery |
|---|---|---|---|---|
| A SRV-DEB-05 / host operator | Requested `*/1`; actual cron/systemd command, user, cwd, PATH, flock, retries, secrets and logs **UNATTESTED**; Debian | UNKNOWN | UNKNOWN | No host access or heartbeat receipt; inventory before any scheduler change, alert on missing local receipt, never install duplicate cron |
| B GitHub / #221 CI owner | Proposed `23 2 * * *` UTC + workflow_dispatch, hosted `quality.yml` PR/push; **not on main** | [#221 exact-head Quality 41239223325](https://github.com/alimtalbi-ata/aiops/actions/runs/41239223325) 3/3 SUCCESS, contract and Chromium steps SUCCESS; artifact 13057325093 synthetic | **No active scheduled next run**; GitHub schedule runs 0 | [#221](https://github.com/alimtalbi-ata/aiops/pull/221) HEAD `4130a8b8e5995c7e28440a183dd1711eac98cac9`, base main `27deb9b1a66faf27df8d69b137a63451f7649d80`; do not claim active cron before approved merge; no self-hosted runner |
| C ChatGPT / owners 1–5 | Five HOURLY configured, not minute cron; ChatGPT | 1–4 last runs completed 20:12–20:17 UTC; 5 currently in progress | **5/5 next_run_time=null** | Flag NEXT_UNKNOWN; use per-owner handoff and exact-head CI, do not promise next execution |
| D internal lab / scenario owners | On-demand ACME/Chromium, PG16/Temporal synthetic/disposable | Previous exact-head CI evidence only, no new scenario delta | N/A | Record scenario/seed/version/proof before claiming new lab run; never count as Debian/NGX/GLPI runtime |

**Governance blocker:** fresh GitHub `main` branch API reports `protected=false`; repository ruleset `pr1` #25389668 has `enforcement=disabled`. Branch-protection detail requires admin permission and is not attested. Treat `main` as **NOT_VERIFIED_PROTECTED** pending administrator correction; do not change protection or push main in this run.

**Reproducibility:** `python -m unittest discover -s tests -p 'test_quality_schedule_contract.py' -v` is the #221 PR contract command (CI step SUCCESS; 3 tests in source). Heartbeat checker remains `python scripts/automation_heartbeat_gate.py --input control-plane-snapshot.json --now <UTC-ISO8601>`; not executed on Debian. No host/runtime writes, no LIVE. Rollback for these documentation changes: revert this commit on #195 only. D0 #221 isolated GO_LIMITED; release D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED.

## 2026-10-31 21:52 Europe/Paris — schedule activation source delta

| Plan / owner | Cadence / workflow / environment | Dernier succès vérifié | Prochaine exécution | Logs / alerting / reprise |
|---|---|---|---|---|
| A Debian / host operator | `*/1` demandé, commande/user/cwd/PATH/flock/systemd inconnus, SRV-DEB-05 | **UNATTESTED**, aucun reçu hôte | UNKNOWN | Inventaire read-only par opérateur; aucun second cron ni modification runtime; exiger receipt local et missed-run |
| B GitHub / CI owner | `.github/workflows/quality.yml` sur **main@77a9d415464c67190c428d8c1559cf22db149d0e**; PR/push + `schedule: 23 2 * * *` UTC + `workflow_dispatch`; GitHub-hosted Ubuntu 24.04 pour Chromium | [#221 PR HEAD 4130a8b8… Quality 41239223325](https://github.com/alimtalbi-ata/aiops/actions/runs/41239223325) **3/3 PASS**, puis **MERGED** as main `77a9d415…` | First future schedule nominally 2026-11-01 02:23 UTC, **NOT_ATTESTED** (GitHub may delay/skip); main push CI NOT_VERIFIED | [#221](https://github.com/alimtalbi-ata/aiops/pull/221); artifact #13057325093 synthetic PR-only; monitor schedule event + conclusion, no host runner or duplicate #188/#189 |
| C ChatGPT / owners 1–5 | Five enabled HOURLY RRULEs, ChatGPT only | Prior completed owner handoffs; five fresh runs **in_progress** at 20:52 UTC | **5/5 next_run_time=null**; cannot guarantee next hour | Flag NEXT_UNKNOWN; inspect last_run/status and exact-head GitHub handoff, alert on missed completed result |
| D Internal lab / owners | ACME seed 20261018, Chromium, PG16, Temporal synthetic/disposable; on demand | #198/#201/#205/#204 isolated CI successes only; #196 evaluator FAIL | N/A | Record seed/version/artifact per test; never claim Debian/NGX/GLPI real runtime |

**Delta evidence:** GitHub compare old main `27deb9b1a66faf27df8d69b137a63451f7649d80` → new main `77a9d415464c67190c428d8c1559cf22db149d0e`: exactly one commit, three files (`.github/workflows/quality.yml`, `docs/automation/MAIN-QUALITY-SCHEDULE.md`, `tests/test_quality_schedule_contract.py`). #221 is merged, not merely proposed. The next schedule time is derived from source cron, not an API-observed next_run timestamp; no scheduled execution or heartbeat receipt yet. GitHub source tests do not qualify D1–D4 or Debian runtime. Release remains **NO_GO**; no host/GLPI/LIVE operations. Rollback for this documentation delta: revert only this commit on #195.


## 2026-10-31 21:50 Europe/Paris — Current scheduler and integration state

Five ChatGPT schedules are enabled and configured hourly in Europe/Paris, staggered 23:00/23:10/23:20/23:30/23:45. Immediate runs have been requested for all five. The automation API still returns `next_run_time=null`; recurrence is configured but not yet independently attested. Each run must be inspected before calling it a heartbeat.

GitHub daily quality workflow #221 has been merged into main at `77a9d415464c67190c428d8c1559cf22db149d0e`; post-merge quality run #41240948760 was in progress at snapshot time. The Debian cron and runtime remain NOT_ATTESTED because no host access is available. The GitHub-hosted freshness observer #222 remains Draft pending a real schema-v3 report file.

The repository is DEV-only. GitHub reports `main.protected=false`, so the architect enforces exact-head checks, focused PR review and rollback manually. #195 (218 commits ahead), #201 (112), #202 (43), #198 (47), #205 (50) and #204 (900 ahead/43 behind) must not be wholesale merged; use selective integration onto a clean main-based candidate.
\n\n## 6. Architect checkpoint — 2026-10-31 22:05 Europe/Paris\n\nMain is now `2c87bc931b170208b7c2f253218d0f939381355a`. #221 and #224 are merged; post-merge quality is 3/3 SUCCESS on both resulting main SHAs. #195 is closed as superseded; its long history was selectively ported, not merged wholesale.\n\nFive team schedules are enabled and their immediate runs completed, but `next_run_time=null` remains an explicit scheduler limitation.\n\nThe four team handoffs are #198 (3/3 but 3 new tests unexecuted), #223 (3/3, stacked on stale #201), #205 (new head no CI; CMDB provenance issue), and #204 (4 workflows green, still stacked on #194). #201 is not ready for main promotion because it is stale and 112 commits ahead.\n\nThe next architect action is to realign the integration candidate to current main, qualify the new exact SHA, and integrate only the validated deltas. No runtime/production/LIVE proof is claimed.\n

## 7. Schedule DTSTART correction — 2026-10-31 22:15 Europe/Paris

The five hourly ChatGPT schedules now use future local DTSTART values 23:00, 23:10, 23:20, 23:30 and 23:45 Europe/Paris. All are enabled. The scheduler still returns `next_run_time=null`, so the future firing remains unverified.

## 2026-10-31 23:48 Europe/Paris — scheduler evidence and missed-run truth

A Debian SRV-DEB-05: requested `*/1`, but command/user/PATH/working directory/flock/timeout/logs/last success/heartbeat/next execution remain UNATTESTED; no host shell or duplicate cron. B GitHub: `23 2 * * *` UTC daily Quality configured on main; post-merge #230 Quality #41242870529 was a push-triggered run, **not** a schedule heartbeat. C ChatGPT: five enabled HOURLY configurations; all five `next_run_time=null`, so future cadence is UNKNOWN. Latest handoffs ACME/Portal/Core completed; Policy was in progress; architect active. D lab: ACME seed 20261018, Chromium, PG16 and Temporal are synthetic/disposable, not Debian/NGX/GLPI runtime. `scripts/automation_heartbeat_gate.py` is offline only; missed runs cannot be certified without timestamped receipts. Alerting/recovery remain proposed, not deployed.


## 2026-11-01 00:41 Europe/Paris — automation truth / architect handoff

| Plane | Owner/cadence/environment | Last evidence | Next/alert/recovery |
|---|---|---|---|
| A Debian SRV-DEB-05 | Host cron `*/1` requested, operator-owned | UNATTESTED: no shell, command/user/PATH/flock/timeout/logs/exit/heartbeat observed | UNKNOWN; inventory before any scheduler installation, local missed-run receipt required |
| B GitHub Actions | Quality daily `23 2 * * *` UTC plus PR/push/dispatch, hosted disposable CI | Candidate [#41253703233](https://github.com/alimtalbi-ata/aiops/actions/runs/41253703233) PR-triggered IN_PROGRESS; NOT a schedule heartbeat | Next actual schedule run NOT_OBSERVED; inspect event, conclusion, artifacts and retention; no host/GLPI/LIVE |
| C ChatGPT 1–5 | Five enabled HOURLY owner/architect automations | Latest owner last_run timestamps 2026-10-31 23:06–23:35 UTC; prompts updated with current contracts | **5/5 next_run_time=null**; NEXT_UNKNOWN, cannot certify recurrence/missed runs without run receipts |
| D Internal lab | ACME seed 20261018, Portal RSA/Chromium, Core PG16, Policy HTTP synthetic/jetable | Source exact-head CIs isolated; combined candidate D0 pending | On-demand only; record seed/version/SHA/artifact, never classify as Debian/NGX/GLPI runtime |

The offline `scripts/automation_heartbeat_gate.py` is not installed on Debian and cannot prove host cron cadence. Do not create duplicate scheduler or confuse GitHub daily schedule with ChatGPT hourly cadence. No host access, no GLPI write or LIVE.


## 2026-11-01 01:48 CET — automation A/B/C/D checkpoint

| Plane / owner | Cadence / command / environment | Last verified success / next | Logs, missed-run alert, recovery |
|---|---|---|---|
| A SRV-DEB-05 / operator | Debian `*/1` requested; cron/systemd inventory NOT_OBSERVED | Last/next UNKNOWN, host heartbeat absent | Inspect user, PATH, working dir, `flock`, timeout, retries, exit/logs/secrets before installing anything; missed-run UNKNOWN; no SSH/sudo |
| B GitHub / architect | Quality PR/push/dispatch + configured `23 2 * * *` UTC; new dedicated HITL PR workflow, hosted disposable PG16 | Source #243 [HITL 41257528325](https://github.com/alimtalbi-ata/aiops/actions/runs/41257528325) 1/1; new candidate exact-head pending; no actual `schedule` heartbeat attested | Actions run IDs/artifacts 7-day retention; detect missed daily schedule only from event+timestamp receipts, not PR CI; rerun scoped CI if needed |
| C ChatGPT owners 1–5 / architect | Five HOURLY enabled; independent of Debian cron | 1–4 latest completed 00:00, 00:12, 00:27, 00:39 UTC on 2026-11-01; 5 in progress; **5/5 `next_run_time=null`** | NEXT_UNKNOWN, not cadence guarantee; handoffs in #186 and source PRs, inspect run details, avoid duplicate schedules |
| D Internal lab / owner | On-demand ACME seed 20261018, OIDC/Chromium, PG16 SQL-model, Policy | Source exact-head CI as above, candidate D0 pending; no Debian/NGX/real GLPI runtime | Record scenario, seed, SHA, test N/N and artifact; synthetic != runtime; no LIVE |

The offline `scripts/automation_heartbeat_gate.py` remains not deployed. No Debian cron changes, runner host access, external mutation, real GLPI write or executor. `RELEASE_STABLE=NO_GO`.


### B GitHub Actions — exact-head correction (2026-11-01)

Review of candidate Quality showed three default PR merge-ref checkouts. Architect pinned all three to `github.event.pull_request.head.sha || github.sha` and added explicit `git rev-parse HEAD` assertions plus contract test on #234 commit `f2bf03f085495348fd80e0acb2a898f9b0b72eb8`. Previous PR-triggered green jobs are **not** evidence of exact source-head D0; new SHA must be requalified. Daily `schedule` trigger still has no observed heartbeat; PR runs are not cron. No Debian host or external effects.


### Architect cycle — 2026-11-01 02:44 CET — selective integration, NO_GO

SOURCE_REVIEWED: DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft #234 from that base, candidate product checkpoint `7fe177ea165e063a64a80acd22bf4e1a8338b355` (final documentation commit and exact-head CI pending). No whole historical #201/#194/#204 merge. Owner source Drafts all based on prior candidate `d5227f5c3981a53dd2a42d5384dce798cfaf0d33`:

| Owner / source | Exact source HEAD; source CI | Architect selective port / paths | Gate and dependency |
|---|---|---|---|
| Core P0 #246 | `a69e68523b6d690dcb8edbaf8bac57b2e8b8cca0`; [Quality 41260773041](https://github.com/alimtalbi-ata/aiops/actions/runs/41260773041) 3/3; Core 30/30, PG16 installed 3/3 | `5d5f776272f2297f0a2e87cadb1f81c78851422f`; actor_resource_authz, itsm_xref router, Core tests/ADR (5 paths) | IdP introspection mocked; GLPI native human rights, nonce replay ledger and positive ALLOW **not qualified** |
| Portal P0 #245 | `78d0471328268f842e70f5ee5d898cc013b35206`; [Quality 41260115750](https://github.com/alimtalbi-ata/aiops/actions/runs/41260115750) 3/3; Portal 12/12 | `4bcf409c3f2aad27ccaad20ea3cf68dee15b557f`; ACL consumer, tests, OIDC/Core contract (3 paths) | ALLOW-shaped JSON is **not authority**; positive_core_contract_matches remains false, Run 503/UNKNOWN, no upstream |
| Policy/HITL P0 #247 | `dc005302819912f90f32dfc0584ff478fcf756f5`; [Quality 41261752806](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752806) 3/3; [Temporal+PG16 41261752843](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752843) 2/2, Worker 10/10, SQL 5/5 | `b7ab2ab1a5280e98b15805b2d6c7fa9bcac1598e`; Worker pure REJECT adapter, tests, doc, dedicated workflow (4 paths), workflow PR base retargeted to main | No Core claim/ACK HTTP, runtime poller, APPROVE, executor or LIVE; only disposable Temporal Worker restart, no Temporal server restart |
| ACME/Twin P1 #244 | `1c9b6f50c92d43fa893f08bcf0da8964873db4ae`; [Quality 41259232141](https://github.com/alimtalbi-ata/aiops/actions/runs/41259232141) 3/3; catalog 48/48, ACME targeted 85/85 | `7fe177ea165e063a64a80acd22bf4e1a8338b355`; synthetic catalog adversarial tests and provenance doc (2 paths) | Seed 20261018, 18 CI/17 edges, candidate blast radius only; owner/SLA/OLA/Change/real maintenance/observed impact UNKNOWN |

**Decision:** four disjoint, source-reviewed ports to one main-based candidate; all source CI are exact source HEAD, but **do not transfer green by proxy** to the new candidate. New D0 Quality + HITL dedicated runs must check final source HEAD; D1 combined disposable ITIL Event→Incident→Twin→Analyst/Critic→Evidence→HITL→SIMULATE→verification→resolution/reopen NOT_QUALIFIED; D2 browser/API same SHA NOT_QUALIFIED; D3 cumulative kit install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. `#196=FAIL`, provider-reported tokens only, cost UNKNOWN without versioned pricing. No real GLPI/IdP runtime, host or LIVE effects.

**Next owner contracts (WIP P0=3):** Core owns source-authenticated GLPI native actor permission and durable nonce/revocation, plus Core-fenced claim/ACK interface; Portal owns an authenticated transport and no-ALLOW-until-qualified exact Run binding, without overlapping Core files; Policy owns a disposable integration test for Core claim/ACK and Worker/Temporal REJECT with zero effects, without wiring poller; ACME owns independently sourced Twin governance facts and a synthetic end-to-end fixture, never invented SLA/OLA. Architect owns shared CI, migrations and candidate promotion. **Rollback:** revert these four focused commits in reverse order ACME→HITL→Portal→Core, remove disposable databases/artifacts; no persistent-data downgrade claimed and no main reset. `RELEASE_STABLE=NO_GO`.

Automation planes: A Debian SRV-DEB-05 cron */1 requested but UNATTESTED (no SSH/sudo/host observation, user/PATH/flock/logs/heartbeat unknown); B GitHub Quality daily 02:23 UTC configured on main, but no schedule-triggered success attested; PR runs are not cron, Worker dedicated PR CI is disposable; C five ChatGPT hourly tasks enabled, 5/5 next_run_time=null at 02:44 CET, last runs observed, future cadence NEXT_UNKNOWN; D lab synthetic ACME/Chromium/PG16/Temporal, not Debian/NGX/real GLPI runtime. Offline heartbeat gate not deployed; missed runs remain UNKNOWN, no second scheduler.


## 2026-11-01 03:48 CET A/B/C/D control-plane observation

A Debian SRV-DEB-05 cron */1 requested, UNATTESTED; host user, working dir, PATH, flock, timeout, exit, retries, logs, heartbeat, last success and next execution UNKNOWN; no host access. B GitHub Quality on main has `23 2 * * *` UTC plus PR/push/dispatch; PR exact-head runs are not schedule runs, no schedule-triggered success attested. C five ChatGPT owner/architect schedules enabled HOURLY, all five `next_run_time=null`; future cadence NEXT_UNKNOWN; latest owner handoffs on #248/#249/#250/#251 reviewed. D ACME/Chromium/PostgreSQL 16/Temporal disposable lab, no Debian/NGX/real GLPI runtime evidence. Offline heartbeat gate is not installed on Debian and cannot assert missed host runs. New integration #234 source ports and gates documented in `docs/release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-0348.md`. No second cron, host/runner mutation, GLPI write, LIVE or executor. RELEASE_STABLE=NO_GO.

### Automation control checkpoint — 2026-11-01 04:50 CET
| Plane | Owner / cadence / command | Environment | Last success | Next | Evidence / alert / recovery |
|---|---|---|---|---|---|
| A Debian SRV-DEB-05 | Host operator, requested */1; actual cron/systemd/user/cwd/PATH/flock/timeout/retry UNKNOWN | Debian host | UNATTESTED | UNKNOWN | No host heartbeat. Inventory logs/secrets/idempotence before any second scheduler; missed-run NO_SUCCESS_EVIDENCE. |
| B GitHub | CI architect, main Quality 23 2 * * * UTC, PR/push/dispatch; new #255 dedicated path-scoped PR workflow | Hosted disposable | Prior #234 6/6 on 98659d95; new candidate CI PENDING | Schedule next not independently observed | Verify event=schedule, exact checkout, artifact retention and conclusion; PR green is not schedule heartbeat. |
| C ChatGPT 1/5–5/5 | Four owners + architect, hourly configured | ChatGPT | Five enabled, last_run present | Five next_run_time=null | NEXT_UNKNOWN; check completed handoffs, missed run after 1h+grace, duplicates. |
| D Lab | ACME seed 20261018, Chromium, PG16, Temporal test Worker, on demand | Synthetic/disposable | Source #252–#255 isolated CI SUCCESS | N/A | Record seed/version/source SHA/artifact; no Debian/NGX/GLPI runtime inference. |
No Debian heartbeat agent installed. Offline scripts/automation_heartbeat_gate.py remains the versioned missed-run gate.

### 04:54 CET exact-head CI closeout for 04:50 integration checkpoint

At source/document HEAD f9b1dd88406b8b7cc47d072d7b69f4a3946867fd all four PR workflows completed SUCCESS, **7/7 jobs**: Quality 41270854470 3/3; HITL PG16/DR 41270854374 1/1; Worker Temporal 41270854443 2/2; combined Core ASGI HTTP/PG16/Temporal 41270854369 1/1. Logs explicitly checked out f9b1dd...; populated Core PG16 tests 5/5, combined 3/3, SQL DR 5/5, pg_dump/pg_restore 16.15. Artifacts: replay 13069685107, Chromium 13069490868, PG16/DR 13068714535, Worker 13069251340, combined 13068654765; ZIP digests GitHub-reported, not independently recalculated. New documentation HEAD after this closeout must be separately requalified (no green-by-proxy). D0 CI_PASS only for f9b1dd...; D1 business path and D2 browser/API lifecycle NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED. Combined test uses in-process ASGI HTTP, synthetic HMAC ownership, REJECT, injected lost ACK response after DB commit and test Worker restart; real network loss, Temporal server restart, native GLPI rights and LIVE effects not observed. Effect receipts 0.


## 2026-11-01 05:48 Europe/Paris — unified scheduler heartbeat / missed-run checkpoint

| Scheduler | Owner | Cadence | Command/workflow | Environment | Last success | Next run | Logs/artifact | Alert/recovery |
|---|---|---|---|---|---|---|---|---|
| A SRV-DEB-05 cron/systemd | Host operator | `*/1` requested, UNATTESTED | command/user/PATH/flock/timeout/retry UNKNOWN; inventory before change | Debian host (not accessible) | UNKNOWN | UNKNOWN | local cron journal, heartbeat UNKNOWN | missed >2 expected ticks only after actual scheduler+heartbeat inventory; no duplicate cron; operator shell read-only |
| B GitHub Actions | Architect/CI | Quality schedule `23 2 * * *` UTC configured; PR/push/dispatch distinct | `.github/workflows/quality.yml`, HITL disposable workflows | hosted synthetic/ephemeral PG16 | source #256–#259 PR runs green; integrated #234 new HEAD pending | UTC cron configured, next actual firing NOT_ATTESTED | Actions jobs/artifacts and retention from workflow | detect no schedule event/failed run; inspect workflow enabled status, permissions, concurrency and artifacts; no private NGX/GLPI/LIVE |
| C ChatGPT 1–5 | ACME/Portal/Core/Policy/Architect | HOURLY configured | five owner prompts, no Debian cron equivalence | ChatGPT cloud | owner last runs 2026-11-01 04:06/04:10/04:24/04:46 UTC, architect prior 03:56 UTC | **5/5 null** | run handoffs in #186; source SHA in owner PR | NEXT_UNKNOWN; check run status, duplicate prompts, refresh handoff; never claim minute guarantee |
| D internal lab | Owners | on-demand | ACME seed 20261018, Portal RSA, PG16 009–013, Temporal Worker REJECT | synthetic/disposable | source PR exact-head CI as above | none | scenario/seed/version/log SHA, source artifact #13070581531 | no runtime claim; rerun exact integrated HEAD; preserve failure evidence |

Heartbeat acceptance record must contain scheduler_id, environment, planned_at, started_at, finished_at, status, exit_code, source_sha, log/artifact URI and observed_at; missed-run detection compares consecutive expected intervals and distinguishes UNKNOWN from FAIL. The offline `scripts/automation_heartbeat_gate.py` does not prove host cron. No Debian SSH/sudo/cron/runner change. All four owner prompts were updated with new focused contracts; 5/5 automations enabled and all next_run_time null at observation.


### Verified schedule event correction — 2026-11-01 05:50 Europe/Paris

GitHub Actions REST `event=schedule` now returns one **real scheduled** Quality run [#41267926085](https://github.com/alimtalbi-ata/aiops/actions/runs/41267926085), created **2026-11-01 03:08:05 UTC** on exact main `ae7c3e5102b99a66bd7806d602146f1309a9749d`: **3/3 SUCCESS** (`core-postgres-noc-real-integration`, `grafana-real-integration`, `policy-and-static`). Artifact `acme-explore-story-ci-simulated` #13067643872, GitHub-provided ZIP digest `sha256:23c7a84184c52b46f6c45c8281e9448c7e41a53d3d53befe4f49f0a1dba1f6a4` (not independently recomputed). This supersedes earlier `0 schedule runs observed` and `schedule success not verified` claims. Actual firing at 03:08 UTC differs from configured cron 02:23 UTC; one success proves a run, **not punctuality, repeated cadence, heartbeat SLA, or Debian cron**. Next scheduled completion remains UNKNOWN. Missed-run detection must compare scheduled UTC date, observed creation and conclusion with tolerances, never equate `workflow_dispatch` or PR CI to schedule.


### Control-plane checkpoint — 2026-11-01 06:45 Europe/Paris

| Scheduler | Owner | Cadence | Command/workflow | Environment | Last observed success | Next | Logs/artifact | Alerting / recovery |
|---|---|---|---|---|---|---|---|---|
| A SRV-DEB-05 cron/systemd | Host operator (not ChatGPT) | `*/1` requested, UNATTESTED | command/user/PATH/flock/timeouts/retries UNKNOWN | Debian host | UNKNOWN | UNKNOWN | host logs/heartbeat NOT_AVAILABLE | inventory cron/systemd first, verify last exit/duration/secret/idempotence; no install without SSH capability |
| B GitHub Actions | Architect / repo | Quality `23 2 * * *` UTC on main; PR events separate | `.github/workflows/quality.yml` and dedicated HITL workflows | GitHub hosted disposable | actual `schedule` [#41267926085](https://github.com/alimtalbi-ata/aiops/actions/runs/41267926085), 2026-11-01 03:08 UTC, 3/3 | future schedule not guaranteed | GitHub run/log/artifact #13067643872 | alert if no `event=schedule` run within daily grace; rerun exact SHA, never infer cron from PR |
| C ChatGPT 1–5 | ACME/Portal/Core/Policy/Architect | HOURLY configured | five owner task prompts | ChatGPT | four owner runs completed, #260–#263 handoffs in #186 | 5/5 `next_run_time=null` | run handoff SHA and #186 | NEXT_UNKNOWN, inspect scheduler status; never call this minute cron |
| D Internal lab | Owners | on demand | ACME seed 20261018, Chromium TLS, PG16 009–013, Temporal REJECT | synthetic/CI disposable | owner source CI #260–#263 green | none | source SHA, seed, scenario, tests and artifact | fail if artifact/seed missing; lab is not Debian/NGX/GLPI runtime |

Heartbeat schema: `scheduler_id, owner, environment, expected_at, started_at, finished_at, source_sha, status, exit_code, duration, log_uri, artifact_uri, observed_at`. Missed-run detection must classify `UNKNOWN` when next_run_time is null and `MISSED` only after expected window and grace with authoritative schedule; never treat a lab PASS as host success. No Debian scheduler mutation, no duplicate cron installation.
