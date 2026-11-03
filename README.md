# ACME AioOps 2.0 — Final Big Bang Deployment Kit

**Author: Abdelhalim Talbi**

This kit is a clean rebuild of the AioOps runtime. It is designed to deploy the largest coherent functional baseline in one operation rather than accumulate another historical version.

## First deployment

```bash
./deploy/install.sh
```

The installer creates a new `.env` with random credentials (or validates an existing `.env`), builds the application images, starts the stack, checks exposed services and launches a deterministic synthetic Golden Demo. Legacy retirement is separate and must only be enabled deliberately with `RETIRE_LEGACY=1`. See `docs/SECURITY.md` for the explicit, isolated-only demo mode.

## External interfaces

- Portal: `17777` (default; override with `AIOPS_PORTAL_HOST_PORT`)
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

## Project continuity and historical reuse

Before resuming work in a new session, read these documents in order:

1. [Project continuity record](docs/PROJECT-CONTINUITY.md)
2. [Architecture and service boundaries](docs/ARCHITECTURE-AND-BOUNDARIES.md)
3. [Architecture/product decision log](docs/DECISION-LOG.md)
4. [Component catalog and AIOps v1/V145 reuse matrix](docs/COMPONENT-CATALOG-AND-REUSE.md)
5. [Change safety and qualification protocol](docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md)

**Maintenance rule:** every significant development session must update the continuity record and all affected architecture, decision, component, qualification and release documents in the same branch/PR. Prefer adapting qualified AIOps v1/V145 capabilities over rebuilding them, but verify source, contracts, dependencies and tests before declaring a component reusable. Never treat a file listing or synthetic demo as qualification evidence.

## Enterprise AIOps convergence

The current development architecture, ITIL 4 operating model, ACME SAN→Payments synthetic customer journey, 48-hour execution board, reuse register, AI benchmark governance and autonomous five-schedule development team are documented here:
- [Reference architecture](docs/architecture/AIOPS2-REFERENCE-ARCHITECTURE-2026-10-30.md)
- [48-hour delivery plan](docs/planning/AIOPS2-48H-DELIVERY-PLAN-2026-10-30.md)
- [Execution control board](docs/planning/AIOPS2-48H-EXECUTION-CONTROL-BOARD-2026-10-30.md)
- [Reuse and convergence register](docs/architecture/AIOPS2-REUSE-CONVERGENCE-REGISTER-2026-10-30.md)
- [ACME SAN→Payments ITIL demonstration](docs/customer-story/ACME-P1-SAN-PAYMENTS-ITIL-DEMO-2026-10-30.md)
- [AI benchmark governance](docs/architecture/AIOPS2-AI-BENCHMARK-GOVERNANCE-2026-10-30.md)
- [Autonomous development team](docs/operations/AIOPS2-AUTONOMOUS-DEV-TEAM-OPERATING-MODEL-2026-10-31.md)
- [Automation control plane](docs/operations/AIOPS2-AUTOMATION-CONTROL-PLANE-2026-10-31.md)

These are development architecture and synthetic qualification plans; they do not claim production deployment or live connector qualification.


## Single Debian DEV stack / canonical Portal 7777 (plan only)

The only approved target is the **existing** SRV-DEB-05 DEV stack with **one** operator Portal at host TCP **7777** (not 17777). Binding, reverse proxy, TLS and firewall remain **NOT_VERIFIED**; no second portal, no new persistent Compose project or deploy-branch push. See the [read-only inventory, KEEP/MIGRATE/STOP-LATER/UNKNOWN plan](docs/operations/AIOPS2-SRV-DEB-05-SINGLE-STACK-7777-PLAN-2026-11-01.md) and [intentionally non-deployable manifest](ops/debian/compose.canonical.plan.yml). Existing Docker volumes, DBs, immutable 013/014 audit and rollback assets must be preserved. `RELEASE_STABLE=NO_GO`.
