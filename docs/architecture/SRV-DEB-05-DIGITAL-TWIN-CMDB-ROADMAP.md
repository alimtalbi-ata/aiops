# SRV-DEB-05 — Digital Twin discovery, CMDB reconciliation and delivery plan

**Status:** Architecture baseline / implementation in progress  
**Last evidence received:** 2026-10-31  
**Reference host:** `SRV-DEB-05`  
**Linux operator:** `aiops`  
**Related implementation:** PR #214 — Debian read-only reporter v2  
**Scope:** AIOps2 lab and enterprise simulation only. This document does not authorize production changes or LIVE remediation.

## 1. Purpose

Turn the actual AIOps2 lab running on SRV-DEB-05 into a governed, repeatable enterprise Digital Twin. The twin must represent infrastructure, application services, dependencies, business services, ownership, lifecycle, incidents and changes. GLPI is the ITSM/CMDB system of record for the demonstration; Docker discovery is an observation source, not an authority to mutate infrastructure.

The intended flow is:

1. Discover runtime facts from Debian/Docker using a least-privilege, read-only agent.
2. Normalize and identify observed resources.
3. Reconcile observations against GLPI configuration items (CIs), preserving manually curated business metadata.
4. Build service/dependency relationships and environment boundaries.
5. Generate realistic ITIL 4 incidents from validated conditions.
6. Measure AI analysis and corrective proposals against evidence and verified outcomes.

## 2. Evidence baseline from operator-provided host output

The following are facts observed in command output supplied by the operator on 2026-10-31. They are not inferred from CI.

### 2.1 Host and capacity

- Host label: `SRV-DEB-05`
- OS: Debian GNU/Linux 13 (Trixie), not Debian 12.
- Kernel: `6.12.107+deb13-amd64`
- Architecture: `x86_64`
- Uptime at collection: approximately 3 weeks, 3 days, 6 hours.
- Root filesystem: 16,886,620,160 bytes total; 11,756,621,824 bytes free (approximately 69.6% free).
- `/home`: 172,898,033,664 bytes total; 144,667,000,832 bytes free (approximately 83.7% free).
- Memory: 25,205,911,552 bytes total; 19,895,537,664 bytes available.
- Swap: 10,838,077,440 bytes total; 9,992,867,840 bytes free.

Capacity policy proposal (not yet enforced): warning when root free space falls below 25%; critical below 15%. Never auto-prune Docker images, containers or volumes as a response to disk pressure.

### 2.2 Main rebuild stack

Operator supplied `docker ps` and `docker inspect` output confirming these running containers:

| Container | Image/service role | Observed state |
|---|---|---|
| `aiops2-rebuild-intelligence` | Intelligence | running / healthy |
| `aiops2-rebuild-simulator` | Simulator | running / healthy |
| `aiops2-rebuild-worker` | Worker | running / healthy |
| `aiops2-rebuild-portal` | Portal | running / healthy |
| `aiops2-rebuild-core` | Core | running / healthy |
| `aiops2-rebuild-twin` | Digital Twin | running / healthy |
| `aiops2-rebuild-policy` | Policy | running / healthy |
| `aiops2-rebuild-copilot` | NOC Copilot | running / healthy |
| `aiops2-rebuild-prometheus` | Prometheus | running / healthy |
| `aiops2-rebuild-grafana` | Grafana | running / healthy |
| `aiops2-rebuild-glpi` | GLPI | running; Docker healthcheck not configured |
| `aiops2-rebuild-postgres` | PostgreSQL | running / healthy |
| `aiops2-rebuild-temporal` | Temporal | running / healthy |
| `aiops2-rebuild-glpi-db` | MariaDB / GLPI database | running / healthy |

The main Portal container publishes `0.0.0.0:17777 -> 777/tcp`. GLPI, Grafana, Prometheus and Temporal UI were shown bound to host address `10.79.94.202` on ports 8080, 3000, 9090 and 8081 respectively. PostgreSQL and Temporal ports are internal to Docker networks in the supplied output; loopback TCP failures do not prove those services are unavailable.

The previously reported `unhealthy` container `aiops2-portal-rollback-v2-20261028` was exited. The active main Portal was independently inspected as healthy. Do not open an incident against the active Portal based on the stopped rollback container.

