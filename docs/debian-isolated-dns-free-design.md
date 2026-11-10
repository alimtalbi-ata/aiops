# DNS-free isolated deployment: architecture gate (issue #553)

Status: **DESIGN ONLY / RELEASE HOLD**. Do not run the installer on Debian 10.79.94.202.

## Known dependencies in `compose.isolated.yml`

| Client | Destination | Current service-name reference |
| --- | --- | --- |
| core, twin, evidence | PostgreSQL | `aiops2-postgres:5432` |
| core | policy, worker | `aiops2-policy:813`, `aiops2-worker:815` |
| copilot | core, twin, evidence | `aiops2-core:810`, `aiops2-twin:811`, `aiops2-evidence:812` |
| worker | core, evidence, policy, twin, Temporal | service names in HTTP URLs and `TEMPORAL_ADDRESS` |
| simulator | core | `aiops2-core:810` |
| portal | core, copilot, twin | service names in HTTP URLs |
| Temporal | Temporal PostgreSQL | `POSTGRES_SEEDS=aiops2-temporal-postgres` |
| Temporal UI | Temporal | `TEMPORAL_ADDRESS=aiops2-temporal:7233` |
| GLPI | MariaDB | `GLPI_DB_HOST=aiops2-glpi-db` |
| n8n | PostgreSQL | `DB_POSTGRESDB_HOST=aiops2-postgres` |

Additional service discovery in mounted Prometheus, Grafana, Alertmanager, application code and image entrypoints is **not yet audited**. No DNS-free claim can be made from Compose alone.

## Required implementation (not yet approved)

1. Choose non-overlapping, dedicated IPv4 subnets for each of the seven networks **only after** comparing them with the target host's routes, Docker address pools, and all existing Docker networks. Never assume a subnet is free. Fail closed on overlap or missing inspection data.
2. Assign a deterministic, unique `ipv4_address` for every service/network attachment. Use the destination address on a network shared with each caller. Verify all 18 containers and every declared dependency.
3. Replace every service-name reference in runtime environment and mounted configuration with an IP literal (or independently reviewed non-DNS mechanism). Validate TLS certificate identity and application-specific hostname assumptions; do not weaken certificate verification.
4. Confirm whether any application or third-party image performs DNS lookups outside the manifest. DNS-free means **no resolver queries**, including Docker's embedded resolver, not merely no external DNS.
5. Test rendered Compose config, static graph reachability, route/subnet collisions, runtime traffic and DNS-query absence. Ensure offline image loading and image identity are validated before any deployment.
6. Retain the unconditional installer HOLD until all acceptance criteria, P0 #535, independent review, backup/restore rehearsal and explicit change approval pass.

## Current safeguard

`deploy/install-isolated.sh` intentionally exits with `HOLD|dns_free_architecture_not_qualified|issue_553` before creating or modifying anything. This is a fail-closed release guard, not a finished installation path.
