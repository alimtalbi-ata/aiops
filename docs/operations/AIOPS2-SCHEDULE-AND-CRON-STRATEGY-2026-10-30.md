# AIOps 2.0 — Schedules, GitHub Actions and Debian cron strategy

**Status:** target schedule; no Debian host change performed.  
**Goal:** maximize feedback without duplicate CI load or accidental production deployment.

## 1. Five existing ChatGPT schedules

The five schedules already exist and are active. The 48-hour work uses them; no sixth schedule is created. Schedule 5/5 is the architecture/release coordinator and is being reoriented to this plan.

1. ACME/Twin: reproduce the existing SAN→Payments Incident/Run and source-backed Twin path.
2. Portal: finish the existing operator journey; no new parallel HTML prototype.
3. NOC/Evidence/GLPI: read-only reconciliation of incident, Run, ticket and evidence IDs.
4. Policy/HITL: reuse SIMULATE and proposal contracts; no synthetic approval authority.
5. Architecture/release: maintain architecture, ADRs, benchmark, interface contracts, CI evidence, release candidate and one GO/NO-GO.

Each schedule must hand off exact SHA, file paths, test command/results, IDs and blockers. If no change occurred, report no_update rather than duplicate comments.

## 2. GitHub Actions schedule convergence

| Workflow | Intended cadence | Trigger | Safety |
|---|---|---|---|
| Full quality | Daily at 02:23 UTC + PR/push + manual dispatch | #188 candidate | Unit, contract, static and ephemeral integration; no production effects |
| Deployed runtime smoke | Every 15 minutes | #188 candidate, repository-scoped `aiops2-runtime` self-hosted runner | Read-only health, image/source contract and Worker→Temporal TCP; no Run creation, Evidence writes, GLPI or restarts |
| Optional quick contract smoke | Every 2 hours only if a distinct, lightweight job is justified | #189 candidate | Do not duplicate full quality; do not activate both schedules as competing full-suite cron |

**Decision:** use #188 as the schedule base; treat #189 as duplicate until its cadence is consolidated. GitHub scheduled workflows run from the default branch and may be delayed. Neither candidate is active until merged. The 15-minute runtime job is additionally blocked until the repository-scoped Debian runner is installed and online.

## 3. Debian cron boundary

Existing #146 and #153 propose automatic update/promotion pollers. They are not authorized for the 48-hour window and are not verified as installed. Do not install or modify crontab, runner service, Docker resources, `deploy/aiops2-stable`, `applied.sha` or deployed images from this architecture change.

Permitted future Debian schedule after operator installation and review:
- Read-only runtime health smoke every 15 minutes, with timeout, lock, bounded output and alert on failure.
- Daily local diagnostics/backup verification only after storage/retention and resource budget are approved.
- Deployment remains manual/approved, exact-SHA, backup-first and rollback-capable. No cron-driven deploy from a development branch.

## 4. Runner and deployment controls

- Repository-scoped runner only; never accept untrusted pull-request code on a Docker host.
- Run as an unprivileged service account; least-privilege read-only Docker access.
- No registration token in Git, shell history, chat or artifacts.
- Runner availability, host identity and exact deployed image must be verified before claiming runtime smoke.
- Runtime smoke is not Temporal E2E, model quality qualification or LIVE readiness.
- Stable promotion requires approved PR, exact source transport, source/runtime equivalence, backup, rollback, health check, manifest/checksum and post-deploy verification.

## 5. 48-hour cadence

- ChatGPT schedules 1/5–4/5: hourly focused work; schedule 5/5 coordinates at H+10 minutes.
- GitHub PR/push checks: on each code change.
- Full suite: one nightly run (plus PR/push).
- Deployed read-only smoke: 15 minutes only when the approved self-hosted runner is online.
- AI benchmark: run on demand after each model/prompt change and once before/after the customer rehearsal; do not schedule repeated GPU-heavy benchmarks without capacity approval.


## 6. Verified trigger audit — 2026-10-30 12:15 UTC

