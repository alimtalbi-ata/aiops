# Qualification de l’orchestration — parent #457

UTC : 2026-11-08T16:41:30Z. Rôle : Integration. Branche : `agent/integration/457-qualification-preflight`.
Base exacte : `adcceb74bfd6289c161e344382e19be7952e3859`, identique au head Git de PR #456 observé.
Le SHA du présent rapport est celui du commit Git qui contient ce fichier ; aucun SHA futur inventé.

## Verdict

**GO pour préparation des missions isolées ; HOLD pour lancement coordonné et intégration ; DEBIAN UNKNOWN ; E2E NOT_RUN.**
Les cinq worktrees locaux sont isolés et leurs contrôles ciblés passent. Aucun agent Codex secondaire n’a été lancé ; les cinq missions ci-dessous sont prêtes à être enregistrées, pas exécutées automatiquement.
La disponibilité d’un dispatcher, les cinq planifications actives et leurs reçus ne sont pas vérifiables avec les accès présents. Aucun nouveau cron/workflow créé.

Lecture effectuée : AGENTS.md, contrat d’orchestration, continuité, catalogue, inventaire transversal, PR #456 et issue #457, puis corps des PR #212/#438/#443/#453/#454/#455/#446/#450 et sources ciblées.
PR #456 est un contrat candidat sans dispatcher. #457 demande cinq issues de rôle, isolation, CI au SHA exact et gates de provenance/E2E.

## Sources et réutilisation vérifiées

484 branches distantes énumérées et récupérées en références locales ; inventaire complet des noms/SHA joint. Références `refs/pull/*/head` énumérées également. Cela ne constitue pas une revue complète de toutes les PR historiques.
Les pages des PR ciblées ont été lues via HTTPS ; les états CI exacts et l’ensemble des conflits d’issues restent UNKNOWN (API GitHub refusée). Un match de head Git ne prouve pas un merge.

| Domaine | Branche candidate / SHA complet | PR | Résultat de lecture |
| --- | --- | --- | --- |
| Intégration | `integration/core-xref-migration-012-20261031` / `0c07090bed333e90aab1248ffcfc51e10d3f3c67` | #212 | Correction de collision 009→012 déjà documentée ; chaîne combinée et récupération encore à qualifier. |
| Core | `core/fs147-fs1250-reconcile-20261108` / `87f0c5746a9d78f1e3696ecfe73bbeea8278eefb` | #454 | `itsm_reconcile_contract.py` est un classificateur pur ; `live_usecase_receipt_gate.py` n’accorde aucune autorisation d’action. Ne pas réimplémenter. |
| Worker | `worker/fs147-policy-adapter-20261106` / `338636c55233233c16d941ba541212edf779f2f6` | #443 | Pipeline DEMO, bridge et Policy adapters existants ; transports injectés/stubbed. Le guard HITL de `test_fs147_action_binding_contract_20261108.py` est défini dans le test : ce passage ne prouve pas son branchement runtime. |
| Twin | `feat/fs147-twin-adapter-qualification-20261108` / `e50fd4e4cc75a29a1837c9f89d9fc6eaa63154e7` | #453 | Matrices négatives et replay offline existants ; certains validateurs sont définis dans les fixtures. Compatibilité avec véritable ingress Twin non démontrée. |
| Portal | `feat/fs364-portal-two-actions-readonly-20261106` / `236d6c503c9a30a38a364ab607f231c6244e4d09` | #438 | `portal-fs364/` fournit une projection avec ACL injectée ; route authentifiée et montage sur `/fs-real` non établis. |

Autres réemplois : client GLPI déjà présent dans `feat/glpi-ai-ticket-enrichment-e2e@5b3b9f327f517e8f5999766389abf69c8a035cf8` ; le client historique sait écrire : ne pas l’invoquer dans cette qualification. PR #455 refuse de transformer des reçus JSON offline en preuve GLPI authentifiée. PR #446 contient une garde Worker runtime ; PR #450 un gate HITL/fencing candidat. Revue de dépendances nécessaire avant tout port.
`main` observé : `0e232c9fdf4a519de36ba8035b506621854e0277` ; stable : `a0d2a751de57001b9a1bd6beb6ecceaf4afdb222`. Aucune de ces branches modifiée.

## Preuves exécutées dans cette qualification

