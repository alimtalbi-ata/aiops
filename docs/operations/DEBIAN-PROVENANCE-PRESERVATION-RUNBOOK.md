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


## 6. Compare two independently captured snapshots — offline, no Docker access

The branch also contains `scripts/ops/compare_debian_provenance.py`, with seven offline regression cases in `tests/test_compare_debian_provenance.py`. Once two reviewed, private snapshots exist, compare them locally:

```sh
python3 scripts/ops/compare_debian_provenance.py /private/before.json /private/after.json
```

The comparator reads two local JSON files and prints a JSON diff to stdout; it never calls Docker, GitHub, a network or a deployment tool. It detects added/missing container names, changes to immutable image IDs and Compose project/service/config hash, and differences in Compose YAML SHA-256. It deliberately emits `release_decision: HOLD`, `feature_parity: UNKNOWN`, `deployment_chronology: UNKNOWN` and `backup_restoration: NOT_ATTESTED`, even when the two snapshots are identical. A container name change is not necessarily a removal or new deployment; a missing container can reflect incomplete access. The comparison is evidence for operator review, **not a feature score, backup or automatic release gate**.

The existing `quality.yml` workflow now executes both collector and comparator tests. Generic CI successes are not proof of Debian host behavior.


## 7. Join existing Debian and GitHub evidence — offline

`scripts/ops/join_debian_github_evidence.py` joins an operator-reviewed candidate manifest to an already captured runtime snapshot. It **never** guesses a source SHA from a tag, service name or image creation date. Candidate entries must have `name`, `component`, `github_sha`; optional `verified_runtime_image_id` must be an exact `sha256:...` image ID. Evidence arrays (`features`, `ci_evidence`, `integration_evidence`, `missing_evidence`) are explicitly operator supplied, not auto-certified.

Minimal private local candidate manifest:

```json
{
  "schema": "aiops2-component-candidates-v1",
  "candidates": [
    {
      "name": "Worker V28 isolation",
      "component": "worker",
      "github_sha": "fd347ec92a1ca3d003bbb8daae70dffba117f308",
      "features": ["SAN-write isolation in FS synthetic observation"],
      "ci_evidence": ["PR #431: 18 successful check-run records, some repeated"],
      "integration_evidence": [],
      "missing_evidence": ["deployed source/image linkage", "host E2E", "backup"]
    }
  ]
}
```

Commands on an already reviewed checkout:

```sh
python3 -m unittest discover -s tests -p 'test_join_debian_github_evidence.py' -v
python3 scripts/ops/join_debian_github_evidence.py /private/runtime.json /private/candidates.json
```

The join always returns `release_decision: HOLD` and `backup_restoration: NOT_ATTESTED`. Even an exact claimed image-ID match does not establish build provenance from the GitHub SHA. Independent source/build receipts and Debian backup/restore checks remain mandatory. This step introduces **no new cron, publisher, GitHub API call, Docker mutation, or release promotion**.


## 8. Reviewed GitHub candidate catalogue

The versioned, **non-runtime** input `docs/operations/github-component-candidates-2026-11-08.json` records eight GitHub candidates with exact PR-head SHA, implemented feature claims, known CI evidence and explicit missing host/E2E evidence. These observations are dated 2026-11-08 and must be refreshed before a later release decision. The manifest deliberately contains **no** `verified_runtime_image_id` because the current Debian image/source mapping has not been proven.

When a private, operator-reviewed snapshot is available, run:

```sh
python3 scripts/ops/join_debian_github_evidence.py \
  /private/runtime.json \
  docs/operations/github-component-candidates-2026-11-08.json
```

Keep the resulting report private until all Compose paths, mount sources, tags and service identifiers have been reviewed. Matching by component name is never treated as a deployed SHA. All eight candidates remain `PRESERVE_AND_QUALIFY`, not `GO`; known failed migrations and E2E gates must be resolved separately.
