# V2.13.13 — Déploiement et qualification finale (2026-10-22)

Résultats effectivement transmis par l'opérateur depuis SRV-DEB-05 :

- Régression V2.13.12 sur asset local V2.13.13 : 13/13 contrôles PASS (lecture automatique, pause, reset, responsive, provenance, aucune erreur JS).
- Copie du script V2.13.12, substitutions v21313 / V21313, `bash -n` PASS. Le script conserve l'image précédente et une fonction rollback.
- `AIOPS_V21313_DEPLOY=PASS`.
- Container ID : `06f0bad72836c585785da2819117646c9fc925fa0b7d14a1c2888eaee8a17145`.
- Image active : `sha256:1c0e808b9cad5ad77236269a2310edbc90658c289940cef226c76a4984fbc071`.
- Test Chromium sur portail unique `http://10.79.94.202:17777/demo/star` : 15/15 PASS, aucune erreur JS.
- Contrôles : vector_icons, optional_detail, detail_expands, scene_focus, twelve_scenes, business_default, technical_reading, evidence_open, provenance, animated_focus_changes, evidence_changes_with_scene, evidence_closed, presenter, mobile_no_overflow, no_js_errors.
- Route historique `/demo/view/AIOPS-REAL-STACK-REPLAY.html` : HTTP 403 (non autorisée).

Livrables locaux : `/home/aiops/aiops-v21313-qualification/v21313-live-browser.json` et `v21313-regression.json`, captures PNG éventuellement générées.

**Portée** : fonctionnement UI synthétique et refus d'un replay non autorisé ; ne constitue pas de preuve d'appel DGX, de chaîne Core, de remédiation LIVE ou d'une revue de sécurité complète. Rollback présent dans le script, non testé par panne durant cette opération.

Déploiement de référence : V2.13.13 sur un seul portail et port utilisateur 17777. Préserver Compose locaux et branche main, conserver PR draft.
