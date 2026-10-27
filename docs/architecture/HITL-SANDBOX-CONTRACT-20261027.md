# HITL Sandbox Lab — contrat initial (2026-10-27)

**Statut : code de bibliothèque testé localement, NON intégré à Core/Temporal/Portal, aucune qualification LIVE.**

Ce micro-lot introduit `app/shared/hitl_lab.py`, un stockage SQLite transactionnel pour les propositions et approbations de laboratoire. Il ne lance aucun shell, Ansible, API de remédiation ou postcheck. Les seules recettes sont `acme.demo.restart-service.v1` et `acme.demo.failover-link.v1`, avec paramètres typés et strictement allowlistés. Modes autorisés : DEMO/REPLAY/STORY; LIVE rejeté.

## Contrat

- `initialize(path)` crée les tables et déclencheurs anti-update/delete.
- `propose(... incident_id, run_id, recipe_id, target_id, params, proposer_id, mode, ttl_seconds)` crée un identifiant aléatoire et un SHA-256 canonique des paramètres et du binding. TTL de 1 à 3600 secondes.
- `approve(... proposal_id, approver_id, approver_role)` exige `approver` et un approbateur différent du proposant. Le jeton aléatoire est retourné une fois; seul son SHA-256 est stocké. Le rôle **doit être attesté par un service d'authentification en amont**; la chaîne fournie à cette bibliothèque n'est pas une preuve d'identité.
- `dry_run(... approval_token, binding complet)` vérifie binding, expiration et jeton, puis consomme l'approbation atomiquement via `BEGIN IMMEDIATE` et écrit un reçu append-only. Retourne `DRY_RUN_PLANNED`, `effect_executed:false`, `execution_allowed:false`, `synthetic:true`, postchecks `NOT_EXECUTED` et rollback `NOT_EXECUTED`.

Une proposition modifiée ne peut pas réutiliser l'approbation : nouvelle proposition, nouveau hash, nouvel accord. La séparation des rôles et le refus de rejouer un jeton sont testés. Les déclencheurs SQLite interdisent UPDATE et DELETE de quatre tables. Ceci n'est pas un registre cryptographiquement attesté contre un administrateur ayant accès au fichier : durabilité, backups, rétention et preuves signées doivent être conçus pour le runtime.

## Limites et prochaine intégration

**NOT_TESTED** : authenticité de l'acteur, RBAC multi-tenant, Core incident/run ownership, policy/fencing, Temporal retries, redémarrage du Worker, service d'approbation HTTP, session portail, vraies exécutions de sandbox et postchecks, sauvegarde/restauration, PostgreSQL multi-répliques. Le lab SQLite est une couche de développement isolée, **pas une seconde source de vérité du Run**.

Avant tout branchement, intégrer derrière Core avec actor ID issu d'une identité authentifiée, vérification de tenant et ownership du Run, corrélation Evidence append-only et `Policy`. Le Golden Demo doit afficher les états exacts `AWAITING_HUMAN_APPROVAL` → `APPROVED_FOR_DRY_RUN_ONLY` → `DRY_RUN_PLANNED`, sans `PASS` ou `REMEDIATED` tant que postchecks et rollback n'ont pas été exécutés et vérifiés. Aucun effet LIVE n'est autorisé par ce module.

### Tests

`python -m unittest discover -s tests -p test_hitl_lab.py -v` : 16 tests exécutés localement, OK. Le workflow existant `.github/workflows/quality.yml` exécute également ce fichier sur PR; son statut doit être confirmé via GitHub Actions, indépendamment du test local.

### Réutilisation PR #36

`app/policy/execution_fence.py` sur PR #36 est un mécanisme de réservation revision-fenced `SIMULATION_ONLY` utilisant un `autonomy_store` distinct et non disponible sur main. Il ne fournit pas l'approbation HITL immuable demandée. Le principe de réservation sans effet et le refus explicite de qualification LIVE sont conservés; pas de portage direct du fichier sans sa dépendance ni double autorité.
