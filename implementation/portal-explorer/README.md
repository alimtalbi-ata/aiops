# FS621 — AIOps2 unified exploration kit

Status: **GitHub implementation candidate; not deployed**. This directory is an additive image overlay built **FROM the exact running portal image**, not a replacement of the deployed GLPI ownership code. It does not alter Core, Worker, Temporal, GLPI, HITL or remediation. Never merge an unverified older `app/portal/glpi_*.py` over the running container.

## Scope

- `/explorer/databases`: three named database sources (core PostgreSQL, Temporal PostgreSQL, GLPI MariaDB), information-schema table list, single SELECT with limit <=200, table output.
- `/explorer/prometheus`: instant and range PromQL, inline time-series canvas chart, target health.
- `/explorer/alerts`: rule inventory, firing alerts, target status, query and duration.
- `/explorer/logs`: Loki LogQL query_range.
- `/explorer/traces`: Tempo trace lookup by validated hex trace ID.
- `/explorer/cmdb`: read-only health connectivity only; **CI inventory API still needs qualification**.
- `/explorer/orchestration`: read-only connectivity only; **Temporal and n8n history APIs still need qualification**.
- `/api/explorer/catalog`, `/api/explorer/observability/...`, `/api/explorer/databases/...`.

All pages are directly accessible **without login or user-supplied token**, but access is **network restricted**. `EXPLORER_ENABLED=1` and `EXPLORER_ALLOWED_CIDRS` are mandatory; without either, the explorer fails closed. Do not put port 7777 on the public Internet. A reverse proxy must not expose this endpoint outside the trusted administration network. The allowlist checks the **actual TCP peer**, not spoofable forwarded headers.

### Explicit limitations / acceptance gates

1. This repository's main branch does not contain the deployed `glpi_run_context.py` or `glpi_client.py` fixes; the exact current base image is therefore mandatory.
2. The FS620 archive exists only on the user's Debian server, not in this GitHub branch. Verify its SHA-256 `0399d2304f99babd130c2c7e758318f448b6450f74796fe421121e596f1abcb3` before source comparison.
3. SQL DSNs are deliberately absent. **Never supply existing write-capable Core/Temporal/GLPI credentials**. Provision independent SELECT-only accounts, restricted to intended schemas/tables, and use transaction READ ONLY. SQL functions may be invoked by SELECT; database roles are the primary protection. Never enable SQL Explorer with privileged roles.
4. Confirm host networking from portal to Loki and Tempo; they may be in another Compose project.
5. Confirm CMDB, Temporal and n8n read API contracts before enabling data browsing; health alone is not an inventory view.
6. Prometheus presently has 5 targets, 2 DOWN (Core, Twin), 1 filesystem rule firing; six-family coverage is **not** established by this kit.
7. No external API calls to GLPI or Worker are added. No automatic HITL approval, remediation, run execution or ticket closure.
8. Candidate build requires package access to install pinned PyMySQL. Use approved internal package mirror in restricted environments.
9. Revalidate existing GLPI env and compose service configuration before the one-time cutover; Compose overlay **inherits** existing service env but cannot restore environment supplied only through prior manual `docker run` commands.
10. The portal home navigation is not patched; links are available by direct path. Integrate navigation only after the current HTML shell is compared with the FS620 source archive.

## Candidate build, without deployment

From the repository root:

```bash
bash implementation/portal-explorer/build-candidate.sh
```

The script builds `aiops2-portal:fs621-explorers-candidate` from the exact deployed image and validates imports and route registration without starting the stack. No running container is changed.

For deeper security tests:

```bash
docker run --rm --entrypoint python3 aiops2-portal:fs621-explorers-candidate -m unittest discover -s /app/explorer_tests -v
```

The Dockerfile must COPY `tests/test_security.py` into `/app/explorer_tests/` before that command (included in this kit).

## Configuration (never commit credentials)

```text
EXPLORER_ENABLED=1
EXPLORER_ALLOWED_CIDRS=<admin client subnet or reverse-proxy TCP peer CIDR>
EXPLORER_PROMETHEUS_URL=http://aiops2-prometheus:9090
EXPLORER_LOKI_URL=<reachable Loki base URL, optional>
EXPLORER_TEMPO_URL=<reachable Tempo base URL, optional>
EXPLORER_CMDB_URL=<verified CMDB base URL, optional>
EXPLORER_TEMPORAL_UI_URL=<verified read-only UI URL, optional>
EXPLORER_N8N_URL=<verified read-only health URL, optional>
EXPLORER_CORE_PG_DSN=<PostgreSQL read-only DSN, optional>
EXPLORER_TEMPORAL_PG_DSN=<PostgreSQL read-only DSN, optional>
EXPLORER_GLPI_MYSQL_DSN=mysql://readonly_user:password@host:3306/glpi
```

Never print these values in logs or paste them into chat. The SQL engine rejects multi-statements, comments, and non-SELECT starts; read-only database privileges and transaction-level READ ONLY are **required**, not optional.

## One-time deployment, only after review

Confirm candidate, source parity, DB roles, service networking, GLPI env preservation, and reverse-proxy network perimeter. Then run the supplied `deploy-once.sh` with `COMPOSE_FILE`, `EXPLORER_ALLOWED_CIDRS`, and explicit `DEPLOY_FS621=YES`. It records the previous image and keeps an overlay for rollback. It never uses `--remove-orphans`.

**Do not deploy solely because the build succeeds.** Full-stack smoke checks, GLPI ownership readback for #149–154, ticket #147 preservation, and negative authorization checks remain deployment acceptance criteria.

## Files

- `app/portal/explorer_api.py`: allowlisted read-only FastAPI router
- `app/portal/explorer_ui.html`: no-CDN standalone accessible navigation
- `app/portal/explorer_ui.js`: browser-side queries, tables and charts
- `Dockerfile`: additive portal image
- `build-candidate.sh`: candidate build and smoke checks
- `deploy-once.sh`: explicitly gated single deployment
- `tests/test_security.py`: negative authorization and SQL validation tests

The kit intentionally does **not** replace the deployed GLPI modules and does **not** claim that unconfigured data sources are operational.
