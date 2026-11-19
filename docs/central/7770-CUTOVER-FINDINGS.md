# Verified 7770 cutover findings

The candidate source `integration/portal-bounded-runs-consolidated-20261111` already contains the FastAPI portal and routes for NOC runtime/correlation, synthetic NOC RAG, Grafana health, ACME impact/explore/run detail, GLPI operator view, and configurable n8n/Thruk/Checkmk/Grafana/GLPI navigation. Its compose.yml defines internal port 777 and configurable host port AIOPS_PORTAL_HOST_PORT (default 17777).

The previously observed Debian container is named `aiops2-rebuild-portal` and published 7777->777. The GitHub compose service `aiops2-portal` is not yet proven to be the exact deployment source for that container. Do NOT run compose up from a different project: that could create a second portal.

Next action: locate the exact compose/deployment file for aiops2-rebuild-portal, then change only its host mapping to 7770 while preserving image digest, mounts, networks, env and dependencies. No rebuild if embedded code already matches. Keep 7777 rollback ready until browser acceptance. Test /, /health, /itsm, /demo/acme-impact, /demo/explore-story, NOC, RAG and Grafana endpoints.

A enrich existing UI only; B real data/history and preserve UNKNOWN; C reuse existing Intelligence/RAG/Copilot/GLPI/Temporal and label synthetic vs real; D non-regression full journeys. CENTRAL one integrated commit and one user-facing portal on 7770. POC01/02 are component sources only, not competing portals.