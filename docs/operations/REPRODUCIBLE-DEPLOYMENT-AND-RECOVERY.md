# Reproducible AIOps2 deployment and recovery on a second server

**Status:** Deployment standard proposed; release-kit gaps explicitly tracked  
**Applies to:** AIOps2 lab / customer demonstration environments  
**Reference host:** SRV-DEB-05 (Debian 13 Trixie)  
**Related PR:** #214  
**Security:** No shared default secrets. No LIVE remediation or production deployment authorization.

## 1. Objective

A second server must be installable from a reviewed, immutable Git revision and documented configuration without relying on shell history, a developer workstation, old conversations, manually copied containers or undocumented state from SRV-DEB-05.

A reproducible deployment is not just a Compose file. The deliverable must include:
- source revision and dependency/image versions;
- host prerequisites and preflight checks;
- configuration template and unique secret generation;
- database schema/migration inventory and supported upgrade path;
- persistent-volume inventory and backup/restore procedure;
- install, start, health verification and qualification commands;
- external integration setup (GLPI, OIDC, Temporal, monitoring, model providers);
- rollback and disaster-recovery steps;
- sanitized acceptance evidence.

## 2. Known repository assets (verified by inspection)

| Asset | Current role | Reproducibility note |
|---|---|---|
| `compose.yml` | Main Compose topology | Pin the exact Git commit and image tags/digests for a release. |
| `config/.env.example` | Environment variable template | Contains empty secret values; never copy secrets from SRV-DEB-05. |
| `deploy/init-env.sh` | Creates a new `.env` and random secrets | Uses OpenSSL; keeps secret values out of stdout. |
| `deploy/check-secrets.sh` | Secret policy validation | Must pass before Compose startup. |
| `deploy/preflight.sh` | Docker/Compose, disk, files and config preflight | Current minimum free-space gate is >8 GiB. |
| `deploy/install.sh` | Initialize env, preflight, build, start, qualification and synthetic E2E | Review side effects and target host before use. |
| `00-Deployment/install.sh` | Copies source into a new target tree | Updated to use generated secrets rather than embedded shared credentials. |
| `00-Deployment/start.sh` | Compose build/start | Start only after secrets and preflight pass. |
| `db/migrations/*.sql` | PostgreSQL initialization schema/seed assets | Compose mounts these into PostgreSQL's init directory; Docker entrypoint initialization normally applies them only to a new empty data volume. This is not a general upgrade mechanism. |
| `scripts/install-debian-reporter.sh` | Read-only Debian observation agent | Separate from platform installation; do not treat it as an application deployment mechanism. |

The repo also contains legacy deployment entrypoints. For a new server, use one documented path only; do not combine legacy installers or copy a live `.env` from another host.

## 3. Security correction

The previous `00-Deployment/install.sh` appended the same hard-coded password/token values to new installations. This was not acceptable for multi-server reproducibility.

It has been corrected on this branch to call `deploy/init-env.sh` and `deploy/check-secrets.sh`, which generate per-install random values and validate them. Do not use old copies of the installer or manually reproduce the former static credentials. Rotate any credentials if those values were ever used on a reachable system.

Every server must have unique:
- PostgreSQL and MariaDB credentials;
- application admin/internal tokens;
- Grafana administrator password;
- n8n encryption key;
- OIDC client secrets and integration tokens.

Secrets must be stored in a host-approved secret store or protected `.env` file (owner restricted, mode 0600); never commit them, paste them into CI logs, or include them in support bundles.

## 4. New-server installation procedure

### 4.1 Release selection

Do not deploy from a moving development branch. A release candidate must first pass the required GitHub Actions checks and be approved. The release record must include:
- immutable commit SHA;
- release tag (once established);
- CI run URLs and conclusions;
- Compose config validation result;
- image digests or immutable tags;
- database migration manifest;
- known issues and rollback target.

At the time this document was written, the branch under active work is not declared a customer release. No release tag is asserted here.

### 4.2 Host prerequisites

