# ACME SAN P1 → Payments P2 : synthetic impact contract

This PR ports three specific reviewed files from PR #36 (not its 374-file diff): `acme-fixtures.json`, `acme_fixture_contract.py`, and `acme_impact_read_model.py`. The portal now mounts:

- `GET /api/demo/acme-impact` — JSON read model, stable synthetic incident IDs and SHA-256-derived simulation run/ticket labels.
- `GET /demo/acme-impact` — local read-only topology and impact presentation linked from the portal navigation.

The source is `SAN-FABRIC-A` (incident `ACME-DEMO-SAN-001`, P1). The validated dependency DAG reaches `APP-PAY-01` (impact incident `ACME-DEMO-PAY-002`, P2) through host/volume and VM dependencies. The blast radius is computed transitively, not hardcoded as a successful runtime incident.

**GLPI:** `ticket_id=null`; `simulation_ticket_id=SIM-GLPI-...` is only a deterministic label, not a GLPI ticket. `run_id=SIM-ACME-...` is derived from fixture bytes, not Core/Temporal. No upstream service is contacted, no database writes occur and no real screenshots are claimed. Nine checkpoint placeholders remain `MISSING`.

**Modes:** this API is synthetic-only, even if the rest of the portal is configured in LIVE mode. Fixture validator rejects non-simulated incidents, LIVE remediation and non-allowlisted actions. Invalid, cyclic, duplicate-key, missing or symlinked fixtures fail closed; endpoint returns HTTP 503 on invalid local fixture. The current route is unauthenticated and intentionally contains only repository-published synthetic data; it must never be reused for sensitive CMDB or LIVE data without RBAC.

**Testing:** `tests/test_acme_impact_read_model.py` checks deterministic IDs, graph path, transitive blast radius, invalid actions/modes, cycles, unknown references, duplicate JSON keys, canonical portal mount, API, page and invalid fixtures. Existing `quality.yml` executes the test suite on PR; CI status is reported separately. No GLPI, n8n, Thruk, Grafana, Core or Debian runtime integration is qualified by these tests.

**Next:** correlate actual Core incident/run IDs and GLPI ticket IDs via authenticated, provenance-bearing adapters. Do not conflate simulated labels with persisted canonical IDs. Golden Demo may link this scenario, but should not claim the static view is a real executed Run.

## 2026-10-28 — Portabilité du point d’entrée de démonstration

Le champ JSON `entrypoint` est désormais `/demo/acme-impact`, chemin relatif au portail unique, et non une URL IP/port d’un serveur Debian. `entrypoint_provenance=RELATIVE_PORTAL_ROUTE_NOT_DEPLOYMENT_URL` explicite qu’il ne s’agit pas d’une preuve de disponibilité runtime. La page propose un retour local `/` ; les identifiants synthétiques, `ticket_id=null`, les neuf checkpoints `MISSING`, le refus LIVE et l’absence de capture authentifiée sont inchangés. Test de non-régression via ASGI avec Host arbitraire, sans appel réseau.
