# SRV-DEB-05 — installation and runtime inventory

> Snapshot date: 2026-11-08 (host-local capture; exact timezone not present in supplied output)  
> Host: `SRV-DEB-05`  
> Working root documented by the project: `/home/aiops`  
> Capture method: read-only Docker inspection supplied in the project conversation.  
> This is a point-in-time observation, **not** a deployment manifest or a statement that every running container is healthy or production-qualified.

## Executive summary

| Measure | Observed |
|---|---:|
| Docker containers (excluding the literal template header in the captured output) | 78 |
| Running | 59 |
| Exited | 18 |
| Created | 1 |
| Compose projects reported by `docker compose ls -a` | 5 |
| Docker networks listed | 18 |
| Docker volumes listed | 59 |

The container-state counts are derived from the supplied `docker inspect` output. The 18-network and 59-volume counts are counts of the entries printed by the corresponding Docker list commands. Health checks are not configured for many containers; `NOT_CONFIGURED` must not be interpreted as healthy.

## Compose projects observed

| Compose project | Observed state | Compose source paths |
|---|---|---|
| `aiops2-demo-observability` | running (3) | `/home/aiops/aiops2-observability-deploy/deploy/observability-demo/compose.yml` |
| `aiops2-e2e-v1` | exited (2), running (10) | `/home/aiops/aiops2-e2e-lab/compose.yml`; `compose.temporal.yml`; `compose.worker.yml`; `compose.intelligence.yml` |
| `aiops2-metrics-cutover` | exited (1), running (3) | `/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml` plus FS worker/core override files and a temporary candidate file (see source audit) |
| `aiops2-rebuild` | created (1), exited (7), running (14) | multiple Compose files and overrides from `aiops2-auto-deploy`, `aiops-v28-demo`, `aiops2-patches`, `aiops2-backups` and `aiops2-noc-rag-work` (see source audit) |
| `aiops2-v27-qual` | exited (2), running (10) | `/home/aiops/aiops2-v27-qual/compose.yml`; `compose.worker.yml`; `compose.temporal.yml`; `compose.intelligence.yml`; `compose.v27.yml` |

Important: Docker reports some containers under a project name that differs from the apparent container name (for example, the worker is named `aiops2-rebuild-worker` but carries the `aiops2-metrics-cutover` Compose project label). Inventory and consolidation must use Docker labels and actual Compose files, not container names alone.

## Runtime components and observed function

The function descriptions below combine the repository's [component catalog](../COMPONENT-CATALOG-AND-REUSE.md) with the observed image/container names. They describe intended responsibility, not proof of end-to-end qualification.

