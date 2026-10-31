# Debian qualification runbook

## Scope

This runbook separates clean Debian userspace qualification from inspection of an already-running AIOps2 host. The default mode is offline and non-mutating. Runtime mode reads the existing Compose configuration, container state and HTTP health endpoints; it does not start, stop, restart, rebuild or migrate services.

The GitHub Actions workflow runs the offline mode in a fresh `debian:12-slim` container and independently validates Compose rendering and builds application images. It does not connect to the production Debian host.

## Target host procedure (Debian 12/13)

Run from a checked-out candidate worktree, as the normal deployment account, not as root:

```bash
git status --short
git rev-parse HEAD
bash scripts/qualify-debian.sh --offline
```

For an existing running stack, with its existing protected `.env` file:

```bash
bash scripts/qualify-debian.sh --runtime
```

Runtime mode expects Docker Engine, the Compose v2 plugin, the existing `.env`, and all services required by `tests/qualification.sh` to be running. It checks Compose rendering, container presence and health URLs. It does not reveal environment values.

## What is tested

- Python virtual environment creation and pinned application dependency installation.
- Python compilation for `app/`, `tests/` and `tools/`.
- Repository static audit.
- Offline policy, Portal GLPI view, NOC tenant/correlation, ACME impact/fixture and cumulative release-kit regression suites.
- JavaScript syntax checks for Portal browser clients.
- In runtime mode: Compose config validation, expected container presence and Portal/GLPI/Prometheus/Grafana health endpoints.

## What is deliberately not done

- No `docker compose up/down/restart`, image rebuild or deployment.
- No PostgreSQL or MariaDB migration, direct SQL write, GLPI ticket/CMDB write or Temporal workflow start.
- No synthetic incident POST; no LIVE execution, SSH, sudo or Ansible.
- No secrets are printed. The temporary Python virtual environment is deleted on exit.

## Interpreting results

- `DEBIAN_OFFLINE_QUALIFICATION=PASS`: clean Debian userspace and selected offline suites passed.
- `DEBIAN_RUNTIME_READONLY_QUALIFICATION=PASS`: the existing stack passed the read-only checks in `tests/qualification.sh`.
- A missing service, unavailable health URL, missing `.env`, or missing Docker Compose is a blocker, not a pass.

## Current evidence boundary

The CI container result is evidence for Debian 12 userspace only. A target-host result must be attached with timestamp, hostname, OS release, candidate SHA, command output and redacted service health summary. Never upload `.env`, credentials, tokens, private keys or unredacted logs.
