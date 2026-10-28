# 2026-10-28 09:34 Europe/Paris — P1 ACME canonical dual-fabric fence

## Point de départ et périmètre
- Repository: `alimtalbi-ata/aiops`; `main` observé avant modification: `111b3bd5988ac35cd5f83c1fc93813b96c09111e`.
- Branche dédiée: `fix/p1-acme-canonical-dual-fabric-fence-20261028-0931`; HEAD de branche revérifié avant le commit documentaire: `bd2448971eb7a7665308eed26766fbc5e2dfe3bf`.
- PR draft: https://github.com/alimtalbi-ata/aiops/pull/112 (cible `main`, pas de merge).
- Lecture préalable: `main`, PR #36/#37/#39/#41/#43, documentation `PROJECT-CONTINUITY`, `COMPONENT-CATALOG-AND-REUSE`, `DECISION-LOG`, workflow `quality.yml`; revue des PR P1 #69/#73/#77/#80/#85/#90/#96/#101/#107.
- Réutilisation ciblée: contrat stdlib `app/portal/acme_fixture_contract.py` et fixture ACME de PR #36 déjà portés sur `main`. Pas de merge massif.

## Livraison
- Commit code/tests/CI: `bd2448971eb7a7665308eed26766fbc5e2dfe3bf`.
- `app/portal/acme_fixture_contract.py`: verrouillage des types et des dépendances exactes des six CI canoniques SAN-A/SAN-B/Host/Volume/VM/Payments. Un chemin SAN→Payments seul ne suffit plus si la chaîne est altérée. Les listes peuvent être réordonnées; redondance uniquement déclarative.
- `tests/test_acme_canonical_topology.py`: six tests offline (cas positif déterministe, raccourci SAN→application, hôte contourné, fabric B manquante, type/CI falsifié, 503 HTTP sans fausse attestation).
- `.github/workflows/quality.yml`: étape dédiée ajoutée au workflow existant; aucune CI parallèle.

## Tests et preuves effectivement observés
- GitHub Actions pull_request: https://github.com/alimtalbi-ata/aiops/actions/runs/40657618712 — `completed/success` sur `bd2448971eb7a7665308eed26766fbc5e2dfe3bf`. Jobs `policy-and-static` et `grafana-real-integration`: `completed/success`.
- GitHub Actions push: https://github.com/alimtalbi-ata/aiops/actions/runs/40657597407 — `completed/success` sur le même commit.
- Étapes vérifiées sur le run PR: tests ACME existants et nouveaux, audit statique, validation Compose, et HTTP réel vers le conteneur Grafana éphémère: `success`.
- Les tests ACME sont des tests offline/ASGI avec fixture synthétique. Le test Grafana utilise un véritable service Grafana conteneurisé, mais ne qualifie ni Core/Temporal ni GLPI.
- Aucun test local revendiqué. Aucun endpoint NGX/Mistral réel contacté; pas de preuve d'équivalence Ollama 4B/192B.

## Limites, risques et non-régressions
- Le verrou fixe le **contrat v1** des six CI. Un futur changement de topologie légitime devra être versionné ou mettre à jour explicitement les invariants/tests; il ne faut pas masquer un changement de modèle en le laissant passer silencieusement.
- Les PR #77 et #107 modifient des vues/tests ACME voisins. Aucun écrasement; réconciliation ciblée à prévoir.
- `NOT_TESTED/BLOCKED`: vraie intégration GLPI éphémère, corrélation authentifiée Incident/Run/ticket, Core+Temporal+PostgreSQL E2E, contrôle de santé/bascule SAN, RBAC serveur sur les contrats ITSM, captures authentifiées, vidéo finale.
- Les champs runtime/GLPI restent absents ou `UNKNOWN`; les labels `SIM-*` ne sont pas des identifiants réels. Aucun merge, accès Debian, déploiement, remédiation LIVE ou migration.

## Prochain micro-lot
- Ajouter un test d'intégration non destructif contre GLPI réel conteneurisé en CI en réutilisant PR #69/#73, sans mock présenté comme intégration, puis vérifier le contrat d'observation `OBSERVED_UNCORRELATED` et l'absence de promotion en preuve Incident/Run.
- Vérifier le run Actions du commit documentaire avant fusion éventuelle. Rollback: revert du commit de code; aucune donnée runtime modifiée.
