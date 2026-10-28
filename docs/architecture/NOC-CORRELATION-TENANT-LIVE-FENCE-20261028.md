# P0 NOC — blocage tenant/LIVE de la corrélation canonique

Date : 2026-10-28 02:08 Europe/Paris. Base main : `0603e86a26978873c3b6196098674932d3378499`. PR : https://github.com/alimtalbi-ata/aiops/pull/75

## Contexte et portage ciblé

Lecture préalable de main, des PR ouvertes #36, #37, #39, #41, #43, de la roadmap PR #39 et de la continuité main. La PR #36 propose des parseurs Livestatus offline (`demo/noc_livestatus_import.py`, `demo/noc_livestatus_services.py`) ; leur contrat reste une source d'inspiration, pas une preuve de monitoring connecté. Aucun merge massif, aucun import non qualifié. La PR #71 modifie déjà `noc_runtime.py` : ce lot se limite au composant de corrélation existant, pour éviter les collisions.

## Comportement

L'API authentifiée `GET /api/noc/correlation` conserve la jointure exacte Incident/Run pour DEMO, REPLAY et STORY. Les Runs LIVE sont refusés : une simple identité canonique n'atteste ni la source de supervision ni le droit de lecture LIVE. La présence de champs tenant/org/workspace/account dans le Run Core ou la projection NOC bloque la corrélation tant qu'une ACL Core tenant-scoped n'est pas qualifiée. Erreurs : HTTP 503 générique, non-cacheable, sans fuite d'identifiants.

Ce filtre est **un garde-fou partiel**, pas un RBAC multitenant. Des métadonnées tenant non projetées par l'adaptateur ou cachées dans des champs non reconnus ne sont pas prouvées absentes. Le modèle NOC signé et l'API Core devront disposer d'une identité tenant authentifiée, d'une décision d'autorisation serveur et de tests cross-tenant avant une mise en service multitenant.

## Validation et limites

`quality.yml` existant lance `python -m unittest discover -s tests -p "test_noc_canonical_correlation.py" -v`, la compilation Python, l'audit statique et Compose config. Tests ajoutés : refus LIVE, champs tenant de chaque côté, non-régression DEMO/REPLAY/STORY, réponse route 503 sans fuite. Tests unitaires synthétiques, pas d'intégration réelle. Checkmk/Thruk, Grafana, ACL Core et inférence NGX/Ollama : **NOT_TESTED/BLOCKED**. Aucune preuve LIVE, aucune commande Debian, aucune fusion, aucun déploiement.

Retour arrière source : revert des commits de la PR après revue, sans commande sur un runtime.
