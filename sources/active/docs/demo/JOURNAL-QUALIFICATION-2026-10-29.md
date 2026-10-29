# Journal de qualification et de reprise — 2026-10-29

**Statut : documentation et contrôles statiques OK ; démonstration intégrée NON QUALIFIÉE.**
**Source : sortie de terminal Debian communiquée par l'opérateur ; aucune session SSH ni Docker n'a été exécutée par l'assistant.**
**But : garder un journal vérifiable, ne pas perdre deux mois de développement, converger vers la démo ACME.**

## 1. Chronologie des opérations attestées

| Ordre | Contexte | Opération | Résultat constaté | Portée réelle |
|---|---|---|---|---|
| 1 | Debian, worktree `/home/aiops/aiops2-p0-consolidation` | Correctif Worker `command=OBSERVE` pour DEMO/REPLAY/STORY, `EXECUTE` pour LIVE | Message `OK`, `py_compile` et `git diff --check` sans erreur ; diff affiché | Source locale, pas un test E2E |
| 2 | Même worktree | `git add`, `git diff --cached --check`, commit et push | `321fd5a` publié sur `feat/p0-runtime-consolidated-20261029` | Sauvegarde distante confirmée |
| 3 | GitHub | Création de `prep/acme-demo-offline-20261029` à partir de la consolidation | Branche créée ; `65f7a729` preflight ; `0274765` gates | Préparation sans déploiement |
| 4 | Debian | `git fetch` explicite de la branche prep, puis `git switch -c ... --track origin/...` | Fetch réussi ; switch échoué : `point de départ ... n'est pas une branche` ; SSH fermé | Erreur de suivi Git, pas une perte de commit |
| 5 | Debian | `git switch -c prep/acme-demo-offline-20261029 refs/remotes/origin/prep/acme-demo-offline-20261029` | Switch réussi ; HEAD `0274765` | Worktree positionné sur prep sans upstream automatique |
| 6 | Debian | `python3 tools/acme_offline_source_preflight.py` | **26 PASS, 0 FAIL**, `ACME_OFFLINE_PREFLIGHT=PASS` | Contrôles source et AST uniquement |
| 7 | GitHub | Publication de `docs/PROJECT-REPRISE-DEMO-2026-10-29.md` et lien dans `docs/PROJECT-CONTINUITY.md` | Commits `1e020953`, puis `adbdc303` | Documentation source de vérité mise à jour |
| 8 | Debian | `git fetch` explicite, `git merge --ff-only refs/remotes/origin/prep/acme-demo-offline-20261029` | Fast-forward `0274765..adbdc30`, 2 fichiers, 63 insertions | Debian synchronisé avec le commit GitHub à cet instant |
| 9 | Debian | `git log -1 --oneline` et `git status --short` | HEAD `adbdc30` ; sortie `status --short` vide | Worktree propre au moment de la commande |

**Remarque de version :** ce journal, publié après le constat `adbdc30`, créera un **nouveau** commit sur GitHub. Le serveur Debian devra le récupérer par `fetch` + `merge --ff-only`. Ne pas affirmer qu'il est déjà présent sur Debian.

## 2. Détail exact des 26 contrôles statiques réussis

**Sources Python trouvées et analysées (11/11)** :
`app/simulator/main.py`,
`app/worker/main.py`,
`app/policy/main.py`,
`app/core/main.py`,
`app/twin/main.py`,
`app/evidence/main.py`,
`app/portal/qualification_lab.py`,
`app/core/demo_evidence_read.py`,
`app/shared/tenant_scope.py`,
`tests/test_p0_policy_consolidated.py`,
`tests/test_p0_twin_consolidated.py`.

**Contrats textuels trouvés (15/15)** :
1. Simulator rejette LIVE.
2. Simulator lance incident et run.
3. Worker transmet une commande Policy non exécutante pour les modes synthétiques.
4. Worker marque les preuves synthétiques `observed_at=None`, `observed=False`.
5. Worker invoque Analyst et Critic.
6. Worker persiste la décision Policy.
7. Policy garde le refus des effets LIVE.
8. Policy exige Critic et un seuil de confiance.
9. Policy peut rendre `SIMULATE` en synthétique.
10. Core contient des propositions sans autorisation d'exécution.
11. Prévisualisation Chaos et Smoke présente.
12. Script E2E runtime présent.
13. Runbook historique ACME présent.
14. Endpoint Prometheus Evidence présent dans le code.
15. Twin distingue l'état d'impact réel inconnu.

