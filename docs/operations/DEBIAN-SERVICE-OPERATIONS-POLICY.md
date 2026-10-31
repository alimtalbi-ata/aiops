# Debian service-operation authorization policy

The operator has explicitly authorized useful interventions on AIOps2 application services and application data while prohibiting Debian host/system administration commands. The machine account remains `aiops`.

The normative machine-readable policy is `config/ops/debian-service-operations-policy.yml`.

## Allowed scope

- Docker/Compose lifecycle operations for explicitly allowlisted application containers/services (inspect, health, start/stop/restart).
- PostgreSQL and MariaDB application-schema migrations and bounded application-data corrections through dedicated least-privilege database roles.
- GLPI lab tickets, CMDB, rules and catalogue through its supported API.
- Grafana lab dashboards, datasources and alert rules through its HTTP API.
- Temporal worker/service operations and synthetic workflows. LIVE remediation remains locked.

## Prohibited scope

No arbitrary shell/remote command strings; no `sudo`, `su`, systemctl/service-manager changes, apt/dpkg, host reboot, users/groups, kernel, SSH, firewall, routing, DNS, host network interfaces, system cron, or broad filesystem permission changes. No Docker exec or unrestricted Docker socket.

## Important privilege boundary

Membership in the `docker` group or direct access to the Docker socket is effectively host-root access. Do not grant either to the general polling agent. Use a narrowly scoped Docker API proxy or a separate service operator with only the permitted container lifecycle endpoints and an explicit container allowlist. Database and application APIs must use dedicated service identities.

## Execution policy

The current `scripts/debian-readonly-reporter.py` remains a read-only telemetry reporter. This authorization does not silently turn it into a remote shell or grant it new host privileges. The next implementation step is a separate typed job executor that accepts only enumerated operation names and validated resource IDs, with expiry, idempotency, bounded timeouts, audit events, pre/post checks and fail-closed behavior.

Service restart may be automated only after two consecutive failed health observations, dependency checks, and confirmation that the target is in the lab allowlist. Database changes must be versioned, backed by a verified restore point for destructive operations, use bounded lock/statement timeouts, and produce pre/postflight evidence. GLPI/Grafana changes use supported APIs and preserve audit history.

No operation may alter Debian host configuration or unlock LIVE remediation. The policy applies to AIOps2 lab resources, not customer production environments.
