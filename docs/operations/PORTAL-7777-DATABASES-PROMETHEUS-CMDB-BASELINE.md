# Portal 7777 — Databases / Prometheus / CMDB integration baseline

Status: discovery, no production deployment authorized.

## Confirmed from operator host
- Production portal: `aiops2-rebuild-portal`, image `aiops2-portal:fs621-explorers-candidate`, host `0.0.0.0:7777 -> 777/tcp`.
- Prometheus: `aiops2-rebuild-prometheus` (`prom/prometheus:v3.14.0`), no host port shown.
- Grafana: `aiops2-rebuild-grafana` (`grafana/grafana:13.2.2`), bound to `10.79.94.202:3000`.
- PostgreSQL: `aiops2-rebuild-postgres` and `aiops2-rebuild-temporal-postgres`; qualification databases also exist.
- Host Git branch: `feat/cron-stable-auto-deploy-20261028`; clean status in operator output.

## Confirmed from GitHub branch source
- `app/portal/main.py`: FastAPI app, existing `/twin` graph and inventory, `/api/portal/bootstrap` and other pages.
- `app/portal/ui_theme.py`: shared `NAV`, `shell`, `panel`, `table` and HTML escaping.
- `app/portal/twin_graph.py`: bounded interactive SVG topology from Twin graph data, with filters and selection.
- `compose.yml`: portal network `aiops2-public` + `aiops2-control`; Prometheus `aiops2-observability` + `aiops2-control`; PostgreSQL is on data network. Do not assume portal direct DB reachability.
- The checked-out source and production image tag differ; code/image parity has not been verified.

## Target UX (candidate)
1. `/databases`: read-only database service health, connectivity, safe summary metrics, freshness and unknown/error states; no arbitrary SQL endpoint or credential exposure.
2. `/prometheus`: server-side allowlisted Prometheus queries and target health, Core/Twin metrics with clear time ranges; no browser access to internal Prometheus or open query proxy.
3. `/cmdb`: reuse Twin graph as existing topology; clearly distinguish Twin graph from authoritative GLPI CMDB. Add authoritative GLPI inventory only after an authenticated read-only integration is qualified.

## Prerequisites before implementation
- Determine whether the live portal image contains the same routes as the Git source.
- Determine which network(s) the running portal and data sources share, and whether a read-only service adapter already exists.
- Identify a qualified CMDB source: GLPI API versus Twin-only graph.
- Establish authentication/authorization for new views: current source shell does not itself demonstrate a user authorization boundary.
- Create tests for input allowlisting, HTML escaping, unavailable upstreams, no secret leaks and zero writes.

## Deployment gate
Implement and build only in a separate qualification image, test on an isolated port, and require explicit user approval before modifying `aiops2-rebuild-portal` or host port 7777.
