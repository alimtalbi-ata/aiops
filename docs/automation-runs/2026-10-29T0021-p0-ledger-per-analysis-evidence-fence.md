# 2026-10-29 00:21 CET — P0 NOC/Copilot — fence Evidence par Analysis

## Baseline / coordination
- HEAD `main` lu avant modification : `103c1ded7bd39daf59699a4e416fc3f91dc74d57` ; HEAD candidate NOC #171 lu et revérifié : `a7cf787cb5acda7eead6722fa72911658699c7b5`. Base Demo Studio V2 historique de #171 : `296ab8136efe9a9068cd6b6045236c5abc52694b`.
- PR ouvertes et travail récent consultés : #171 (candidate unique NOC), #169 (UI), #170 (Twin), #156 (Recette 5/5), #145/#149/#154/#161/#162/#167 (sources historiques) et dernier journal NOC de #171. Pas de merge massif, pas de PR NOC supplémentaire.
- Branche existante du seul owner NOC : `release/p0-noc-ledger-converged-20261029-0004`, PR draft [#171](https://github.com/alimtalbi-ata/aiops/pull/171). Aucune modification de `main` ni de `deploy/aiops2-stable`.

## Micro-livraison et contrat
- Commit code/tests : `d582d9af3b00838ff213f9a778a03561829dfd86` (parent `a7cf787c`). Fichiers : `app/portal/demo_ledger_read.py`, `tests/test_demo_ledger_read.py`.
- Le Portal vérifie désormais que chaque Critique ne cite que les Evidence de **son Analysis liée**. Avant correction, un échange des Evidence entre deux Critiques pouvait conserver l'union globale et passer sans `supported=true` ; le resolver Core ne vérifie que l'union du Run. Le garde-fou refuse la relation cross-Analysis, même sans claim soutenu.
- Test ajouté : multi-Analysis cohérent autorisé (contrôle positif), échange des Evidence cross-Analysis refusé (503 `UNKNOWN`, `no-store`, sans fuite IDs/token). Tests négatifs existants 401 Core/Portal, LIVE, source absente, tenant, Evidence future conservés.
- Contrat public : `aiops.demo-ledger-read.v1` **schéma inchangé**, sémantique fail-closed renforcée ; `aiops.core-demo-evidence-refs.v1` inchangé. Documentation : `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md`. Ce n'est ni une ACL tenant ni une preuve d'origine des données.

## Qualification au moment de rédaction
- [quality.yml #40786938137](https://github.com/alimtalbi-ata/aiops/actions/runs/40786938137) sur le SHA code `d582d9af` : **IN_PROGRESS** au moment de ce journal. Étapes `Compile Python source`, `Demo Studio AI ledger viewer RBAC contract tests (unit only)`, `Policy safety unit tests` observées **SUCCESS** ; ne pas assimiler à une CI globale PASS.
- [V2.8 #40786938241](https://github.com/alimtalbi-ata/aiops/actions/runs/40786938241), [Offline Integrity #40786938120](https://github.com/alimtalbi-ata/aiops/actions/runs/40786938120) et [Historical Trace #40786938159](https://github.com/alimtalbi-ata/aiops/actions/runs/40786938159) : **completed/success** sur le SHA code, vérifiés par GitHub Actions.
- Aucune exécution locale, aucun test Debian. Les jobs HTTP Core/Portal/PostgreSQL, Temporal, release-kit et la CI du commit documentaire doivent être recontrôlés avant tout statut PASS global ; les URLs/résultats finaux seront transmis sur la PR #171 et à la Recette #156.

## Risques / NO-GO
- **READY_FOR_STABLE=BLOCKED / NO-GO** : aucune qualification tenant A/B authentifiée, ni causalité Twin Payments, métriques SAN observées, inférence Ollama 4B, Policy SIMULATE E2E, preuve navigateur, rollback terrain, smoke Debian ou `applied.sha` authentifié.
- Le déployeur V2 ne transporte pas `app/core/demo_evidence_read.py` et les autres modules Core/Portal. Une promotion partielle casserait le resolver : aucune promotion directe autorisée. Seul le lot Recette 5/5 (#156) peut assembler et décider.
- Aucune action LIVE, aucun accès Debian, aucune fusion, aucun secret de production ni appel NGX.

## Prochain micro-lot
Qualifier tous les checks GitHub du SHA final de #171, transmettre le SHA exact à #156 ; puis, sous responsabilité Recette 5/5, tester la couverture complète du déployeur et la recette lecture seule avec rollback et preuve `applied.sha` avant promotion.
