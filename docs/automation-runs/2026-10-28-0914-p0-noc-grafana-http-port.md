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
