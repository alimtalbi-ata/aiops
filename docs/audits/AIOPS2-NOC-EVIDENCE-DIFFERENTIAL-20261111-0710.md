# AIOPS2 — audit différentiel NOC/Grafana versus Evidence (2026-11-11 07:10 Europe/Paris)

## Périmètre et provenance
Audit source seulement. `app/portal/main.py` blob `16d156c912ccc7592383f7d67a6a6a36fef50629` lu sur `main` : le shell affiche « Grafana réel — contrôle HTTP uniquement », « NOT_TESTED — service non interrogé », un NOC runtime `UNKNOWN` et une corrélation NOC/Run non attestée. Le contrôle HTTP Grafana ne prouve **ni métriques Checkmk/Thruk, ni autorisation tenant, ni Evidence**. `GET /api/noc/runtime-state` et `GET /api/noc/correlation` sont mentionnés dans le shell ; ne pas déduire leur comportement runtime de ces libellés. Aucun E2E effectué.

## Matrice avant/après et recette
| Fonction / route | v28/V145/fs1073/fs1051/fs621 | Source actuelle | Actif 7777 | Candidat 17778 | Risque/cause hypothétique | Priorité | Restauration autorisée |
|---|---|---|---|---|---|---|---|
| NOC Grafana contrôle HTTP (shell `GET /`) | UNKNOWN | bouton « Tester Grafana réel (HTTP) », NOT_TESTED initial | UNKNOWN | UNKNOWN | HTTP 200 pris pour preuve d'observabilité | P1 | séparer transport et Evidence, sans mutation |
| NOC `GET /api/noc/runtime-state` | UNKNOWN | route annoncée, HMAC/fraîcheur revendiqués par texte UI | UNKNOWN | UNKNOWN | signature/horodatage absents ou périmés | P0 | refuser preuve non qualifiée |
| NOC `GET /api/noc/correlation` | UNKNOWN | lecture annoncée, affichage UNKNOWN initial | UNKNOWN | UNKNOWN | Run non autorisé ou corrélation erronée | P0 | conserver fail-closed tenant |
| Evidence / Twin / Runs | UNKNOWN | états UNKNOWN sans données attestées | UNKNOWN | UNKNOWN | « healthy » dérivé du simple HTTP Grafana | P0 | conserver UNKNOWN sans Evidence |
| Navigation GLPI/ITSM `/itsm`, Copilot `#copilot` | UNKNOWN | liens visibles dans shell ; ACL API séparée | UNKNOWN | UNKNOWN | lien cassé ou fuite d'URL configurée | P1 | vérifier DOM et ACL, pas de contournement |

**Test négatif de recette (fixture synthétique, hors production)** : simuler Grafana HTTP 200 avec `metrics=[]`, absence de signature NOC, `source_freshness=UNKNOWN` et tenant non qualifié. Attendu : transport éventuellement joignable, mais état Evidence/Run/Twin toujours UNKNOWN, aucune métrique « healthy », aucune corrélation LIVE, aucun lien opérateur sensible, aucun appel Core/Twin/GLPI ni mutation. Répéter avec timeout, 404, signature invalide, preuve périmée et corrélation Run contradictoire ; chaque échec doit rester non attesté. Contrôle positif distinct : seule une fixture explicitement autorisée, signée et fraîche peut alimenter une lecture qualifiée, jamais un succès HTTP seul. **Recette définie, non exécutée.**

## Critères de preuve avant comparaison
Pour chaque version : SHA source, digest image complet, provenance image↔commit, contexte Docker rootless, horodatage UTC, route/méthode, statut HTTP, réponse expurgée et empreinte, rôle/tenant synthétiques, résultat CI au SHA exact. Une capture `sudo docker` rootful vide ne renseigne pas l'inventaire rootless `aiops` (UID 1001, socket `/run/user/1001/docker.sock`). #557 : faux diagnostic rootful/rootless selon preuves opérateur ; aucune recherche de stockage, reconstruction ou accès Debian.

**Statuts** : SOURCE attestée sur GitHub ; CI à vérifier sur SHA du présent document ; DEBIAN UNKNOWN (pas d'accès hôte direct frais) ; E2E NON VÉRIFIÉ ; v28/V145, images rollback et HTTP 7777/17778 UNKNOWN. Ne pas qualifier un refus ACL/HITL de régression. Aucun changement de stacks, runtime, secrets, PG/GLPI, Docker ou `main`.

**Rollback GitHub uniquement** : fermer la PR Draft ou revert le commit documentaire sur cette branche. Handoff coordinateur #555 ; handover `docs/ops/HANDOVER-AIOPS2-CURRENT.md` existe sur `docs/debian-deployment-qualification-plan-20261110` (blob `3e970b4d3f5cc74aaa106a9ba72b7d05c56d0421`), non modifié pour éviter collision.
