# P0 — Projection défensive des read models Core/Twin

Date : 2026-10-28. Portail unique (cible 17777), **source uniquement**.

## Contrat

Le module `app/portal/portal_read_models.py` continue d'interroger exclusivement les vrais endpoints configurés : `Core /api/dashboard`, `Core /api/runs` et `Twin /api/twin/summary`. Il n'ajoute ni service, ni proxy, ni données simulées.

Les réponses sont désormais **projetées** vers les champs utiles à l'interface :

- Dashboard : `open_p1`, `open_incidents`, `running`, `blocked`, `twin_nodes`, `degraded_nodes` (entiers positifs ou nuls).
- Runs : `items` (au maximum 100), chacun avec `run_id` obligatoire et `mode`, `status`, `overall_confidence`, `scenario_id` facultatifs. Les textes sont bornés ; la confiance doit être un nombre fini entre 0 et 1 ou `null`. Identités dupliquées rejetées.
- Twin : `nodes`, `edges` et, si présents, `nodes_by_type` et `states` (dictionnaires de compteurs bornés).

Tout champ supplémentaire (tokens, payloads, attestations, secrets, etc.) est **supprimé** et n'est pas renvoyé au navigateur. Un champ affiché malformé rend seulement le read model concerné `UNKNOWN` avec `null`, sans fausse liste vide. `READABLE_UNVERIFIED` indique uniquement une lecture de forme valide, **jamais** une attestation d'authentification, d'intégration ou de LIVE.

Le contrat est volontairement limité aux champs consommés par le portail existant ; les vues opérateur Incident/Evidence de PR #51 disposent de leur propre projection et RBAC. Le portage de `platform_registry` depuis PR #36, déjà dans `main`, est conservé sans fusion de PR #36.

## Validation et limites

Les tests unitaires existants `tests/test_portal_read_models.py` ont été étendus avec des cas négatifs : secrets supplémentaires, fausses attestations, confiance NaN/booléenne/hors plage, champs imbriqués, identité dupliquée, données Twin invalides et inventaire vide. Ils sont exécutés par le workflow existant `.github/workflows/quality.yml` sur PR ; aucun workflow parallèle n'est ajouté.

**NOT_TESTED** : conteneurs Core/Twin réels en CI, intégration n8n/Thruk/Grafana/GLPI, authentification globale (PR #74/#51/#57/#70), navigateur Debian, preuves de captures et vidéo. Ce correctif est une défense en profondeur et **ne remplace pas** le RBAC du portail. Aucun accès à `10.79.94.202`, aucun déploiement, aucune remédiation LIVE.

Prochain micro-lot : après revue des PR de sécurité concurrentes, intégrer sans écrasement le bootstrap authentifié et les projections opérateur, puis qualifier le chemin de lecture contre des conteneurs éphémères réels.
