# AIOps V2.13.14 — Déploiement réel et qualification (22 octobre 2026)

Résultats transmis par l'opérateur sur SRV-DEB-05.

- Déploiement : `AIOPS_V21314_DEPLOY=PASS`, service `aiops2-portal` uniquement.
- Conteneur : `0eb1b15033f3fd990926b58ae2942287162da8b74d68a465306658b8b51084af`.
- Image active : `sha256:f812e8c35f8c46c28d7786735c9eb6ff8ced0001cd0d7014f738b2c79805f486`.
- Chromium sur URL réellement servie `http://10.79.94.202:17777/demo/star` : `scope=V21314_SYNTHETIC_TIMELINE`; `passed=true`; `errors=[]`; **11/11 contrôles PASS** : twelve_scenes, initial_signal, analyst, critic, blocked, human_review, one_active_step, svg_present, source_label, mobile, no_js_errors.
- Replay historique `/demo/view/AIOPS-REAL-STACK-REPLAY.html` : HTTP 403.
- Non-régression avant déploiement sur HTML candidat : V2.13.13 15/15 et V2.13.12 13/13.
- Le script local est syntaxiquement valide, sauvegarde l'image précédente et prévoit une fonction rollback. Aucun test de rollback par panne n'est revendiqué.

## Limites
UI synthétique validée; aucune nouvelle inférence DGX, aucune preuve Policy LIVE, aucune action remédiation ni accès historique approuvé. Les 28 tests de non-régression ont été réalisés sur le fichier local, pas rejoués en exploitation.

## Continuité
Préserver l'unique portail 17777, les Compose locaux et la branche main; ne pas fusionner automatiquement la PR #36. Livrable local du test live : `/home/aiops/aiops-v21314-qualification/v21314-live-browser.json`.
