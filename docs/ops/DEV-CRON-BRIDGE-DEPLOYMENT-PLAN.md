# AIOPS2 — DEV deployment through existing cron bridge (discovery required)

Date: 2026-11-10. User authorizes **development iteration and controlled replacement** on isolated noncritical Debian after preserving the currently working function. This is a **change of risk appetite**, not proof of a working command channel.

## Facts checked
- The GitHub `main` tree has `deploy/preflight.sh`, `00-Deployment/status.sh`, `scripts/automation_heartbeat_gate.py`.
- `00-Deployment/status.sh` invokes `docker compose --env-file .env ps`; it requires local Docker and cannot run through the GitHub connector.
- `deploy/preflight.sh` calls `deploy/init-env.sh`, so **it is not strictly read-only**. Do not use it as the first inventory command.
- `scripts/automation_heartbeat_gate.py` evaluates an offline evidence JSON and **explicitly does not invoke a scheduler or runtime**.
- The minute-based bidirectional Debian cron bridge described by the user is **not identified in the GitHub main paths examined**, and no command dispatch/receipt protocol has been verified. Do not invent a path, endpoint, or response.

## Historical GitHub evidence recovered — 2026-11-10

A full recursive tree of `main` was inspected (247 entries, not truncated). No minute-based cron command inbox/outbox or dispatcher appears as a tracked path. This is a **source-tree finding**, not proof that the cron does not exist on Debian.

- [Cron strategy](https://github.com/alimtalbi-ata/aiops/blob/main/docs/operations/AIOPS2-SCHEDULE-AND-CRON-STRATEGY-2026-10-30.md) distinguishes ChatGPT schedules, GitHub Actions and Debian cron. At the time of that document, Debian cron was **UNATTESTED**. This may be stale relative to the user's more recent host configuration.
- [Issue #464](https://github.com/alimtalbi-ata/aiops/issues/464) identifies **Agent 8, the Debian↔GitHub bridge** and an existing audit artifact `aiops2-audit-20261108T112946Z.json`. Its exact path and confidentiality were not verified. It names three modified local checkouts: `/home/aiops/aiops-v28-demo`, `/home/aiops/aiops2-fs-demo-source`, `/home/aiops/aiops2-p0-consolidation`. **Do not reset/clean/overwrite them.**
- [Issue #396](https://github.com/alimtalbi-ata/aiops/issues/396) documents a historical `deploy/aiops2-stable` poller, with source SHA and image digest at the time of the report. **This is a historical deployment receipt, not current host verification.**
- [Issue #457](https://github.com/alimtalbi-ata/aiops/issues/457) distinguishes ChatGPT schedules from an actual Codex/host dispatcher.
- Product priority from [#385](https://github.com/alimtalbi-ata/aiops/issues/385), [#386](https://github.com/alimtalbi-ata/aiops/issues/386) and [#186](https://github.com/alimtalbi-ata/aiops/issues/186): restore Portal navigation, NOC, GLPI, n8n login, DemoCenter/recorder and evidence-backed SAN→Payments journey before cosmetic redesign.

**Actionable next discovery**: inspect historical stable poller and Agent 8 handoff comments for exact bridge script paths, request/response transport and current host receipts. A minute cron is not the same as a ChatGPT automation or a GitHub scheduled workflow. Do not create another cron until the existing one is identified.

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
