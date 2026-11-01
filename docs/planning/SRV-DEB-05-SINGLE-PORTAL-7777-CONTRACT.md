# AIOps2 DEV — single portal entry on TCP 7777

**Decision:** 2026-11-01, user directive. One Debian 13 host `SRV-DEB-05`, one persistent DEV infrastructure, one canonical portal entry **host TCP 7777**. The requirement is an **acceptance contract**, not an assertion that the host is already listening on 7777.

## Evidence and gap

GitHub-published read-only report `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected `2026-11-01T13:14:01.830140+00:00` inventories `aiops2-rebuild-portal` running plus `aiops2-portal-candidate-web-20261029` and `aiops2-noc-rag-test` running, `aiops2-portal-rollback-v2-20261028` exited, and `aiops2-demo-web-v1` running. It does **not** report port bindings or ingress routing. Loopback probes include **17777 reachable**, not **7777**; do not confuse these distinct ports. `7777` is **NOT_VERIFIED** as of this report.

## Acceptance gates

1. Collect redacted read-only `docker inspect` port bindings/labels/mounts/network for each portal, `docker compose config` for its actual project, `ss -lnt` scoped to 7777 and 17777, and reverse proxy/firewall routes. Avoid exporting environment secrets.
2. Choose **one** existing healthy portal (prefer `aiops2-rebuild-portal` if it is the active canonical UI after traffic/config verification); preserve its volumes, session state and upstream API contracts.
3. Produce a single canonical compose service and ingress mapping for host TCP `7777`; other components remain internal unless an explicit technical dependency needs exposure. Avoid accidental volume recreation caused by Compose project rename.
4. Prove `http://127.0.0.1:7777` (or HTTPS if configured) responds with expected portal identity and application smoke; test authenticated operator flows and upstream Core/GLPI without LIVE actions. If TLS/hostname is required, record exact probe scheme/Host header. A listening socket alone is not an application test.
5. Confirm exactly one externally reachable DEV portal; inventory and safely retire duplicate portal listeners after preserving rollback artifacts and checking active clients. No removal of volumes or databases, no `down -v`, no prune.
6. Qualify in-place update and rollback, with SHA/image digest, before changing stable deployment. `deploy/aiops2-stable` remains unchanged until approval.

**Owner:** Architecte intégrateur (5/5) coordinates Portal (2/5) and all other teams. All five existing schedules have received this directive. Required status is `PORT_7777=NOT_VERIFIED` until real Debian evidence. Reference [consolidation contract](SRV-DEB-05-INPLACE-CONSOLIDATION-2026-11-01.md).