The current reference host is Debian 13 x86_64. The installation preflight checks Docker, Compose v2, required files and free disk space, but does not yet enforce a formal supported-OS matrix.

Before supporting a second server, record and validate:
- Debian release and architecture;
- Docker Engine and Compose plugin versions;
- CPU, RAM, swap and free disk by filesystem;
- required inbound ports and bind addresses;
- DNS, NTP/time synchronization and outbound registry/model-provider access;
- storage driver, filesystem and persistent-volume locations;
- backup destination and restore capacity.

Do not run the installer as root. Do not use `sudo` as part of the application deployment procedure. Host-level Docker installation and account provisioning are separate infrastructure prerequisites performed under the customer's host-management process.

### 4.3 Obtain the reviewed source

After a release tag exists, the documented pattern is:

```bash
git clone --branch <approved-release-tag> --depth 1 <repository-url> aiops2
cd aiops2
git rev-parse HEAD
```

The operator must compare the displayed SHA with the approved release record. Until a release tag is published, use only an explicitly approved immutable commit SHA for lab qualification; do not invent or assume a tag.

### 4.4 Preflight, secrets and installation

The intended canonical sequence from the repository root is:

```bash
bash deploy/preflight.sh
bash deploy/init-env.sh
bash deploy/check-secrets.sh .env
chmod 600 .env
docker compose --env-file .env config
```

Note: `deploy/preflight.sh` itself invokes the environment initializer, so a fresh install creates the `.env` file once and later invocations preserve it. Review generated configuration without printing secret values.

For a reviewed full lab deployment, the repository entrypoint is:

```bash
bash deploy/install.sh
```

It initializes/validates configuration, builds images, starts Compose services, then runs qualification and synthetic E2E scripts. This is an application deployment and will create/update containers and persistent resources. It must not be run against an existing customer environment without a backup, change approval and target review.

Alternative source-tree staging via `00-Deployment/install.sh` copies the checkout into `/home/aiops/aiops2-v8` by default and prepares a fresh secret file; its output explicitly instructs the operator to run `00-Deployment/start.sh` separately. Do not use both paths on the same target.

### 4.5 Post-install acceptance

A server is not considered reproducible/accepted merely because `docker compose up` succeeds. Require:
1. `docker compose ps` has all mandatory services running and healthy (or documented healthcheck exception).
2. Core, Twin, Evidence, Policy, Worker, Simulator and Portal health endpoints pass.
3. PostgreSQL and Temporal persistence checks pass.
4. GLPI and MariaDB application-level checks pass.
5. Grafana/Prometheus scrape and dashboard checks pass.
6. Synthetic scenario completes and evidence is persisted.
7. HITL DEMO/REPLAY/STORY behavior is verified; LIVE remains locked.
8. CI qualification, offline integrity and synthetic E2E pass.
9. A sanitized deployment manifest and acceptance report are archived.

## 5. Database and state portability

A second server must not be populated by copying live Docker volumes or copying the source host's `.env`.

Before a migration/restore procedure can be called supported, create and test:
- a versioned inventory of PostgreSQL and MariaDB databases, schemas and extensions;
- a migration manifest with ordered IDs, checksums, compatibility and rollback classification;
- explicit distinction between fresh initialization scripts and upgrade migrations;
- consistent backups for PostgreSQL, MariaDB, GLPI files/documents and required application state;
- encryption and access control for backup artifacts;
- restore into an isolated clean host with integrity checks;
- documented RPO/RTO and data-loss limitations.

The current Compose PostgreSQL service mounts `db/migrations` into `/docker-entrypoint-initdb.d`. That directory is suitable for initialization of a new empty database volume; it does not automatically apply new SQL files to an already initialized database. A separate migration runner and tested upgrade/rollback process are release blockers for reliable in-place upgrades.

Do not assume that Temporal history, GLPI document storage, n8n credentials/workflows, Grafana dashboards, Prometheus data or model artifacts are all captured by the PostgreSQL backup. Each persistent volume and external integration must be inventoried.

