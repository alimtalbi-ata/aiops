# AIOPS2 — One-Stack Runtime Convergence Plan

**Date:** 2026-11-11  
**Repository:** `alimtalbi-ata/aiops`  
**Target:** Debian SRV-DEB-05, Docker rootless user `aiops` (UID 1001)  
**Status:** Inventory-backed plan; runtime changes NOT executed.

## 1. Binding operating decision

AIOPS2 must converge to **one operational Docker Compose project**. Only containers required by that consolidated stack remain running during normal operation.

All other test, qualification, demo, candidate, rollback and historical containers are not permanent runtime services. Their useful capabilities, code, configuration and tests must first be recovered, integrated into the canonical stack, and validated. Once validated, non-target containers should be stopped and retained only as long as needed for rollback/evidence; removal is a separate later approval.

Every useful finding, migration, image/source mapping, test result and operational procedure must remain documented in this GitHub repository. Conversation history is not the system of record.

### Lifecycle vocabulary

| State | Meaning |
|---|---|
| `RUN` | Required service in the single canonical runtime stack |
| `STOP/KEEP` | Non-target container stopped after dependency/data checks; retained temporarily for rollback or evidence |
| `REMOVE` | Eligible for removal only after recovery, backup, validation, and explicit approval |
| `UNKNOWN` | Ownership or dependency not sufficiently established; do not change |

**No action is implied by assigning a provisional state in this document.**

## 2. Runtime facts confirmed by operator

- Docker rootless context: `rootless`, endpoint `unix:///run/user/1001/docker.sock`.
- User service `docker`: active.
- Docker data root: `/home/aiops/.local/share/docker`.
- Snapshot: 87 containers and 210 images.
- The `default` context points separately to `/var/run/docker.sock`; do not use it for this project.
- Runtime operations must be performed as user `aiops`, not with `sudo docker`.

Five Compose projects were reported:
- `aiops2-rebuild` — candidate runtime project; Compose reports 14 running, 7 exited, 1 created.
- `aiops2-metrics-cutover` — 3 running, 1 exited; it currently owns containers named `aiops2-rebuild-worker`, `aiops2-rebuild-evidence`, and `aiops2-rebuild-policy`.
- `aiops2-e2e-v1` — 10 running, 2 exited.
- `aiops2-v27-qual` — 10 running, 2 exited.
- `aiops2-demo-observability` — 3 running.

Container names do not establish Compose ownership. Use Compose labels and config-file labels.

## 3. Canonical target and source-of-truth rule

The repository `compose.yml` on `main` is the declarative starting point for the consolidated stack, not proof of the exact configuration currently running on SRV-DEB-05.

The candidate runtime project `aiops2-rebuild` is not yet a clean, standalone canonical project: its Compose ownership references a fragmented set of 17 Compose/override files across rebuild, demo, patches, backup, NOC/RAG and temporary locations. Do not run this multi-file configuration blindly.

Create one version-controlled canonical Compose manifest (plus only explicitly approved, versioned overrides if absolutely necessary). Compare its service definitions with the live deployment and the current `compose.yml`; record every intentional difference.

## 4. Service recovery and provisional lifecycle matrix

| Runtime item | Observed fact | Provisional treatment |
|---|---|---|
| Core, Portal, Twin, Intelligence | Active rebuild-named services; some have no reliable Compose ownership in supplied excerpt | `RUN` candidate; verify exact dependencies and image provenance |
| Worker, Evidence, Policy | Names begin `aiops2-rebuild-`, but Compose ownership is `aiops2-metrics-cutover` | `RUN` candidate; migrate ownership/config into canonical project only after parity tests |
| Simulator, Copilot | Active rebuild-named services | Validate whether required in normal runtime; then `RUN` or `STOP/KEEP` |
| PostgreSQL application, Temporal PostgreSQL, Temporal server/UI/schema | Active and separately persisted | `RUN` if required by production workflows; preserve DB separation |
| GLPI + MariaDB, n8n | Active with persistent data | `RUN` only if these integrations are part of the agreed operational product |
| Prometheus, Grafana, Alertmanager | Active; Prometheus config has an external FS patch bind mount | `RUN` if observability is part of baseline; version and migrate config first |
| E2E, v27 qualification, v29/FS qualification | Test/qualification containers and projects | `STOP/KEEP` after tests and evidence are captured |
| Demo observability (OTel/Loki/Tempo) | Separate demo project | Recover required observability features/config; then `STOP/KEEP` |
| CloudBeaver, test LLM, NOC/RAG test containers, HTTP qualification, FS lab/ingest | Utility or test containers; business necessity not yet demonstrated | `UNKNOWN`; decide individually, do not keep running by default |
| Portal/Core/Twin rollback containers | Historical images/containers | `STOP/KEEP`; retain through acceptance and rollback window |
| Metrics normalizer and demo web/read-only containers | Test/experimental containers | `STOP/KEEP` after capability extraction and validation |

This matrix is deliberately provisional. Do not stop a service solely because its name looks like a test, and do not keep a service running solely because its name begins `aiops2-rebuild`.

## 5. Persistent data — protect before lifecycle changes

Confirmed rebuild volumes include:

- `aiops2-rebuild-postgres-data` → PostgreSQL application data.
- `aiops2-rebuild-temporal-postgres-data` → Temporal PostgreSQL data.
- `aiops2-rebuild-glpi-db-data` → GLPI MariaDB data.
- `aiops2-rebuild-glpi-data` → GLPI files.
- `aiops2-rebuild-grafana-data` → Grafana state.
- `aiops2-rebuild-n8n-data` → n8n state/workflows.
- `aiops2-rebuild-prometheus-data` → Prometheus TSDB.
- `aiops2-rebuild_aiops2-fs-demo-data` → FS Demo data.

