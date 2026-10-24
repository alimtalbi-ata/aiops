# V2.13.14 — Qualification Chromium locale (22 octobre 2026)

D'après les résultats fournis par l'opérateur sur SRV-DEB-05 :
- Extraction depuis `feat/v21310-star-portal-continuity-20261022` : `AIOPS_V21314_SOURCE=PASS`.
- Chromium sur fichier local `file:///home/aiops/aiops-portal-v21314-source/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html`.
- `scope=V21314_SYNTHETIC_TIMELINE` ; `passed=true` ; `errors=[]`.
- 11/11 contrôles PASS : twelve_scenes, initial_signal, analyst, critic, blocked, human_review, one_active_step, svg_present, source_label, mobile, no_js_errors.
- Rapport local : `/home/aiops/aiops-v21314-qualification/v21314-browser.json`.
- Pas de qualification Docker ou d'exploitation V2.13.14 à ce stade. Portail unique 17777 : version V2.13.13 précédente.
- Aucune preuve d'inférence DGX, interposition Policy LIVE ni remédiation.

Suite : exécuter le test de régression V2.13.13 sur l'HTML V2.13.14 (15 contrôles), puis V2.13.12 chronométré (13 contrôles), construire l'image isolée, vérifier les routes et la présence de l'asset. Après seulement, bascule contrôlée du seul portail avec rollback et HTTP 403 historique; répéter les tests Chromium sur le portail réel.
