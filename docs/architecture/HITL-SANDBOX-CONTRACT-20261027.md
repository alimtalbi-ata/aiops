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


## Golden Demo — projection vérifiable et lecture seule (incrément 22:25)

- `read_status(path, proposal_id, now)` lit la base SQLite en `mode=ro` + `query_only`, sans créer le fichier ni exposer jeton, hash de jeton ou identités d'approbateur. Le résultat est expurgé avec `source=LOCAL_SANDBOX_SQLITE_NOT_CORE`, `execution_allowed=false`, `effect_executed=false`, postchecks/rollback `NOT_EXECUTED`. Les séquences d'audit incohérentes sont rejetées. Un accord expiré est `EXPIRED`; une planification déjà émise reste `DRY_RUN_PLANNED`, jamais une remédiation réussie.
- `python -m demo.hitl_golden_demo --output /tmp/aiops-hitl-story.json` exécute réellement `propose → approve → dry_run` sur une base temporaire SQLite, puis exporte les **trois états observés** et le reçu. Le jeton reste uniquement en mémoire et n'est pas exporté. Le SHA-256 est une somme d'intégrité locale, **pas** une attestation d'authenticité, ni une preuve d'intégration Core/Temporal.
- Le portail unique dispose de `/demo/hitl` et `/api/demo/hitl`, lecture seule. Sans configuration : `NOT_CONFIGURED`. Pour afficher l'artefact, configurer `AIOPS_HITL_DEMO_ARTIFACT` vers un fichier JSON généré par le script et monté en lecture seule dans le conteneur portail. Le routeur refuse les liens symboliques, fichiers instables, charges trop grandes, champs supplémentaires, états incohérents, mode LIVE, fausses preuves et altération du digest. **Aucun jeton, POST d'approbation ou action de remédiation n'est exposé par le portail.**
- Les libellés `INC-SIM-*` et `RUN-SIM-*` ne sont **pas** des IDs canoniques Core. L'artefact est une démonstration de la bibliothèque HITL en laboratoire, **pas** une intégration du Run réel. Il ne faut pas le présenter comme une capture LIVE ni une approbation GLPI.
- Test local/CI : `python -m unittest discover -s tests -p 'test_hitl_story.py' -v`; tests négatifs d'altération, de jeton, d'expiration, de binding, de symlink, de fichier malformé et de preuve LIVE falsifiée. Les résultats CI doivent être relevés après exécution.

**Limites :** aucun RBAC authentifié Core, aucune écriture Evidence, aucune attestation de provenance, aucun postcheck exécuté et aucun rollback réalisé. Prochaine étape : relier les statuts au Run canonique via Core après qualification de l'identité et du stockage transactionnel; ne pas monter SQLite dans le portail comme autorité.

## Durcissement de la cohérence des bindings (23:19)

Le lecteur SQLite `read_status` recalcule maintenant le SHA-256 canonique de `incident_id/run_id/recipe_id/target_id/params_hash/mode` et rejette une ligne dont le binding stocké ne correspond pas, même si un opérateur du fichier a contourné les triggers SQLite. Le validateur du récit côté portail recalcule le même binding pour chaque état et refuse un `binding_hash` ou `params_hash` falsifié, **même si l'auteur de l'artefact a recalculé `story_sha256`**. Des tests négatifs sont ajoutés.

Cette vérification garantit seulement la cohérence des champs, **pas** leur authenticité : SHA-256 sans secret, fichier SQLite local et JSON non signés. L'intégration Core/Evidence avec provenance authentifiée reste obligatoire. La PR #49 diverge de `main`; ses nouveaux tests ne doivent pas être annoncés comme PASS avant exécution sur le HEAD concerné.
