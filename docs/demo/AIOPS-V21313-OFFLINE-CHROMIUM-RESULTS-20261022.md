# AIOps V2.13.13 — Qualification Chromium hors déploiement, 22 octobre 2026

Résultats opérateur obtenus sur SRV-DEB-05.

- `AIOPS_V21313_SOURCE=PASS` : copie source V2.13.12 vers V2.13.13, extraction GitHub de l'asset STAR et du test Playwright.
- Exécution du test sur `file:///home/aiops/aiops-portal-v21313-source/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html`.
- `scope=V21313_BROWSER_FUNCTIONAL`, `passed=true`, `errors=[]`.
- **15/15 checks PASS** : vector_icons, optional_detail, detail_expands, scene_focus, twelve_scenes, business_default, technical_reading, evidence_open, provenance, animated_focus_changes, evidence_changes_with_scene, evidence_closed, presenter, mobile_no_overflow, no_js_errors.
- Rapport sur Debian : `/home/aiops/aiops-v21313-qualification/v21313-browser.json`, capture `v21313-browser.png` si générée.
- Les tests certifient les interactions UI synthétiques, et non l'exécution DGX/Core ni la remédiation LIVE.

## État et suite
Version déployée connue : V2.13.12 sur portail unique 17777. V2.13.13 **pas encore construite Docker ni déployée**. Prochaines étapes : rejouer le smoke fonctionnel V2.13.12 pour la lecture automatique/pause sur le nouveau fichier, construire une image v21313 hors réseau, vérifier asset et routes, déployer le seul portail avec rollback, tester 200/403 et requalifier Chromium sur URL réelle. Aucun second portail, aucun accès historique déverrouillé.
