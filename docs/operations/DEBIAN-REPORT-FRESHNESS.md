# Debian runtime report freshness

## Design

The Debian reporter remains a local, read-only collector. It publishes one sanitized JSON snapshot every five minutes to the existing Git branch `ops/debian-runtime-reports`. A GitHub-hosted workflow reads that branch every 15 minutes and checks freshness and the small, explicit runtime contract.

This avoids a self-hosted GitHub runner on SRV-DEB-05, avoids exposing Docker access to GitHub Actions, and does not use SSH or remote shell commands. The workflow only checks a report that Debian has already published.

## Checks

- Snapshot file exists, is a regular file and is no larger than 64 KiB.
- Schema is v3, host label is SRV-DEB-05 and reporter identity is `aiops-debian-readonly/1.1.0`.
- `collected_at` is timezone-aware, no more than 15 minutes old and not materially in the future.
- Required primary containers are observed as running/healthy when Docker inventory is available.
- Published endpoint probes for Portal, GLPI, Grafana, Prometheus and Temporal UI are checked.
- Missing Docker inventory or missing endpoint probes are surfaced as WARN, never silently represented as healthy.
- Unreachable published endpoints and unhealthy/stopped primary containers are surfaced as WARN in the workflow log.

A fresh report means only that the Debian→GitHub telemetry channel is functioning and the reported snapshot is recent. It is not proof of a successful Temporal Run, real NIM Analyst/Critic execution, GLPI synchronization or LIVE qualification.

## Schedule

`.github/workflows/debian-report-freshness.yml` runs every 15 minutes and supports manual dispatch. It uses GitHub-hosted Ubuntu 24.04 only. Scheduled runs become active only after the workflow is merged into the default branch.

## Current blocker

The branch `ops/debian-runtime-reports` exists, but `ops/debian-reports/SRV-DEB-05/latest.json` has not yet been published. The reporter's GitHub Contents token is not confirmed as provisioned. Until a fresh schema-v3 report exists, the scheduled check will fail closed with `report_file_missing_or_unsafe`. This is intentional and must not be reclassified as host health.
