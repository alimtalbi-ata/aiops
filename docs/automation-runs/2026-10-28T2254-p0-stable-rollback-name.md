# 2026-10-28 22:54 Europe/Paris — Recette 5/5, nom de sauvegarde Docker

## Vérifications initiales et coordination
- `main` HEAD vérifié avant écriture : `13c455256f34e5e0f0ac55146326888b0fb84c42` (#160 intégré).
- `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée** ; comparaison GitHub : historique divergé, 40 commits devant et 633 derrière depuis stable vers main. Pas de fast-forward sûr.
- #153 HEAD `d5243b769035aedf4e66b1416a7cdee83ff2ea24`, base `feat/demo-studio-v2-delivery-20261028` HEAD `296ab8136efe9a9068cd6b6045236c5abc52694b`, checks propres de #153 verts mais ne couvrent ni la recette Debian ni Core/Twin/Copilot.
- PR #140–#146 examinées : #141 fusionnée, #144 fermée après portage ciblé #160, #142/#143 encore ouvertes, #146 non fusionnable, #140/#145 empilées. Travaux récents #159 Twin (CI propre verte), #161/#162 Evidence Ledger (CI globale non qualifiée), #163 Core/Policy (nouvelle PR) ; journaux de ces créneaux consultés. #156 reste candidate Recette séparée, sans qualification terrain.
- Continuité `docs/PROJECT-CONTINUITY.md`, déployeur #153, poller et `.github/workflows/quality.yml` lus avant changement.

## Micro-lot vertical
- Branche isolée `fix/p0-stable-rollback-docker-name-20261028-2251` issue de #153 HEAD, [PR draft #164](https://github.com/alimtalbi-ata/aiops/pull/164) **vers la branche de #153**, sans écraser cette branche ni modifier stable.
- Correction `deploy/deploy-demo-studio-v2.sh` : le suffixe littéral `-$` devient `-$$` (PID Bash) dans le nom de sauvegarde horodaté, pour respecter la grammaire Docker et réduire les collisions dans la même seconde.
- `tests/test_demo_stable_rollback_name.py` : quatre tests offline (expansion Bash du nom, unicité des processus, refus de noms invalides, symétrie des références de rollback). Ils **n'exécutent pas** le déployeur, Docker ou le serveur.
- `.github/workflows/quality.yml` : ajoute un seul step dans le job qualité existant pour exécuter ce test et les cinq tests du poller `tests/test_poll_approved_deploy.py`. Pas de nouveau workflow.
- Commits : `4827f12993468f1710697b0c613b7bfd980a4a7a` (arbre initial), `8ba9569044729d7caabd6b7d0e4c6ff11636ff2e` (correction harness), `8fb6bac34a8170a25431bc2441d10b7bdebda5e5` (correctif réel). Un commit intermédiaire `15f6603` n'a modifié aucun blob : erreur d'échappement de `$$` dans l'appel de remplacement JS, corrigée ensuite ; ne constitue pas une validation.
- Contrat : aucune modification d'API ni de mode DEMO/LIVE. Invariant ajouté : nom de sauvegarde Docker valide et distinct par exécution de shell.

## Validation et limites
- CI GitHub Actions existante sur SHA code `8fb6bac34a8170a25431bc2441d10b7bdebda5e5` : [run PR #40775656541](https://github.com/alimtalbi-ata/aiops/actions/runs/40775656541) et [run push #40775648869](https://github.com/alimtalbi-ata/aiops/actions/runs/40775648869). **En cours au moment de la première rédaction** : ne pas considérer PASS avant contrôle final des jobs et logs.
- Test local de la suite complète : **NOT_TESTED** (environnement de travail sans accès GitHub réseau direct) ; validation attendue des tests par CI réelle.
- Test Docker rename/start/rollback, panne pendant switch, préservation des fichiers locaux, `applied.sha`, smoke Debian : **NOT_TESTED**.
- E2E ACME Core→Temporal→Analyst/Critic→Policy→Evidence→Portal, IDs corrélés, tenant RBAC, impact Payments et captures authentifiées : **NOT_TESTED / NO_GO**.
- Risque majeur : déployeur #153 ne transporte que le portail ; ne pas promouvoir Core/Twin/Copilot. Script reste un déployeur à effets réels, **jamais exécuté dans cette livraison**.

## Décision et prochain micro-lot
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO**. Aucun merge de stable, accès Debian, exécution de déployeur ou remédiation LIVE.
- Attendre la CI finale du SHA et confirmer la compatibilité de la PR empilée ; intégrer le correctif dans #153 uniquement après checks verts. Ensuite construire un candidat unique avec couverture effective Core/Twin/Copilot, rollback vérifié et recette terrain en lecture seule avec reçus `applied.sha` et smoke-tests authentifiés.