| Capability | Observed installation evidence | Intended function / boundary |
|---|---|---|
| Portal / Command Center | `aiops2-rebuild-portal`; candidate and rollback portal containers | Operator experience, incident/run timeline, evidence and decisions. Calls Core API; must not write the database directly. |
| Core API | `aiops2-rebuild-core`; FS1318 qualification container; v27 and E2E Core candidates; v28 QF candidates | Canonical API and business lifecycle/state transitions. Single authority for Incident/Run state. |
| Worker | `aiops2-rebuild-worker`; v27 and E2E Worker candidates | Executes Temporal workflow activities; activity idempotency and bounded retries required. |
| Temporal + UI | `aiops2-rebuild-temporal`, `aiops2-rebuild-temporal-ui`; separate v27/E2E Temporal instances | Durable workflow orchestration, retry, timeout, replay and recovery. |
| PostgreSQL | `aiops2-rebuild-postgres`, `aiops2-rebuild-temporal-postgres`; separate qualification databases | Persistent application and Temporal data stores. They are distinct observed services/volumes; do not merge or repoint without data migration review. |
| Digital Twin | `aiops2-rebuild-twin`; v27 and E2E Twin candidates; rollback candidate | Service/CI topology, dependencies and impact context; data freshness and provenance must be visible. |
| Evidence | `aiops2-rebuild-evidence`; v27 and E2E Evidence candidates | Evidence acquisition/storage/provenance. Evidence is append-only; missing proof remains UNKNOWN. |
| Policy | `aiops2-rebuild-policy`; v27 and E2E Policy candidates | Deterministic safety gate, independent of LLM; fail-closed on unsafe or unqualified inputs. |
| Simulator | `aiops2-rebuild-simulator` | Controlled scenario/remediation simulation. Keep execution isolated; no live side effects inferred. |
| Intelligence / test LLM | `aiops2-rebuild-intelligence`, `aiops2-rebuild-test-llm`; v27/E2E candidates | Analyst/Critic and model test endpoint. AI output is advisory and cannot authorize Policy or execution. |
| Copilot / NOC RAG | `aiops2-rebuild-copilot`, `aiops2-noc-rag-test`, `aiops2-noc-rag-copilot-test` | Operator assistance and retrieval-augmented knowledge interface; access control and citation/ACL qualification remain required. |
| GLPI + MariaDB | `aiops2-rebuild-glpi`, `aiops2-rebuild-glpi-db`; separate HTTP qualification and recovery DB containers | Service desk / ticketing and its data store. Read-only ticket context is distinct from approval or execution. |
| n8n | `aiops2-rebuild-n8n` | Integration and notification workflow boundary; must not own Incident/Run lifecycle state. |
| Prometheus / Grafana / Alertmanager | `aiops2-rebuild-prometheus`, `aiops2-rebuild-grafana`, `aiops2-rebuild-alertmanager` | Metrics scraping, dashboards and alert routing. Observability is a signal source, not the business lifecycle authority. |
| OpenTelemetry / Loki / Tempo | `aiops2-demo-observability-demo-otel-1`, `...-loki-1`, `...-tempo-1` | Demo observability collection, logs and traces. Separate Compose project observed. |
| CloudBeaver | `aiops2-rebuild-cloudbeaver` | Database administration UI; access is sensitive and must remain controlled. |
| FS ingestion / lab | `aiops2-fs385-ingest`, `aiops2-fs-lab`, `aiops2-fs-qualification` | FS feature-specific ingestion, lab and qualification surfaces; exact feature contracts must be mapped to their source PRs. |
| Metrics normalizer / demo read-only surfaces | `aiops2-metrics-normalizer-v1`, `aiops2-demo-web-v1`, `aiops2-demo-readonly` | Candidate metrics-normalization and read-only demo/qualification functions; exact source and owner need confirmation. |

## Complete container name/state inventory

This list preserves every container name in the supplied audit. `running`, `exited` and `created` are the observed Docker states at capture time.

### Running (59)

