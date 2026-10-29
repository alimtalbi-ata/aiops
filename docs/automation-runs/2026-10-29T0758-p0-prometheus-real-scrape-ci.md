# 2026-10-29 07:58 Europe/Paris — P0 ACME Twin : scrape Prometheus réel en CI

## Sources et coordination
- HEAD `main` lu : `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, inchangée.
- PR ouvertes, branches récentes et journaux `docs/automation-runs` consultés. Candidate ACME **unique** [#170](https://github.com/alimtalbi-ata/aiops/pull/170), base main, draft, mergeable observée, ahead=28/behind=0 au SHA code. #142 puis #148 : CI historique verte sur leurs SHA respectifs, non fusionnées ; leur correctif de direction et leurs arêtes sourcées sont déjà repris dans #170.
- Autres créneaux : #156 Recette 5/5 (HEAD `c391029a`, bloque la promotion et qualifie Evidence offline seulement), #153 déployeur (portail seulement), #176 Policy, #171 NOC/Copilot et #177 UI. Aucun résultat de ces branches ne constitue un E2E ACME intégré.

## UNE livraison verticale : vrai Prometheus -> vrai Twin/PostgreSQL en CI
La candidate précédente testait `/metrics` par client HTTP, mais **pas le scrape du binaire Prometheus**. Cette livraison ajoute :
- `tests/test_prometheus_twin_real_scrape.py` : assertions fail-closed sur l'API Prometheus `/api/v1/targets`, `up{job="aiops2-twin"}=1`, `aiops_twin_nodes{job="aiops2-twin"}=25`, cible et dernière collecte réelles ; tests négatifs pour cible DOWN, doublon, valeur forgée ou absente.
- Un pas dans **`.github/workflows/quality.yml` existant** : lancement éphémère de `prom/prometheus:v3.14.0` en Docker contre le **vrai Twin Docker + PostgreSQL 16 seedé** dans le même job. La config de production est copiée en répertoire CI et **seul** le hostname cible est remplacé par `127.0.0.1` pour le réseau host CI. Credential synthétique éphémère `ci-twin-metrics-ephemeral-only` monté en lecture seule, jamais une valeur de production. Prometheus et Twin sont détruits en `always()`.
- **Aucun changement de contrat runtime** : les routes Twin, le Bearer metrics-only, les arêtes SQL, `compose.yml` et les secrets déployés sont inchangés. Aucun nouveau workflow, aucune mutation métier ou LIVE.

## Tests réellement exécutés et SHA
- Commits : `8ea7e56d56c2c4f41dbe48c42ef90b50cecea6f9` (test), `2a8402b322b1affd71acb68a8bc148d361faf85f` (sélection du job Twin dans les cibles Prometheus multiples), `1f5aa5bcc635b0ca4659802ea0e123d50a3b13cc` (CI).
- [quality.yml #40832352072](https://github.com/alimtalbi-ata/aiops/actions/runs/40832352072) : **completed/success sur SHA code `1f5aa5bcc635b0ca4659802ea0e123d50a3b13cc`, 3/3 jobs SUCCESS**. Logs du job Core/PostgreSQL consultés : **14/14 Twin** et **2/2 tests Prometheus**, dont `test_real_prometheus_scrapes_twin_seed ... ok`, ainsi que **14/14 Core/Policy**. Les jobs statique/Policy et Grafana sont verts. Ce résultat atteste un scrape réel **dans CI éphémère uniquement**, pas sur Debian.
- Tests ciblés locaux : **NOT_TESTED** (aucun clone local du dépôt). La nouvelle CI a exécuté le test ciblé avant la fin des autres étapes du job. Le commit du présent journal change le SHA : **ne pas réutiliser la CI du SHA code comme qualification du nouveau HEAD** ; vérifier `quality.yml` sur le SHA final avant handoff.

## Provenance et limites
- Le seed `db/migrations/003_seed_twin.sql` + `005_seed_acme.sql` décrit 25 nœuds, 23 arêtes. Traversée inverse SAN-A -> stockage -> VM -> application -> service -> Payments par `ACME-E08/E06/E04/E02/E01` : **SIMULATED / TOPOLOGY_ONLY**, pas une panne Payments ni un lien SAN -> hôte.
- Le modèle Portal `SAN-FABRIC-A -> HOST-ESX-01 -> VM-PAY-01 -> APP-PAY-01` n'est pas joint au Twin par des IDs CMDB attestés. `runtime_impact_state=UNKNOWN`, `tenant_acl_qualified=false`.
- `NOT_TESTED` : vrai scrape sur Debian, tenant RBAC, corrélation Core -> IA -> Policy SIMULATE -> Evidence -> Demo Studio, migration des credentials existants, compatibilité déployeur multi-services, rollback, `applied.sha` et smoke-tests terrain. Le poller Debian ne valide pas E2E.

## Handoff Recette 5/5
**READY_FOR_STABLE=BLOCKED ; GO/NO-GO=NO-GO.** Le déployeur stable ne transporte pas Twin/Core/Copilot/Prometheus ; aucune promotion ni fusion ne doit être déclenchée sans assemblage qualifié, CI complète verte sur SHA final, recette, rollback et preuve serveur horodatée. La PR #170 reste draft ; aucune écriture sur `deploy/aiops2-stable`, aucun accès Debian et aucune action LIVE.

Prochain lot : Recette 5/5 doit intégrer de manière contrôlée le transport multi-services, confirmer le scrape et la chaîne métier sur une version approuvée, puis demander `applied.sha` et résultats observés avant décision GO.
