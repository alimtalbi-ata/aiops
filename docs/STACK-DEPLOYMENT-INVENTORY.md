# AIOps 2.0 — Stack Deployment Inventory and Qualification Boundary

**Author:** Abdelhalim Talbi  
**Source:** GitHub README, compose.yml, deploy scripts, migration list and tests reviewed 2026-10-19.  
**Status:** Source-level inventory only; running services have not been inspected in this task.

## Current stack declared in Compose

The Compose file is the deployment source of truth. The reviewed file declares the following runtime roles; exact image/build details remain in compose.yml.

| Role | Responsibility | Qualification focus |
|---|---|---|
| PostgreSQL | Canonical operational state and migrations | Migration ordering, backup/restore, concurrency, integrity |
| Core API | Incident/run lifecycle and authoritative state transitions | Auth, versioning, idempotency, audit and contract tests |
| Digital Twin | ACME topology/facts/impact model | Defer feature expansion until core gates pass; freshness and uncertainty |
| Evidence service | Append-only evidence records and provenance | Hashing, duplicate handling, source freshness and access |
| Policy engine | Deterministic disposition gate | P1, critic validity, freshness, preconditions, fencing, approval |
| Copilot | User-facing conversational integration | Evidence citations, scope, secret redaction and safe tool boundaries |
| Worker / Temporal | Durable run stages, retries and replay | Worker restart, duplicate activities, bounded retry and blocked LIVE behavior |
| Simulator | Synthetic event/scenario execution | Isolated execution network, explicit mode/token, deterministic seed |
| Portal | Operator experience | API-only state changes, auth, stale/error states and accessibility |
| GLPI + database | ITSM and HITL integration boundary | Ticket idempotency, approval binding, resume/close and reconciliation |
| n8n | External integration workflows | Must not own run state; retry/idempotency and credential isolation |
| Prometheus | Metrics | Target coverage and actionable alert rules |
| Grafana | Dashboards | Source-backed values and clear synthetic/live labels |
| Alertmanager | Alert routing | Safe test routing, deduplication and secret-safe configuration |

## Network and authority boundaries

- Portal calls Core API; it must not write directly to PostgreSQL.
- Temporal/Worker own durable stage progression; n8n is an integration boundary.
- Simulator remains isolated on the execution network and cannot directly reach production data/control systems.
- Events and evidence are append-only.
- LIVE action requires real qualified adapters and independent policy checks. Placeholder/synthetic evidence cannot make a LIVE run look successful.
- Secrets remain in local .env/secret management and never enter ZIP, Git, chat or logs.
- Legacy retirement remains separate and explicitly opted in; ordinary install must not perform destructive cleanup.

## Deployment kit acceptance

The cumulative deployment kit should include:
- compose.yml and every override actually required;
- secure .env template plus secret-generation/preflight scripts;
- all Dockerfiles and pinned dependency manifests;
- ordered SQL migrations, schema/catalog and migration/upgrade strategy;
- service configuration in YAML/JSON with safe examples;
- install, preflight, start, status, qualification, diagnostics, backup/restore and rollback scripts;
- static/unit/contract/integration/synthetic E2E tests;
- architecture, network map, data contracts, runbooks, release notes and test evidence;
- checksums and a manifest that excludes secrets, databases and runtime logs.

## What is and is not validated

The GitHub source currently includes install/preflight/qualification and synthetic E2E scripts, policy safety tests, static audit, runtime contract checks and a SQL audit. Prior continuity notes record CI passing static and policy checks, but explicitly state container build, full runtime qualification and synthetic E2E had not been run at that time. Re-run current branch CI and capture fresh results before asserting current status.

This task performed source inspection through GitHub. It did not connect to Debian, restart containers, run a production test, or claim a current host state.
