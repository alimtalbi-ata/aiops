# 2/5 Portail — sélection de timeline ACME (29/10/2026, 22:15 Europe/Paris)

- **Candidate existante :** PR #185, branche `release/p0-acme-integrated-candidate-20261029-1100`, parent `a21c991fec16dfa7998035873f9f792b65f29d96`. SHA de livraison : voir le commit de ce journal et le handoff #185.
- **Verticale P0 :** `/demo-studio` → `/timeline` doit sélectionner un run Core DEMO/REPLAY/STORY terminal et non ambigu plutôt qu'un ancien RUNNING ou LIVE. La sélection explicite `?run_id=` est conservée. Sans candidat : UNKNOWN ; sans fraîcheur vérifiée : UNKNOWN.
- **Fichiers :** `app/portal/main.py`, `tests/test_demo_v2.py`. Aucun nouveau prototype, module, dépendance, endpoint, workflow ni action LIVE.
- **Contrat :** sélection par inventaire Core uniquement, identifiant valide et unique ; priorité BLOCKED/RESOLVED. Aucune preuve SAN→Payments, GLPI ou HITL n'est attestée par cette navigation.
- **Tests ajoutés :** sélection terminale malgré RUNNING/LIVE/doublons, et refus de sélection ambiguë. **CI quality.yml : PENDING au moment du commit** ; aucun test Debian ou navigateur exécuté ici.
- **Transport :** `app/portal/main.py` doit être inclus intégralement dans l'image Portal et le plan de déploiement ; le cron installé `deploy/aiops2-stable` reste portal-only et n'applique pas automatiquement cette candidate. Rollback, applied.sha et smoke terrain : NOT_TESTED.
- **Décision :** READY_FOR_STABLE=BLOCKED ; 5/5 seul responsable de la qualification et de la promotion. Aucun push stable ni déploiement Debian.
