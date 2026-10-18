# AioOps 2.0 — Final Architecture Review

Author: Abdelhalim Talbi

## Decision

The platform is rebuilt around five authorities:

1. **Core** — canonical Run state and lifecycle.
2. **Temporal/Worker** — only execution engine for Run stages.
3. **Twin** — authoritative synthetic/operational topology and impact context.
4. **Evidence** — provenance-bearing observations and claims.
5. **Policy** — safety decision; fail closed.

Portal, Copilot, n8n and Grafana are consumers/integration boundaries and are not competing authorities.

## Required first deployment behaviour

The first deployment must provide a usable synthetic ACME environment, not an empty framework. The seed therefore includes business, service, application, compute, storage, SAN and network objects plus Golden scenarios.

All DEMO/REPLAY/STORY mutations carry explicit synthetic provenance and are blocked from production mutation paths.

## Failure modes deliberately addressed

- duplicate Run creation: idempotency key;
- duplicate commands: command receipts;
- duplicate stage events after Temporal retry: event keys;
- stale Run updates: optimistic version check;
- unknown evidence: foreign-key validation plus API validation;
- policy failure: BLOCKED, never implicit ALLOW;
- simulator reaching production data: separate execution network;
- legacy runtime collision: preflight + explicit retirement;
- port collision: fixed port registry;
- restart/retry: Temporal retry policy + run checkpoints;
- unsupported Copilot claims: evidence-first response and UNKNOWN policy.

## Remaining qualification boundary

A source-tree audit cannot prove Docker runtime behaviour. On the target VM the Big Bang script must prove image pull/build, container health, Temporal task execution, database migrations, HTTP connectivity, synthetic E2E, restart/recovery and port ownership.
