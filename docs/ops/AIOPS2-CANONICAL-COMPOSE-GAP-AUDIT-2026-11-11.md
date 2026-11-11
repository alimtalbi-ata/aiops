# AIOPS2 — Audit d'écart du Compose canonique vs runtime Debian

**Date:** 2026-11-11  
**Repository:** `alimtalbi-ata/aiops`  
**Runtime:** SRV-DEB-05, Docker rootless, utilisateur `aiops` (UID 1001)  
**Statut:** Analyse documentaire basée sur `compose.yml` de `main` et les inventaires opérateur. Aucun changement runtime.

## 1. Objet

Ce document complète `docs/ops/AIOPS2-ONE-STACK-RUNTIME-CONVERGENCE-2026-11-11.md`.

La cible reste un seul projet Compose opérationnel et uniquement les conteneurs requis démarrés. Les environnements de qualification, tests, démo et rollback ne sont pas des services permanents. Leurs fonctions utiles doivent être récupérées et validées avant arrêt.

**Important :** le `compose.yml` du dépôt est un point de départ déclaratif; il n'est pas encore démontré qu'il reproduit fidèlement la configuration active sur Debian.

## 2. Compose du dépôt : services déclarés

Le `compose.yml` consulté sur `main` déclare 18 services :

| Domaine | Services |
|---|---|
| Core et données | `aiops2-postgres`, `aiops2-core`, `aiops2-twin`, `aiops2-evidence`, `aiops2-policy` |
| Exécution | `aiops2-copilot`, `aiops2-worker`, `aiops2-simulator` |
| Interface | `aiops2-portal` |
| Temporal | `aiops2-temporal-postgres`, `aiops2-temporal`, `aiops2-temporal-ui` |
| Observabilité | `aiops2-prometheus`, `aiops2-grafana`, `aiops2-alertmanager` |
| Intégrations | `aiops2-glpi-db`, `aiops2-glpi`, `aiops2-n8n` |

Réseaux déclarés : `aiops2-public`, `aiops2-control`, `aiops2-data`, `aiops2-execution`, `aiops2-temporal-data`, `aiops2-integration`, `aiops2-observability`.

Volumes nommés déclarés :
`aiops2-postgres-data`, `aiops2-temporal-postgres-data`, `aiops2-prometheus-data`, `aiops2-grafana-data`, `aiops2-glpi-db-data`, `aiops2-glpi-data`, `aiops2-n8n-data`.

## 3. Écarts constatés avec l'inventaire Debian

| Sujet | Manifeste GitHub | Runtime observé | Conséquence |
|---|---|---|---|
| Nom projet | `aiops2` | Projets `aiops2-rebuild`, `aiops2-metrics-cutover`, E2E, v27, demo | Pas de correspondance prouvée |
| PostgreSQL application | volume `aiops2-postgres-data` | `aiops2-rebuild-postgres-data` | Ne pas démarrer avec le volume vide par erreur |
| Temporal PostgreSQL | `aiops2-temporal-postgres-data` | `aiops2-rebuild-temporal-postgres-data` | Conserver la base Temporal existante |
| GLPI MariaDB | `aiops2-glpi-db-data` | `aiops2-rebuild-glpi-db-data` | Migration/attachement explicite requis |
| GLPI fichiers | `aiops2-glpi-data` | `aiops2-rebuild-glpi-data` | Migration/attachement explicite requis |
| Grafana | `aiops2-grafana-data` | `aiops2-rebuild-grafana-data` | Éviter l'initialisation d'un Grafana vide |
| n8n | `aiops2-n8n-data` | `aiops2-rebuild-n8n-data` | Préserver workflows et clés |
| Prometheus | `aiops2-prometheus-data` | `aiops2-rebuild-prometheus-data` | Préserver TSDB selon politique de rétention |
| FS Demo | Aucun volume FS Demo déclaré dans le manifeste | `aiops2-rebuild_aiops2-fs-demo-data` et volume anonyme partagé | Ajouter le stockage FS explicitement après analyse des données |
| Worker FS | Dockerfile copie `shared` et `worker`; aucun bind mount FS déclaré dans Compose | Worker actif reçoit runtime bridge + quatre fichiers Python depuis `aiops2-patches/fs-portal-v30` | La build standard n'est pas équivalente au runtime |
| Prometheus FS | `./config/prometheus:/etc/prometheus:ro` | Config montée depuis `aiops2-patches/fs-portal-v30/build/prometheus-fs` | Réconcilier règles et scrape targets avant remplacement |
| Intelligence | Aucun service `aiops2-intelligence` dans le manifeste | Conteneur `aiops2-rebuild-intelligence` actif | Fonctionnalité non représentée dans le Compose cible |
| Services externes de test | Absents du manifeste | CloudBeaver, NOC/RAG, FS lab/ingest, qualification HTTP, candidats Portal et observabilité demo | Examiner les capacités; ne pas les promouvoir automatiquement |

Les volumes du manifeste ont des noms différents des volumes rebuild actuellement montés. Avec les noms explicites déclarés dans `compose.yml`, un `compose up` pourrait créer de nouveaux volumes vides au lieu de réutiliser les volumes rebuild. **Aucun démarrage ne doit être tenté avant une stratégie explicite de mapping et de sauvegarde.**

## 4. Dépendances Worker FS à récupérer

Le Worker actif est étiqueté par Compose comme appartenant à `aiops2-metrics-cutover`, malgré son nom `aiops2-rebuild-worker`.

Montages relevés :
- `/home/aiops/aiops2-patches/fs-portal-v30/runtime/fs-bridge` → `/run/aiops2-fs-bridge`;
- `build/app/worker/fs_lab_activity.py`;
- `build/app/worker/fs_lab_evidence.py`;
- `build/app/worker/main.py`;
- `build/app/worker/workflow.py`.