GLPI is running, but lacks a Docker healthcheck. This is an observability gap, not proof of application failure. Add an application-level HTTP/API probe in a later change after confirming the correct health endpoint and authentication model.

### 2.3 Coexisting runtime generations and networks

The operator output shows multiple simultaneous stacks, including:

- rebuild (primary current lab stack);
- v27 qualification;
- e2e-v1;
- NOC RAG;
- demo observability;
- portal candidate;
- GLPI HTTP qualification/recovery databases;
- older qualification and rollback containers, some exited.

Observed Docker bridge networks include:

- `aiops2-rebuild-control`
- `aiops2-rebuild-data`
- `aiops2-rebuild-execution`
- `aiops2-rebuild-integration`
- `aiops2-rebuild-observability`
- `aiops2-rebuild-public`
- `aiops2-rebuild-temporal-data`
- `aiops2-v27-qual_control`, `aiops2-v27-qual_data`, `aiops2-v27-qual_temporal_data`
- `aiops2-e2e-v1_control`, `aiops2-e2e-v1_data`, `aiops2-e2e-v1_temporal_data`

Do not assume that every container with an old-looking name is disposable. Some are qualification evidence, recovery resources or rollback assets. No bulk cleanup is authorized by this architecture document.

## 3. Environment and CI classification

Normalize environment identity explicitly. Initial mapping proposal:

| Logical environment | Discovery mapping rule | Intended purpose |
|---|---|---|
| `LAB-REBUILD` | Compose project/service labels and verified rebuild network membership | Primary enterprise demonstration |
| `QUALIFICATION` | Verified v27/qualification compose projects | Compatibility and release qualification |
| `E2E` | Verified e2e-v1 compose project/networks | Synthetic end-to-end tests |
| `SANDBOX` | Explicitly registered experimental project or owner metadata | Isolated experiments |
| `CANDIDATE` | Candidate Portal project/container labels | Pre-promotion validation |
| `OBSERVABILITY` | Demo observability project | Telemetry infrastructure |

These are logical labels, not claims that all containers have already been mapped conclusively. Prefer Compose project/service labels and network membership over name-prefix heuristics. Unknown resources must be classified as `UNCLASSIFIED` and queued for review rather than silently assigned to an environment.

## 4. Target discovery and reconciliation architecture

### 4.1 Observation model

The Debian agent emits a versioned, bounded JSON snapshot. Reporter v2 adds:

- container state and health;
- image reference;
- Compose project and service labels;
- restart count and exit code;
- attached Docker network names;
- published host/container port bindings;
- Docker network name, driver and scope;
- one-shot per-container CPU and memory usage.

Sensitive and high-volume information remains excluded: container environment variables, mount details, logs, secrets, database contents, GLPI records and arbitrary command output.

The reporter is read-only. It must not restart containers, run `docker exec`, pull/build images, mutate databases or call GLPI write APIs.

### 4.2 Canonical CI model

Recommended CI types:

- Host / VM
- Docker Engine
- Docker network
- Container instance
- Container image / release artifact
- Application component
- Database instance
- Middleware / workflow engine
- Monitoring component
- Business application
- Business service

Recommended CI fields:

- stable external key (source + immutable runtime identifier where available);
- display name and CI type;
- environment and lifecycle state;
- host and runtime placement;
- image/release reference;
- observed health and last-seen timestamp;
- owner/support group (curated, not guessed);
- business criticality and data classification (curated);
- discovery source and confidence;
- last reconciliation result;
- GLPI entity/tenant;
- lifecycle: discovered, active, stale, retired, exception.

Do not use a container name alone as a durable identity: names can be reused. Prefer Docker container ID for an instance; use Compose project + service as a logical workload key. A replacement container should be linked to the same logical service but represented as a new runtime instance.

### 4.3 Relationship model

At minimum, model:

- host **runs** Docker Engine;
- Docker Engine **hosts** container instance;
- container **attached to** Docker network;
- container **implements** application component;
- application component **depends on** database/middleware/API;
- application component **part of** business service;
- business service **supports** business capability;
- CI **owned by** support group;
- incident **impacts** CI/business service;
- change **affects** CI and dependency closure.

Relationships must be directional where dependency/impact semantics require direction. Record source, confidence, observed time and validity interval for discovered relationships.

