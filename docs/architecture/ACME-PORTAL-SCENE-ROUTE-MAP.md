# ACME Workbench Demo — source-backed Portal route map

**Status: SOURCE_ONLY / BROWSER_NOT_TESTED / LIVE_NO_GO.** Derived from `@app.get` decorators in `app/portal/main.py` on the #805 base; this is not a deployed-route or selector qualification.

| Scene | Candidate existing GET routes | Evidence level / gap |
|---|---|---|
| NOC overview | `/`, `/demo-studio` | Route in source; not a verified NOC scene |
| Signals / correlation | `/timeline`, `/qualification-lab` | Routes in source; no P1→P2 browser assertion |
| Twin dependency | `/twin`, `/demo-studio` | Routes in source; no verified SAN→Payments graph |
| Analyst / Critic | `/demo-studio/run/{rid}` | Source route requires a **real eligible DEMO/REPLAY/STORY Run ID**; no synthetic run ID substitution |
| Policy / HITL | `/policy`, `/policy-control`, `/policy-story` | Routes in source; no approval or execution authority implied |
| ITSM / worker receipt | **None qualified** | `NOT_IMPLEMENTED` until a read-only, tenant-qualified, SIM-GLPI worker receipt route is confirmed |
| Timeline / export | `/timeline`, `/demo-studio/run/{rid}` | Source routes; export evidence and 17-stage completeness unverified |

Source inspection additionally found `/acme-stories`, `/qualification`, `/qualification-lab` and `/api/demo-status/{rid}`. The latter is a GET polling endpoint, but the scene inventory does **not** treat it as an independent browser proof. `POST /api/demo` and `POST /api/demo-enriched` are deliberately excluded from all capture candidates.

The existing `/demo-studio` view may display an operator token field and an enabled demo launch button when `AIOPS_DEMO_LAUNCH_ENABLED=true`. **Never** automate the launch, enter tokens or capture a page containing secrets. Its read-only narrative is not a verified E2E receipt. The run detail route may return 404 when the run is not available; do not fabricate a `RUN-*` identifier.

## Deterministic source check

```bash
python scripts/acme_portal_route_inventory.py
python -m unittest discover -s tests -p 'test_acme_portal_route_inventory.py' -v
```

The inventory CLI deliberately returns exit **2** while any of seven scene categories has no confirmed source route (currently ITSM/worker), even if all other source routes are present. Output explicitly sets every selector to `NOT_VERIFIED`, browser to `NOT_TESTED`, deployed route to `NOT_VERIFIED`, and `seven_scenes_browser_qualified=false`.

## Next qualification step (requires separate sandbox approval)

Confirm exact selectors and tenant access on a **disposable isolated sandbox**. Adapt the **existing** `deploy/debian-portal-playwright-snapshot.py` GET-only, same-origin, private atomic screenshot mechanism, without adding a competing runner or modifying its host schedule. Only after seven actual scenes and their runtime provenance are qualified should the addon accept a scene evidence manifest. Do not bypass the Convergence Run detail `TENANT_ACL_NOT_QUALIFIED` boundary.

Related: #804 (tracking), #805 (readiness), #807 (capture reuse inventory), #808 (addon).
