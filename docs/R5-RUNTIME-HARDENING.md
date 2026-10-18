# AioOps 2.0 — R5 Runtime Hardening

## Objective

R5 hardens the deployment/runtime boundary identified during the R4 qualification:

- Temporal must have an explicit, valid dynamic configuration file.
- Temporal readiness must gate dependent services.
- Runtime qualification must test actual service readiness, not only container existence.
- `00-Deployment/start.sh` must not report success before qualification and synthetic E2E.
- The existing internal service ports remain unchanged.

## Temporal

Temporal 1.32.1 is configured with:

- PostgreSQL backend: `aiops2-temporal-postgres:5432`
- gRPC endpoint: `aiops2-temporal:7233`
- dynamic configuration: `config/dynamicconfig/docker.yaml`
- read-only container mount: `/etc/temporal/config/dynamicconfig`

The dynamic configuration file is deliberately minimal. It exists to satisfy the configured runtime contract; environment-specific overrides must be qualified before addition.

## Health gating

The worker and Temporal UI now depend on Temporal health rather than process start alone. Qualification additionally checks Temporal cluster health and the Temporal UI endpoint from inside its container.

## Python service ports

The application Dockerfiles use explicit, deterministic internal Uvicorn ports (810–816 and portal 777). This avoids the R4 failure mode where an empty environment variable was passed to Uvicorn as `--port`.

## Start/qualification contract

The supported start path is:

1. preflight
2. image build
3. Compose startup
4. service qualification
5. Temporal cluster health
6. external observability/UI health checks
7. synthetic E2E
8. final `AIOPS2_START=QUALIFIED`

A failed qualification or E2E test produces a non-zero exit code.

Author: Abdelhalim Talbi
