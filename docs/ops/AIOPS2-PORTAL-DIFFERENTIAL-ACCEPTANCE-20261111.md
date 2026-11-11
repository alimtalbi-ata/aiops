# AIOPS2 portal — differential upgrade acceptance, 2026-11-11 02:12 UTC

Scope: **audit, not reconstruction**. This document is a source-level acceptance protocol; it is **not** evidence of HTTP, Debian, CI, or E2E behavior. Do not run against live tenants without authorized test identities. Do not deploy, merge, restart, manipulate Docker, PG, GLPI or secrets.

## Provenance and freshness

- GitHub `app/portal/main.py` on `main` read 2026-11-11, blob `16d156c912ccc7592383f7d67a6a6a36fef50629`. This is source provenance **only**, not a deployed image mapping.
- #567 head `ebdc3f74e1925f2adcd3cccf6d03887f3f800bc4` contains a fragment-navigation negative regression test. GitHub Actions run 42937411840 reported completed/success for that SHA; this does **not** prove the specific pytest executed without inspecting jobs/logs.
- Debian rootless operator evidence: user `aiops`, UID 1001, context rootless, `/run/user/1001/docker.sock`, 87 containers / 210 images at time reported. It refutes the rootful `sudo docker` inventory as a loss diagnosis; it is not a fresh host inspection this cycle. **DEBIAN UNKNOWN (direct access not attested)**.
- Active portal observed image prefix `a1f3adcf1e11` on 2026-11-10, candidate `10.79.94.202:17778`, rollback fs1073/fs1051/fs621, historic v28/V145: runtime source mapping and HTTP response provenance **UNKNOWN**. Never infer regressions from labels alone.
- E2E **NOT VERIFIED**. For any receipt, record collection time, collector, identity/tenant class (not credentials), exact image digest, route, response status, sanitized body, and expiry. Do not promote expired receipts.

## Differential acceptance matrix (UNKNOWN is not failure)

| Capability / route | Source contract on main (before) | Candidate / rollback / historic (after) | Evidence and probable cause if discrepancy | Priority | Restoration strategy |
| --- | --- | --- | --- | --- | --- |
| Shell `GET /` / fragment navigation | #567 test expects anchors runs, twin, copilot, noc, integrations each resolve to one DOM id | HTTP 7777/17778, fs1073/fs1051/fs621, v28/V145 UNKNOWN | Source test; missing/duplicate id would indicate template drift, not confirmed runtime regression | P1 | Fix template fragment only on isolated branch; keep tenant gates |
| Dashboard/Core/Twin/Runs `GET /api/portal/bootstrap` | Viewer auth alone yields 503 `UNKNOWN` / `TENANT_ACL_NOT_QUALIFIED`; no upstream read | UNKNOWN | Source `main.py`; 200 for shared viewer without server-derived tenant ACL would be security regression | P0 | Preserve fail-closed; restore authorized contract only after qualified tenant/actor |
| Navigation/GLPI/NOC `GET /api/portal/components` | Viewer auth alone yields 503 `UNKNOWN` / `TENANT_ACL_NOT_QUALIFIED` | UNKNOWN | Source; registry disclosure before authorization would be security regression | P0 | Keep registry and operator URLs inaccessible until ACL qualification |
| Copilot `POST /api/copilot` | Viewer alone yields 503 `UNKNOWN` / `TENANT_ACL_NOT_QUALIFIED` | UNKNOWN | Source; unauthorized upstream request would be security regression | P0 | No fallback to legacy unrestricted Copilot |
| Evidence / NOC / GLPI | Routers imported/included in `main.py`; exact route contracts not qualified here | UNKNOWN | Router inclusion is not evidence of HTTP success or permissions | P1 | Inventory explicit routes and compare sanitized authenticated responses; preserve HITL |
| Visualisation / UX | Shell route exists; accessibility, rendering and chart semantics unqualified | UNKNOWN | Requires DOM/visual E2E under authorized test actor | P1 | Isolated UI correction after verified before/after artifact |
| `GET /health` | Returns status/component/ports; no tenant data | UNKNOWN | Source only; HTTP response and healthcheck UNKNOWN | P2 | Diagnose separately, no runtime changes |

## Read-only negative acceptance protocol

1. **Freeze evidence**: identify exact commit/image digest and timestamp for each comparison. Expire any stale Debian receipt; report `DEBIAN UNKNOWN` if no direct attestation. Do not infer rootless loss from rootful `sudo docker` output.
2. **Source-level CI**: on #567 head, run `pytest -q tests/test_portal_fragment_navigation_integrity_20261111.py`; record exit code, job URL, head SHA. Independently verify duplicate/missing fragment target causes a test failure (controlled test fixture only). No HTTP/E2E claim.
3. **Security negative** (authorized staging only): with a shared viewer token but *without* qualified tenant/actor, `GET /api/portal/bootstrap`, `GET /api/portal/components`, `POST /api/copilot` must remain fail-closed; expect HTTP 503, state UNKNOWN and reason TENANT_ACL_NOT_QUALIFIED. Assert zero Core/Twin/Copilot upstream requests. Never create a privileged test identity or bypass ACL.
4. **Functional before/after** (authorized staging only): compare route availability, navigation targets, empty/error states, dashboard and Runs contracts, NOC/GLPI/Evidence links, Copilot refusal, visual accessibility and HITL. For each environment record route, HTTP code, sanitized schema, actor class, freshness and screenshot/DOM evidence. No writes to PG/GLPI.
5. **Decision**: classify each discrepancy as CONFIRMED REGRESSION only with matching identity and fresh before/after proof; otherwise UNKNOWN. Block release for P0 ACL/HITL regression, avoid restoring historical unsafe behavior.
6. **Rollback of this documentation-only increment**: close Draft PR or revert its single documentation commit on the audit branch. **No operational rollback**.

Handoff: #555; canonical operational handover is `docs/ops/HANDOVER-AIOPS2-CURRENT.md` on `docs/debian-deployment-qualification-plan-20261110`, not on main. Do not concurrently edit that shared handover. #557 remains the resolved diagnostic distinction between rootful and rootless inventories, not evidence of lost Docker data.
