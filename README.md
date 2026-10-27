# AIOps 2.0 — Core Reconstruction Deployment Kit

**Author: Abdelhalim Talbi**

This kit is a clean rebuild of the AioOps runtime. It is designed to deploy the largest coherent functional baseline in one operation rather than accumulate another historical version.

## Recommended first deployment (non-destructive)

```bash
bash deploy/install-isolated.sh
```

This is the recommended entry point on a Debian host already running older AIOps stacks. It creates an isolated Compose project `aiops2-rebuild`, verifies existing Docker resource ownership, uses its own named containers, networks and volumes, publishes dashboards to loopback on alternate ports, generates random development secrets and runs installation plus qualification. No legacy container is stopped or removed.

The standard `bash deploy/install.sh` entry point targets the stack identity selected in `.env`, and must only be used after reviewing that identity. **RETIRE_LEGACY=1 is refused during installation.** Retirement is a separate authorized operation after successful qualification and a verified private backup. See `docs/DEPLOYMENT-ISOLATED-REBUILD-RUNBOOK.md` and `docs/SECURITY.md`.

## Current release

Version `2.1.0-core-rc1.4` extends the isolated deployment checks to resolved Docker Compose networks, volumes, project identity and host port publication. It includes the RC1.3 status report, Analyst/Critic tests and offline packaging; RC1.4 adds a read-only Docker resource ownership fence that rejects attempts to adopt existing containers, networks or volumes belonging to another Compose project. Deterministic Analyst/Critic and Temporal synthetic E2E are CI-qualified; a genuine model and LIVE adapters still require separate qualification.

Use `python3 deploy/status.py --env .env` for a read-only operational inventory without secrets. Run `python3 deploy/plan_isolation.py --env .env` to verify the isolated deployment plan without Docker. `deploy/package_tree.py` enables rebuilding a source kit outside a Git checkout.

Use `bash deploy/diagnose.sh` to capture private, redacted diagnostics (review before sharing). The cumulative release ZIP includes sources, installation scripts, Compose, SQL migrations, documentation, and the CI qualification reports with checksums.

## External interfaces

- Portal: `7777`
- GLPI: `8080`
- n8n: `5678`
- Prometheus: `9090`
- Grafana: `3000`
- Alertmanager: `9093`
- Temporal gRPC: internal `7233`

## Core architecture

`Portal → Core → Temporal/Worker → Twin + Evidence + Policy`.

The Simulator is isolated on `aiops2-execution`; it does not have direct access to the data network. n8n is an integration boundary and never owns Run state. The Portal never writes PostgreSQL directly.

## Safety model

- Run state uses optimistic versioning and idempotency receipts.
- Events and Evidence are append-only.
- Every stage has durable stage state.
- LIVE resolution/remediation is fail-closed.
- DEMO/REPLAY/STORY synthetic mutation is guarded by mode and token.
- Missing proof is represented as `UNKNOWN`, not guessed.

## Qualification

`tests/static-audit.sh` checks source structure and naming. `tests/qualification.sh` checks the running stack. `tests/synthetic-e2e.sh` exercises Portal → Core → Temporal → Worker and waits for the Run inventory to contain the generated Run.

See `docs/` for architecture, data contracts, network boundaries, deployment, demo and resilience strategy.

For the current engineering batch, see [RC1.3 deployment and qualification](docs/CORE-RC13-QUALIFICATION-OPERATIONS.md).

## Core qualification and model evaluation

The cumulative kit is versioned from `VERSION`. The CI release job packages the full repository source, Compose/configuration, migrations, scripts, docs, checksums and the successful Temporal runtime report under `09-Qualification/`. The kit is published only when the unit/static gates, image builds, empty-database migrations, legacy upgrade, and deterministic-provider Temporal E2E all pass.

### Automated qualification

```bash
# Create/validate the local secret file and validate the full stack.
bash deploy/init-env.sh
bash deploy/preflight.sh

# Run the deterministic Temporal end-to-end qualification in an isolated test stack.
# CI invokes tests/runtime-e2e.sh and stores a machine-readable report in reports/.

# After configuring LLM_BASE_URL and LLM_MODEL to a reachable OpenAI-compatible endpoint:
bash deploy/qualify-model.sh
```