**Ce que ces contrôles NE démontrent PAS** : images construites, schéma DB migré, Temporal connecté, modèle IA réel joignable, qualité du RCA, ticket GLPI, simulation effective de remédiation avant/après, dashboard exploitable, absence de fuite de secrets, déploiement sûr. Ils vérifient des motifs source, pas le comportement de bout en bout.

## 3. Autres preuves connues, à ne pas mélanger

- **18 tests P0** rapportés lors de la consolidation : 11 Policy, 7 Twin. Le test de traversée Twin utilisait une base factice ; pas de PostgreSQL intégré.
- **CI historique du 20 octobre** : le document `docs/PROJECT-CONTINUITY.md` rapporte une qualification d'un kit Core avec fournisseur déterministe, Temporal synthétique et zéro effet. Le SHA et les liens CI historiques doivent être revérifiés avant réutilisation ; ce résultat ne valide pas la branche du 29 octobre.
- **Runbook UI historique du 22 octobre** : `docs/ACME-DEMO-RUNBOOK-V2114.md` décrit un parcours de présentation et des tests effectués précédemment, pas une nouvelle campagne.
- **Prometheus** : 5 cibles DOWN observées précédemment sur le runtime Debian ; source consolidée modifiée, **aucun déploiement ni nouveau scrape PASS** prouvé.
- **GLPI/n8n, DGX réel, remediation simulation** : pas de résultat d'intégration récent. Ne pas annoncer PASS.

## 4. Catalogue de réutilisation : recherche prioritaire

| Domaine | Indices à investiguer dans toutes les branches et sur Debian | Preuve manquante | Priorité |
|---|---|---|---|
| ACME scénario incident SAN / Payments | `app/simulator/main.py`, `app/worker/main.py`, seeds Core, scénarios historiques | Run reproductible et isolé | P1 |
| Analyst / Critic / Evidence | `app/intelligence`, `app/evidence`, Temporal, tests et rapports | Réponse réelle + IDs d'evidence + Critic indépendant | P1 |
| Remédiation proposée | API `/api/runs/{rid}/proposals`, historique runbooks et adapters | Liaison au même run et à la topologie | P1 |
| **Remédiation simulée** | Rechercher `simulate`, `what-if`, `rollback`, `postcondition`, `recovery` dans branches, commits et code non suivi | Avant/après, échec, rollback, audit, zéro effet | **P1 bloquant** |
| Chaos et Smoke | `app/portal/qualification_lab.py`, scripts historiques | Scénarios et Critic/Policy E2E | P1 |
| Tickets et communication | GLPI, n8n, connecteurs, historique portail | Ticket lié au run, statuts, rôles et communications | P1 |
| Copilot / RAG / rôles | Services Copilot/RAG, historique V1/V145, portail | Questions métier avec contexte et contrôle d'accès | P2 |
| Cockpit | `/acme-stories`, `/timeline`, `/policy-story`, `/qualification-lab`, `/copilot`, Grafana | Navigation et données courantes | P1 |
| Déploiement | `deploy/install-isolated.sh`, Compose, migrations, CI, backup | Staging vierge, identité isolée, rollback testé | P1 |

**Ne pas interpréter « non trouvé dans cette branche » comme « inexistant dans le projet ».** Le worktree historique `/home/aiops/aiops-v28-demo` possède des fichiers non suivis, notamment `app/portal/demo_v2.py` et des tests. Préserver et examiner avant toute consolidation.

## 5. Décisions et règles

- La branche de préparation n'est **pas** une release candidate déployable ; aucune bascule du stack existant.
- Une décision Policy `PASS/SIMULATE` n'est pas une simulation de remédiation réussie.
- Le scénario doit être **synthétique, déterministe et traçable par run_id**, avec un cas succès et un cas échec ; aucun effet réel.
- Ne pas réinitialiser volumes, DB, secrets, ni déployer des migrations sans backup et plan de rollback.
- Tous les nouveaux travaux doivent être enregistrés avec chemin, commit, test, sortie et limite dans GitHub.
- Le focus reste l'**expérience de démonstration** : incident → preuves → IA RCA → Critic → remédiation proposée → simulation avant/après/rollback → Policy → ticket/communication → cockpit.

