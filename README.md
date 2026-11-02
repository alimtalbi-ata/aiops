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

## ACME-TEST causal incident-to-resolution sandbox (Draft #358; NOT deployed)

The V28 vertical sandbox is opt-in (`AIOPS_ACME_SANDBOX_ENABLED=false` by
default) and isolated to tenant `ACME-TEST`, scenario
`ACME-SAN-PAYMENTS`. Its GLPI ticket is `SIM-GLPI-*` synthetic data,
**not** an authenticated GLPI human ticket or an IdP/READ/READMY permission.
Twin issues a short-lived HMAC-attested approval with
`approval_kind=SIMULATED` and `approval_issuer=TWIN_ACME_SIMULATED`;
the signing key is generated/stored privately on the Debian host, never in Git.

The causal sequence is: Simulator POST → Core creates one synthetic Incident,
Run, seven correlated source events, evidence, Analyst/Critic and a PREPARED
simulated ticket → Twin calculates SAN→Payments impact and issues signed
SIMULATED approval → Policy independently re-reads Core/Twin and returns
SIMULATE only → Temporal Worker independently validates PREPARED and emits
SIMULATED_NO_EFFECT with zero effect receipts → **Core alone** accepts a
terminal POST after independently verifying Worker/Twin/Policy and persists
RESOLVED → Debian runner performs two rounds of independent final GETs.
No human ALLOW, real GLPI write, LIVE executor or effect is permitted.
If any authority, freshness, signature, tenant, source hash or readback is
unavailable, the chain fails closed; a 200 /health or source-only CI is not
an E2E PASS.

The single stable-based candidate is
[PR #358](https://github.com/alimtalbi-ata/aiops/pull/358). Its
`deploy/debian-acme-sandbox-release.json` stays `enabled:false` until
exact-HEAD PG16 009→017 migration/restore, Worker/Temporal/Policy tests,
Compose backup and rollback, security review and a qualified immutable SHA
are recorded in [issue #186](https://github.com/alimtalbi-ata/aiops/issues/186).
The existing Debian poller invokes the optional in-place
`deploy/debian-acme-sandbox-upgrade.sh` only when this manifest is explicitly
enabled. It must preserve the canonical portal :7777, GLPI, Temporal DB and
all volumes; only the five existing Core/Twin/Policy/Worker/Simulator
containers may be recreated after image build, PG16 native backup and
read-only ownership/health checks. It writes a private machine-readable
upgrade receipt with stable/product/DEV SHA, image and container IDs,
HTTP 200 JSON checks, backup checksum and rollback. The separate
`acme-sim-e2e.json` receipt must contain correlated incident/run/ticket/
proposal/approval IDs and a verified final RESOLVED state. The publisher
sidecar reports `GO_SIMULATED_SANDBOX_ONLY` only if **both** fresh host
receipts qualify; it never grants LIVE or human GLPI authority.

**Rollback**: disable the sandbox flag, restore previous pinned application
images for only those five services via targeted Compose `up --no-deps`
and verify health. Preserve the additive 011–017 database schema and
immutable audit, and retain the native PG16 backup; never use
`down -v`, prune or automatic destructive DB restore. A failed or stale
publisher does not convert local checks into host evidence: check the
published Debian report timestamp before declaring DEPLOYED/E2E PASS.