Hashes SHA-256 consignés par l'opérateur :
- `fs_lab_activity.py`: `90e7bf8bd81136f11680f62864730a8ec2854c4a221a63c093fef164fb0d8b4c`
- `fs_lab_evidence.py`: `27787fbff5b80d08a7ba7ac25908a4f7f46d3dbf3700378eb5b980dbfc6ef1fc`
- `main.py`: `3d2137540c73fab8fb484f802ed283879a0db51a2094805d6d0deee9e6739e88`
- `workflow.py`: `947aaa5cf29e7cff5b34596a69ea68a92c56e768167ab6bfaf62d0b9fc3bb9c5`

Le répertoire `fs-portal-v30` n'est pas un dépôt Git autonome. Avant intégration :
1. retrouver le commit source dans le dépôt principal ou un autre dépôt;
2. si introuvable, importer les fichiers dans un chemin versionné en préservant les hashes et en documentant la provenance inconnue;
3. examiner les imports, dépendances, variables, contrats API, accès fichiers et tests;
4. intégrer le bridge comme composant versionné et configurer le secret par mécanisme de secrets (ne jamais committer `bridge.token`);
5. construire une image immuable et exécuter les tests FS avant tout remplacement du Worker actif.

## 5. Intelligence et observabilité

Le service `aiops2-rebuild-intelligence` est actif selon l'inventaire mais absent du Compose GitHub. Son rôle, API, image ID, dépendances, données et besoin opérationnel doivent être identifiés. Ne pas l'ajouter au Compose canonique sur le seul nom du conteneur.

La configuration Prometheus active provient du patch FS et doit être comparée à `config/prometheus` du dépôt : jobs, labels, alert rules, recording rules, targets, relabeling et règles spécifiques FS. L'intégration doit être testée par validation de configuration et vérification des targets avant cutover.

L'observabilité de démo OTel/Loki/Tempo est une stack séparée. Récupérer les dashboards, pipelines, alert rules et configurations utiles dans le socle observabilité; le choix des backends permanents doit être explicite pour éviter de faire tourner deux plateformes d'observabilité.

## 6. Matrice de décision préliminaire

| Élément | Décision provisoire | Condition avant action |
|---|---|---|
| Core, Twin, Evidence, Policy, Portal | Candidats RUN | Prouver image/config/volumes/health et contrats |
| Worker | Candidat RUN | Internaliser et qualifier les cinq montages FS |
| Intelligence | UNKNOWN | Décrire rôle, interfaces et dépendances |
| Temporal et sa base | Candidats RUN si workflows actifs | Vérifier namespace, task queue, schéma et données |
| PostgreSQL applicatif | Candidat RUN | Mapper le volume existant sans créer une base vide |
| Prometheus/Grafana/Alertmanager | Candidats RUN si observabilité dans le périmètre | Réconcilier config, dashboards et données |
| GLPI/MariaDB, n8n | RUN si intégrations requises | Valider usage réel, secrets et persistance |
| Simulator | À confirmer | Distinguer service d'exploitation de banc de démo |
| E2E, v27/v29, qualification FS, demo OTel/Loki/Tempo | STOP/KEEP après extraction | Capturer résultats, sources et configurations |
| CloudBeaver, NOC/RAG test, FS lab/ingest, HTTP qual, Portal candidates | UNKNOWN individuellement | Cartographier fonctionnalité et dépendances |
| Rollback containers/images | KEEP arrêtés après retrait | Garder fenêtre de rollback et volumes partagés |

Cette matrice n'est pas un ordre d'arrêt. Toute entrée UNKNOWN reste inchangée.

## 7. Contrôles bloquants avant Compose canonique

- Inventaire complet `docker inspect` incluant tous les conteneurs actifs et arrêtés, leurs labels, images, mounts, réseaux, ports et health.
- Table volume → conteneurs (actifs ET arrêtés) → destinations → sauvegarde vérifiée → service cible.
- Comparaison du rendu effectif de chacun des projets Compose et de leurs overrides; secrets masqués avant tout partage.
- Image ID/digest → tag → source commit → build workflow → tests.
- Inventaire des endpoints et ports exposés; détection de collisions.
- Cartographie des dépendances Core, Worker, Temporal, Twin, Evidence, Policy, Portal, FS, GLPI et n8n.
- Test de restauration de chaque base/volume critique.
- Plan de bascule réversible et critères d'acceptation écrits.

## 8. Limites et interdictions

Les éléments ci-dessus sont une analyse documentaire, pas une observation live supplémentaire. Les snapshots Debian ont été fournis par l'opérateur et peuvent évoluer.

Aucune connexion shell à SRV-DEB-05 n'a été utilisée pour ce document. Aucun conteneur n'a été arrêté, démarré, recréé ou supprimé. Aucun volume, réseau, image, secret ou jeu de données n'a été modifié.

Jusqu'à approbation d'un plan exact :
- pas de `docker compose up` ou recreate;
- pas de `down`, `stop`, `rm`, `prune`, `volume rm`, `image rm`;
- pas de migration/copie de données;
- pas de changement de secrets, ports, réseau ou Docker data-root.

## 9. Critère de sortie

Le Compose unique est prêt uniquement quand tous les services démarrés appartiennent à un seul projet, les données persistantes existantes sont correctement rattachées, les bind mounts ad hoc ont disparu, les fonctionnalités récupérées sont couvertes par des tests, et le rollback est démontré. Les stacks de test restent arrêtées, pas en fonctionnement permanent.