## 6. Prochaine action opérateur — lecture seule

**Après publication de ce journal** : récupérer le nouveau commit GitHub dans le worktree courant avec le refspec explicite, sans `--track` :

```bash
cd /home/aiops/aiops2-p0-consolidation
set -e
git fetch origin refs/heads/prep/acme-demo-offline-20261029:refs/remotes/origin/prep/acme-demo-offline-20261029
git merge --ff-only refs/remotes/origin/prep/acme-demo-offline-20261029
git log -1 --oneline
git status --short
```

Ensuite : produire un inventaire **lecture seule** des branches/PR et des fichiers historiques manquants de GitHub, puis une matrice de réutilisation vérifiable. Aucune action Docker demandée à ce stade.

## 7. Discipline de mise à jour

Chaque nouvelle session ajoute une entrée datée à ce journal ou crée `docs/demo/session-YYYY-MM-DD-NN.md` avec : SHA GitHub, SHA Debian, branche, objectif, commandes et sorties, vérifications réalisées, hypothèses, échecs, risques, décisions, critères GO/NO-GO et **une seule prochaine action opérateur**. Mettre à jour `docs/PROJECT-CONTINUITY.md` et `docs/PROJECT-REPRISE-DEMO-2026-10-29.md` pour maintenir le point d'entrée. Ne jamais copier de secrets ou de dumps dans GitHub.


## 8. 2026-10-29 — Qualification offline du laboratoire de remédiation sur Debian

**Source : sortie de terminal communiquée par l'opérateur, non exécutée par l'assistant.** Worktree : `/home/aiops/aiops2-p0-consolidation`, branche `prep/acme-demo-offline-20261029`.

| Commande / étape | Résultat observé | Qualification |
|---|---|---|
| `git fetch` explicite puis `git merge --ff-only` | `e1748b7..8901ca9`, fast-forward, 8 fichiers, 701 insertions | Code du labo et de la projection récupéré sur Debian |
| `git log -1 --oneline` | HEAD `8901ca9` | SHA Debian confirmé au moment de l'essai |
| `python3 -m unittest discover -s tests -p 'test_remediation_lab.py' -v` | **10 tests OK**, `Ran 10 tests in 0.005s` | Contrats historiques : recettes, approbations, sécurité, idempotence, zéro effet |
| `python3 -m unittest discover -s tests -p 'test_acme_remediation_projection.py' -v` | **8 tests OK**, `Ran 8 tests in 0.003s` | Projection pure : succès, échec, rollback hypothétique, LIVE refusé, préconditions, cible, déterminisme |
| `python3 tools/acme_offline_source_preflight.py` | `ACME_OFFLINE_PREFLIGHT=PASS | checks=26 | failed=0` | Contrôle statique existant toujours PASS |
| `git diff --check`, `git status --short` | Aucune sortie | Aucun défaut de diff ni changement local signalé |

**Total des nouveaux tests de remédiation exécutés dans cette session : 18/18 PASS.** Les 26 contrôles de preflight sont distincts des tests unitaires ; ne pas annoncer 44 tests unitaires.

**Gates toujours ouverts :** pas de DB/Temporal, aucun raccord `run_id` entre Core et simulation, aucun ticket GLPI/n8n qualifié, pas de preuve Analyst/Critic réel, aucune postcondition observée ni rollback réel, aucun E2E conteneur. Les états `SIMULATED_SUCCESS` et `SIMULATED_FAILURE` sont des projections `WHAT_IF_FIXTURE_NOT_OBSERVED` ; `effect_applied=False`, `postchecks=NOT_RUN`. Le script de preflight n'a pas été étendu dans cet incrément pour inspecter le nouveau module ; sa réussite ne remplace pas les 18 tests.

**Suite technique prioritaire :** raccordement synthétique traçable au run ACME, conservation de la provenance et de la séparation Policy/HITL, exposition read-only sécurisée, puis E2E isolé. Pas de modification Docker avant qualification et autorisation.


