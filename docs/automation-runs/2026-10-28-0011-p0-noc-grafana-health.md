# Automation run — P0 NOC / Grafana HTTP readiness

- Date/heure : 2026-10-28 00:11–00:14 Europe/Paris (UTC+01).
- Base `main` inspectée : `0603e86a26978873c3b6196098674932d3378499`; revérifiée avant travail.
- PR existantes examinées : #36 (réutilisation ciblée du contexte Grafana synthétique), #37, #39, #41, #43; docs README, PROJECT-CONTINUITY, ARCHITECTURE-AND-BOUNDARIES, DECISION-LOG, et fichiers NOC/RAG du `main`.
- Branche dédiée : `feat/noc-grafana-health-readonly-20261028-0009`.
- PR draft : https://github.com/alimtalbi-ata/aiops/pull/58
- Fichiers modifiés/ajoutés : `app/portal/noc_grafana_health.py`, `app/portal/main.py`, `tests/test_noc_grafana_health.py`, `tests/test_noc_grafana_real_integration.py`, `.github/workflows/quality.yml`, `docs/architecture/NOC-GRAFANA-HEALTH-BOUNDARY-20261028.md`, ce journal.
- Commits de code/tests/docs : `16aa6e3`, `ba5405d`, `a3aa3cf`, `e201be5`, `d24bda3`, `8b129f0`.
- Tests réellement exécutés : GitHub Actions `AIOps quality gates`, run [40600371311](https://github.com/alimtalbi-ata/aiops/actions/runs/40600371311), sur `8b129f0bd3ca43043949161ed2f067926b861867`, statut **completed / success**. Job `policy-and-static` réussi (compileall, tests NOC Grafana contractuels et régressions existantes, static audit, Compose config). Job `grafana-real-integration` réussi, **vrai conteneur Grafana 11.6.0**, son endpoint HTTP réel interrogé; pas de mock de service.
- Portée : le portail peut afficher `GRAFANA_HTTP_READY_UNATTESTED` lorsque le service HTTP réel répond et `NOT_TESTED` pour métriques NOC, ACL et qualification LIVE. L'authentification opérateur précède toute lecture; URL allowlist, GET-only, no redirect/proxy, taille/JSON stricts.
- Risques et blocages : **BLOCKED** pour la connexion Debian car Compose isole Grafana sur `aiops2-observability` et le portail sur `aiops2-control/public`; pas de pont réseau créé sans revue. Pas de métriques Checkmk/Thruk interrogées; aucune ACL tenant qualifiée; pas de preuve navigateur ni de diagnostic NIM/Ollama. La fixture Grafana de PR #36 reste synthétique et n'est pas utilisée comme preuve.
- Aucun merge, accès Debian, déploiement, migration ni commande LIVE.
- Prochain micro-lot : concevoir un accès Grafana en lecture seule sur réseau dédié, puis requêtes métriques liées à Incident/Run avec contrôle d'identité tenant et provenance. Ne jamais transformer `/api/health` en attestation d'observabilité.