Python 3.12.14, Node 24.22.1, dépendances applicatives épinglées dans `.venv` du checkout initial ; pytest 8.4.2 ajouté pour le runner existant. Aucun code, test, lockfile ou manifeste modifié.
Chaque worktree a son répertoire et sa branche `agent/<role>/457-qualification-preflight`, tous initialement à la base ci-dessus. Un marqueur temporaire a été écrit successivement dans chacun et son absence vérifiée dans les quatre autres, puis supprimé. Les branches des autres contributeurs n’ont pas été modifiées. Les worktrees partagent les objets Git et le venv en lecture ; les futures missions doivent isoler leurs services/ports/bases si elles écrivent des fixtures.

| Worktree `/workspace/aiops-qualification/…` | Commande dans ce worktree | Résultat |
| --- | --- | --- |
| integration | `bash tests/static-audit.sh` | PASS |
| core | `python -m unittest discover -s tests -p test_core_noc_real_integration.py -v` | 5/5 PASS, véritable Core HTTP + PostgreSQL local isolé |
| worker | `python -m unittest discover -s tests -p test_simulation_policy_contract.py -v` | 6/6 PASS |
| twin | `python -m unittest discover -s tests -p test_acme_impact_read_model.py -v` | 9/9 PASS |
| portal | `node --test tests/test_portal_navigation_client.mjs tests/test_portal_bootstrap_client.mjs tests/test_portal_noc_client.cjs` | 33/33 PASS |

`python` désigne `/workspace/aiops/.venv/bin/python`. Le contrôle Core utilise les services locaux créés pendant l’onboarding, jamais PostgreSQL de production. Les autres tests utilisent des fixtures.

Les candidats ont été exportés sans modification par `git archive origin/<branche>` dans `/workspace/aiops-qualification/candidates/<role>` ; SHA du tableau ci-dessus :

- Core : `python -m unittest discover -s tests -p test_itsm_reconcile_contract.py -v` : 13 PASS ; même commande avec `test_live_usecase_receipt_gate.py` : 10 PASS.
- Worker : unittest `test_fs147_action_binding_contract_20261108.py` : 8 PASS. Premier essai du bridge avec unittest : erreur d’import pytest ; ce runner n’exécute pas les fonctions pytest. Après installation de pytest, `python -m pytest -q tests/test_worker_fs147_bridge_adapter.py` : 17 PASS.
- Worker : `python -m pytest -q tests/test_fs147_service_fail_closed.py tests/test_fs147_service_pipeline.py tests/test_fs147_policy_reply_correlation.py` : 20 PASS ; transports stubbed, aucun effet distant.
- Twin : `python -m unittest discover -s tests -p 'test_fs147_twin*contract.py' -v` : 24 PASS offline.
- Portal : `node --test portal-fs364/fs-real-questions-read-gating.test.mjs portal-fs364/fs-real-two-actions-contract.test.mjs` : 11 PASS.

Logs, commandes, sorties et inventaires : [qualification-457](qualification-457/). `candidate-results.json` conserve honnêtement l’échec initial ; `worker-candidate-pytest.log` contient le rerun correct. Les résultats locaux ne sont pas des GitHub Actions. CI au SHA exact : UNKNOWN, aucun lien Actions attesté. Le test navigateur Chromium reste bloqué par `403 Domain forbidden` sur cdn.playwright.dev / playwright.download.prss.microsoft.com constaté à l’onboarding. Suite complète Temporal/GLPI et E2E bout en bout : NOT_RUN. Reçus Debian/image digest/horodatage/fraîcheur : UNKNOWN, aucun accès au serveur effectué.

## Cinq missions Codex indépendantes, prêtes à dispatcher

Base commune proposée : SHA `adcceb74bfd6289c161e344382e19be7952e3859` sur la branche d’orchestration, à faire confirmer par Integration avant port. Pas de cherry-pick global des anciennes branches empilées. Chaque session commence par rechercher les issues/PR récentes et les conflits de chemins, lit son issue et fige les SHA source.
Les cinq worktrees présents sont des preuves de préflight, rattachés au parent #457 ; ils ne remplacent pas les cinq issues distinctes demandées. À leur création, réserver `agent/<role>/<nouveau-numéro>-<slug>` sans renommer une branche existante. Une issue, une branche, une PR DRAFT vers la base convenue, un handoff `docs/handoffs/<role>/latest.md`. Aucune session n’est prétendue lancée.

