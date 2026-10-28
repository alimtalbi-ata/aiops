# 2026-10-29 00:33 Europe/Paris — P0 Policy HTTP réel en CI éphémère

## Base et coordination
- HEAD `main` relu juste avant modification : `103c1ded7bd39daf59699a4e416fc3f91dc74d57` ; branche dédiée `test/p0-policy-real-http-ci-20261029-0033`.
- Stable `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée**.
- PR ouvertes consultées : #171 NOC/Ledger, #170 Twin, #169 Studio, #156 Recette 5/5, #137 Story HITL, et les piles historiques #140/#142/#143/#145/#146. #144/#147/#155/#163 sont déjà convergées dans `main` via #160/#163. Journal précédent `2026-10-29T0004-p0-policy-release-convergence.md` relu.
- Micro-lot **unique** : qualifier le moteur Policy via HTTP réel, au lieu de seulement TestClient, dans `.github/workflows/quality.yml` existant. Aucun nouveau workflow.

## Fichiers et contrat
- `tests/test_policy_real_http_integration.py` : 8 tests HTTP sans mock, contre Policy FastAPI réellement démarré sur loopback éphémère CI. Chemin DEMO `PASS/SIMULATE`, absence d'Evidence `UNKNOWN`, P1 `ESCALATE`, refus des effets LIVE malgré `human_approved=true`, rejet commandes libres et mode invalide, garde-fou de lecture LIVE.
- `.github/workflows/quality.yml` : ajout du démarrage, de la disponibilité, des tests et de l'arrêt de Policy au job existant `core-postgres-noc-real-integration`, qui utilise déjà Core HTTP + PostgreSQL 16. Aucun NGX, Ollama, secret prod, migration ni déploiement.
- Contrat API **inchangé** : `POST /api/policy/check` et `aiops.core-demo-policy-observation.v1` restent identiques. La décision HTTP Policy est indépendante de la gate persistée dans Core : **aucun E2E de corrélation revendiqué**.

## Vérification et limites
- Tests locaux : **NOT_TESTED** au moment du commit (la validation cible est GitHub Actions sur services éphémères).
- CI candidate `quality.yml` : **PENDING** jusqu'à run confirmé ; ne pas marquer PASS par anticipation.
- **NOT_TESTED** : HITL authentifié, Temporal sandbox, postchecks/rollback, Evidence/AI Ledger, isolation tenant runtime, chaîne SAN→Payments, Debian, `applied.sha` et smoke terrain.
- Les sept Runs DEMO (5 BLOCKED sans gate, 1 RESOLVED/PASS/SIMULATE, 1 RUNNING ancien) sont des observations utilisateur du 28/10, **pas** des mesures de cette exécution. `SIMULATE` ne prouve ni remédiation LIVE ni retour à la normale.

## Décision / handoff
- **NO-GO E2E ; READY_FOR_STABLE=BLOCKED**. Déployeur V2 ne transporte pas automatiquement Core/Policy ni les scripts de qualification ; rollback terrain non validé.
- PR candidate à remettre exclusivement au lot Recette 5/5 (#156), sans pousser sur `deploy/aiops2-stable`.
- Prochain micro-lot : après CI verte, vérifier une corrélation authentifiée `run_id`/`incident_id` entre gate Core et décision Policy SIMULATE, sans écriture ni effet LIVE ; sinon consigner NOT_TESTED.
