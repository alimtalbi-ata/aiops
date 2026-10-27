# Debian installation and controlled upgrade kit

**Status:** initial source implementation; NOT runtime-qualified on a Debian host. This kit does not claim a zero-downtime upgrade, transactional rollback, verified backup or completed migration. No production actions were performed.

## Existing stack and intended deployment

The main branch already provides `deploy/install.sh`, `deploy/init-env.sh`, `deploy/preflight.sh`, `compose.yml`, `tests/qualification.sh` and `tests/synthetic-e2e.sh`. The installer initializes secrets, builds, starts the stack and launches a synthetic demo. **Do not run it on an existing host without an approved change window and inventory.** The Compose project is `aiops2`; legacy AIOps services and volumes must be inventoried separately.

## Installation on a new, isolated Debian host

1. Inventory OS version, architecture, disk, ports, DNS, firewall, Docker/Compose and conflicts with legacy services.
2. Verify source SHA and review Compose images, secrets and network isolation.
3. Run `bash deploy/debian-preflight.sh` (read-only; no environment creation).
4. Back up or snapshot the host before any installation; confirm port availability and data isolation.
5. After authorization, run `bash deploy/install.sh` in a maintenance window. This creates `.env` only if absent and runs qualification and synthetic E2E. Do not set `RETIRE_LEGACY=1` without a separately approved retirement plan.
6. Record actual service health, UI accessibility, workflow execution, CI IDs, qualification outputs and rollback steps.

## Evolution of an existing installation

1. **Inventory**: current Git SHA, Compose config, running containers, service/volume/network names, .env location, ports, DB schemas, host resource pressure and pending migrations. Do not print secrets.
2. **Read-only plan**: `bash deploy/upgrade.sh --plan`. This validates Debian, tools, Docker, existing `.env`, Compose syntax, reports services and source SHA; it does not change services.
3. **Backup and verify**: perform *external* consistent backups of PostgreSQL, Temporal PostgreSQL, GLPI MariaDB, named volumes, `.env` (securely), config and current source/image digests. Restore-test on a separate host. Create an operator-controlled `BACKUP-VERIFIED` marker in a restricted absolute backup directory only **after** verification; the script checks the marker but cannot verify backup contents.
4. **Assess compatibility**: compare DB migrations, API schemas, Compose versions and port collisions. Resolve incompatible or irreversible changes separately; do not run `docker compose down -v` or `--remove-orphans` as an upgrade shortcut.
5. **Approve maintenance window**: document change ID, authorized actor, host name, downtime expectations, snapshots, rollback owner and acceptance tests. Review all images for mutable tags and pin digests for reproducibility.
6. **Controlled apply** (only after all gates): `AIOPS_UPGRADE_APPROVED=1 bash deploy/upgrade.sh --apply --backup-dir /absolute/verified-backups --confirm-host "$(hostname)"`. This builds and updates the Compose project in place, does not delete orphan services or volumes, and runs the existing qualification script. It **does not** run synthetic E2E or apply schema migrations explicitly. **Caution:** Compose `up -d` may recreate containers and cause downtime. Orphans are preserved because no `--remove-orphans` option is supplied.
7. **Post-upgrade**: verify business flows, database health, Temporal workflow durability, GLPI and Portal, monitoring and security gates. Run synthetic E2E only in a fenced test environment, never on production without approval.
8. **Rollback**: stop the rollout, restore the previous pinned source/images and database/volume snapshots under the approved procedure. A code-only rollback may be unsafe after a schema migration. No automatic rollback is claimed.

## Fail-closed conditions

No existing `.env`, missing Debian/Docker/Compose prerequisites, failed existing secret preflight, invalid Compose, absent backup verification marker, hostname mismatch or missing approval flag blocks apply. Preflight reports metadata but must not print environment variables or passwords. Manual approval remains mandatory.

## Future hardening before production qualification

