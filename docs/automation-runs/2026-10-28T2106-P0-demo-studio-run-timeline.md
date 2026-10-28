# P0 UI — navigation Core et fraîcheur RUNNING Demo Studio V2

- Date : 2026-10-28, 21:06 Europe/Paris.
- HEAD main lu : `b6cac31f6713d60f517bc6c4648002297fb87de6`.
- Branche V2 lue : `feat/demo-studio-v2-delivery-20261028` à `296ab8136efe9a9068cd6b6045236c5abc52694b`.
- Base de portage ciblé : PR #140, `752a8399d1d55e3a5ec5a20613e5f2b43fa55e21`; conserver ses états HTTP 401/403/UNKNOWN.
- Branche de travail : `ui/p0-demo-v2-run-timeline-20261028-2106`, PR empilée sur la branche de #140, pas de merge massif.
- Fichiers : `app/portal/demo_v2.py`, `tests/test_demo_v2.py`, `.github/workflows/quality.yml`, ce journal.
- Contrat : `render_demo_v2(detail, ledger, gates, now=None)` reste rétrocompatible ; lien vers `/timeline?run_id=<id>` uniquement pour identifiant Core validé ; dernière date événement Core UTC si tous les horodatages sont valides ; RUNNING ancien après 30 min sans événement récent vérifiable, sans conclure à un blocage ou à un effet LIVE.
- Tests ajoutés : lien sûr, refus d'ID injecté/traversal, fraîcheur selon dernier événement, horodatages futurs/invalides fail-closed ; `test_demo_v2.py` désormais appelé dans `quality.yml` existant.
- CI : NOT_TESTED au moment de ce commit ; URL et verdict à compléter après exécution GitHub Actions. Aucun PASS anticipé. Le workflow #140 comportait un job en échec historique Policy : https://github.com/alimtalbi-ata/aiops/actions/runs/40744018535 .
- Dépendances : #140 (auth états) ; #145 (lecture ai-ledger) ; #142 (direction Twin), #144 (Policy), #146 (déploiement) examinées pour éviter tout conflit. Aucun changement de contrat Core/Twin/Policy.
- Risques : lecture Core en ligne non qualifiée, isolation tenant runtime non qualifiée ; l'absence d'horodatage est UNKNOWN et non une preuve de stagnation. Démonstration navigateur, captures authentifiées, scénario SAN→Payments complet : NOT_TESTED. Aucun accès Debian, aucun déploiement, aucune remédiation LIVE.
- Prochain micro-lot : qualifier les liens et la timeline avec vrais runs Core dans un environnement isolé autorisé ; traiter les échecs Policy historiques avant toute fusion.