- `fs1318-http-qual`
- `aiops2-rebuild-worker`
- `aiops2-rebuild-core`
- `aiops2-rebuild-cloudbeaver`
- `aiops2-rebuild-portal`
- `aiops2-rebuild-twin`
- `aiops2-fs385-ingest`
- `aiops2-rebuild-prometheus`
- `aiops2-fs-lab`
- `aiops2-v29-qualification`
- `aiops2-fs-qualification`
- `aiops2-rebuild-evidence`
- `aiops2-rebuild-policy`
- `aiops2-rebuild-simulator`
- `aiops2-rebuild-intelligence`
- `aiops2-portal-candidate-web-20261029`
- `aiops2-glpi-http-qual-db`
- `aiops2-demo-observability-demo-otel-1`
- `aiops2-demo-observability-demo-loki-1`
- `aiops2-demo-observability-demo-tempo-1`
- `aiops2-rebuild-copilot`
- `aiops2-noc-rag-test`
- `aiops2-noc-rag-copilot-test`
- `aiops2-rebuild-n8n`
- `aiops2-rebuild-glpi`
- `aiops2-rebuild-alertmanager`
- `aiops2-rebuild-temporal-ui`
- `aiops2-rebuild-grafana`
- `aiops2-glpi-recovery-db`
- `aiops2-rebuild-test-llm`
- `aiops2-rebuild-temporal`
- `aiops2-rebuild-postgres`
- `aiops2-rebuild-temporal-postgres`
- `aiops2-rebuild-glpi-db`
- `aiops2-v28-core-qf186`
- `aiops2-v28-sql-qual`
- `aiops2-v27-qual-aiops2-worker-1`
- `aiops2-v27-qual-aiops2-core-1`
- `aiops2-v27-qual-aiops2-intelligence-1`
- `aiops2-v27-qual-aiops2-policy-1`
- `aiops2-v27-qual-aiops2-twin-1`
- `aiops2-v27-qual-aiops2-evidence-1`
- `aiops2-v27-qual-aiops2-test-llm-1`
- `aiops2-v27-qual-aiops2-temporal-1`
- `aiops2-v27-qual-aiops2-temporal-postgres-1`
- `aiops2-v27-qual-aiops2-postgres-1`
- `aiops2-metrics-normalizer-v1`
- `aiops2-demo-web-v1`
- `aiops2-demo-readonly`
- `aiops2-e2e-v1-aiops2-worker-1`
- `aiops2-e2e-v1-aiops2-intelligence-1`
- `aiops2-e2e-v1-aiops2-test-llm-1`
- `aiops2-e2e-v1-aiops2-twin-1`
- `aiops2-e2e-v1-aiops2-temporal-1`
- `aiops2-e2e-v1-aiops2-temporal-postgres-1`
- `aiops2-e2e-v1-aiops2-evidence-1`
- `aiops2-e2e-v1-aiops2-core-1`
- `aiops2-e2e-v1-aiops2-policy-1`
- `aiops2-e2e-v1-aiops2-postgres-1`

### Exited (18)

- `aiops2-rebuild-portal-fs1085-rollback-20261106-233813`
- `aiops2-rebuild-portal-fs1062-rollback-20261106-231345`
- `aiops2-rebuild-core-rollback-20261107T164456Z`
- `aiops2-rebuild-portal-fs1047-rollback-20261106-224850`
- `aiops2-rebuild-portal-fs563-rollback`
- `aiops2-rebuild-twin-fs1015-rollback`
- `aiops2-rebuild-core-before-metrics`
- `aiops2-rebuild-twin-before-metrics`
- `aiops2-rebuild-policy-before-metrics`
- `aiops2-portal-rollback-v2-20261028`
- `aiops2-rebuild-temporal-namespace`
- `aiops2-rebuild-evidence-before-metrics`
- `aiops2-rebuild-temporal-schema`
- `aiops2-v28-core-qf183`
- `aiops2-v27-qual-aiops2-temporal-namespace-1`
- `aiops2-v27-qual-aiops2-temporal-schema-1`
- `aiops2-e2e-v1-aiops2-temporal-namespace-1`
- `aiops2-e2e-v1-aiops2-temporal-schema-1`

### Created (1)

- `aee3afd900f2_aiops2-rebuild-worker`

## Selected image/version observations

