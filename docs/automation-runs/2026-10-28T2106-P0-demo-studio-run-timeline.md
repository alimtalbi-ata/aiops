# P0 UI — navigation Core et fraîcheur RUNNING Demo Studio V2

- Date : 2026-10-28, 21:06 Europe/Paris.
- HEAD main lu : `b6cac31f6713d60f517bc6c4648002297fb87de6`.
- Branche V2 lue : `feat/demo-studio-v2-delivery-20261028` à `296ab8136efe9a9068cd6b6045236c5abc52694b`.
- Base de portage ciblé : PR #140, `752a8399d1d55e3a5ec5a20613e5f2b43fa55e21`; conserver ses états HTTP 401/403/UNKNOWN.
- Branche de travail : `ui/p0-demo-v2-run-timeline-20261028-2106`, PR empilée sur la branche de #140, pas de merge massif.
- Commits : `bd147a3b` (code/tests/CI/journal), `529247ed` (horodatage futur), `238d046a` (tests fail-closed), puis commit de correction des attentes historiques (SHA dans PR #150).
- PR : https://github.com/alimtalbi-ata/aiops/pull/150 (draft, base #140).
- Fichiers : `app/portal/demo_v2.py`, `tests/test_demo_v2.py`, `.github/workflows/quality.yml`, ce journal.
- Contrat : `render_demo_v2(detail, ledger, gates, now=None)` reste rétrocompatible ; lien vers `/timeline?run_id=<id>` uniquement pour identifiant Core validé ; dernière date événement Core UTC si tous les horodatages sont valides ; RUNNING ancien après 30 min sans événement récent vérifiable, sans conclure à un blocage ou à un effet LIVE.
- Tests ajoutés : lien sûr, refus d'ID injecté/traversal, fraîcheur selon dernier événement, horodatages futurs/invalides fail-closed ; `test_demo_v2.py` désormais appelé dans `quality.yml` existant.
- CI : première exécution sur `238d046a` : https://github.com/alimtalbi-ata/aiops/actions/runs/40760657227 ; job `quality-build-package` FAIL sur deux attentes historiques obsolètes dans `test_demo_v2.py` (libellé source depuis #140 et ancien libellé RUNNING), corrigées dans ce micro-lot. Les autres jobs et la CI du SHA final restent PENDING / NOT_TESTED au moment de cette écriture. Aucun PASS anticipé. Le workflow #140 comportait aussi un job en échec Policy : https://github.com/alimtalbi-ata/aiops/actions/runs/40744018535 .
- Dépendances : #140 (auth états) ; #145 (lecture ai-ledger) ; #142 (direction Twin), #144 (Policy), #146 (déploiement) examinées pour éviter tout conflit. Aucun changement de contrat Core/Twin/Policy.
- Risques : lecture Core en ligne non qualifiée, isolation tenant runtime non qualifiée ; l'absence d'horodatage est UNKNOWN et non une preuve de stagnation. Démonstration navigateur, captures authentifiées, scénario SAN→Payments complet : NOT_TESTED. Aucun accès Debian, aucun déploiement, aucune remédiation LIVE.
- Prochain micro-lot : qualifier les liens et la timeline avec vrais runs Core dans un environnement isolé autorisé ; traiter les échecs Policy historiques avant toute fusion.

## Résultat de validation GitHub Actions (SHA `8492f310`)

- `quality.yml` : https://github.com/alimtalbi-ata/aiops/actions/runs/40760809139 ; étape **Demo Studio source authentication and UNKNOWN regressions : PASS**. Logs authentiques : 5/5 tests source-state et 9/9 tests `test_demo_v2.py` exécutés avec succès.
- **Quality global : FAIL / NON FUSIONNABLE**. L'étape `Policy safety unit tests` échoue sur 11/15 assertions historiques (`AUTONOMY_STATE_UNAVAILABLE` et différences de décision), sans lien direct avec les deux fichiers UI modifiés. Ne pas contourner ou modifier Policy dans ce lot UI.
- `V2.12.8 Offline Integrity` : SUCCESS https://github.com/alimtalbi-ata/aiops/actions/runs/40760809118 .
- `V2.12.9 Historical Trace Qualification` : SUCCESS https://github.com/alimtalbi-ata/aiops/actions/runs/40760809184 .
- `V2.8 Core qualification (isolated)` : SUCCESS https://github.com/alimtalbi-ata/aiops/actions/runs/40760809219 .
- Ces workflows historiques ne démontrent **pas** l'intégration E2E du scénario ACME ni la qualification navigateur du nouvel écran.
- Correction effectuée dans le même micro-lot : deux assertions UI héritées de l'ancienne version de `demo_v2.py` ont été alignées sur le contrat fail-closed #140 et sur le nouveau libellé de prudence RUNNING, sans modifier la sécurité.
- Aucun merge : PR #150 reste draft empilée sur #140. La CI déclenchée par le commit de ce journal est à contrôler séparément ; ne pas réutiliser le verdict d'un SHA antérieur comme verdict du SHA final.