## 5. Reconciliation rules

1. Discovery creates an observation, not an automatic destructive CMDB change.
2. Match by stable external key first; use names only as a secondary candidate match.
3. Never overwrite curated owner, business criticality, service tier, SLA, data classification or support group with runtime guesses.
4. New observations create proposed CIs or a review queue before GLPI write operations are enabled.
5. Missing resources become stale only after a configurable grace period and repeated missed observations.
6. Never automatically delete a CI or close an incident merely because a container disappeared.
7. Preserve source snapshot, reconciliation decision, actor, timestamp and before/after values.
8. Duplicate candidates are merged only through an auditable, reversible operation.
9. Separate physical runtime state from logical service state: one unhealthy container does not necessarily mean the business service is unavailable.
10. Every discovered fact must carry provenance: Docker API/CLI observation, agent version, host, collection time and confidence.

## 6. ITIL 4 operational workflows

The demonstration should represent a complete service-management lifecycle:

- Event management: normalize and deduplicate telemetry.
- Incident management: create incidents with impact, urgency, priority, affected CI and evidence.
- Major incident management: correlate multiple CI failures to a business-service outage.
- Problem management: group recurring incidents and maintain known errors / workarounds.
- Change enablement: classify corrective action, risk, approval, schedule and implementation evidence.
- Service configuration management: maintain CI identity, attributes and relationships.
- Monitoring and event management: retain signal-to-incident traceability.
- Knowledge management: link verified runbooks and known errors.
- Continual improvement: use measured outcomes to refine detection and remediation.

A generated incident must include detection source, timestamp, affected CI, business service, impact statement, urgency/priority rationale, deduplication key, evidence references, proposed diagnosis, confidence and verification plan. Do not create a customer-impact claim from a container health status alone.

## 7. AI benchmarking requirements

Every Analyst/Critic/RCA/recommendation evaluation should record:

- model/provider and model version;
- prompt/template version;
- input/output token counts where provider exposes them;
- estimated and actual cost with currency and pricing source/version;
- latency and retry count;
- evidence IDs and evidence coverage;
- root-cause correctness against adjudicated ground truth;
- recommendation safety and policy compliance;
- actionability and execution feasibility;
- human acceptance/rejection and reason;
- verified resolution outcome;
- false-positive/false-negative and duplicate rates.

Core metrics:

- cost per incident analyzed;
- tokens per incident and per successful resolution;
- time to detect / acknowledge / diagnose / resolve;
- RCA precision and recall;
- recommendation acceptance rate;
- verified remediation success rate;
- rollback/failure rate;
- analyst/critic disagreement rate;
- evidence coverage and unsupported-claim rate.

Never optimize token consumption in isolation: compare cost against correctness, evidence quality, safety and time saved. Benchmark on a fixed, versioned replay corpus with reproducible scenarios and blinded ground truth.

## 8. Delivery roadmap and acceptance criteria

### P0 — Discovery contract and runtime topology

- [x] Reporter v1 installed on SRV-DEB-05 under Linux account `aiops`.
- [x] One-minute local cron collection confirmed by operator.
- [x] First host/container inventory received.
- [x] Active Portal healthy; stopped rollback container distinguished from active service.
- [x] Main and legacy Docker networks enumerated by operator.
- [ ] Reporter v2 CI green on final PR head.
- [ ] Reporter v2 installed on SRV-DEB-05 and schema-v2 snapshot reviewed.
- [ ] Confirmed Compose project/service mapping for every active container.
- [ ] Application-level health probes added for GLPI and services lacking Docker healthchecks.

### P1 — GLPI CMDB reconciliation (read-only dry run first)

- [ ] Inspect existing GLPI entities, CI types, fields and relationships.
- [ ] Export a baseline before any writes.
- [ ] Produce a discovery-to-CMDB diff with create/update/stale/duplicate proposals.
- [ ] Validate external-key idempotency and multi-environment isolation.
- [ ] Review sample mappings with a human before enabling lab writes.
- [ ] Create lab CIs and relationships via supported GLPI API/plugin interface.
- [ ] Demonstrate reconciliation after container replacement and after a missed observation.

### P2 — Enterprise service model and ITIL workflow

