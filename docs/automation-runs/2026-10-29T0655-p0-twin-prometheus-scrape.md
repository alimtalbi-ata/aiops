# 2026-10-29 06:55 Europe/Paris — P0 ACME Twin / Prometheus metrics, identité dédiée

## Sources / coordination
- HEAD `main` lu : `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (protégée, inchangée).
- PR ouvertes, branches de livraison récentes et `docs/automation-runs` consultés ; candidate **unique** [#170](https://github.com/alimtalbi-ata/aiops/pull/170) (base main, draft). Travail parallèle : #156 recette, #153 déployeur, #176 Policy, #171 NOC, #177 UI. Ne pas fusionner leurs contrats par supposition.
- #142 puis #148 qualifiées historiquement ; la candidate #170 conserve le chemin **SIMULATED / TOPOLOGY_ONLY** `ACME-E08/E06/E04/E02/E01` depuis le seed SQL. Portal et Twin ne partagent pas d'identité CI vérifiée. Aucun lien SAN→hôte ni impact Payments runtime attesté.
- Comparaison GitHub main...candidate après changements : **ahead=21, behind=0**. Cette avance n'est ni un merge ni une qualification E2E.

## Une livraison verticale P0 : scrape Twin sans jeton administrateur
**Problème observé dans le code** : `config/prometheus/prometheus.yml` scrape `/metrics` sans Bearer, alors que Twin le refuse par 401. Initialement `AIOPS_INTERNAL_TOKEN` et `AIOPS_ADMIN_TOKEN` sont générés identiques : réutiliser l'un des deux pour Prometheus aurait diffusé une capacité administrateur dans le conteneur de supervision.

**Correctif sur la candidate #170** :
1. `AIOPS_TWIN_METRICS_TOKEN` **distinct** de l'admin et de l'interservice ; refus de démarrage Twin si absent/identique. `/metrics` accepte **uniquement** ce Bearer. Toutes les autres lectures Twin continuent leur auth précédente, `/health` reste public, et la mutation synthétique demeure admin-only.
2. `/metrics` retourne une exposition Prometheus en **texte**, non une chaîne JSON.
3. Prometheus utilise `authorization.credentials_file`, jamais de Bearer dans Git ; Compose bind-mount le **fichier uniquement** en lecture seule, sans créer silencieusement le chemin absent (`create_host_path: false`).
4. `deploy/init-env.sh` crée un jeton dédié pour les nouvelles installations. Sur une installation **existante**, le script ne modifie pas `.env` automatiquement : préparation opérateur explicite via `python3 scripts/prepare_prometheus_twin_scrape.py --provision` puis `python3 scripts/prepare_prometheus_twin_scrape.py --check`. La préparation refuse les symlinks, les clés dupliquées, les permissions .env non privées et les fichiers périmés ; aucune valeur secrète n'est imprimée. Fichier hôte `.local/prometheus/twin-metrics-token` ignoré par Git, répertoire hôte privé 0700, fichier 0644 **pour permettre la lecture par l'UID non-root Prometheus après bind-mount du fichier seul**. Ne jamais monter le répertoire.
5. Tests de provisionnement/refus et test HTTP réel Twin/PostgreSQL de `/metrics` (anonymous/admin/internal=401, métriques dédiées=200, impossibilité de lire impact ou POST avec ce jeton), dans le workflow existant `quality.yml`. Aucun nouveau workflow.

**Contrats modifiés** : variable `AIOPS_TWIN_METRICS_TOKEN` désormais requise pour Twin, fichier local requis pour Prometheus, `/metrics` text/plain et identité Bearer dédiée. **Migration obligatoire avant tout démarrage des services**. Les consommateurs qui appelaient `/metrics` avec admin/interservice recevront 401, volontairement.

## SHA, tests, NOT_TESTED
- Commit code + tests : `8c769c12b356421cd42556b690e83d6a01630eab`.
- Correction d'assertion du saut de ligne exposition : `cac50494933a60b907ad7f0035d8dc851c442ab3`.
- Tests locaux ciblés : **NOT_TESTED** (pas de dépôt GitHub monté dans l'environnement local). La CI `quality.yml` du SHA exact doit être vérifiée ; ne pas confondre `queued/in_progress` et SUCCESS.
- **NOT_TESTED** : vrai Prometheus→Twin scrape (les tests HTTP utilisent un client dédié), Portal navigateur, tenant RBAC, liaison Run→IA→Policy SIMULATE→Evidence→Studio, déployeur multi-services, rollback, Debian `applied.sha`, smoke-tests serveur.
- La présence d'un fichier de credentials n'atteste pas la sécurité globale de Prometheus ou le RBAC tenant ; les métriques sont des agrégats Twin, pas une panne Payments.

## Recette opérateur avant toute promotion (sans action ici)
- Sur une **copie qualifiée** de la candidate et après validation 5/5 seulement : provisionner `.env` et le fichier scrape via les deux commandes ci-dessus, puis `docker compose --env-file .env config`, vérifier le montage et la compatibilité des images.
- Démarrer uniquement selon la procédure de déploiement approuvée avec rollback. Vérifier `/api/v1/targets` du Prometheus réel : job `aiops2-twin` UP, erreur de scrape absente, aucune valeur de token dans les logs. Vérifier 401 sans auth et avec admin/interservice sur `/metrics`, 200 uniquement sous jeton dédié. Ne pas publier le token dans les preuves.
- Collecter SHA appliqué par cron Debian, preuves UTC, résultats Core/Twin/Copilot/Portal, Policy SIMULATE, provenance synthétique, IDs Run/Evidence et rollback. **Le poller seul ne valide pas l'E2E.**

**READY_FOR_STABLE=BLOCKED ; overall=NO_GO.** Le script de déploiement actuel ne transporte pas Twin/Core/Copilot/Prometheus, et la recette 5/5 est seule habilitée à décider d'une éventuelle promotion. Aucun push stable, aucune fusion, aucun accès Debian, aucun LIVE. Prochain lot : vérifier CI finale et vrai scrape Prometheus éphémère, puis remettre le SHA et les blocages à #156.

## Addendum CI : correction de régression de test
- CI initiale du SHA `8c769c12b356421cd42556b690e83d6a01630eab` : [quality.yml #40826341422](https://github.com/alimtalbi-ata/aiops/actions/runs/40826341422), **FAILURE** (job Core/Twin), malgré policy-and-static et Grafana SUCCESS. Logs réels lus : 14 tests Twin exécutés, 3 échecs, dont deux anciennes assertions qui supposaient à tort que le jeton admin/interservice avait accès à `/metrics`, et une assertion sur un saut de ligne littéral.
- Correction saut de ligne : `cac50494933a60b907ad7f0035d8dc851c442ab3` ; correction des deux assertions historiques : `2c97ce42e4bdfb4788d98c62e39b35e4af3c85e3`.
- **Ne pas qualifier READY_FOR_STABLE sur les CI précédentes** : la CI du dernier SHA doit réussir intégralement. Ce journal documentaire produit lui-même un nouveau SHA et requiert une nouvelle vérification.

## Qualification finale observée avant addendum
- SHA avec code et journal : `d7cad9eb911ad43c45b4bcfb5b5faf778f46b25d`.
- [quality.yml #40826458509](https://github.com/alimtalbi-ata/aiops/actions/runs/40826458509) : **completed/success sur ce SHA exact, 3/3 jobs SUCCESS** (Core/PostgreSQL/Twin, policy-and-static, Grafana).
- Logs du job Core/Twin consultés : **14/14 tests Twin HTTP réel sur Docker + PostgreSQL 16**, dont `test_prometheus_metrics_only_accept_dedicated_scrape_identity` et `test_distinct_internal_identity_reads_but_cannot_write_synthetic_events` ; **14/14 Core/Policy, 8/8 Policy HTTP, 5/5 NOC**. Logs du job statique : **3/3 tests de préparation Prometheus** réussis et `STATIC_AUDIT=PASS`.
- La CI de `2c97ce42e4bdfb4788d98c62e39b35e4af3c85e3` est également **3/3 SUCCESS** (job results consultés). L'échec initial est documenté ci-dessus et n'a pas été contourné.
- **Limite** : ces validations ne lancent pas le binaire Prometheus pour un vrai scrape. `PROMETHEUS_REAL_SCRAPE=NOT_TESTED`, et les contrôles Debian, E2E, rollback et tenant restent `NOT_TESTED`.
- Cet addendum documentaire modifie encore le SHA de tête : la CI du nouveau HEAD doit être vérifiée séparément avant handoff.