### 1. Intégration — registre, contrats et gates

Objectif : enregistrer les cinq missions, arbitrer les collisions et produire le DAG de sélection de réemploi et les gates source/CI/provenance.
Chemins possédés : `docs/handoffs/integration/**`, `docs/architecture/AIOPS2-MULTIAGENT-ORCHESTRATION.md`, `AGENTS.md`, continuité et catalogue canoniques ; les fichiers canoniques ne sont modifiés qu’ici. Aucun changement source applicatif, cron, Compose ou workflow.
Réutiliser #212, #455, contrat #456 et parent #457. Dépendances : métadonnées des quatre rôles, accès GitHub pour issues/PR/checks ; travail documentaire indépendant possible dès maintenant.
Acceptation : cinq issues distinctes et propriétaires, matrice de chemins sans chevauchement, SHA et tests exacts, CI avec liens de runs au même SHA, échecs/skips conservés ; audit statique. G0 ne vaut ni G1 ni G3. L’ordre d’intégration suit le DAG et une revue séparée, sans merge automatique.
Arrêt : identité de source ou base ambiguë, absence de reçu, collision de migration, API/écriture GitHub refusée ou propriété concurrente non arbitrée. Mettre HOLD, ne pas inventer un numéro d’issue ni un résultat.

### 2. Core — admission et réconciliation en lecture

Objectif : comparer/porter sélectivement le classificateur #454 et les contrats xref existants, sans ticket ni réparation persistante automatique.
Chemins réservables après arbitrage : `app/core/itsm_reconcile_contract.py`, `app/core/live_usecase_receipt_gate.py`, `tests/test_itsm_reconcile_contract.py`, `tests/test_live_usecase_receipt_gate.py`, `docs/handoffs/core/**`. `app/core/main.py` et toute migration sont des points de coordination, pas des droits implicites.
Interfaces : statuts MATCHED/EXISTING_UNLINKED/AMBIGUOUS/MISSING/NOT_ELIGIBLE/UNKNOWN/CONFLICT ; tenant/incident/run/ticket/readback ; gate reçu v1 ne vaut pas admission. Dépendances : snapshot GLPI authentifié fourni par une future intégration autorisée ; Worker/Portal consomment les sorties figées. Tests purs indépendants de ces services.
Acceptation : 13+10 tests existants, mauvais tenant/run, données incomplètes, doublons, Policy BLOCKED, reçu périmé/futur ; tests HTTP/PG uniquement sur DB jetable pour tout port runtime ; aucune création GLPI ni écriture production.
Arrêt : besoin de backfill/migration réelle, concurrence sur Core/main/schema, GLPI non authentifié, confusion absence xref/absence ticket. UNKNOWN/HOLD sans remplacement de l’API existante.

### 3. Worker — composition et refus d’exécution

Objectif : qualifier le pipeline existant #443 avec #446/#450 ; distinguer predicate de fixture et admission effective avant Temporal.
Chemins réservables : `worker/fs147_*.py`, tests `tests/test_worker_fs147_*.py`, `tests/test_fs147_*.py` hors famille Twin, `docs/handoffs/worker/**`. Tests spécifiques du rôle seulement ; `app/worker/main.py` et `app/shared/**` nécessitent un handoff avant écriture. Aucun changement Policy ou schéma Core implicite.
Interfaces : Core claim durable et résultat ambigu, identité tenant/actor/run/action, Evidence fraîche, retour Policy corrélé, Critic, STOP_AUTO, liaison HITL action/digest/révision/expiration. Dépendances : contrat Core figé, observation Twin explicitement synthétique ; transports stubbed permis en phase unitaire, pas présentés comme réels.
Acceptation : bridge 17 tests et service/corrélation 20 tests ci-dessus ; matrice négative idempotence/concurrence, claim UNKNOWN, double livraison, Policy/Critic refusés, révocation et expiration ; preuve de zéro dispatch sur refus. Toute intégration Temporal isolée doit produire son vrai reçu avant déclaration E2E.
Arrêt : transport authentifié indisponible, claim durable non démontré, besoin d’action LIVE ou signal réel, bypass HITL, collision de contrat Core. Conserver NO_EFFECT/HOLD.

