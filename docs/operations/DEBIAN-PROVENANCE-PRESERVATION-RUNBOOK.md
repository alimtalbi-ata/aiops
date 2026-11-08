# SRV-DEB-05 — Preservation-first provenance collector review

Status: **DRAFT / operator-run only / not installed / not a backup**. This document belongs to PR #452 and does not authorize a Debian change.

## 1. Existing runtime and control-plane baseline

Reuse the four existing `aiops` crontab entries and their responsibilities. In particular, `~/.local/bin/aiops-debian-reporter` already collects `latest.json` and `~/.local/bin/aiops-publish-report` already publishes it via SSH to `ops/debian-runtime-reports`. The current publisher's path is `ops/debian-reports/SRV-DEB-05/latest.json`. Do not add a fifth cron, alter the live deploy poller, modify the filesystem watcher or assume the publisher has already succeeded.

The five *Compose projects* previously observed (not cron jobs) are `aiops2-rebuild`, `aiops2-v27-qual`, `aiops2-e2e-v1`, `aiops2-metrics-cutover`, `aiops2-demo-observability`. Prior host observation was 78 containers, 59 volumes and 18 networks; these are historical counts, not a new live inspection.

## 2. Review-only collector

Source: `scripts/ops/debian_provenance_snapshot.py`. Offline tests: `tests/test_debian_provenance_snapshot.py`. Existing CI: `.github/workflows/quality.yml` step `Debian provenance collector offline regression (no Docker host access)`.

On a reviewed checkout, the operator can validate Python syntax and run offline tests without connecting to Docker:

```sh
python3 -m py_compile scripts/ops/debian_provenance_snapshot.py
python3 -m unittest discover -s tests -p 'test_debian_provenance_snapshot.py' -v
```

**Only after checking the code and choosing an appropriate private local destination**, the operator may manually invoke the read-only inventory:

```sh
umask 077
python3 scripts/ops/debian_provenance_snapshot.py --output "$HOME/aiops2-provenance-review.json"
```

The output is **exclusive-create**: a second run refuses to overwrite an existing file. Keep the file local until its mount paths, Compose locations, project labels, image tags and network names are reviewed for disclosure. Do not send it to GitHub automatically. If Docker access is missing, record the error and stop rather than escalating to sudo or mutating permissions.

The script reads Docker metadata and hashes existing Compose YAML files, but never copies image layers, Compose file contents, volumes, database contents, Git worktrees or credentials. The report's 48-hour window is only a reference time interval, not a deployment chronology. `Created` and `StartedAt` cannot alone prove a deployment in that interval.

## 3. What must be attested before a selection

| Evidence | Required | Current state |
|---|---|---|
| Container -> immutable image ID/digest | Docker inspect, verified against running host | UNKNOWN |
| Container -> Compose project/service and effective overrides | Labels, actual files and SHA-256; inspect drift | UNKNOWN |
| Image -> source Git commit and dirty worktree | Build provenance/receipts, explicit operator review | UNKNOWN |
| Recent 48h deployment chronology | Deploy receipts/logs, source/build mapping, operator confirmation | UNKNOWN |
| Persistent volumes and simulated data | Mount inventory + separate backup manifest | UNKNOWN |
| Verified backup and restoration | Offline copies, checksums and restore test, separately approved | NOT_DONE |
| Component features and contract/schema parity | Source comparison and targeted test receipts | PARTIAL_GITHUB_ONLY |
| Exact candidate integration/E2E | CI plus host/operator proof where required | PARTIAL_GITHUB_ONLY |
| Rollback to installed baseline | Image/config/data recovery plan, validated | NOT_DONE |

A collector success alone does not satisfy the preservation gate G0 or technical gate G1. It only reduces uncertainty about current runtime identity.

## 4. Comparison and no-regression rules

For each of Core, Worker, Policy, Twin, Evidence, Portal, Intelligence and Temporal:

1. Keep every installed component and its recent development artifacts untouched.
2. List same-function candidate variants and exact SHAs, distinguishing source, image and deployment.
3. Mark a feature as PRESENT only if implemented and evidenced; otherwise UNKNOWN, not ABSENT.
4. Block replacement if an installed feature is missing in a candidate, unless a separate reviewed patch restores it.
5. Require exact-head feature-specific tests, API/DB contract compatibility, integration/E2E, operational readiness and validated rollback before promotion.
6. Prefer additive cherry-picks/patches to wholesale version replacement when safer.

Priority GitHub candidates for comparison: Twin Decimal metrics PR #448 (operator-reported host tests; confirm source/image mapping), Worker V28 isolation PR #431 (CI green, host E2E unknown), Worker FS147 PR #443, Core HITL PR #450, Twin FS147 PR #451 (migration CI failure), Worker guard PR #446 (migration CI failures), Portal PR #438 (backend/E2E missing). FS147 release PR #449 remains NO_GO (runtime-e2e and package-build failures).

## 5. Stop conditions

Do not merge, deploy, restart, migrate, prune, delete, alter crontab, publish unreviewed metadata, approve HITL, or write to GLPI/Temporal. Do not assume an SSH session or a Debian backup exists. The operator must explicitly approve any runtime integration and any backup procedure after reviewing its storage and impact.
