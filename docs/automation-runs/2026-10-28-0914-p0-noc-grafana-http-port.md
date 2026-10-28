# P0 NOC — portage ciblé Grafana HTTP — 2026-10-28 09:14 Europe/Paris

- Départ : `main` SHA `d95ff789edfc0419d766f6204c807451864acb14` (HEAD revérifié avant création de branche).
- Branche dédiée : `feat/p0-noc-grafana-http-port-20261028-0914`. PR : à renseigner après création.
- Revue : PR #36 (dashboard Grafana synthétique `SIMULATED_TARGET`, non importé comme preuve), PR ouvertes #36/#37/#39/#41/#43, continuité/architecture/roadmap et PR #58.
- Portage **ciblé** de PR #58 : `app/portal/noc_grafana_health.py`, `tests/test_noc_grafana_health.py`, `tests/test_noc_grafana_real_integration.py`, `docs/architecture/NOC-GRAFANA-HEALTH-BOUNDARY-20261028.md`; montage et bouton dans `app/portal/main.py`; réutilisation de `.github/workflows/quality.yml` avec un vrai conteneur Grafana 11.6.0.
- Frontières : jeton opérateur avant réseau, URL interne autorisée, GET uniquement, pas de redirection/proxy, JSON borné et sans clés dupliquées, réponse 503/no-store en échec. `GRAFANA_HTTP_READY_UNATTESTED` n'atteste **ni métriques, ni ACL tenant, ni LIVE**.
- Tests : GitHub Actions sur le HEAD de la branche à confirmer; tests unitaires contractuels avec substitution HTTP (pas intégration); job dédié **vrai Grafana conteneur** ou BLOCKED si échec. Core tenant, Checkmk/Thruk réel, métriques Grafana, Ollama 4B, NGX 192B : NOT_TESTED.
- Risque / blocage : réseaux Compose portail et Grafana disjoints; ne pas activer le contrôle Debian sans conception réseau/ACL approuvée. Aucun accès Debian, déploiement, migration ni commande LIVE.
- Rollback : fermer la PR / revert des commits ciblés.
- Prochain micro-lot : lecture métriques Grafana observées et scoped par identité tenant serveur, avec Core/PostgreSQL éphémères et tests ACL A/B avant exposition.

## Qualification GitHub Actions — 2026-10-28 09:17 Europe/Paris

- PR draft : [#110](https://github.com/alimtalbi-ata/aiops/pull/110).
- Commit de code/tests/docs : [`22a5678497f4e0a5e3eb5ddc2d15bb5d1694706c`](https://github.com/alimtalbi-ata/aiops/commit/22a5678497f4e0a5e3eb5ddc2d15bb5d1694706c).
- [quality.yml run #40655638892](https://github.com/alimtalbi-ata/aiops/actions/runs/40655638892) : **completed/success**, HEAD exact `22a5678497f4e0a5e3eb5ddc2d15bb5d1694706c`.
- Job `policy-and-static` : **success**, compilation, tests contractuels Grafana (auth, refus de sources, redirection, JSON malformé, doublons, taille), régressions NOC/portail, audit statique, configuration Compose.
- Job `grafana-real-integration` : **success**, conteneur réel `grafana/grafana:11.6.0` initialisé, endpoint `/api/health` effectivement interrogé, test de l'adaptateur sans mock **success**.
- Ces résultats n'attestent ni des métriques observées, ni le RBAC tenant, ni la connectivité Debian. Pas de preuve LIVE.
- Un commit documentaire final est nécessaire pour consigner cette preuve : ses checks devront être revérifiés avant toute fusion. Aucun résultat non exécuté n'est déclaré PASS.

## Fusion et qualification post-fusion — 2026-10-28 Europe/Paris

- PR [#110](https://github.com/alimtalbi-ata/aiops/pull/110) fusionnée en **squash** sur `main` : SHA [`ac683b5e00dd36555f13909542754bc8439c8fa9`](https://github.com/alimtalbi-ata/aiops/commit/ac683b5e00dd36555f13909542754bc8439c8fa9). Absence de conflits et checks verts sur le HEAD `3fcad9450ecb02e977474891b9be390a98715902` vérifiés avant fusion; aucun contournement des protections GitHub.
- [quality.yml PR #40655732939](https://github.com/alimtalbi-ata/aiops/actions/runs/40655732939) : **completed/success**, jobs `policy-and-static` et `grafana-real-integration` **success** sur HEAD documentaire final.
- [quality.yml main #40655866536](https://github.com/alimtalbi-ata/aiops/actions/runs/40655866536) : **completed/success** sur SHA fusionné `ac683b5e00dd36555f13909542754bc8439c8fa9`.
- La qualification reste limitée à un vrai Grafana éphémère CI et aux contrats HTTP; aucun accès Debian, aucun Checkmk/Thruk, aucune métrique, ACL tenant, inférence Ollama ou preuve LIVE qualifiés.
- Cette mise à jour documentaire est proposée séparément pour ne pas modifier rétroactivement le SHA de code testé.