### 4. Twin — frontières de scénarios et provenance

Objectif : réutiliser #453/#451 et relier les matrices offline au véritable ingress candidat avant toute qualification runtime.
Chemins réservables : `tests/test_fs147_twin*contract.py`, `docs/handoffs/twin/**` ; `app/twin/**` et `app/simulator/**` uniquement après analyse du diff et déclaration précise des fichiers dans l’issue. Aucun accès infrastructure/client.
Interfaces : candidate.v1, tenant/source/event/correlation/incident/run/Evidence, graph/namespace, timestamps, métrique, resource et arêtes. Dépendances : contrats de lecture Core/Worker figés ; fixtures autonomes sans services.
Acceptation : 24 tests offline ; replay déterministe, substitution de tenant/source/graph/namespace, arête étrangère, provenance imbriquée et URI interdite ; tester aussi l’entrée applicative réutilisée pour ne pas qualifier seulement une fonction définie dans le test. Étiquettes SIMULATED/UNKNOWN conservées.
Arrêt : mélange SAN/fs-lab, données client, URI/transport sortant non autorisé, source/runtime non mappé ou conflit d’ownership. Aucun E2E réel inféré du replay.

### 5. Portal — projection authentifiée et états honnêtes

Objectif : qualifier le module #438 et les vues de trace/HITL/annulation FS1113 existantes avant de monter une route ; pas de nouvelle UI parallèle sans recherche préalable.
Chemins réservables : `portal-fs364/**`, `docs/handoffs/portal/**` ; fichiers précis de `app/portal/**` et tests `test_portal_*` à déclarer après découverte et arbitrage. Pas de Core xref write, Policy ou migrations.
Interfaces : projection GET same-origin, principal actor/tenant authentifié, ACL ticket/tenant, même Run Core/Temporal/Policy ; absence de preuve rend UNKNOWN, jamais approved/resolved. Dépendances : contrat Core stable, champs Worker en lecture ; mock transport acceptable pour tests, pas pour preuve de montage réel.
Acceptation : 11 tests candidats et 33 tests DOM de base ; 401/403/503/redirection login, pas de fetch avant ACL, mauvais ticket/run/tenant, réponse périmée et annulation de requête ; régression FS1113 localisée après découverte de son implémentation. Test navigateur réel de la route montée requis avant claim navigateur/E2E.
Arrêt : endpoint absent, modèle d’identité non attesté, besoin d’écrire GLPI, confusion HITL affiché/autorisé, Chromium indisponible ou conflit de chemin. Rapporter BLOCKED/UNKNOWN.

## Dépendances, actions et publication

DAG : Integration réserve les contrats → Core fixe le read-model/admission → Worker et Twin qualifient les adaptateurs → Portal consomme ; tests offline et découverte peuvent avancer indépendamment. Integration consolide les cinq handoffs, vérifie les SHA et soumet les gates. Aucune fusion dans cette mission.
Chaque rôle doit s’arrêter sur une issue active propriétaire des mêmes chemins et demander l’arbitrage Integration. Les réservations ci-dessus sont des propositions, pas un verrou global validé : API issues/PR indisponible.

Action requise : rétablir l’accès GitHub API autorisé pour lire les conflits/CI, créer les cinq issues, publier un commentaire dans #457 et ouvrir les PR DRAFT si une mission modifie code/tests. Ne pas demander de secret en chat. L’authentification Git HTTPS existante fonctionne en lecture ; cela ne prouve pas l’autorisation API ou push.
Ce rapport documentaire sera poussé uniquement sur la nouvelle branche Integration si Git autorise l’écriture. Aucun code ni test modifié : pas de PR de code nécessaire. L’échec d’un push sera signalé sans prétendre à une publication.

Risques : compatibilité interbranches et migration combinée non qualifiées, dispatcher et schedules non audités, CI distante inconnue, branche historique GLPI capable d’écriture, tests fixture-only insuffisants. Rollback : abandonner le commit documentaire et les seules branches/worktrees de préflight créés ici après conservation des preuves ; aucun rollback production nécessaire ou autorisé.
Prochain propriétaire : Integration pour accès GitHub, réservation des issues/chemins et dispatch explicite ; opérateur séparément autorisé pour toute future preuve Debian.
