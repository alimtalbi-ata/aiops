# ACME v1 — frontière de provenance Portal ↔ Twin (release P0)

**Décision : UNBOUND / NO-GO E2E.** Ce document interdit de présenter les deux graphes synthétiques comme une CMDB unifiée. Il ne crée **aucun alias d'identité** et ne change aucun endpoint.

## Sources réellement consultées (GitHub, 2026-10-29 02:57 CET)

- `app/portal/acme-fixtures.json` + `app/portal/acme_fixture_contract.py` sur `main` `27deb9b1a66faf27df8d69b137a63451f7649d80` : `aiops.acme.demo.v1`, `SIMULATED_TARGET`, `SAN-FABRIC-A` → `HOST-ESX-01` → `VM-PAY-01` → `APP-PAY-01`. Incident pédagogique P1 SAN et P2 Payments ; pas de télémétrie.
- `db/migrations/003_seed_twin.sql` + `005_seed_acme.sql`, `app/twin/main.py` sur candidate #170 : 25 nœuds/23 arêtes seed ; chemin inverse sourcé `ACME-SAN-FABRIC-A` → `ACME-STO-PURE01` → `ACME-VM-PAY01` → `ACME-APP-ORACLEPAY` → `ACME-SVC-PAYMENTS` → `ACME-BIZ-PAYMENTS` via E08/E06/E04/E02/E01. La liaison `ACME-VM-PAY01` → `ACME-SRV-RHEL01` (E10) **n'est pas** une liaison SAN → hôte.

**Constat contractuel :** les six identifiants CI Portal ne coïncident avec aucun identifiant Twin seed ; la topologie et le type d'hôte diffèrent. L'homonymie « Payments » et les préfixes similaires ne sont **pas** une preuve d'identité. Il n'existe dans cette qualification ni table d'alias sourcée/validée, ni liaison Run↔Policy↔Evidence, ni ACL tenant qualifiée.

## Contrat de consommation v1 (informatif, sans nouvelle API)

```json
{
  "schema": "aiops.acme-cross-source-boundary.v1",
  "scope": "TWO_INDEPENDENT_SYNTHETIC_MODELS",
  "portal": {"schema": "aiops.acme.demo.v1", "source_ci_id": "SAN-FABRIC-A", "target_ci_id": "APP-PAY-01"},
  "twin": {"root_node_id": "ACME-SAN-FABRIC-A", "business_node_id": "ACME-BIZ-PAYMENTS", "path_edge_ids": ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02", "ACME-E01"]},
  "verified_identity_mapping": [],
  "cross_source_join_verified": false,
  "tenant_acl_qualified": false,
  "runtime_impact_state": "UNKNOWN",
  "live_remediation_authorized": false,
  "overall": "NO_GO"
}
```

Un consommateur Explore/Story doit conserver le label `SIMULATED / TOPOLOGY_ONLY` et **ne jamais** réunir les IDs Portal/Twin comme s'ils représentaient les mêmes CI. Tout raccordement futur exige une table d'alias tenant-scopée, avec provenance CMDB vérifiée, revue et tests de refus ; ne pas déduire le lien par normalisation des noms.

## Test et portée

`tests/test_twin_impact_real_integration.py::test_portal_fixture_and_twin_seed_are_not_an_authenticated_join` valide le fixture canonique et confronte les deux espaces d'IDs, les arêtes et le résultat HTTP Twin au PostgreSQL 16 éphémère dans **quality.yml existant**. Aucun workflow supplémentaire, aucun changement de contrat HTTP.

**NOT_TESTED :** identité CI réelle, tenant A/B, navigateur client, Debian, applied.sha, déployeur Twin/Core, rollback, CMDB authentifiée, E2E IA→Policy SIMULATE→Evidence→Studio et impact Payments runtime. `READY_FOR_STABLE=BLOCKED`. Handoff à Recette 5/5 #156, sans push stable ni LIVE.
