# 2026-10-29 05:04 CET — ACME Twin P0, fail-closed read auth

## Sources
- main: 27deb9b1a66faf27df8d69b137a63451f7649d80.
- stable: e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 (unchanged).
- Candidate PR #170 parent: 930dc4269de541a8cabe424d91c056d00d7e9421. Historical #142/#148 reviewed.
- Other slots: #156 Recette, #153 deployer, #176 Policy, #169/#177 UI, #171 NOC.
- Prior automation-runs reviewed, including 2026-10-29T0257-p0-acme-cross-source-boundary.md.

## One P0 vertical
- Require existing internal Bearer on Twin summary/nodes/graph/at/metrics before DB access.
- Keep health public and impact semantics unchanged.
- Add real HTTP integration regression to existing Twin/PostgreSQL CI job.
- Document compatibility break: Portal bootstrap and Prometheus may now see 401.
- Topology seed E08/E06/E04/E02/E01 remains SIMULATED/TOPOLOGY_ONLY.
- No SAN-to-host link or real Payments incident; Portal fixture has separate IDs.

## Gate / limitations
- SHA: use PR #170 HEAD after this commit; checks pending until verified.
- Targeted CI: real Twin HTTP/PostgreSQL job; full quality.yml (3 jobs).
- Tests locally: NOT_TESTED. Debian: NOT_TESTED.
- READY_FOR_STABLE=BLOCKED / E2E NO-GO (deadline 05:00 CET missed).
- Tenant A/B RBAC, Core/IA/Policy SIMULATE/Evidence/Studio correlation,
  deployer transport of Twin/Core/Policy, rollback and applied.sha NOT_TESTED.
- Handoff to #156 only; no stable push, merge, Debian access or LIVE action.

## CI observée sur commit code/tests
- SHA `a81f93a7421f829dbf9c87409592a64744c96618` (PR #170).
- `quality.yml` run https://github.com/alimtalbi-ata/aiops/actions/runs/40815867966 : completed/success, 3/3 jobs SUCCESS.
- Log du job Core/PostgreSQL/Twin lu : 12/12 tests Twin HTTP réel, dont le nouveau test de fermeture des cinq lectures ; 14/14 Core/Policy et 8/8 Policy HTTP, 5/5 NOC.
- Grafana réel et policy-and-static : SUCCESS. Tests CI éphémères uniquement, aucun smoke Debian.
- Cette annotation documentaire produit un HEAD ultérieur : ne pas transférer automatiquement la CI du SHA précédent ; revalider la CI sur HEAD final.
- READY_FOR_STABLE=BLOCKED / NO-GO, notamment pour compatibilité Portal/Prometheus et tenant RBAC.
