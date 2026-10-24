# V2.13.12 — Qualification Chromium hors production (22 octobre 2026)

Résultats de l'opérateur sur SRV-DEB-05 :
- Extraction du HTML et du test de la branche `feat/v21310-star-portal-continuity-20261022` via FETCH_HEAD : `AIOPS_V21312_SOURCE=PASS`.
- Exécution Chromium sur le fichier local `file:///home/aiops/aiops-portal-v21312-source/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html`.
- `scope=V21312_BROWSER_FUNCTIONAL`; `passed=true`; erreurs JavaScript `[]`.
- **13/13 checks PASS** : loaded, initial_12, presenter_hides_notes, presenter_restores_notes, playing_state, automatic_advance, paused_state, paused_does_not_advance, reset, mobile_content_visible, mobile_no_horizontal_overflow, provenance, no_js_errors.
- Rapports sur Debian : `/home/aiops/aiops-v21312-qualification/v21312-browser.json` et PNG associé.

Limites : il s'agit d'un test de la page HTML locale, **pas** d'un déploiement. La V2.13.12 n'est pas encore construite en image, ni qualifiée en HTTP sur le port 17777. Aucun appel DGX ni accès historique ni action LIVE n'est couvert. La dernière version active connue sur le portail unique reste V2.13.11.

Suite : `docker build` candidate V2.13.12 (aucun conteneur modifié), contrôle des routes et asset via `docker run --network none`, puis bascule contrôlée du seul portail avec sauvegarde/rollback et vérification 200/403 avant replay Chromium sur URL réelle. Ne jamais démarrer de profil test par erreur, ne pas modifier les autres services.
