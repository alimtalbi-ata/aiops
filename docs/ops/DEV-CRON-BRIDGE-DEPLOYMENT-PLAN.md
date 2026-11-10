# AIOPS2 — DEV deployment through existing cron bridge (discovery required)

Date: 2026-11-10. User authorizes **development iteration and controlled replacement** on isolated noncritical Debian after preserving the currently working function. This is a **change of risk appetite**, not proof of a working command channel.

## Facts checked
- The GitHub `main` tree has `deploy/preflight.sh`, `00-Deployment/status.sh`, `scripts/automation_heartbeat_gate.py`.
- `00-Deployment/status.sh` invokes `docker compose --env-file .env ps`; it requires local Docker and cannot run through the GitHub connector.
- `deploy/preflight.sh` calls `deploy/init-env.sh`, so **it is not strictly read-only**. Do not use it as the first inventory command.
- `scripts/automation_heartbeat_gate.py` evaluates an offline evidence JSON and **explicitly does not invoke a scheduler or runtime**.
- The minute-based bidirectional Debian cron bridge described by the user is **not identified in the GitHub main paths examined**, and no command dispatch/receipt protocol has been verified. Do not invent a path, endpoint, or response.

## First operation when bridge is located
Use a bounded, **read-only** inventory request; record request ID, expected response path, timestamp, host identity, and receipt:
```sh
date -Is
hostname
docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}'
docker compose ls --format json
docker image ls --format '{{.Repository}}:{{.Tag}}|{{.ID}}'
```
Do not print environment variables, secret mounts, tokens, credentials or database rows. Preserve full output as a local restricted artifact, report only the necessary non-sensitive facts in GitHub.

## Development replacement protocol
1. Identify the precise component, its active container/image, compose project, port and dependencies.
2. Preserve the **working version**: image reference/digest, Compose config, relevant application files, rollback command. Snapshot persistent data **only when the change can touch it**.
3. Prepare a replacement candidate with separate image/tag and nonconflicting resources, preferably an isolated validation port.
4. Run static/CI tests, container smoke tests and selected Portal user journeys; do not infer Debian success from CI.
5. Replace **only** the targeted component when baseline and rollback are documented. Check service health and key routes; restore previous image/config if acceptance tests fail.
6. Log command ID, operator authorization, SHA, test evidence, outcome and rollback status to issue #555 and the handover.

## Guardrails even in dev
No blind overwrite of five Compose stacks, no deletion of databases or volumes, no publication of secrets, no invented successful deployment. Internal Docker DNS allowed; off-server DNS forbidden. A live command requires the actual bridge and a verified request/receipt contract.

## Next action
Find the existing cron bridge's **command inbox, polling script, result outbox, authentication/allowlist, and repository/branch**; validate a harmless ping/host identity round trip; only then send the inventory above. If the bridge is not stored in this repository, obtain its exact repository or filesystem contract from the operator.
