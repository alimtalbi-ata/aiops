# Journal — 2026-10-28 02:35–02:39 Europe/Paris — P1 ACME/ITSM

## Point de départ / lecture

- Main HEAD vérifié par GitHub REST `refs/heads/main` : `0603e86a26978873c3b6196098674932d3378499` avant création de la branche.
- PR lues : #36 (374 fichiers, base divergente), #37, #39, #41, #43, et branches adjacentes #56, #69, #73. Roadmap `docs/DEVELOPMENT-ROADMAP-2026-10-27.md` lue sur le HEAD #39 `484cb153` ; continuité et architecture de main consultées.
- Portage **ciblé du concept** de graphe de `demo/noc_topology.py` sur #36, blob `987274c915fc759ea445168d3695ee0b4ec8d109`, sans reprendre son snapshot NOC ni fusionner la PR.
- Aucun accès Debian, portail LIVE, GLPI ou NGX.

## Livraison GitHub

- Branche : `feat/acme-declared-topology-20261028-0235` issue du SHA main ci-dessus.
- PR draft : [#77](https://github.com/alimtalbi-ata/aiops/pull/77), base `main`, pas de fusion.
- Fichiers : `app/portal/acme_declared_topology.py` (nouveau), `app/portal/acme_impact_read_model.py`, `tests/test_acme_impact_read_model.py`, `docs/demo/ACME-DECLARED-TOPOLOGY-20261028.md`, ce journal.
- Commits de code/docs : `af10b714` (graphe), `c8f7fb30` (API/portail), `f809c241` (tests), `a8fe5ac2` (libellé HTML), `cca5b451` (documentation).
- Fonction : graphe déterministe de six CI / sept arêtes du fixture ; chemin alternatif déclaré Fabric B → Payments, jamais présenté comme failover sain. Route `GET /api/demo/acme-topology` et cartes sur `/demo/acme-impact`. GLPI ticket, lien GLPI et Run canonique restent `null`; runtime, CMDB et failover `UNKNOWN`.

## Tests et preuves

- Workflow existant `.github/workflows/quality.yml` réutilisé ; aucun workflow CI parallèle ajouté.
- [GitHub Actions run 40616145232](https://github.com/alimtalbi-ata/aiops/actions/runs/40616145232), sur HEAD `cca5b451` : **IN_PROGRESS au moment de cette entrée** ; ne pas déclarer PASS avant conclusion réelle.
- Tests ajoutés (non qualifiés tant que CI non terminée) : ordre déterministe, alternative manquante `UNKNOWN`, interdiction LIVE, dépendances invalides, HTML hostile/XSS, route JSON et montage portail.
- Test local non exécuté : le conteneur d'analyse ne résout pas `github.com` pour `git ls-remote` (DNS). L'exécution effective des tests dépend de GitHub Actions.
- **NOT_TESTED/BLOCKED** : conteneurs réels Checkmk/Thruk/GLPI/Core/Temporal/n8n/Grafana, capture navigateur authentifiée, ticket GLPI réel, intégration complète, Debian, NIM 192B et Ollama 4B. Les tests unitaires n'en simulent pas les intégrations.

## Risques, non-régression et suite

- La topologie est une déclaration issue du fixture, pas une observation NOC/CMDB. Une route publique de démonstration ne doit jamais contenir de données CMDB réelles sans RBAC.
- Vérifier la conclusion CI et corriger toute régression avant revue. Pas de fusion ni de déploiement dans ce créneau.
- Micro-lot suivant : corrélation d'identités NOC/Core/GLPI authentifiées, après qualification des services réels en CI conteneurisée et du RBAC par tenant ; conserver `UNKNOWN` si les preuves manquent.
