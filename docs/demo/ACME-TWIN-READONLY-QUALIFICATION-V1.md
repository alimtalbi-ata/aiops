# ACME Twin — qualification HTTP lecture seule (v1)

**Périmètre :** script `scripts/qualify_acme_twin_readonly.py`, basé sur la correction
de parcours inversé PR #142 et les arêtes SQL exposées par PR #148. Aucune
nouvelle route API. Aucun accès à Debian ni au portail client.

## Exécution sûre

Après démarrage **volontaire** d'un Twin isolé sur `127.0.0.1:811`, avec le
seed `db/migrations/003_seed_twin.sql` puis `005_seed_acme.sql` dans une
base éphémère et un jeton local non productif :

```sh
AIOPS_TWIN_READ_TOKEN="<jeton éphémère du Twin>" \
  python scripts/qualify_acme_twin_readonly.py --base-url http://127.0.0.1:811
```

Le script n'accepte que l'hôte littéral `127.0.0.1`, HTTP, un port explicite,
sans chemin, query, credentials, caractères de contrôle ni redirection.
Les variables d'environnement `HTTP_PROXY`, `HTTPS_PROXY` et `ALL_PROXY`
sont ignorées explicitement pour empêcher l'envoi du bearer à un proxy
ambiant. Un HTTP 401 anonyme n'est accepté qu'avec `Cache-Control: no-store`
et `WWW-Authenticate: Bearer`. Il effectue **deux GET** :
un appel anonyme attendu HTTP 401, puis une lecture authentifiée
`GET /api/twin/impact/ACME-SAN-FABRIC-A`. Il ne déclenche ni migration,
ni mutation, ni action LIVE. La réponse est bornée à 256 KiB, avec
`Cache-Control: no-store`. Le décodeur JSON exige UTF-8, refuse les clés
dupliquées à toute profondeur (notamment `edge_id`), `NaN`, `Infinity`,
`-Infinity`, les corps tronqués et les structures trop profondes. Un
JSON ambigu est `BLOCKED / NO_GO`, jamais une preuve topologique.
Le jeton n'est jamais imprimé.

## Exemple de résultat synthétique attendu

```json
{
  "schema": "aiops.acme-twin-readonly-qualification.v1",
  "scope": "SEEDED_TWIN_TOPOLOGY_ONLY",
  "contract_status": "PASS",
  "overall": "NO_GO",
  "provenance": "SIMULATED_TOPOLOGY_NOT_RUNTIME_IMPACT",
  "root": "ACME-SAN-FABRIC-A",
  "topological_candidates": 10,
  "path_nodes": [
    "ACME-SAN-FABRIC-A", "ACME-STO-PURE01", "ACME-VM-PAY01",
    "ACME-APP-ORACLEPAY", "ACME-SVC-PAYMENTS", "ACME-BIZ-PAYMENTS"
  ],
  "path_edge_ids": ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02", "ACME-E01"],
  "san_host_link_verified": false,
  "runtime_impact_state": "UNKNOWN",
  "blockers": [
    "TENANT_RBAC_NOT_QUALIFIED",
    "DEBIAN_TWIN_NOT_TESTED",
    "CMDB_AND_RUNTIME_IMPACT_NOT_ATTESTED",
    "SAN_HOST_LINK_ABSENT_FROM_SEED",
    "CORE_COPILOT_POLICY_EVIDENCE_E2E_NOT_TESTED",
    "DEPLOY_COVERAGE_AND_ROLLBACK_NOT_QUALIFIED"
  ]
}
```

**Important :** `contract_status=PASS` signifie seulement que la réponse
correspond exactement aux **25 nœuds / 23 arêtes** du seed CI, avec
10 candidats topologiques atteignables et 10 arêtes shortest-hop sourcées
par ID. Le test d'intégration compare aussi les arêtes à PostgreSQL réel.
Cela ne prouve ni un incident Payments, ni un lien SAN → hôte, ni une
propagation runtime. Le lien `ACME-E10` est VM → hôte, pas SAN → hôte ;
le parcours affiché est SAN → stockage → VM → application → service →
business. SAN-B reste une dépendance alternative, sans qualification de
basculement. Un changement de seed ou une réponse non conforme est BLOCKED,
jamais automatiquement promu.

## Intégration et décision de release

Le test `tests/test_twin_impact_real_integration.py` appelle le script contre
le **vrai Twin Docker et PostgreSQL 16 éphémères** du workflow
`.github/workflows/quality.yml`. Tests négatifs : refus anonyme, URLs non
loopback, provenance/ACL/runtime falsifiés, arêtes et nœuds inventés ou absents,
duplicats, direction incorrecte. Aucun workflow parallèle.

**READY_FOR_STABLE = BLOCKED / NO-GO.** Les PR #142 puis #148 sont empilées :
le SHA de ce micro-lot est une candidate **de qualification CI**, pas une
release. Le poller Debian ne déploie que `deploy/aiops2-stable` et le
déployeur portail existant ne couvre pas automatiquement `app/twin/main.py`,
ce script, ni les tests. La PR #156 traite ce garde-fou. Transmettre ce
contrat au lot 5/5 Recette pour vérification d'intégration, rollback et
décision de promotion ; **ne pas pousser sur stable**.

**NOT_TESTED :** serveur Debian, ACL tenant qualifiée, CMDB authentifiée,
Core/Temporal/GLPI/Copilot/Policy/Evidence E2E, smoke-tests après déploiement,
captation opérateur et vidéo. Le cron ne constitue pas une recette E2E.

## Micro-lot de durcissement JSON — 2026-10-28 23:03 CET

Portage ciblé du motif de parsing strict de la sonde Core/Policy PR #163,
adapté au contrat Twin, sans importer son module ni modifier l'API Twin.
Le test HTTP positif lit le véritable Twin/PostgreSQL éphémère en CI ; les
variantes négatives sont des octets adversariaux construits à partir de
cette réponse, pas des appels réseau simulés. Les réponses JSON malformées
ne peuvent plus être qualifiées via un parseur permissif. La sortie
`aiops.acme-twin-readonly-qualification.v1` est inchangée.