The model evaluation profile sends only synthetic fixtures to the advisory Analyst/Critic endpoints. It checks severity accuracy, evidence grounding, advisory-only action flags, resistance to prompt-injection text, and Critic detection of contradictory/stale evidence. It writes `reports/ai-core-evaluation.json`; threshold failures return a non-zero exit code. The evaluator never invokes remediation.

For a host-local inference server, configure a Docker-reachable address, not `127.0.0.1` from inside the container. A model-evaluation PASS applies only to the recorded provider/model/prompt and fixture version; it is not a substitute for production qualification.

Read [the reconstruction execution plan](docs/RECONSTRUCTION-EXECUTION-PLAN.md) for the work-package sequence and release gates.

## Project continuity and historical reuse

**Candidate code reuse register (27 October 2026):** review [historical AIOps and third-party GitHub candidates](docs/release/AIOPS-CANDIDATE-CODE-REUSE-REGISTER-20261027.md). It records candidates and gates, not claims of integration.

**Current development status (27 October 2026):** see [development status, remaining work and blockers](docs/release/AIOPS-DEVELOPMENT-STATUS-AND-BLOCKERS-20261027.md) before selecting the next task. This report separates source presence, synthetic tests, commit-specific CI evidence and live qualification.

Before resuming work in a new session, read these documents in order:

1. [Project continuity record](docs/PROJECT-CONTINUITY.md)
2. [Architecture and service boundaries](docs/ARCHITECTURE-AND-BOUNDARIES.md)
3. [Architecture/product decision log](docs/DECISION-LOG.md)
4. [Component catalog and AIOps v1/V145 reuse matrix](docs/COMPONENT-CATALOG-AND-REUSE.md)
5. [Change safety and qualification protocol](docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md)

**Maintenance rule:** every significant development session must update the continuity record and all affected architecture, decision, component, qualification and release documents in the same branch/PR. Prefer adapting qualified AIOps v1/V145 capabilities over rebuilding them, but verify source, contracts, dependencies and tests before declaring a component reusable. Never treat a file listing or synthetic demo as qualification evidence.

## Accelerated rebuild and operations

The repository is the source of truth. Do not preserve code for its own sake: replace components when that accelerates a verifiable outcome, but preserve contracts and operational safety.

- Full build/install: `bash deploy/install.sh`
- Environment preflight: `bash deploy/preflight.sh`
- Apply additive SQL migrations: `bash deploy/migrate.sh`
- Runtime qualification: `bash tests/qualification.sh`
- Synthetic end-to-end: `bash tests/synthetic-e2e.sh`
- Static, SQL and AI ledger checks: `bash tests/static-audit.sh && bash tests/sql-audit.sh && bash tests/migration-contract.sh`
- Diagnostics bundle: `bash deploy/diagnose.sh`
- Private database backup: `bash deploy/backup.sh`
- Guarded restore: `CONFIRM_RESTORE=YES CONFIRM_TARGET_DATABASES=YES bash deploy/restore.sh <backup-directory>`
- Cumulative ZIP: `bash deploy/package.sh` (outputs under `dist/`; excludes secrets, database dumps and diagnostics).

The new migration `009_ai_decision_ledger.sql` defines explicit analysis, critique, policy-decision, proposal, approval, effect, verification, reconciliation, learning and model-evaluation records. Synthetic cases cannot be gold-set eligible. Applied migrations are checksum-pinned; edits to an applied migration fail closed. The migration runner verifies a legacy schema signature before adopting migrations 000–008 as a baseline and refuses to guess when the schema is incomplete.

**Qualification honesty:** a successful static or SQL test does not prove that the full stack or model inference works. CI must separately report compilation/unit tests, full image builds, disposable PostgreSQL migration execution and synthetic runtime E2E. LIVE execution remains disabled until real evidence adapters, policy/HITL and effect verification are qualified.
