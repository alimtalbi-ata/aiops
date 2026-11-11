# ACME — topologie déclarative SAN → Payments (2026-10-28)

## Incrément

Le portail existant `GET /demo/acme-impact` montre désormais les **six CI** du fixture et un chemin alternatif **déclaré** depuis `SAN-FABRIC-B`. L'API `GET /api/demo/acme-topology` retourne les nœuds et arêtes complets, triés de façon déterministe. `GET /api/demo/acme-impact` contient le même graphe sous `topology`, avec SHA-256 des octets exacts et identifiant de run `SIM-ACME-*` dérivé du fixture.

La fonction pure `app/portal/acme_declared_topology.py::build_declared_topology` adapte **uniquement le concept de graphe** de `demo/noc_topology.py` de la PR #36 (source blob `987274c915fc759ea445168d3695ee0b4ec8d109`), sans importer ses états de supervision, ses hôtes ou son backend fictif. Elle valide le fixture canonique avant de dériver le graphe.

## Sémantique de sécurité

- Les arêtes `from → to` signifient « dépendance déclarée → consommateur » ; elles ne prouvent pas un lien observé.
- `alternate_declared_path` signale un chemin **déclaré** depuis Fabric B ; `alternate_path_status=DECLARED_NOT_VERIFIED` ne prouve ni sa santé, ni la redondance opérationnelle, ni un basculement.
- Si Fabric B ou son chemin manque, `alternate_path_status=UNKNOWN`, `alternate_declared_path=null`. Aucune déduction optimiste.
- Chaque nœud a `runtime_health=UNKNOWN`; `cmdb_verified=false`, `live_discovery=false`, `failover_verified=false`, `live_remediation_authorized=false`.
- `canonical_run_id=null`, `glpi_ticket_id=null`, `glpi_ticket_url=null`. Les deux incidents ACME sont **synthétiques** ; aucun ticket GLPI ni Run canonique n'est attesté.
- La route ne contacte aucun service, n'exécute aucune action, et réutilise l'ouverture bornée du fixture sans suivi de symlink. Le HTML échappe les noms de CI. Les données sont uniquement les fixtures publics du dépôt ; **ne pas y ajouter de CMDB réelle sans RBAC**.

## Tests / qualification

`tests/test_acme_impact_read_model.py` (workflow existant `.github/workflows/quality.yml`) couvre le tri, le chemin alternatif, l'absence d'alternative, les incidents LIVE rejetés, les références inconnues, le HTML hostile, l'API et le montage dans le portail. Les résultats CI doivent être vérifiés sur la PR et consignés dans le journal, jamais supposés.

**NOT_TESTED** : Checkmk, Thruk, GLPI, Core/Temporal, navigateur authentifié, conteneurs éphémères de ces services, Debian et LIVE. Ce lot est un contrat de graphe purement synthétique ; il ne constitue pas un test d'intégration des services.

## Suite

Lier des observations authentifiées NOC/Core/GLPI au graphe sans modifier les fixtures publics, puis afficher `UNKNOWN` pour toute identité ou preuve manquante. Vérifier le graphe et les vrais tickets contre des services conteneurisés avant toute qualification d'intégration.