- [ ] Map application components to business services and owners.
- [ ] Define business criticality, SLA/OLA, support groups and escalation.
- [ ] Generate synthetic incidents from validated evidence.
- [ ] Demonstrate correlation, major incident, problem, change and knowledge links.
- [ ] Verify incident closure only after an explicit post-condition check.

### P3 — AI quality and cost benchmark

- [ ] Establish a fixed replay dataset and adjudicated ground truth.
- [ ] Instrument model/provider, tokens, latency, cost and retries.
- [ ] Score RCA, evidence grounding, corrective action safety and resolution.
- [ ] Publish a benchmark dashboard and reproducible report.
- [ ] Compare model choices on quality-adjusted cost, not tokens alone.

### P4 — Controlled lab remediation

- [ ] Typed operation catalog and allowlisted targets.
- [ ] Preflight, approval, idempotency, audit and postflight checks.
- [ ] Canary one lab service at a time.
- [ ] Verified rollback path and failure quarantine.
- [ ] No LIVE remediation unlock as part of this roadmap.

## 9. Operational safety boundaries

The operator has authorized useful application-level operations on the AIOps2 lab (Docker lifecycle for allowlisted services, PostgreSQL/MariaDB application migrations, GLPI/Grafana APIs and Temporal synthetic operations). That authorization is not equivalent to granting arbitrary shell or host administration.

Prohibited:
- `sudo`, `su`, systemctl/service-manager mutation, apt/dpkg, host reboot;
- OS users/groups, kernel, SSH, firewall, routing, DNS or host network changes;
- system cron/timer mutation;
- arbitrary shell commands received from GitHub;
- `docker exec`, unrestricted Docker socket or docker-group grant to a general agent;
- database superuser access;
- destructive changes to production data;
- LIVE remediation or production deployment without a separate explicit authorization.

The Debian reporter remains read-only. Any future operator must use typed operations, allowlisted resources, least-privilege service identities, bounded timeouts, idempotency keys, pre/postconditions and append-only audit evidence.

## 10. Change log

| Date | Change |
|---|---|
| 2026-10-31 | Recorded first operator-confirmed SRV-DEB-05 inventory and Debian 13 host facts. |
| 2026-10-31 | Corrected interpretation: active Portal is healthy; unhealthy rollback container is exited. |
| 2026-10-31 | Recorded coexistence of rebuild, v27 qualification, e2e-v1, NOC RAG, observability and candidate stacks. |
| 2026-10-31 | Defined environment classification, canonical CI model, relationship model and reconciliation guardrails. |
| 2026-10-31 | Defined ITIL 4 workflows and AI quality/cost benchmarking measures. |
| 2026-10-31 | Reporter v2 topology/resource inventory implementation added to PR #214; CI outcome pending at time of writing. |
| 2026-10-31 | Added second-server deployment and recovery standard; corrected legacy fresh-install script to remove embedded shared credentials and use generated per-install secrets. |

## 11. Reproducible deployment on a second server

The customer/server portability and recovery standard is maintained in [`docs/operations/REPRODUCIBLE-DEPLOYMENT-AND-RECOVERY.md`](../operations/REPRODUCIBLE-DEPLOYMENT-AND-RECOVERY.md). It documents verified repository assets, unique per-install secrets, immutable release selection, installation sequence, migration caveats, backup/restore gaps and release acceptance criteria. Current status is **partially reproducible**; a clean second-server install and full restore drill have not yet been demonstrated.

## 12. Source of truth and update discipline

- Architecture and this roadmap: this document in Git.
- Operational authorization: `config/ops/debian-service-operations-policy.yml`.
- Reporter implementation: `scripts/debian-readonly-reporter.py`.
- Reporter installation: `scripts/install-debian-reporter.sh`.
- Debian runbook: `docs/operations/DEBIAN-CRON-REPORTER.md`.
- Host evidence: sanitized, versioned report snapshots in `ops/debian-runtime-reports` once GitHub token publication is enabled.
- CI evidence: GitHub Actions runs attached to PR #214.

Every implementation PR must update this document (or a linked decision record) with scope, files/config/schema changed, tests run, result, operational impact, rollback and remaining risks. Keep status labels honest: planned, implemented, CI-passing, host-deployed and host-verified are distinct states.
