# ACME AioOps 2.0 — Final Big Bang Deployment Kit

**Author: Abdelhalim Talbi**

This kit is a clean rebuild of the AioOps runtime. It is designed to deploy the largest coherent functional baseline in one operation rather than accumulate another historical version.

## First deployment

```bash
./deploy/install.sh
```

The installer creates a new `.env` with random credentials (or validates an existing `.env`), builds the application images, starts the stack, checks exposed services and launches a deterministic synthetic Golden Demo. Legacy retirement is separate and must only be enabled deliberately with `RETIRE_LEGACY=1`. See `docs/SECURITY.md` for the explicit, isolated-only demo mode.

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

`deploy/package.sh` creates a versioned cumulative Debian deployment kit with a manifest and SHA-256 checksums. `tests/static-audit.sh` checks source structure and safety contracts. `tests/qualification.sh` checks application health and exposed endpoints. `tests/synthetic-e2e.sh` exercises Portal → Core → Temporal → Worker, verifies idempotency, requires all 13 stages and a PASS/SIMULATE policy gate, and fails on a blocked or incomplete Run.

See `docs/` for architecture, data contracts, network boundaries, deployment, demo and resilience strategy.

## Project continuity and historical reuse

Before resuming work in a new session, read these documents in order:

1. [Project continuity record](docs/PROJECT-CONTINUITY.md)
2. [Architecture and service boundaries](docs/ARCHITECTURE-AND-BOUNDARIES.md)
3. [Architecture/product decision log](docs/DECISION-LOG.md)
4. [Component catalog and AIOps v1/V145 reuse matrix](docs/COMPONENT-CATALOG-AND-REUSE.md)
5. [Change safety and qualification protocol](docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md)

**Maintenance rule:** every significant development session must update the continuity record and all affected architecture, decision, component, qualification and release documents in the same branch/PR. Prefer adapting qualified AIOps v1/V145 capabilities over rebuilding them, but verify source, contracts, dependencies and tests before declaring a component reusable. Never treat a file listing or synthetic demo as qualification evidence.