| Container | Image |
|---|---|
| `aiops2-rebuild-core` | `aiops2-core:fs1212-integrated-candidate` |
| `aiops2-rebuild-worker` | `aiops2-worker:fs-demo-candidate-20261105` |
| `aiops2-rebuild-portal` | `aiops2-portal:fs1073-csp-candidate` |
| `aiops2-rebuild-twin` | `aiops2-twin:fs1009-decimal-metrics-candidate-20261106` |
| `aiops2-rebuild-evidence` | `aiops2-evidence:prometheus-fix-20261104` |
| `aiops2-rebuild-policy` | `aiops2-policy:prometheus-fix-20261104` |
| `aiops2-rebuild-simulator` | `aiops2-acme-sandbox-simulator:e9a21e3e13f9` |
| `aiops2-rebuild-intelligence` | `aiops2-rebuild-aiops2-intelligence` |
| `aiops2-rebuild-temporal` | `temporalio/server:1.31.0` |
| `aiops2-rebuild-postgres` | `postgres:16-alpine` |
| `aiops2-rebuild-temporal-postgres` | `postgres:16-alpine` |
| `aiops2-rebuild-glpi` | `glpi/glpi:11.0.9` |
| `aiops2-rebuild-glpi-db` | `mariadb:11.4` |
| `aiops2-rebuild-n8n` | `n8nio/n8n:2.40.6` |
| `aiops2-rebuild-prometheus` | `prom/prometheus:v3.14.0` |
| `aiops2-rebuild-grafana` | `grafana/grafana:13.2.2` |
| `aiops2-rebuild-alertmanager` | `prom/alertmanager:v0.34.1` |
| `aiops2-demo-observability-demo-otel-1` | `otel/opentelemetry-collector-contrib:0.123.0` |
| `aiops2-demo-observability-demo-loki-1` | `grafana/loki:3.5.0` |
| `aiops2-demo-observability-demo-tempo-1` | `grafana/tempo:2.7.2` |

## Qualification and health caveats

- The v27 qualification project has its own Core, Worker, Intelligence, Policy, Twin, Evidence, Temporal and PostgreSQL containers.
- The E2E v1 project has a separate Core, Worker, Intelligence, Policy, Twin, Evidence, Temporal and PostgreSQL set.
- v29 qualification, FS qualification, v28 QF and HTTP/GLPI qualification containers are also present.
- Several rollback/before-metrics containers are exited; at least some are explicitly reported `unhealthy`.
- Many containers report `HEALTH=NOT_CONFIGURED`. This is absence of a Docker health check, not a pass.
- Some containers have no Compose labels. Their exact source-of-truth Compose definition is therefore not established by this inventory.
- One Compose source path in the metrics-cutover project points to a temporary `/tmp` file and the audit reports it missing. Treat this as configuration drift to investigate.
- The audit did not query application APIs, databases, HTTP endpoints, ports, or business workflows. It therefore does not prove functional availability or data integrity.

## Consolidation rules

1. Do not delete, stop, recreate, merge or migrate containers, networks or volumes solely from this inventory.
2. Determine ownership from Compose labels, source files, image digests, mounts, networks and repository history.
3. Preserve qualification environments until their test coverage and unique functions have been mapped.
4. Preserve rollback images and volumes until a replacement is qualified and rollback is tested.
5. Keep Core as the sole Incident/Run authority; Temporal/Worker orchestrate; Evidence is append-only; Policy is deterministic; Intelligence is advisory; Portal is an API-backed experience.
6. The next runtime capture should add Docker image digests, published ports, restart policy, health-check details, network membership, volume ownership, Compose file hashes and timestamp.
7. Never commit secrets, environment variable values, access tokens, private keys, database credentials or customer data to this repository.

## Related architecture documents

- [Component catalog and reuse matrix](../COMPONENT-CATALOG-AND-REUSE.md)
- [Architecture and service boundaries](../ARCHITECTURE-AND-BOUNDARIES.md)
- [Project continuity record](../PROJECT-CONTINUITY.md)
- [Qualification and change protocol](../QUALIFICATION-AND-CHANGE-PROTOCOL.md)
- [Reuse and convergence register](../architecture/AIOPS2-REUSE-CONVERGENCE-REGISTER-2026-10-30.md)

## Provenance

Source: user-provided read-only Docker audit captured on `SRV-DEB-05` and supplied in the conversation on 2026-11-08. The source command inspected Docker Compose projects, containers, images, labels, networks, mounts and volumes, and checked Compose file presence and SHA-256. It explicitly reported no HTTP requests, database access, container start/stop/removal, volume removal or configuration modification.