- Add manifest/packaging command with source SHA, image digests, checksums, SBOM and signed release artifacts.
- Add verified DB-specific backup/restore playbooks and migration compatibility matrix.
- Add explicit port/service conflict checks, systemd maintenance handling, network fencing, health-based phased rollout, structured logs and operator-friendly reports.
- Test the upgrade on a restored clone of the Debian server, including interrupted upgrade, insufficient disk, bad migration and rollback.
- Review PR #36 candidate kit scripts for reusable manifest/checksum ideas, without importing its entire divergent branch.
- Keep the five continuity docs and per-schedule logs updated; no automatic merge or production cutover.

## Source review and qualification statement

This PR adds a conservative preflight and opt-in upgrade wrapper. **Not tested** on the target Debian server; no Docker runtime or database migration test was executed. A successful preflight is not proof of upgrade safety. `tests/qualification.sh` currently checks container presence and a subset of HTTP endpoints; it is not a complete application/DB/business qualification.

## Confirmed target endpoint and single-portal constraint (user supplied 2026-10-27)

- Target Debian host: `10.79.94.202` (private network address); authoritative user-facing entry point: `http://10.79.94.202:17777/`.
- All AIOps functions must be reachable **through this portal** (NOC, incident/run, investigator, authorized knowledge, ACME twin, HITL, remediation lab, evidence, observability and admin). This is a navigation/API gateway requirement, **not** a mandate to publish all backend ports or co-locate services.
- **Port mismatch to resolve before upgrade:** reviewed `main` Compose publishes `7777:777`, while the reported existing host uses `17777`. The current host routing, reverse proxy, containers, listener ownership and firewall have **not** been inspected. Do not change a published port, add a competing listener or cut over without a read-only inventory and explicit plan.
- Target design: preserve the existing `17777` entry point, route component views through a single authenticated portal/reverse-proxy layer, keep Core/Temporal/DB/GLPI/n8n internal unless expressly justified, enforce SSO/RBAC and per-feature authorization, and show explicit unknown/unavailable states instead of synthetic runtime claims.
- Required acceptance: `GET /` serves the single shell; route inventory proves mounted paths; NOC and incident drilldowns show authorized real data only; protected APIs reject unauthenticated requests; synthetic/demo data is labeled; no extra exposed production listener; existing bookmarks remain functional; authenticated E2E on a staging clone and rollback pass.
- **No claim** that `10.79.94.202:17777` was reached or inspected; it is user-reported information. Never include private host credentials in this repository.

## 2026-10-27 development increment — portal port gate

`deploy/portal-port-audit.py` inspects normalized Compose JSON in read-only mode. It compares the published `aiops2-portal` port with the target `17777` and reports `BLOCKED` if the declaration differs. This is **not** a live listener or reverse proxy probe. The upgrade `--plan` displays this audit without mutating the host. `--apply` fails closed on a mismatch unless the operator has independently verified the existing reverse proxy/listener mapping and explicitly sets `AIOPS_EXTERNAL_PORTAL_VERIFIED=1` alongside all other approval/backup conditions. Do not set this override merely to bypass a failure. The main Compose declaration is currently `7777:777`, so the gate is expected to report a mismatch until the real host routing is inspected. Unit tests: `python3 -m unittest discover -s tests -p 'test_portal_port_audit.py' -v`. Tests were exercised against a matching local test fixture, but not against the Debian host.

## Backup inventory development increment

`python3 deploy/backup-inventory.py` generates a **read-only** inventory from normalized Compose JSON. It checks PostgreSQL, Temporal PostgreSQL, GLPI MariaDB, plus persistent GLPI/n8n/Grafana/Prometheus volumes. Missing service/volume declarations block the plan. `--output /restricted/new-file.json` writes an inventory file with mode `0600` and refuses overwrite; it is **not a backup**, a restore proof or a change approval. Offline fixtures may be checked with `--config-file`. Unit tests: `python3 -m unittest discover -s tests -p 'test_backup_inventory.py' -v`. These tests have not been run against the target host. This is a prerequisite for actual database-aware backup tooling, not a replacement for it.
