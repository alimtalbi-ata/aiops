# 2026-10-28 11:01 Europe/Paris — P0 Golden DEMO operator RBAC

## Périmètre et provenance

- Heure de début : 2026-10-28 10:57 Europe/Paris ; validation finale du code : 11:01 Europe/Paris.
- Départ `main` : `4652a8893b4ec2fffae8aa515d4b2087259bf7bf` ; HEAD vérifié avant création de branche et avant écriture.
- Branche de code : `fix/p0-demo-operator-boundary-20261028-1057` ; commit `87d92db1e3f4f372781ff812ac0feffb298b7a33`.
- [PR #122](https://github.com/alimtalbi-ata/aiops/pull/122), initialement draft puis passée en revue et fusionnée après checks verts, sans conflit (`mergeable_state=clean`).
- **SHA fusionné dans `main` : `2253bd21bd948a349b9b7a4a941ecf1e3357d96c`** (squash).
- Sources relues : `main`, PR #36/#37/#39/#41/#43 et continuité, PR #57 (garde DEMO) et PR #70 (Copilot). Aucun merge massif de #36/#57.

## Fichiers de code et tests

- `app/portal/main.py` : `POST /api/demo` refuse sans opérateur avant tout appel Core, impose des reçus Incident/Run/execute cohérents et projette un accusé `DEMO_SUBMITTED_UNVERIFIED` sans champ LIVE ; page anonyme avec jeton opérateur à usage unique, requête sans cookies, sans redirection et sans stockage.
- `app/portal/portal_command_auth.py` : garde fail-closed porté de #57, séparation operator/viewer/internal, validation des identifiants Core avant l'appel suivant.
- `tests/test_portal_demo_command_auth.py` : tests HTTP in-process d'autorisation/refus, séparation des rôles, refus de reçus malformés ou LIVE, non-divulgation des erreurs, absence d'appel Core avant autorisation et contrôle de la page anonyme.
- `.github/workflows/quality.yml` : exécution des tests DEMO dans la CI existante.
- `compose.yml`, `config/.env.example`, `deploy/init-env.sh` : variables explicites viewer/operator ; secrets distincts générés uniquement pour une installation neuve, sans rotation de `.env` existant.

## CI réellement exécutée

- [Push quality #40668539080](https://github.com/alimtalbi-ata/aiops/actions/runs/40668539080) : **SUCCESS** sur `87d92db`.
- [PR quality #40668555197](https://github.com/alimtalbi-ata/aiops/actions/runs/40668555197) : **SUCCESS** sur `87d92db`.
- [Post-merge quality #40668685395](https://github.com/alimtalbi-ata/aiops/actions/runs/40668685395) : **SUCCESS** sur `2253bd21`.
- Étapes confirmées : tests DEMO HTTP négatifs et régression, compilation Python, autres tests Policy/NOC/portail du workflow, audit statique, préflight des secrets existant et validation Compose avec secrets synthétiques. Job Grafana réel : conteneur éphémère, HTTP health et adapter testés avec **SUCCESS**.
- Ces tests DEMO utilisent `TestClient` et des substituts in-process de `post_json` : ils ne prouvent pas une intégration Core/Temporal réelle.
- Pas de suite Ollama/LLM exécutée dans ce lot ; NGX 192B non contacté. Aucune équivalence de qualité revendiquée.

## Risques, blocages et non-qualification

- **NOT_TESTED** : vrai Core/Temporal, navigateur réel, intégrations n8n/Thruk/GLPI, Ollama, captures authentifiées, vidéo finale, Debian et LIVE. Le seul test conteneur réel ici concerne Grafana.
- Le contrôle d'opérateur n'est pas une ACL tenant ; `DEMO_SUBMITTED_UNVERIFIED` ne prouve ni succès métier ni exécution LIVE.
- Les écritures Core précédant un échec de reçu peuvent déjà avoir eu lieu ; aucune transaction distribuée/compensation n'est revendiquée. L'idempotency key DEMO historique est conservée.
- Les anciens `.env` sont préservés ; si les nouveaux jetons ne sont pas renseignés, les routes protégées refusent (fail-closed). Le préflight de secrets existant ne qualifie pas encore la séparation viewer/operator : micro-lot de durcissement à prévoir.
- Aucune connexion à `10.79.94.202`, aucun SSH, aucun déploiement, aucune migration destructive, aucune commande LIVE.

## Prochain micro-lot

Converger le Copilot de PR #70 sur `main` actuel : auth viewer/operator, validation stricte de la question, projection sans attestations LIVE, tests de refus avant upstream et `UNKNOWN` sur réponse incohérente. Puis qualifier le préflight des nouveaux secrets et les services réels en conteneurs CI.