## 6. Configuration and integration inventory

Maintain a generated, secret-free `deployment-manifest.json` containing:
- release SHA/tag and build time;
- host OS/architecture and Docker/Compose versions;
- Compose project name and service/image references;
- image digests;
- migration IDs/checksums;
- enabled integrations and endpoint hostnames (never credentials);
- exposed ports/bind addresses;
- volume names and backup identifiers;
- qualification run URLs and acceptance status.

Maintain a separate secret inventory with secret *names*, owner, source, rotation date and dependent services only. Never export secret values.

External integrations (OIDC provider, GLPI API, model endpoints, SMTP, monitoring, GitHub reporting) must be configured independently per target. A successful core install does not imply that these integrations are connected.

## 7. Backup, restore and rollback

Before any upgrade:
1. Record release SHA and Compose state.
2. Capture sanitized configuration manifest and migration status.
3. Verify backup freshness and restore access.
4. Back up databases and all persistent application/document volumes using service-consistent methods.
5. Verify checksums and retain a protected copy off-host.
6. Record rollback target and compatibility of schema/data with that version.

Rollback of application images is not necessarily a database rollback. Do not downgrade schema by simply starting old images. If a migration is irreversible, restore a consistent backup into a recovery environment and document the resulting RPO.

A restore drill on a second clean server is required before calling the kit disaster-recovery ready.

## 8. Release-kit acceptance checklist

- [ ] One canonical new-server install path; legacy entrypoints clearly marked.
- [ ] Immutable release tag/SHA and image digests.
- [ ] Per-install unique secret generation; no default credentials.
- [ ] Formal supported Debian/Docker/Compose matrix.
- [ ] Host resource/port/network preflight documented.
- [ ] Complete Compose service, volume, port and external dependency inventory.
- [ ] PostgreSQL and MariaDB migration manifest and upgrade runner.
- [ ] GLPI database plus document/files backup and restore.
- [ ] Temporal, n8n, Grafana and Prometheus state backup strategy.
- [ ] Clean-server installation CI or reproducible integration environment.
- [ ] Post-install health, synthetic E2E and security acceptance.
- [ ] Restore drill on a different server with recorded RPO/RTO.
- [ ] Rollback and disaster-recovery runbooks.
- [ ] Customer-facing deployment manifest and sanitized evidence bundle.

## 9. Current status — do not overstate readiness

| Capability | Status |
|---|---|
| Compose topology and service definitions | Exists; release pinning still required |
| Environment template | Exists |
| Per-install random secret generation | Exists in `deploy/init-env.sh` |
| Legacy installer static-secret defect | Corrected on this branch; must pass CI |
| Basic Docker/Compose/disk preflight | Exists; OS/resource matrix incomplete |
| Build/start/qualification entrypoint | Exists |
| PostgreSQL initialization SQL | Exists |
| General PostgreSQL/MariaDB upgrade runner | Not yet demonstrated |
| Consistent all-service backup | Not yet demonstrated |
| Full clean-server restore drill | Not yet demonstrated |
| Immutable customer release tag and manifest | Not yet established |
| Debian reporter | Separate read-only observer; not a deployment agent |

AIOps2 is therefore **partially reproducible**, not yet certified for one-command customer installation or disaster recovery. The next engineering work must close the release, migration, backup and restore gaps and demonstrate installation on a clean second server.

## 10. Documentation change policy

Every PR that changes installation, Compose, environment variables, database schema, volumes, secrets, integrations or runtime behavior must update this guide and the architecture roadmap. Each change must state:
- exact files/config/schema and compatibility impact;
- test commands and CI run URLs;
- whether only CI, a lab host, or a second clean host was verified;
- backup/rollback steps;
- remaining risks and operator actions.

Never mark a feature "deployed" based only on a CI build. Use separate statuses: implemented, unit-tested, CI-qualified, installed on reference lab, verified on second host, customer-release approved.
