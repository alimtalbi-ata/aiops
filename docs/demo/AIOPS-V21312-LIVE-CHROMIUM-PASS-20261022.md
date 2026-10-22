# V2.13.12 — Qualification Chromium en situation déployée (22 octobre 2026)

D'après la sortie fournie par l'opérateur SRV-DEB-05.

- URL testée : `http://10.79.94.202:17777/demo/star`.
- Le test Playwright corrigé depuis GitHub utilise `expect(page.locator("#counter")).to_have_text("2 / 12", timeout=8500)` plutôt que `wait_for_function` interdit par la CSP actuelle.
- Résultat réel : `scope=V21312_BROWSER_FUNCTIONAL`, `passed=true`, `errors=[]`, **13/13**.
- Checks : loaded, initial_12, presenter_hides_notes, presenter_restores_notes, playing_state, automatic_advance, paused_state, paused_does_not_advance, reset, mobile_content_visible, mobile_no_horizontal_overflow, provenance, no_js_errors.
- Lors du déploiement précédent, l'image active était `sha256:a9e764d065085ea18aa4a0521740ff9c0565ea02b1d10b02dc12236ebd0f3126` et les routes /health, /demo/, /demo/star retournaient 200, l'accès au replay historique non autorisé 403.
- Le script local de déploiement a été corrigé syntaxiquement pour afficher V21312 et non V21311, sans redéployer.
- Artefact rapport : `/home/aiops/aiops-v21312-qualification/v21312-live-browser.json`.

## Portée et limites
Validation du théâtre fictif et de ses interactions réelles sur le portail. Ce test n'est pas une preuve d'inférence DGX, de réparation LIVE, de chaîne de décision Core complète, ni d'autorisation d'accès aux historiques.

## Prochain jalon
Consolider en GitHub le code effectivement déployé, renforcer la navigation accessible et la revue de sécurité des assets; préparer des scénarios de comité sans ajouter une seconde interface. Conserver un portail / port 17777, préserver les configurations Compose locales, aucun merge automatique.
