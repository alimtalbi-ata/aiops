# 2026-10-28 10:35–10:39 Europe/Paris — P1 GLPI real HTTP negative CI

## Base et lecture préalable
- `main` HEAD initial et revérifié avant écriture : `4652a8893b4ec2fffae8aa515d4b2087259bf7bf`.
- Base dédiée empilée sur draft PR #69, HEAD vérifié `fec7866cf8979fb646e416a150845acdcb84b455` ; aucune modification de la branche d'autrui.
- PR #36, #37, #39, #41, #43 inspectées, ainsi que #69/#73 et autres PR P1 (#77/#80/#85/#90/#96/#101/#107/#112). Continuité, architecture, protocole de qualification, fixture et `quality.yml` lus.
- PR #36 : reprise ciblée des fixtures et contrats ACME déjà portés en amont, sans fusion massive. Ce micro-lot qualifie le lecteur de #69 contre un service réel.

## Fichiers et commits
- `tests/test_glpi_real_http.py` — test HTTP négatif réel, sans transport mock : commit `eb7522a9e8ae67f00305247f86e27a76c1a1e95a`.
- `.github/workflows/quality.yml` — ajout d'un job GLPI/MariaDB réels au workflow existant : commit `30d8d7e5f008ba442563c4fab32d9ef7359fa2d7`.
- `docs/architecture/GLPI-REAL-HTTP-CI-20261028.md` — contrat de preuve, limites et rollback : commit `53044f2564d376d63d2365485d7fa9bfd64061f5`.
- Ce journal : commit GitHub à consulter dans l'historique de la PR.
- PR draft : https://github.com/alimtalbi-ata/aiops/pull/120 (base #69).

## Exécution / preuves
- Lecture source GitHub : DONE.
- Tests unitaires préexistants #69 : NON RÉEXÉCUTÉS localement dans ce créneau.
- Tests réels GLPI + MariaDB : **PENDING** GitHub Actions au moment de la création de ce journal ; ne pas interpréter la présence du job comme PASS.
- Tests Core/Temporal/GLPI positif, authentification GLPI réelle, ticket créé, corrélation IDs et RBAC serveur : **NOT_TESTED**.
- Aucun endpoint NVIDIA NGX ou Debian contacté ; aucune commande LIVE ni déploiement.

## Risques / blocages
- Démarrage initial GLPI 11.0.9 potentiellement long ; API REST possiblement désactivée : dans ces cas le test doit échouer avec BLOCKED, jamais être remplacé par un mock.
- Base #69 ancienne par rapport à `main` ; réconciliation des changements `quality.yml` et revue des protections GitHub nécessaires avant fusion.
- Un rejet de jeton CI invalide est une preuve négative limitée, pas une preuve de ticket authentifié ni d'intégration end-to-end.
- Aucun merge tant que checks, conflits et sécurité non vérifiés.

## Prochain micro-lot
1. Lire le run GitHub Actions du HEAD final, corriger les erreurs d'initialisation/contrat dans ce micro-lot si possible.
2. Configurer une authentification API GLPI éphémère et un ticket de test réellement créé dans CI, avec vérification d'entité ; jamais de ticket réel revendiqué sans réponse GLPI authentifiée.
3. Raccorder ensuite les scopes Incident/Run/entité à une identité RBAC serveur, avec non-régression DEMO/LIVE et séparation des preuves.