Other test/qualification/recovery volumes exist (E2E, v27, v28 SQL, v29, FS qualification, GLPI recovery, CloudBeaver and demo observability). Keep them until their contents, owners and retention requirements are established.

Two FS volumes are shared by the active Portal and multiple rollback Portal containers:
- named volume `aiops2-rebuild_aiops2-fs-demo-data`, mounted at `/data/fs-demo`;
- anonymous volume `a353205c8c462b13f0538ea1b210bec7aa4824415a27c4e551e0c5ff4bbb076e`, mounted at `/var/lib/aiops-fs-demo`.

Do not remove either volume when retiring rollback containers. More generally, a volume must not be deleted because it is anonymous, old, or apparently unused; verify mounts across active and stopped containers and take a tested backup first.

## 6. External bind mounts that must be internalized

The active Worker uses files from `/home/aiops/aiops2-patches/fs-portal-v30/`:
- `runtime/fs-bridge` → `/run/aiops2-fs-bridge`;
- `build/app/worker/fs_lab_activity.py`;
- `build/app/worker/fs_lab_evidence.py`;
- `build/app/worker/main.py`;
- `build/app/worker/workflow.py`.

Observed SHA-256:
- `fs_lab_activity.py`: `90e7bf8bd81136f11680f62864730a8ec2854c4a221a63c093fef164fb0d8b4c`
- `fs_lab_evidence.py`: `27787fbff5b80d08a7ba7ac25908a4f7f46d3dbf3700378eb5b980dbfc6ef1fc`
- `main.py`: `3d2137540c73fab8fb484f802ed283879a0db51a2094805d6d0deee9e6739e88`
- `workflow.py`: `947aaa5cf29e7cff5b34596a69ea68a92c56e768167ab6bfaf62d0b9fc3bb9c5`

The patch directory is not itself a Git repository (`git rev-parse HEAD` failed). The source commit/branch must be located or these exact files imported into a tracked source repository with documented provenance before rebuilding the Worker.

The patch directory contains `runtime/fs-bridge/bridge.token`. Never display, copy into issues, commit, or expose its contents. Treat it as secret material; only document the secret reference/rotation procedure.

Prometheus mounts `/home/aiops/aiops2-patches/fs-portal-v30/build/prometheus-fs` to `/etc/prometheus`. Bring this configuration into version control and validate it before rebuilding Prometheus.

## 7. Image provenance

Record for each target service: container name, Compose project/service labels, configured image reference, immutable image ID/digest, source repository, commit/build provenance, configuration, and successful test evidence.

The operator supplied image IDs for active and stopped containers. Several candidate and rollback images exist. Tags and age alone do not establish whether an image can be removed. Keep rollback images through the acceptance period; do not prune.

## 8. Fast, safe execution sequence

1. Freeze the current inventory as evidence: Compose project labels/config paths, all containers (including stopped), mounts, volume labels, networks, ports, health, image IDs, and bind-mount hashes.
2. Build a complete service dependency map and classify every container `RUN`, `STOP/KEEP`, `REMOVE`, or `UNKNOWN`.
3. Recover unique features from metrics-cutover, E2E, v27, v29, FS qualification, demo observability, NOC/RAG and rollback candidates. Link each feature to source files/commit, tests, dependencies, and target service.
4. Internalize external Worker and Prometheus bind mounts into versioned source; remove all runtime dependencies on ad-hoc patch directories.
5. Author one canonical Compose project with explicit service names, networks, healthchecks, secrets references and named persistent volumes. Preserve separate application and Temporal databases.
6. Validate rendered Compose configuration without exposing secret values. Run static, unit, integration, security, migration, FS, Portal, GLPI, n8n, Temporal and observability tests.
7. Back up required data and prove restore procedures. Plan a reversible cutover with explicit acceptance criteria.
8. After approval and successful cutover, stop non-target projects in controlled batches. Keep rollback containers/data for the agreed retention period.
9. Remove obsolete containers/images/volumes only after a separate review and explicit authorization. Never use broad prune commands.

## 9. Immediate safety boundary

No remote shell access to SRV-DEB-05 is available through this GitHub documentation workflow. No container has been stopped, started, recreated or removed; no volume/image/network has been modified; no database migration or data copy has been performed.

Until a validated per-container lifecycle list and a migration/rollback plan are approved:
- no `docker compose down`, `stop`, `rm`, `prune`, `volume rm`, `image rm`;
- no `compose up` or recreate;
- no data-root, network, port or secret changes;
- use the rootless `aiops` Docker context only.

## 10. Acceptance criteria for "one stack"

- Exactly one intended Compose project is operational for AIOPS2.
- Every running AIOPS2 container belongs to that project and has an approved service purpose.
- No runtime bind mount depends on an untracked temporary/patch directory.
- Every required persistent dataset is attached to the intended service and has a tested backup/restore path.
- No duplicate test/demo/qualification service remains running.
- All recovered features have source provenance and passing regression evidence.
- Core/Portal/Worker/Twin/Policy/Evidence, FS workflows, Temporal, GLPI/n8n integrations and observability pass the agreed operational tests.
- GitHub contains the canonical Compose, service/data inventory, recovery matrix, image provenance, migration journal, rollback procedure and operator runbook.
