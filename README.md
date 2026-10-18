# ACME AioOps 2.0 — Final Big Bang Deployment Kit

**Author: Abdelhalim Talbi**

This kit is a clean rebuild of the AioOps runtime. It is designed to deploy the largest coherent functional baseline in one operation rather than accumulate another historical version.

## First deployment

```bash
cp config/.env.example .env
RETIRE_LEGACY=1 ./deploy/install.sh
```

The installer builds the application images, starts the complete stack, checks the exposed services and launches a deterministic synthetic Golden Demo.

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