## 9. 2026-10-29 — Deuxième passe autonome : analyse et code offline

**Dernière preuve Debian communiquée :** HEAD `5c408cf`, **28/28 tests Python PASS** (10 laboratoire, 8 projection, 10 receipt), compilation des 3 modules sans erreur. La commande envoyée contient une fin de here-doc suivie du texte `BASHstatus --short` ; **ne pas en déduire** que `git status --short` ou `git diff --check` a été exécuté lors de cette passe. Les sorties des tests et de `py_compile` sont bien présentes et réussies.

**Travaux GitHub effectués depuis ce SHA :**
1. Audit comparatif des branches `feat/p0-acme-scenario-contract-20261028-1153`, `feat/acme-core-noc-itsm-correlation-20261027`, `feat/p1-glpi-real-http-ci-20261028-1035`, `feat/golden-demo-journey-20261027`, `release/p0-demo-v2-ui-candidate-20261029-0004`. Fichiers source ciblés lus. Voir [audit d'architecture](AUDIT-ARCHITECTURE-CONVERGENCE-2026-10-29.md).
2. Correction de sécurité métier : une recette read-only (inspection ou ticket) ne peut plus projeter arbitrairement `HEALTHY`. Test dédié ajouté.
3. Nouveau `app/shared/acme_demo_offline.py` : CLI JSON déterministe SUCCESS/FAILURE sans Docker, sans secrets en clair ni effets ; 4 tests dédiés.
4. État : code publié, **aucun test de ce nouvel incrément exécuté sur Debian**. Attendus 33 tests (10 + 9 + 10 + 4), plus 26 preflight statiques. Ne pas annoncer PASS avant la sortie opérateur.

**Risques encore ouverts :** CLI basée sur fixtures non observées, IDs Core/Evidence non vérifiés, pas de GLPI, aucune authentification réelle HITL, aucune simulation SAN, aucune traversée DB/Temporal/Portal. Les tests sont de la logique offline uniquement.

**Prochaine action opérateur** : synchroniser GitHub puis exécuter les 33 tests Python et les deux sorties JSON de la CLI ; ne pas toucher Docker.


## 10. 2026-10-29 — Qualification Debian de l'incrément CLI et des 33 tests

**Preuve :** transcription de terminal fournie par l'opérateur, HEAD Debian `43734aa`, branche `prep/acme-demo-offline-20261029`. `git fetch` puis `merge --ff-only` ont avancé `5c408cf..43734aa` (7 fichiers, 209 insertions).

- `test_remediation_lab.py` : **10/10 PASS**.
- `test_acme_remediation_projection.py` : **9/9 PASS**, y compris `test_read_only_recipe_cannot_claim_recovery`.
- `test_acme_remediation_receipt.py` : **10/10 PASS**.
- `test_acme_demo_offline.py` : **4/4 PASS**.
- Total tests Python de ces quatre suites : **33/33 PASS**.
- `tools/acme_offline_source_preflight.py` : **26/26 PASS** ; contrôles de source statiques distincts.
- `python3 -m app.shared.acme_demo_offline --outcome SUCCESS` : JSON produit, `SIMULATED_SUCCESS`, `DEGRADED -> HEALTHY` hypothétique, `effect_applied=false`, `postchecks=NOT_RUN`, `core_run_verified=false`, `evidence_verified=false`, `persisted=false`.
- `python3 -m app.shared.acme_demo_offline --outcome FAILURE` : JSON produit, `SIMULATED_FAILURE`, état inchangé, rollback `PROJECTED_ONLY`, zéro effet.
- Le digest de receipt diffère entre SUCCESS et FAILURE ; la clé d'idempotence du gate reste stable pour la même proposition.
- `git log -1 --oneline` : `43734aa`. Les commandes `git diff --check` et `git status --short` n'ont émis aucune sortie dans la transcription, cohérent avec un worktree propre.

**Limites :** preuve d'exécution offline Python uniquement ; aucun run Core persistant ni référence Evidence vérifiée, aucun appel GLPI/n8n, aucun runtime E2E ni action LIVE. Les IDs `RUN-ACME-OFFLINE-001` et `EVD-ACME-OFFLINE-*` sont des fixtures et non des identités Core attestées.
