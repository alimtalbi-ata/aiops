# AIOps 2.0 — Compose source recovery runbook

**Author:** Abdelhalim Talbi  
**Status:** Required before any deployment attempt  
**Mode:** Read-only discovery only

## Why this exists

The 2026-10-19 host audit showed that Docker labels on the running V2 core/worker point to `/home/aiops/aiops2-v8-r4/00-Deployment/compose.yml`, but the path was absent at preflight time. A missing source file must not be recreated from container labels or inferred from a different historical deployment.

## Run on SRV-DEB-05

From the uploaded/extracted V1.1 kit directory:

```bash
cd /home/aiops/aiops2-deployment-kit-v1.1/AIOps2-Deployment-Kit-V1.1
chmod 700 scripts/discover-compose.sh
./scripts/discover-compose.sh
```

Default report directory:

`/home/aiops/recovery/DB-BACKUP-20261019-193924/validation/compose-source-discovery`

The script:
- reads Docker Compose labels from the current V2 containers;
- reports whether labeled files exist and their SHA-256 hashes;
- lists candidate Compose files under `/home/aiops`, excluding recovery/backups and caches;
- does not print environment values or secrets;
- does not restart containers, start workflows or modify databases.

## Decision gates

1. Confirm the candidate belongs to the running `aiops2` deployment by comparing labels, working directory, services and image references.
2. Inspect each Compose override and verify that the candidate set matches the active configuration. Do not print expanded `.env` values.
3. Compare files to GitHub and backups using hashes/diffs; preserve the original source before edits.
4. Check Docker image IDs/digests and daemon logs separately; do not conflate missing Compose source with the reported containerd blob-not-found error.
5. Only after these checks, fix the preflight to use verified paths and run it again.
6. Run deployment in plan-only mode. Never include Temporal, PostgreSQL or other stateful services in a first reconciliation plan.
7. Any apply requires an explicit approval, backup/rollback plan and qualified source/image set.

## Shell/SSH output handling

Use `set -Eeuo pipefail`, restrictive umask, timestamped report files and exit status capture. Run scripts from a stable SSH session; if the session drops, reconnect and inspect the report file rather than assuming the command completed. Avoid copying terminal output containing credentials. Preserve exact errors and hashes.

## Current status

- Runtime audit: captured.
- Preflight: failed because the labeled Compose path was missing.
- Compose source recovery: pending operator execution.
- Deployment and production qualification: not run.