- `main:.github/workflows/quality.yml` has `pull_request` and `push` only, **no schedule**. Neither PR #188 nor #189 is merged, so no GitHub Quality cron can be claimed active.
- #188 head `7512fdd`: full quality `23 2 * * *` and separate `*/15 * * * *` runtime smoke, which requires an approved, online repository-scoped `aiops2-runtime` runner. Its CI passed; no runner or deployed smoke was verified.
- #189 head `233f4ed`: actual YAML `23 */2 * * *`; the PR description's six-hour claim is stale. It duplicates the full quality suite and must not be enabled alongside #188.
- The five ChatGPT schedule cadence is separate from GitHub Actions. #146/#153 auto-deploy remains unauthorized. The stable portal-only deployer cannot install the integrated four-image candidate.


## 4. Operational redirection — 2026-10-30 14:46 Europe/Paris

All five existing ChatGPT schedules were updated to the 48-hour architecture and the saved schedules were asked to run immediately. No sixth schedule was created. Schedule 2/5 Portal was previously paused and has now been re-enabled.

| Schedule | Current owner scope | Immediate direction |
|---|---|---|
| 1/5 | ACME / Twin | Re-audit #198 and source-backed SAN→Payments; keep missing Core Evidence refs UNKNOWN; assess #190 as a main-based minimal fix only |
| 2/5 | Portal | Reuse current main routers; implement a minimal authenticated read-only Run detail route only from existing APIs; no divergent Portal tree |
| 3/5 | NOC / Evidence / GLPI | Re-audit #197, map authenticated read-only relations, do not claim a ticket/Evidence link without source proof |
| 4/5 | Policy / HITL | Re-audit #199 and #194 contracts; SIMULATE only; failure-injection tests for Critic/Policy/HITL/outbox |
| 5/5 | Architecture / benchmark / release | Coordinate exact SHAs, resolve overlap, benchmark AI, update ADR/reuse register and rebuild one cumulative kit |

The saved schedules retain their existing cadence. Immediate-run requests confirm only that runs were requested; they do not mean the work has completed. Handoffs must include exact branch/base/SHA, commands, test counts, Actions links and explicit UNKNOWN/NOT_TESTED limitations.

## 5. GitHub Actions versus Debian cron

- The repository's existing PR/push quality workflow remains the authoritative continuous test path.
- #188 is still the preferred candidate for one daily full quality run plus a 15-minute **read-only** runtime smoke, but it is unmerged and the self-hosted runner is not attested.
- #189 remains a duplicate two-hour quality cron and must not be enabled alongside #188.
- #146/#153 auto-deployment schedules remain disabled. No 5-minute or 15-minute auto-deploy is authorized.
- No Debian host/runner/cron access is available through this GitHub session. Therefore no crontab, systemd unit, Docker service, volume, deployed image or `applied.sha` was changed. The host-side installation procedure remains a documented operator task requiring explicit access and change approval.

## 6. Safe activation sequence

1. Merge/review only one consolidated schedule PR after checking its exact base and workflow diff.
2. Install a repository-scoped Debian runner only through an approved change, with a dedicated unprivileged account, restricted labels, no deployment secrets and outbound-only connectivity.
3. Run a manual read-only smoke and verify it cannot POST/PUT/PATCH/DELETE, mutate GLPI or execute remediation.
4. Enable the 15-minute read-only schedule only after runner health, ownership, log retention, alerting and rollback are tested.
5. Keep deployment automation separate. Require a protected release artifact, signed/checksummed manifest, backup, explicit approval, deployer path coverage, health smoke, applied SHA and tested rollback before any deployment schedule is considered.

## 2026-10-31 21:11 Paris — control-plane evidence update

See [Automation Control Plane A/B/C/D](AIOPS2-AUTOMATION-CONTROL-PLANE-2026-10-31.md) and offline heartbeat verifier `scripts/automation_heartbeat_gate.py`. Current five ChatGPT tasks are enabled HOURLY but all return `next_run_time=null`; main Actions has no `schedule`/`workflow_dispatch`, and Debian minute cron remains UNATTESTED. Do not install or modify host scheduling. GitHub scheduled-run API returns zero. Only read-only operator inventory is proposed.
